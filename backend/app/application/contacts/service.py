"""Contact use cases: scoped reads with access logging, creation, updates, anonymisation."""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from app.application.accounts.service import ensure_account_writer, load_visible_account
from app.application.contacts.commands import ConsentInput, CreateContact, UpdateContact
from app.application.shared.unit_of_work import UnitOfWork
from app.domain.accounts.entities import Account
from app.domain.contacts.entities import ConsentRecord, ConsentStatus, Contact
from app.domain.shared.audit import diff_fields
from app.domain.shared.errors import NotFoundError, PermissionDeniedError
from app.domain.users.entities import User
from app.domain.users.errors import UnknownReferenceError
from app.domain.users.roles import Role
from app.infrastructure.logging import get_request_context

ROLES_NOT_LOGGED: frozenset[Role] = frozenset({Role.ADMIN, Role.SALES_MANAGER})


def access_must_be_logged(actor: User, account: Account) -> bool:
    """Owner, managers and admins are expected readers; everyone else leaves a trace."""
    return actor.role not in ROLES_NOT_LOGGED and actor.id != account.owner_id


class ContactService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    # --- reads -----------------------------------------------------------

    async def list_for_account(
        self, account_id: UUID, *, actor: User, include_inactive: bool = False
    ) -> list[Contact]:
        async with self._uow as uow:
            account = await load_visible_account(uow, account_id, actor)
            contacts = await uow.contacts.list_by_account(
                account_id, include_inactive=include_inactive
            )
            await self._log_access(uow, actor, account, [c.id for c in contacts])
            return contacts

    async def get(self, contact_id: UUID, *, actor: User) -> tuple[Contact, Account]:
        async with self._uow as uow:
            contact, account = await self._load(uow, contact_id, actor)
            await self._log_access(uow, actor, account, [contact.id])
            return contact, account

    # --- writes ----------------------------------------------------------

    async def create(self, command: CreateContact, *, actor: User) -> Contact:
        async with self._uow as uow:
            account = await load_visible_account(uow, command.account_id, actor)
            await ensure_account_writer(uow, actor, account)
            await self._validate_references(uow, command.details)
            consent = self._consent_record(command.consent, actor)
            contact = Contact.create(
                account_id=account.id,
                first_name=command.first_name,
                last_name=command.last_name,
                details=command.details,
                is_primary=command.is_primary,
                consent=consent,
            )
            if contact.is_primary:
                await self._demote_current_primary(uow, account.id, contact, actor)
            await uow.contacts.add(contact)
            uow.audit.record(
                entity_type="contact",
                entity_id=contact.id,
                action="contact.created",
                changes=diff_fields(
                    {},
                    {
                        **contact.snapshot(),
                        "account_id": account.id,
                        "is_primary": contact.is_primary,
                    },
                ),
                actor_id=actor.id,
            )
            if consent is not None and consent.status != ConsentStatus.UNKNOWN:
                uow.audit.record(
                    entity_type="contact",
                    entity_id=contact.id,
                    action="contact.consent_changed",
                    changes=diff_fields(ConsentRecord().as_dict(), consent.as_dict()),
                    actor_id=actor.id,
                )
            await uow.commit()
            return contact

    async def update(self, contact_id: UUID, command: UpdateContact, *, actor: User) -> Contact:
        async with self._uow as uow:
            contact, account = await self._load(uow, contact_id, actor)
            await ensure_account_writer(uow, actor, account)
            await self._validate_references(uow, command.changes)
            before = contact.snapshot()
            consent_before = contact.consent.as_dict()
            contact.update_details(command.changes)
            if isinstance(command.is_active, bool):
                if command.is_active:
                    contact.activate()
                else:
                    contact.deactivate()
            if command.consent is not None:
                contact.record_consent(self._consent_from(command.consent, actor))
            contact.validate_channels()
            primary_changed = False
            if isinstance(command.is_primary, bool) and command.is_primary != contact.is_primary:
                if command.is_primary:
                    contact.make_primary()
                    await self._demote_current_primary(uow, account.id, contact, actor)
                else:
                    contact.demote()
                primary_changed = True
            await uow.contacts.save(contact, expected_version=command.expected_version)
            changes = diff_fields(before, contact.snapshot())
            if changes:
                uow.audit.record(
                    entity_type="contact",
                    entity_id=contact.id,
                    action="contact.updated",
                    changes=changes,
                    actor_id=actor.id,
                )
            if primary_changed and not contact.is_primary:
                uow.audit.record(
                    entity_type="contact",
                    entity_id=contact.id,
                    action="contact.primary_changed",
                    changes=diff_fields({"is_primary": True}, {"is_primary": False}),
                    actor_id=actor.id,
                )
            consent_changes = diff_fields(consent_before, contact.consent.as_dict())
            if consent_changes:
                uow.audit.record(
                    entity_type="contact",
                    entity_id=contact.id,
                    action="contact.consent_changed",
                    changes=consent_changes,
                    actor_id=actor.id,
                )
            await uow.commit()
            return contact

    async def anonymise(self, contact_id: UUID, *, expected_version: int, actor: User) -> Contact:
        if actor.role not in {Role.ADMIN, Role.SALES_MANAGER}:
            raise PermissionDeniedError("Only sales managers and administrators can anonymise")
        async with self._uow as uow:
            contact, _ = await self._load(uow, contact_id, actor)
            cleared = contact.anonymise(now=datetime.now(UTC))
            await uow.contacts.save(contact, expected_version=expected_version)
            uow.audit.record(
                entity_type="contact",
                entity_id=contact.id,
                action="contact.anonymised",
                # Field names only: the audit log must not retain the erased values.
                changes={"fields": {"cleared": list(cleared)}},
                actor_id=actor.id,
            )
            await uow.commit()
            return contact

    # --- helpers ---------------------------------------------------------

    @staticmethod
    async def _load(uow: UnitOfWork, contact_id: UUID, actor: User) -> tuple[Contact, Account]:
        contact = await uow.contacts.get(contact_id)
        if contact is None:
            raise NotFoundError("Contact not found")
        try:
            account = await load_visible_account(uow, contact.account_id, actor)
        except NotFoundError:
            raise NotFoundError("Contact not found") from None
        return contact, account

    @staticmethod
    async def _log_access(
        uow: UnitOfWork, actor: User, account: Account, contact_ids: Sequence[UUID]
    ) -> None:
        if not contact_ids or not access_must_be_logged(actor, account):
            return
        await uow.personal_data_access.record(
            user_id=actor.id, contact_ids=contact_ids, trace_id=get_request_context().trace_id
        )
        await uow.commit()

    @classmethod
    def _consent_record(cls, consent: ConsentInput | None, actor: User) -> ConsentRecord | None:
        return None if consent is None else cls._consent_from(consent, actor)

    @staticmethod
    def _consent_from(consent: ConsentInput, actor: User) -> ConsentRecord:
        recorded_by = actor.id if consent.status != ConsentStatus.UNKNOWN else None
        return ConsentRecord(
            status=consent.status, at=consent.at, source=consent.source, recorded_by=recorded_by
        )

    @staticmethod
    async def _validate_references(uow: UnitOfWork, details: object) -> None:
        if not isinstance(details, dict):
            return
        job_title_id = details.get("job_title_id")
        if job_title_id is not None and not await uow.job_titles.existing_ids([job_title_id]):
            raise UnknownReferenceError("job_title_id", [str(job_title_id)])
        specialty_id = details.get("specialty_id")
        if specialty_id is not None and not await uow.specialties.existing_ids([specialty_id]):
            raise UnknownReferenceError("specialty_id", [str(specialty_id)])

    @staticmethod
    async def _demote_current_primary(
        uow: UnitOfWork, account_id: UUID, new_primary: Contact, actor: User
    ) -> None:
        current = await uow.contacts.find_primary(account_id)
        if current is None or current.id == new_primary.id:
            return
        current.demote()
        await uow.contacts.save(current, expected_version=current.version)
        uow.audit.record(
            entity_type="contact",
            entity_id=current.id,
            action="contact.primary_changed",
            changes=diff_fields(
                {"primary_contact_id": current.id}, {"primary_contact_id": new_primary.id}
            ),
            actor_id=actor.id,
        )
