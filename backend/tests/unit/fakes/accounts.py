import unicodedata
from collections.abc import Iterable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from uuid import UUID

from app.domain.accounts.entities import Account
from app.domain.accounts.errors import TaxIdAlreadyExistsError
from app.domain.activities.entities import Activity, ActivityStatus
from app.domain.contacts.entities import Contact
from app.domain.reference.entities import JobTitle, Specialty
from app.domain.reference.errors import JobTitleNameAlreadyExistsError
from app.domain.shared.errors import ConcurrentModificationError
from app.domain.shared.policies import ScopeFilter


def unaccented(value: str) -> str:
    """The Python twin of the repository's `f_unaccent(lower(...))` comparison."""
    decomposed = unicodedata.normalize("NFKD", value.strip())
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def account_in_scope(account: Account, scope: ScopeFilter | None) -> bool:
    """Python twin of the SQL predicate (kept identical on purpose)."""
    if scope is None:
        return True
    if account.owner_id == scope.user_id:
        return True
    if account.territory_id is None or account.territory_id not in scope.territory_ids:
        return False
    return not account.division_ids or bool(account.division_ids & scope.division_ids)


class InMemoryAccountRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Account] = {}
        # Wired by FakeUnitOfWork so the summary can be recomputed like the SQL version.
        self.activities: InMemoryActivityRepository | None = None
        self.contact_type_ids: set[UUID] = set()

    async def get(self, account_id: UUID, *, scope: ScopeFilter | None = None) -> Account | None:
        row = self.rows.get(account_id)
        if row is None or not account_in_scope(row, scope):
            return None
        return deepcopy(row)

    async def find_id_by_tax_id(self, tax_id: str) -> UUID | None:
        for row in self.rows.values():
            if row.tax_id == tax_id:
                return row.id
        return None

    async def find_id_by_normalised_name(self, normalised_name: str) -> UUID | None:
        from app.application.imports.report import normalise_text

        for row in self.rows.values():
            if normalise_text(row.name) == normalised_name:
                return row.id
        return None

    async def add(self, account: Account) -> None:
        self._check_tax_id(account)
        self.rows[account.id] = deepcopy(account)

    async def save(self, account: Account, *, expected_version: int) -> None:
        current = self.rows.get(account.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        self._check_tax_id(account)
        account.version = expected_version + 1
        self.rows[account.id] = deepcopy(account)

    async def refresh_activity_summary(self, account_id: UUID) -> None:
        account = self.rows.get(account_id)
        if account is None or self.activities is None:
            return
        rows = [a for a in self.activities.rows.values() if a.account_id == account_id]
        done = [
            a.scheduled_at
            for a in rows
            if a.status is ActivityStatus.DONE and a.activity_type_id in self.contact_type_ids
        ]
        planned = [a.scheduled_at for a in rows if a.status is ActivityStatus.PLANNED]
        account.last_contact_at = max(done) if done else None
        account.next_activity_at = min(planned) if planned else None

    def _check_tax_id(self, account: Account) -> None:
        if account.tax_id is None:
            return
        for row in self.rows.values():
            if row.id != account.id and row.tax_id == account.tax_id:
                raise TaxIdAlreadyExistsError(row.id)


class InMemoryContactRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Contact] = {}

    async def get(self, contact_id: UUID) -> Contact | None:
        row = self.rows.get(contact_id)
        return deepcopy(row) if row else None

    async def list_by_account(
        self, account_id: UUID, *, include_inactive: bool = False
    ) -> list[Contact]:
        rows = [
            deepcopy(r)
            for r in self.rows.values()
            if r.account_id == account_id and (include_inactive or r.is_active)
        ]
        return sorted(rows, key=lambda r: (not r.is_primary, r.last_name.lower(), r.first_name))

    async def find_primary(self, account_id: UUID) -> Contact | None:
        for row in self.rows.values():
            if row.account_id == account_id and row.is_primary:
                return deepcopy(row)
        return None

    async def add(self, contact: Contact) -> None:
        self.rows[contact.id] = deepcopy(contact)

    async def save(self, contact: Contact, *, expected_version: int) -> None:
        current = self.rows.get(contact.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        contact.version = expected_version + 1
        self.rows[contact.id] = deepcopy(contact)


class InMemoryActivityRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Activity] = {}
        self.contact_accounts: dict[UUID, UUID] = {}

    async def get(self, activity_id: UUID) -> Activity | None:
        row = self.rows.get(activity_id)
        return deepcopy(row) if row else None

    async def add(self, activity: Activity) -> None:
        self.rows[activity.id] = deepcopy(activity)

    async def save(self, activity: Activity, *, expected_version: int) -> None:
        current = self.rows.get(activity.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        activity.version = expected_version + 1
        self.rows[activity.id] = deepcopy(activity)

    async def contacts_belong_to(self, account_id: UUID, contact_ids: Iterable[UUID]) -> bool:
        return all(self.contact_accounts.get(c) == account_id for c in contact_ids)


@dataclass(frozen=True)
class AccessEntry:
    user_id: UUID
    contact_id: UUID
    trace_id: str | None


class InMemoryPersonalDataAccessLog:
    def __init__(self) -> None:
        self.entries: list[AccessEntry] = []

    async def record(
        self, *, user_id: UUID, contact_ids: Sequence[UUID], trace_id: str | None
    ) -> None:
        self.entries.extend(AccessEntry(user_id, c, trace_id) for c in contact_ids)


class InMemoryJobTitleRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, JobTitle] = {}

    async def get(self, job_title_id: UUID) -> JobTitle | None:
        row = self.rows.get(job_title_id)
        return deepcopy(row) if row else None

    async def matching(self, *, code: str, name: str) -> JobTitle | None:
        wanted = unaccented(name)
        for row in self.rows.values():
            if row.code == code or unaccented(row.name_es) == wanted:
                return deepcopy(row)
        return None

    async def list_all(self) -> list[JobTitle]:
        return sorted((deepcopy(r) for r in self.rows.values()), key=lambda r: r.sort_order)

    async def existing_ids(self, ids: Iterable[UUID]) -> frozenset[UUID]:
        return frozenset(i for i in ids if i in self.rows)

    async def next_sort_order(self) -> int:
        return max((r.sort_order for r in self.rows.values()), default=0) + 10

    async def add(self, job_title: JobTitle) -> None:
        self._check_name(job_title)
        self.rows[job_title.id] = deepcopy(job_title)

    async def save(self, job_title: JobTitle, *, expected_version: int) -> None:
        current = self.rows.get(job_title.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        self._check_name(job_title)
        job_title.version = expected_version + 1
        self.rows[job_title.id] = deepcopy(job_title)

    def _check_name(self, job_title: JobTitle) -> None:
        for row in self.rows.values():
            if row.id != job_title.id and (
                row.name_es.lower() == job_title.name_es.lower() or row.code == job_title.code
            ):
                raise JobTitleNameAlreadyExistsError()


class InMemorySpecialtyRepository:
    """Reads plus creation; renaming and deactivating stay in the admin screens."""

    def __init__(self) -> None:
        self.rows: dict[UUID, Specialty] = {}

    async def list_all(self) -> list[Specialty]:
        return sorted((deepcopy(r) for r in self.rows.values()), key=lambda r: r.sort_order)

    async def existing_ids(self, ids: Iterable[UUID]) -> frozenset[UUID]:
        return frozenset(i for i in ids if i in self.rows)

    async def matching(self, *, code: str, name: str) -> Specialty | None:
        wanted = unaccented(name)
        for row in self.rows.values():
            if row.code == code or unaccented(row.name_es) == wanted:
                return deepcopy(row)
        return None

    async def next_sort_order(self) -> int:
        return max((r.sort_order for r in self.rows.values()), default=0) + 10

    async def add(self, specialty: Specialty) -> None:
        self.rows[specialty.id] = deepcopy(specialty)

    async def save(self, specialty: Specialty, *, expected_version: int) -> None:
        current = self.rows.get(specialty.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        specialty.version = expected_version + 1
        self.rows[specialty.id] = deepcopy(specialty)
