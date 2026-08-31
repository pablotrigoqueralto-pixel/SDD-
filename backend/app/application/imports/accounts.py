"""Accounts & contacts importer: CIF-first matching, embedded contact columns."""

from typing import Any
from uuid import UUID

from app.application.accounts.commands import CreateAccount, UpdateAccount
from app.application.accounts.service import AccountService
from app.application.imports.report import (
    ImportReport,
    RowOutcome,
    RowReport,
    normalise_tax_id,
    normalise_text,
)
from app.application.shared.unit_of_work import UnitOfWork
from app.domain.accounts.entities import ADMINISTRATIVE_FIELDS, PhoneEntry
from app.domain.contacts.entities import Contact
from app.domain.shared.audit import diff_fields
from app.domain.shared.errors import DomainError, ValidationFailedError
from app.domain.users.entities import User
from app.infrastructure.imports.reader import read_table

ACCOUNT_COLUMNS: dict[str, tuple[str, ...]] = {
    "name": ("name", "nombre", "centro", "cliente"),
    "tax_id": ("tax_id", "cif", "nif"),
    "province_code": ("province_code", "provincia", "cod provincia", "código provincia"),
    "city": ("city", "ciudad", "localidad", "población", "poblacion"),
    "street": ("street", "dirección", "direccion", "domicilio"),
    "postal_code": ("postal_code", "código postal", "codigo postal", "cp"),
    "phone": ("phone", "teléfono", "telefono"),
    "email": ("email", "correo", "e-mail"),
    "account_type": ("account_type", "tipo", "tipo de centro"),
    "contact_first_name": ("contact_first_name", "contacto nombre", "nombre contacto"),
    "contact_last_name": ("contact_last_name", "contacto apellidos", "apellidos contacto"),
    "contact_email": ("contact_email", "contacto email", "email contacto"),
    "contact_phone": ("contact_phone", "contacto teléfono", "contacto telefono", "móvil contacto"),
    "contact_job_title": ("contact_job_title", "cargo", "cargo contacto"),
}
ACCOUNT_REQUIRED = frozenset({"name", "province_code"})

_ACCOUNT_FIELDS = ("tax_id", "city", "street", "postal_code", "email")
PRIMARY_PHONE_LABEL = "Principal"
CONTACT_PHONE_LABEL = "Móvil"
_CONTACT_FIELDS = ("contact_first_name", "contact_last_name", "contact_email", "contact_phone")


def _row_error(row_number: int, label: str, message: str) -> RowReport:
    return RowReport(row=row_number, outcome=RowOutcome.ERROR, label=label, message=message)


def _message(error: Exception) -> str:
    errors = getattr(error, "errors", None)
    if errors:
        return "; ".join(str(item.get("message", "")) for item in errors)
    return getattr(error, "detail", None) or str(error)


