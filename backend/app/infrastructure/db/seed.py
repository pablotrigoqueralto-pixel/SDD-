"""Idempotent reference data seed.

Seeds the seven product divisions with stable ids and prepares the least-privilege
application role `crm_app` (append-only on audit_log). Safe to run repeatedly.

Usage: `make seed` or `python -m app.infrastructure.db.seed`.
"""

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.infrastructure.db.models import (
    AccountTypeModel,
    ActivityTypeModel,
    BrandModel,
    DivisionModel,
    JobTitleModel,
    LossReasonModel,
    PipelineDivisionModel,
    PipelineModel,
    PipelineStageModel,
    ProductFamilyModel,
    SpecialtyModel,
)
from app.infrastructure.logging import get_logger
from app.infrastructure.settings import get_settings

DIVISION_NAMESPACE = UUID("6f1c2d3e-4a5b-4c6d-8e7f-90a1b2c3d4e5")
REFERENCE_NAMESPACE = UUID("2b7c9e10-5d34-4f6a-9c1e-7a8b9c0d1e2f")
APP_ROLE = "crm_app"

logger = get_logger("seed")


@dataclass(frozen=True)
class DivisionSeed:
    code: str
    name_es: str
    sort_order: int

    @property
    def id(self) -> UUID:
        # Deterministic id so re-running the seed (or seeding another environment) never drifts.
        return uuid5(DIVISION_NAMESPACE, f"division:{self.code}")


DIVISIONS: tuple[DivisionSeed, ...] = (
    DivisionSeed("assisted_reproduction", "Reproducción asistida", 10),
    DivisionSeed("consumables", "Fungibles", 20),
    DivisionSeed("gynaecology", "Ginecología", 30),
    DivisionSeed("vascular", "Vascular", 40),
    DivisionSeed("neurology", "Neurología", 50),
    DivisionSeed("equipment", "Equipos", 60),
    DivisionSeed("carts_and_arms", "Carros y brazos soporte", 70),
)

# APP_ROLE is a constant identifier, never user input.
CREATE_APP_ROLE = f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
        CREATE ROLE {APP_ROLE} NOLOGIN;
    END IF;
