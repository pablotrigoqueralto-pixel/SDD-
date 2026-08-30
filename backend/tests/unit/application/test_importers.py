from decimal import Decimal
from uuid import UUID

import pytest

from app.application.imports.accounts import AccountImporter
from app.application.imports.products import ProductImporter
from app.application.imports.report import (
    RowOutcome,
    normalise_tax_id,
    normalise_text,
    parse_spanish_number,
)
from app.domain.reference.entities import AccountType, Brand, JobTitle, ProductFamily
from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.fakes.reference import InMemoryReferenceReadRepository

IVF = AccountType(UUID(int=1), "ivf_clinic", "Clínica FIV", 10, False, True)
HOSPITAL = AccountType(UUID(int=2), "public_hospital", "Hospital público", 20, True, True)
CENTRO = Territory.create(name="Centro", provinces=frozenset({"28"}))
HADECO = Brand.create(name="Hadeco", is_own=True, division_ids=frozenset())
GYNAECOLOGIST = JobTitle(UUID(int=3), "gynaecologist", "Ginecólogo/a", 10)


def make_user(role: Role) -> User:
    return User.create(
        email=Email(f"{role.value}@quermed.com"),
        full_name=role.value,
        role=role,
        password_hash="h",
    )


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.reference = InMemoryReferenceReadRepository(
        account_types=[IVF, HOSPITAL], activity_types=[]
    )
    uow.territories.rows[CENTRO.id] = CENTRO
    uow.brands.rows[HADECO.id] = HADECO
    uow.job_titles.rows[GYNAECOLOGIST.id] = GYNAECOLOGIST
    return uow


@pytest.fixture
def back_office(uow: FakeUnitOfWork) -> User:
    user = make_user(Role.BACK_OFFICE)
    uow.users.rows[user.id] = user
    return user


class TestHelpers:
    def test_spanish_numbers(self) -> None:
        assert parse_spanish_number("1.234,56") == Decimal("1234.56")
        assert parse_spanish_number("1234.56") == Decimal("1234.56")
        assert parse_spanish_number("1234") == Decimal("1234")

    def test_normalisers(self) -> None:
        assert normalise_text("  Clínica   TAMBRE ") == "clinica tambre"
        assert normalise_tax_id(" b-123.456 78 ") == "B12345678"


PRODUCT_CSV = (
    "Código;Nombre;Marca;Familia;PVP;Coste\nIMP-1;Doppler importado;Hadeco;Dopplers;1.250,50;900\n"
)


@pytest.fixture
def family(uow: FakeUnitOfWork) -> ProductFamily:
    item = ProductFamily(
        id=UUID(int=9),
        code="dopplers",
        name_es="Dopplers",
        division_id=UUID(int=8),
        sort_order=10,
    )
    uow.product_families.rows[item.id] = item
    return item


class TestProductImporter:
    async def test_dry_run_previews_without_writing(
        self, uow: FakeUnitOfWork, back_office: User, family: ProductFamily
    ) -> None:
        report = await ProductImporter(uow).run(
            "productos.csv", PRODUCT_CSV.encode(), dry_run=True, actor=back_office
        )

        assert [row.outcome for row in report.rows] == [RowOutcome.CREATED]
        assert uow.products.rows == {}
        assert uow.actions() == []

    async def test_apply_creates_then_reimport_is_unchanged(
        self, uow: FakeUnitOfWork, back_office: User, family: ProductFamily
    ) -> None:
        first = await ProductImporter(uow).run(
            "productos.csv", PRODUCT_CSV.encode(), dry_run=False, actor=back_office
        )
        assert first.created == 1 and first.errors == 0
        stored = next(iter(uow.products.rows.values()))
        assert stored.list_price == Decimal("1250.50")
        assert "import.products_executed" in uow.actions()

        again = await ProductImporter(uow).run(
            "productos.csv", PRODUCT_CSV.encode(), dry_run=False, actor=back_office
        )
        assert again.unchanged == 1

        preview = await ProductImporter(uow).run(
            "productos.csv",
            PRODUCT_CSV.replace("1.250,50", "1.300,00").encode(),
            dry_run=True,
            actor=back_office,
        )
        assert [row.outcome for row in preview.rows] == [RowOutcome.UPDATED]

    async def test_unknown_brand_and_family_are_row_errors(
        self, uow: FakeUnitOfWork, back_office: User, family: ProductFamily
    ) -> None:
        csv = (
            "Código;Nombre;Marca;Familia;PVP\n"
            "A-1;Uno;Desconocida;Dopplers;10\n"
            "A-2;Dos;Hadeco;Inexistente;10\n"
        )
        report = await ProductImporter(uow).run(
            "productos.csv", csv.encode(), dry_run=False, actor=back_office
        )

        assert report.errors == 2
        assert "Desconocida" in (report.rows[0].message or "")
        assert "Inexistente" in (report.rows[1].message or "")
        assert uow.products.rows == {}


ACCOUNT_CSV = (
    "Nombre;CIF;Provincia;Teléfono;Contacto nombre;Contacto apellidos;Contacto email;Cargo\n"
    "Clínica Importada;12345678Z;28;+34910000001;Ana;Pérez;ana@imp.es;Ginecólogo/a\n"
)