class AccountImporter:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow
        self._service = AccountService(uow)

    async def run(
        self, filename: str, content: bytes, *, dry_run: bool, actor: User
    ) -> ImportReport:
        table = read_table(filename, content, columns=ACCOUNT_COLUMNS, required=ACCOUNT_REQUIRED)
        rows: list[RowReport] = []
        for index, raw in enumerate(table, start=2):  # row 1 is the header
            label = raw["name"] or f"fila {index}"
            try:
                rows.append(await self._row(index, label, raw, dry_run=dry_run, actor=actor))
            except (ValidationFailedError, DomainError) as error:
                rows.append(_row_error(index, label, _message(error)))
        report = ImportReport(rows=rows)
        if not dry_run:
            await self._audit(filename, report, actor)
        return report

    async def _row(
        self, index: int, label: str, raw: dict[str, str], *, dry_run: bool, actor: User
    ) -> RowReport:
        account_id = await self._match(raw)
        messages: list[str] = []
        if account_id is None:
            outcome = RowOutcome.CREATED
            if not dry_run:
                account_id = await self._create_account(raw, actor)
        else:
            changed = await self._update_account(account_id, raw, actor, dry_run=dry_run)
            outcome = RowOutcome.UPDATED if changed else RowOutcome.UNCHANGED
        if self._has_contact(raw):
            contact_outcome = await self._contact(
                account_id, raw, actor, dry_run=dry_run, messages=messages
            )
            if contact_outcome and outcome is RowOutcome.UNCHANGED:
                outcome = RowOutcome.UPDATED
        return RowReport(
            row=index,
            outcome=outcome,
            label=label,
            message="; ".join(messages) if messages else None,
        )

    async def _match(self, raw: dict[str, str]) -> UUID | None:
        async with self._uow as uow:
            if raw["tax_id"]:
                by_tax = await uow.accounts.find_id_by_tax_id(normalise_tax_id(raw["tax_id"]))
                if by_tax is not None:
                    return by_tax
            return await uow.accounts.find_id_by_normalised_name(normalise_text(raw["name"]))

    async def _account_type_id(self, raw_type: str) -> UUID:
        async with self._uow as uow:
            account_types = await uow.reference.account_types()
        if raw_type:
            wanted = normalise_text(raw_type)
            for account_type in account_types:
                if account_type.code == raw_type.strip().lower():
                    return account_type.id
                if normalise_text(account_type.name_es) == wanted:
                    return account_type.id
            raise ValidationFailedError(
                [
                    {
                        "field": "account_type",
                        "message": f"Unknown account type: {raw_type}",
                        "code": "account_type_not_found",
                    }
                ]
            )
        return sorted(account_types, key=lambda item: item.sort_order)[0].id

    async def _create_account(self, raw: dict[str, str], actor: User) -> UUID:
        details: dict[str, Any] = {field: raw[field] for field in _ACCOUNT_FIELDS if raw[field]}
        if "tax_id" in details:
            details["tax_id"] = normalise_tax_id(details["tax_id"])
        if raw["phone"]:
            details["phones"] = [PhoneEntry.create(label=PRIMARY_PHONE_LABEL, number=raw["phone"])]
        view = await self._service.create(
            CreateAccount(
                name=raw["name"],
                account_type_id=await self._account_type_id(raw["account_type"]),
                province_code=raw["province_code"],
                details=details,
            ),
            actor=actor,
        )
        return view.account.id

    async def _update_account(
        self, account_id: UUID, raw: dict[str, str], actor: User, *, dry_run: bool
    ) -> bool:
        async with self._uow as uow:
            account = await uow.accounts.get(account_id)
        if account is None:  # matched a heartbeat ago; treat as unchanged
            return False
        changes: dict[str, Any] = {}
        for field in _ACCOUNT_FIELDS:
            if not raw[field]:
                continue
            value = normalise_tax_id(raw[field]) if field == "tax_id" else raw[field]
            if (getattr(account, field) or None) != value:
                changes[field] = value
        if raw["phone"]:
            incoming = PhoneEntry.create(label=PRIMARY_PHONE_LABEL, number=raw["phone"])
            current = account.phones[0] if account.phones else None
            if current is None or current.number != incoming.number:
                # Replace the primary entry only; other labelled phones are preserved.
                changes["phones"] = [incoming, *account.phones[1:]]
        illegal = set(changes) - ADMINISTRATIVE_FIELDS
        if illegal:
            changes = {key: value for key, value in changes.items() if key not in illegal}
        if not changes:
            return False
        if not dry_run:
            await self._service.update(
                account_id,
                UpdateAccount(expected_version=account.version, changes=changes),
                actor=actor,
            )
        return True

    @staticmethod
    def _has_contact(raw: dict[str, str]) -> bool:
        return any(raw[field] for field in _CONTACT_FIELDS)

    async def _contact(
        self,
        account_id: UUID | None,
        raw: dict[str, str],
        actor: User,
        *,
        dry_run: bool,
        messages: list[str],
    ) -> bool:
        """Create/update the embedded contact directly at domain level (see delta spec:
        the endpoint's role gate authorises this; manual endpoints keep their rules)."""
        first = raw["contact_first_name"]
        last = raw["contact_last_name"]
        if not first or not last:
            raise ValidationFailedError(
                [
                    {
                        "field": "contact_first_name",
                        "message": "Embedded contacts need first and last name",
                        "code": "contact_name_required",
                    }
                ]
            )
        email = raw["contact_email"].lower() or None
        if dry_run and account_id is None:
            return True  # new account: the contact would be created with it
        job_title_id, job_message = await self._job_title(raw["contact_job_title"])
        if job_message:
            messages.append(job_message)
        async with self._uow as uow:
            existing = await self._find_contact(uow, account_id, email, f"{first} {last}")
            details: dict[str, Any] = {}
            if email:
                details["email"] = email
            if raw["contact_phone"]:
                details["phones"] = [
                    PhoneEntry.create(label=CONTACT_PHONE_LABEL, number=raw["contact_phone"])
                ]
            if job_title_id:
                details["job_title_id"] = job_title_id
            if existing is None:
                if dry_run:
                    return True
                contact = Contact.create(
                    account_id=account_id,  # type: ignore[arg-type]
                    first_name=first,
                    last_name=last,
                    details=details,
                )
                await uow.contacts.add(contact)
                uow.audit.record(
                    entity_type="contact",
                    entity_id=contact.id,
                    action="contact.created",
                    changes=diff_fields({}, contact.snapshot()),
                    actor_id=actor.id,
                )
                await uow.commit()
                return True
            before = existing.snapshot()
            existing.update_details(details)
            changes = diff_fields(before, existing.snapshot())
            if not changes:
                return False
            if dry_run:
                return True
            await uow.contacts.save(existing, expected_version=existing.version)
            uow.audit.record(
                entity_type="contact",
                entity_id=existing.id,
                action="contact.updated",
                changes=changes,
                actor_id=actor.id,
            )
            await uow.commit()
            return True

    async def _find_contact(
        self, uow: UnitOfWork, account_id: UUID | None, email: str | None, full_name: str
    ) -> Contact | None:
        if account_id is None:
            return None
        contacts = await uow.contacts.list_by_account(account_id, include_inactive=True)
        if email:
            for contact in contacts:
                if (contact.email or "").lower() == email:
                    return contact
        wanted = normalise_text(full_name)
        for contact in contacts:
            if normalise_text(contact.full_name) == wanted:
                return contact
        return None

    async def _job_title(self, raw: str) -> tuple[UUID | None, str | None]:
        if not raw:
            return None, None
        async with self._uow as uow:
            titles = await uow.job_titles.list_all()
        wanted = normalise_text(raw)
        for title in titles:
            if normalise_text(title.name_es) == wanted:
                return title.id, None
        return None, f"cargo no encontrado: {raw}"

    async def _audit(self, filename: str, report: ImportReport, actor: User) -> None:
        async with self._uow as uow:
            uow.audit.record(
                entity_type="import",
                entity_id=None,
                action="import.accounts_executed",
                changes={
                    "file": {"before": None, "after": filename},
                    "created": {"before": None, "after": str(report.created)},
                    "updated": {"before": None, "after": str(report.updated)},
                    "unchanged": {"before": None, "after": str(report.unchanged)},
                    "errors": {"before": None, "after": str(report.errors)},
                },
                actor_id=actor.id,
            )
            await uow.commit()