END
$$;
"""  # noqa: S608

APP_ROLE_GRANTS: tuple[str, ...] = (
    f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}",
    f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}",
    # audit_log and personal_data_access_log are append-only for the application.
    f"REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM {APP_ROLE}",
    f"GRANT SELECT, INSERT ON audit_log TO {APP_ROLE}",
    f"REVOKE UPDATE, DELETE, TRUNCATE ON personal_data_access_log FROM {APP_ROLE}",
    f"GRANT SELECT, INSERT ON personal_data_access_log TO {APP_ROLE}",
)


async def seed_divisions(engine: AsyncEngine) -> int:
    statement = insert(DivisionModel).values(
        [
            {
                "id": division.id,
                "code": division.code,
                "name_es": division.name_es,
                "sort_order": division.sort_order,
            }
            for division in DIVISIONS
        ]
    )
    upsert = statement.on_conflict_do_update(
        index_elements=[DivisionModel.code],
        set_={"name_es": statement.excluded.name_es, "sort_order": statement.excluded.sort_order},
    )
    async with engine.begin() as connection:
        await connection.execute(upsert)
    return len(DIVISIONS)


# ---------------------------------------------------------------------------
# Reference data (change 02): stable ids, admin edits never overwritten.
# ---------------------------------------------------------------------------


def reference_id(table: str, code: str) -> UUID:
    return uuid5(REFERENCE_NAMESPACE, f"{table}:{code}")


def division_id(code: str) -> UUID:
    return next(division.id for division in DIVISIONS if division.code == code)


@dataclass(frozen=True)
class StageSeed:
    code: str
    name_es: str
    probability: int
    is_won: bool = False
    is_lost: bool = False
    is_at_risk: bool = False


@dataclass(frozen=True)
class PipelineSeed:
    code: str
    name_es: str
    sort_order: int
    divisions: tuple[str, ...]
    stages: tuple[StageSeed, ...]


ACCOUNT_TYPES: tuple[dict[str, object], ...] = (
    {
        "code": "ivf_clinic",
        "name_es": "Clínica FIV / laboratorio",
        "sort_order": 10,
        "buys_via_tender": False,
    },
    {
        "code": "public_hospital",
        "name_es": "Hospital público",
        "sort_order": 20,
        "buys_via_tender": True,
    },
    {
        "code": "private_hospital",
        "name_es": "Hospital privado",
        "sort_order": 30,
        "buys_via_tender": False,
    },
    {
        "code": "private_practice",
        "name_es": "Clínica o consulta privada",
        "sort_order": 40,
        "buys_via_tender": False,
    },
    {
        "code": "podiatry_center",
        "name_es": "Centro de podología / pie diabético",
        "sort_order": 50,
        "buys_via_tender": False,
    },
    {
        "code": "distributor",
        "name_es": "Distribuidor",
        "sort_order": 60,
        "buys_via_tender": False,
    },
)

ACTIVITY_TYPES: tuple[dict[str, object], ...] = (
    {
        "code": "visit",
        "name_es": "Visita",
        "sort_order": 10,
        "icon": "map-pin",
        "counts_as_contact": True,
    },
    {
        "code": "call",
        "name_es": "Llamada",
        "sort_order": 20,
        "icon": "phone",
        "counts_as_contact": True,
    },
    {
        "code": "email",
        "name_es": "Email",
        "sort_order": 30,
        "icon": "mail",
        "counts_as_contact": True,
    },
    {
        "code": "demo",
        "name_es": "Demo",
        "sort_order": 40,
        "icon": "presentation",
        "counts_as_contact": True,
    },
    {
        "code": "training",
        "name_es": "Formación",
        "sort_order": 50,
        "icon": "graduation-cap",
        "counts_as_contact": True,
    },
    {
        "code": "note",
        "name_es": "Nota",
        "sort_order": 60,
        "icon": "sticky-note",
        "counts_as_contact": False,
    },
)

OWN_BRANDS: tuple[tuple[str, str], ...] = (
    ("fertipro", "Fertipro"),
    ("hadeco", "Hadeco"),
    ("viasonix", "Viasonix"),
    ("siemens", "Siemens"),
    ("comen", "Comen"),
    ("minitube", "Minitube"),
    ("three_gen", "3Gen"),
    ("atys", "Atys"),
    ("uscom", "Uscom"),
    ("northern_meditec", "Northern Meditec"),
    ("rimos", "Rimos"),
    ("prodimed", "Prodimed"),
    ("huckerts", "Huckerts"),
)

LOSS_REASONS: tuple[dict[str, object], ...] = (
    {
        "code": "price",
        "name_es": "Precio",
        "sort_order": 10,
        "requires_brand": False,
        "requires_note": False,
    },
    {
        "code": "competitor",
        "name_es": "Competidor",
        "sort_order": 20,
        "requires_brand": True,
        "requires_note": False,
    },
    {
        "code": "no_budget",
        "name_es": "Sin presupuesto",
        "sort_order": 30,
        "requires_brand": False,
        "requires_note": False,
    },
    {
        "code": "project_cancelled",
        "name_es": "Proyecto cancelado",
        "sort_order": 40,
        "requires_brand": False,
        "requires_note": False,
    },
    {
        "code": "timing",
        "name_es": "Plazos",
        "sort_order": 50,
        "requires_brand": False,
        "requires_note": False,
    },
    {
        "code": "other",
        "name_es": "Otro",
        "sort_order": 60,
        "requires_brand": False,
        "requires_note": True,
    },
)

PIPELINES: tuple[PipelineSeed, ...] = (
    PipelineSeed(
        code="equipment",
        name_es="Equipos",
        sort_order=10,
        divisions=("gynaecology", "vascular", "neurology", "equipment", "carts_and_arms"),
        stages=(
            StageSeed("contact", "Contacto", 10),
            StageSeed("demo", "Demo", 30),
            StageSeed("quote", "Presupuesto", 50),
            StageSeed("negotiation", "Negociación/Licitación", 70),
            StageSeed("won", "Ganada", 100, is_won=True),
            StageSeed("lost", "Perdida", 0, is_lost=True),
        ),
    ),
    PipelineSeed(
        code="consumables",
        name_es="Consumibles",
        sort_order=20,
        divisions=("assisted_reproduction", "consumables"),
        stages=(
            StageSeed("trial", "Prueba", 20),
            StageSeed("first_order", "Pedido inicial", 60),
            StageSeed("recurring", "Recurrente", 100, is_won=True),
            StageSeed("at_risk", "En riesgo", 100, is_at_risk=True),
            StageSeed("lost", "Perdida", 0, is_lost=True),
        ),
    ),
)


SPECIALTIES: tuple[tuple[str, str], ...] = (
    ("gynaecology", "Ginecología"),
    ("assisted_reproduction", "Reproducción asistida"),
    ("embryology", "Embriología"),
    ("vascular_surgery", "Cirugía Vascular"),
    ("angiology", "Angiología"),
    ("neurology", "Neurología"),
    ("neurophysiology", "Neurofisiología"),
    ("radiology", "Radiología"),
    ("anaesthesiology", "Anestesiología"),
    ("podiatry", "Podología"),
    ("nursing", "Enfermería"),
    ("medical_management", "Dirección médica"),
)


JOB_TITLES: tuple[tuple[str, str], ...] = (
    ("gynaecologist", "Ginecólogo/a"),
    ("embryologist", "Embriólogo/a"),
    ("ivf_lab_director", "Director/a de laboratorio FIV"),
    ("vascular_surgeon", "Cirujano/a vascular"),
    ("neurologist", "Neurólogo/a"),
    ("head_of_department", "Jefe/a de servicio"),
    ("nursing_supervisor", "Supervisor/a de enfermería"),
    ("purchasing", "Compras / suministros"),
    ("management", "Gerencia"),
    ("clinical_engineering", "Electromedicina / ingeniería clínica"),
    ("other", "Otro"),
)


# (division code, family code, Spanish name). Starter list: admins edit it freely.
PRODUCT_FAMILIES: tuple[tuple[str, str, str], ...] = (
    ("assisted_reproduction", "medios_cultivo", "Medios de cultivo"),
    ("assisted_reproduction", "micromanipulacion", "Micromanipulación"),
    ("assisted_reproduction", "incubadoras", "Incubadoras"),
    ("assisted_reproduction", "laboratorio_fiv", "Laboratorio FIV"),
    ("consumables", "electrodos", "Electrodos"),
    ("consumables", "fungible_general", "Fungible general"),
    ("gynaecology", "ecografos_ginecologia", "Ecógrafos de ginecología"),
    ("gynaecology", "colposcopios", "Colposcopios"),
    ("vascular", "dopplers", "Dopplers"),
    ("vascular", "ecografos_vasculares", "Ecógrafos vasculares"),
    ("neurology", "monitorizacion_neurologica", "Monitorización neurológica"),
    ("neurology", "electroencefalografia", "Electroencefalografía"),
    ("equipment", "monitores", "Monitores"),
    ("equipment", "equipos_generales", "Equipos generales"),
    ("carts_and_arms", "carros", "Carros"),
    ("carts_and_arms", "brazos_soporte", "Brazos soporte"),
)


async def seed_product_families(engine: AsyncEngine) -> None:
    """Insert-only by id: admin renames, reorders and deactivations survive re-seeding."""
    positions: dict[str, int] = {}
    rows: list[dict[str, object]] = []
    for division_code, code, name in PRODUCT_FAMILIES:
        positions[division_code] = positions.get(division_code, 0) + 10
        rows.append(
            {
                "id": reference_id("product_families", code),
                "code": code,
                "name_es": name,
                "division_id": division_id(division_code),
                "sort_order": positions[division_code],
            }
        )
    async with engine.begin() as connection:
        statement = insert(ProductFamilyModel).values(rows)
        await connection.execute(
            statement.on_conflict_do_nothing(index_elements=[ProductFamilyModel.id])
        )


async def seed_job_titles(engine: AsyncEngine) -> None:
    """Insert-only by code: admin renames, reorders and deactivations survive re-seeding."""
    async with engine.begin() as connection:
        statement = insert(JobTitleModel).values(
            [
                {
                    "id": reference_id("job_titles", code),
                    "code": code,
                    "name_es": name,
                    "sort_order": position * 10,
                }
                for position, (code, name) in enumerate(JOB_TITLES, start=1)
            ]
        )
        await connection.execute(
            statement.on_conflict_do_nothing(index_elements=[JobTitleModel.code])
        )


async def seed_specialties(engine: AsyncEngine) -> None:
    """Insert-only by code, like job titles: admin edits survive re-seeding."""
    async with engine.begin() as connection:
        statement = insert(SpecialtyModel).values(
            [
                {
                    "id": reference_id("specialties", code),
                    "code": code,
                    "name_es": name,
                    "sort_order": position * 10,
                }
                for position, (code, name) in enumerate(SPECIALTIES, start=1)
            ]
        )
        await connection.execute(
            statement.on_conflict_do_nothing(index_elements=[SpecialtyModel.code])
        )


async def seed_reference_data(engine: AsyncEngine) -> None:
    """Upsert by code. Semantic flags are refreshed; admin-editable columns (names,
    probabilities, order, active flag, links) are only written on insert."""
    async with engine.begin() as connection:
        account_types = insert(AccountTypeModel).values(
            [{"id": reference_id("account_types", str(r["code"])), **r} for r in ACCOUNT_TYPES]
        )
        await connection.execute(
            account_types.on_conflict_do_update(
                index_elements=[AccountTypeModel.code],
                set_={"buys_via_tender": account_types.excluded.buys_via_tender},
            )
        )
        activity_types = insert(ActivityTypeModel).values(
            [{"id": reference_id("activity_types", str(r["code"])), **r} for r in ACTIVITY_TYPES]
        )
        await connection.execute(
            activity_types.on_conflict_do_update(
                index_elements=[ActivityTypeModel.code],
                set_={
                    "icon": activity_types.excluded.icon,
                    "counts_as_contact": activity_types.excluded.counts_as_contact,
                },
            )
        )
        brands = insert(BrandModel).values(
            [
                {"id": reference_id("brands", code), "code": code, "name": name, "is_own": True}
                for code, name in OWN_BRANDS
            ]
        )
        await connection.execute(brands.on_conflict_do_nothing(index_elements=[BrandModel.code]))
        loss_reasons = insert(LossReasonModel).values(
            [{"id": reference_id("loss_reasons", str(r["code"])), **r} for r in LOSS_REASONS]
        )
        await connection.execute(
            loss_reasons.on_conflict_do_update(
                index_elements=[LossReasonModel.code],
                set_={
                    "requires_brand": loss_reasons.excluded.requires_brand,
                    "requires_note": loss_reasons.excluded.requires_note,
                },
            )
        )
        for pipeline in PIPELINES:
            pipeline_uuid = reference_id("pipelines", pipeline.code)
            await connection.execute(
                insert(PipelineModel)
                .values(
                    id=pipeline_uuid,
                    code=pipeline.code,
                    name_es=pipeline.name_es,
                    sort_order=pipeline.sort_order,
                )
                .on_conflict_do_nothing(index_elements=[PipelineModel.code])
            )
            await connection.execute(
                insert(PipelineDivisionModel)
                .values(
                    [
                        {"pipeline_id": pipeline_uuid, "division_id": division_id(code)}
                        for code in pipeline.divisions
                    ]
                )
                .on_conflict_do_nothing()
            )
            stages = insert(PipelineStageModel).values(
                [
                    {
                        "id": reference_id("pipeline_stages", f"{pipeline.code}:{stage.code}"),
                        "pipeline_id": pipeline_uuid,
                        "code": stage.code,
                        "name_es": stage.name_es,
                        "sort_order": position,
                        "probability": stage.probability,
                        "is_won": stage.is_won,
                        "is_lost": stage.is_lost,
                        "is_at_risk": stage.is_at_risk,
                    }
                    for position, stage in enumerate(pipeline.stages, start=1)
                ]
            )
            await connection.execute(
                stages.on_conflict_do_update(
                    index_elements=[PipelineStageModel.pipeline_id, PipelineStageModel.code],
                    set_={
                        "is_won": stages.excluded.is_won,
                        "is_lost": stages.excluded.is_lost,
                        "is_at_risk": stages.excluded.is_at_risk,
                    },
                )
            )


async def prepare_app_role(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(text(CREATE_APP_ROLE))
        for grant in APP_ROLE_GRANTS:
            await connection.execute(text(grant))


async def run_seed(engine: AsyncEngine) -> None:
    count = await seed_divisions(engine)
    await seed_reference_data(engine)
    await seed_job_titles(engine)
    await seed_specialties(engine)
    await seed_product_families(engine)
    await prepare_app_role(engine)
    logger.info("seed_completed", divisions=count, app_role=APP_ROLE)


async def main() -> None:
    engine = create_async_engine(get_settings().database_url)
    try:
        await run_seed(engine)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
