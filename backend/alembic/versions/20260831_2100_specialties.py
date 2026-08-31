"""medical specialties catalogue and contacts.specialty_id replacing division_id

Revision ID: 0010_specialties
Revises: 0009_phone_lists
Create Date: 2026-08-31 21:00:00+00:00

Reviewed by hand:
- the catalogue rows are written here as well as by the application seed: on a deploy the
  seed runs AFTER alembic, so waiting for it would leave the mapping below with nothing to
  point at. Both use the same deterministic ids and the seed is insert-only by `code`, so
  the rows are written once and an administrator's later edits survive
- only four divisions have an unambiguous medical meaning and are mapped:
  vascular -> Cirugía Vascular, assisted_reproduction -> Reproducción asistida,
  gynaecology -> Ginecología, neurology -> Neurología. consumables, equipment,
  carts_and_arms and any custom division are NOT specialties: those contacts are
  left without one instead of receiving a plausible-looking guess
- the mapped/unmapped counts are printed so the deploy log shows how many
  contacts a rep should review
- downgrade restores division_id for the four mapped specialties; contacts left
  without a specialty simply come back without a division
"""

from collections.abc import Sequence
from uuid import UUID, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_specialties"
down_revision: str | None = "0009_phone_lists"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The catalogue is seeded by the application seed, which runs AFTER alembic on a deploy.
# The mapping below therefore cannot wait for it: this revision inserts the same rows with
# the same deterministic ids (copied from app.infrastructure.db.seed — a migration must not
# import application code), and the seed's insert-only upsert by `code` then finds them and
# leaves them alone.
REFERENCE_NAMESPACE = UUID("2b7c9e10-5d34-4f6a-9c1e-7a8b9c0d1e2f")

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

# division code -> specialty code, only where the medical meaning is unambiguous
DIVISION_TO_SPECIALTY = {
    "vascular": "vascular_surgery",
    "assisted_reproduction": "assisted_reproduction",
    "gynaecology": "gynaecology",
    "neurology": "neurology",
}

INSERT_SPECIALTY = """
INSERT INTO specialties (id, code, name_es, sort_order, is_active, version)
VALUES (:id, :code, :name_es, :sort_order, true, 1)
ON CONFLICT (code) DO NOTHING
"""

MAP_ONE = """
UPDATE contacts c
SET specialty_id = s.id
FROM specialties s, divisions d
WHERE s.code = :specialty_code
  AND d.code = :division_code
  AND c.division_id = d.id
"""

COUNT_MAPPED = "SELECT count(*) FROM contacts WHERE specialty_id IS NOT NULL"
COUNT_UNMAPPED = "SELECT count(*) FROM contacts WHERE specialty_id IS NULL"

RESTORE_ONE = """
UPDATE contacts c
SET division_id = d.id
FROM specialties s, divisions d
WHERE s.code = :specialty_code
  AND d.code = :division_code
  AND c.specialty_id = s.id
"""


def upgrade() -> None:
    op.create_table(
        "specialties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name_es", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )

    op.add_column(
        "contacts",
        sa.Column(
            "specialty_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("specialties.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("ix_contacts_specialty_id", "contacts", ["specialty_id"])

    # The catalogue rows must exist before the mapping can point at them.
    connection = op.get_bind()
    connection.execute(
        sa.text(INSERT_SPECIALTY),
        [
            {
                "id": uuid5(REFERENCE_NAMESPACE, f"specialties:{code}"),
                "code": code,
                "name_es": name,
                "sort_order": position * 10,
            }
            for position, (code, name) in enumerate(SPECIALTIES, start=1)
        ],
    )

    for division_code, specialty_code in DIVISION_TO_SPECIALTY.items():
        connection.execute(
            sa.text(MAP_ONE),
            {"division_code": division_code, "specialty_code": specialty_code},
        )
    mapped = connection.execute(sa.text(COUNT_MAPPED)).scalar_one()
    unmapped = connection.execute(sa.text(COUNT_UNMAPPED)).scalar_one()
    print(  # noqa: T201 - the deploy log is where this belongs
        f"0010_specialties: {mapped} contacts mapped to a specialty, "
        f"{unmapped} left without one (non-medical divisions are not guessed)"
    )

    op.drop_column("contacts", "division_id")


def downgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column(
            "division_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("divisions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    connection = op.get_bind()
    for division_code, specialty_code in DIVISION_TO_SPECIALTY.items():
        connection.execute(
            sa.text(RESTORE_ONE),
            {"division_code": division_code, "specialty_code": specialty_code},
        )

    op.drop_index("ix_contacts_specialty_id", table_name="contacts")
    op.drop_column("contacts", "specialty_id")
    op.drop_table("specialties")