class TestAccountImporter:
    async def test_creates_account_with_defaults_and_contact(
        self, uow: FakeUnitOfWork, back_office: User
    ) -> None:
        report = await AccountImporter(uow).run(
            "centros.csv", ACCOUNT_CSV.encode(), dry_run=False, actor=back_office
        )

        assert [row.outcome for row in report.rows] == [RowOutcome.CREATED]
        account = next(iter(uow.accounts.rows.values()))
        assert account.territory_id == CENTRO.id  # from province 28
        assert account.tax_id == "12345678Z"
        contact = next(iter(uow.contacts.rows.values()))
        assert contact.account_id == account.id
        assert contact.email == "ana@imp.es"
        assert contact.job_title_id == GYNAECOLOGIST.id
        assert "import.accounts_executed" in uow.actions()
        assert "contact.created" in uow.actions()

    async def test_cif_match_updates_administrative_fields_only(
        self, uow: FakeUnitOfWork, back_office: User
    ) -> None:
        importer = AccountImporter(uow)
        await importer.run("centros.csv", ACCOUNT_CSV.encode(), dry_run=False, actor=back_office)

        changed = ACCOUNT_CSV.replace("+34910000001", "+34910000099").replace(
            "Clínica Importada",
            "Clinica Importada SL",  # name differs; CIF wins, no rename
        )
        report = await importer.run(
            "centros.csv", changed.encode(), dry_run=False, actor=back_office
        )

        assert [row.outcome for row in report.rows] == [RowOutcome.UPDATED]
        account = next(iter(uow.accounts.rows.values()))
        assert account.phone == "+34910000099"
        assert account.name == "Clínica Importada"

    async def test_name_fallback_and_near_name_creates(
        self, uow: FakeUnitOfWork, back_office: User
    ) -> None:
        no_cif = "Nombre;Provincia\nClínica Importada;28\n"
        importer = AccountImporter(uow)
        await importer.run("centros.csv", no_cif.encode(), dry_run=False, actor=back_office)

        same_normalised = "Nombre;Provincia\nclinica   IMPORTADA;28\n"
        matched = await importer.run(
            "centros.csv", same_normalised.encode(), dry_run=False, actor=back_office
        )
        assert [row.outcome for row in matched.rows] == [RowOutcome.UNCHANGED]

        near = "Nombre;Provincia\nClínica Importada SL;28\n"
        created = await importer.run("centros.csv", near.encode(), dry_run=False, actor=back_office)
        assert [row.outcome for row in created.rows] == [RowOutcome.CREATED]
        assert len(uow.accounts.rows) == 2

    async def test_idempotent_rerun_and_contact_update(
        self, uow: FakeUnitOfWork, back_office: User
    ) -> None:
        importer = AccountImporter(uow)
        await importer.run("centros.csv", ACCOUNT_CSV.encode(), dry_run=False, actor=back_office)

        rerun = await importer.run(
            "centros.csv", ACCOUNT_CSV.encode(), dry_run=False, actor=back_office
        )
        assert [row.outcome for row in rerun.rows] == [RowOutcome.UNCHANGED]
        assert len(uow.contacts.rows) == 1

        new_phone = ACCOUNT_CSV.replace("Cargo\n", "Cargo;Contacto teléfono\n").replace(
            "Ginecólogo/a\n", "Ginecólogo/a;+34600000001\n"
        )
        updated = await importer.run(
            "centros.csv", new_phone.encode(), dry_run=False, actor=back_office
        )
        assert [row.outcome for row in updated.rows] == [RowOutcome.UPDATED]
        contact = next(iter(uow.contacts.rows.values()))
        assert contact.mobile == "+34600000001"

    async def test_invalid_province_is_a_row_error(
        self, uow: FakeUnitOfWork, back_office: User
    ) -> None:
        bad = "Nombre;Provincia\nCentro Malo;99\n"
        report = await AccountImporter(uow).run(
            "centros.csv", bad.encode(), dry_run=False, actor=back_office
        )
        assert report.errors == 1
        assert uow.accounts.rows == {}

    async def test_dry_run_writes_nothing(self, uow: FakeUnitOfWork, back_office: User) -> None:
        report = await AccountImporter(uow).run(
            "centros.csv", ACCOUNT_CSV.encode(), dry_run=True, actor=back_office
        )
        assert [row.outcome for row in report.rows] == [RowOutcome.CREATED]
        assert uow.accounts.rows == {} and uow.contacts.rows == {}
        assert uow.actions() == []

    async def test_unknown_job_title_is_a_message_not_an_error(
        self, uow: FakeUnitOfWork, back_office: User
    ) -> None:
        odd = ACCOUNT_CSV.replace("Ginecólogo/a", "Astronauta")
        report = await AccountImporter(uow).run(
            "centros.csv", odd.encode(), dry_run=False, actor=back_office
        )
        assert [row.outcome for row in report.rows] == [RowOutcome.CREATED]
        assert "Astronauta" in (report.rows[0].message or "")
        contact = next(iter(uow.contacts.rows.values()))
        assert contact.job_title_id is None
