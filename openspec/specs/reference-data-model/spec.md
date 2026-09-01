# reference-data-model

## Purpose
Tables, invariants and idempotent seed for account types, activity types, brands, loss reasons, pipelines and stages.

## Requirements

### Requirement: Account types
The system SHALL store account types with `id`, `code` (unique, immutable), `name_es`, `sort_order`, `buys_via_tender` and `is_active`, and SHALL seed exactly six: `ivf_clinic`, `public_hospital` (`buys_via_tender = true`), `private_hospital`, `private_practice`, `podiatry_center`, `distributor`. Administrators SHALL be able to **create** further types, whose `code` is derived from the name and whose `buys_via_tender` is stated explicitly at creation (default `false`); the seeded six SHALL remain untouched by a re-seed.

Required fields and justification: `code` (stable reference from code and imports), `name_es` (label in every account form and report), `sort_order` (dropdown order), `buys_via_tender` (defaults the tender stage for opportunities of public hospitals — a type created without stating it would silently behave like a private clinic).

#### Scenario: Seed creates the six types
- **WHEN** the seed runs on an empty database
- **THEN** six account types exist in `sort_order` with the Spanish names Clínica FIV / laboratorio, Hospital público, Hospital privado, Clínica o consulta privada, Centro de podología / pie diabético, Distribuidor, and only Hospital público has `buys_via_tender = true`

#### Scenario: Administrator adds a type
- **WHEN** an administrator creates the type "Consorcio sanitario" with `buys_via_tender = true`
- **THEN** it is stored with `code = "consorcio_sanitario"`, a `sort_order` after every existing type, `is_active = true`, and the tender fields become available to opportunities of centres of that type

### Requirement: Activity types
The system SHALL store activity types with `id`, `code` (unique, immutable), `name_es`, `sort_order`, `icon`, `counts_as_contact` and `is_active`, and SHALL seed exactly six: `visit`, `call`, `email`, `demo`, `training`, `note` (`counts_as_contact = false`).

Required fields and justification: `icon` (timeline rendering), `counts_as_contact` (activity reports count only real customer contacts).

#### Scenario: Seed creates the six types
- **WHEN** the seed runs on an empty database
- **THEN** six activity types exist with the Spanish names Visita, Llamada, Email, Demo, Formación, Nota, and only Nota has `counts_as_contact = false`

### Requirement: Brands
The system SHALL store brands with `id`, `code` (unique, immutable, derived from the name), `name` (unique, case-insensitive), `is_own`, `is_active`, `version`, and a set of linked divisions. The seed SHALL create the thirteen represented manufacturers (Fertipro, Hadeco, Viasonix, Siemens, Comen, Minitube, 3Gen, Atys, Uscom, Northern Meditec, Rimos, Prodimed, Huckerts) as own brands without division links.

Required fields and justification: `name` (shown on products, accounts and loss reasons), `is_own` (manufacturer reports vs competitor tracking).

#### Scenario: Seed creates own brands
- **WHEN** the seed runs on an empty database
- **THEN** thirteen active brands with `is_own = true` exist and `3Gen` has code `three_gen`

#### Scenario: Name uniqueness is case-insensitive
- **WHEN** a brand named `fertipro` is created while `Fertipro` exists
- **THEN** the operation fails with `brand_name_already_exists`

#### Scenario: Division links reference existing divisions
- **WHEN** a brand is linked to a division id that does not exist
- **THEN** the operation fails with `unknown_reference` on field `division_ids`

### Requirement: Loss reasons
The system SHALL store loss reasons with `id`, `code`, `name_es` (unique, case-insensitive), `sort_order`, `requires_brand`, `requires_note`, `is_active`, `version`, and SHALL seed six: `price` Precio, `competitor` Competidor (`requires_brand`), `no_budget` Sin presupuesto, `project_cancelled` Proyecto cancelado, `timing` Plazos, `other` Otro (`requires_note`).

Required fields and justification: `requires_brand` / `requires_note` (the pipeline change enforces them when an opportunity is lost).

#### Scenario: Seed creates the six reasons
- **WHEN** the seed runs on an empty database
- **THEN** six loss reasons exist in `sort_order`, only Competidor has `requires_brand = true` and only Otro has `requires_note = true`

### Requirement: Pipelines and stages
The system SHALL store pipelines (`id`, `code`, `name_es` unique, `sort_order`, `version`, linked default divisions) and stages (`id`, `pipeline_id`, `code` unique per pipeline, `name_es`, `sort_order` unique per pipeline, `probability` 0–100, `is_won`, `is_lost`, `is_at_risk`, `is_active`, `version`). A division SHALL have at most one default pipeline. A stage SHALL NOT be both won and lost. **Terminal stages** — those carrying `is_won`, `is_lost` or `is_at_risk` — SHALL always occupy the last positions of their pipeline: no ordering SHALL place a terminal stage before an advancing one.

The seed SHALL create:
- `equipment` Equipos (divisions gynaecology, vascular, neurology, equipment, carts_and_arms) with stages Contacto 10 %, Demo 30 %, Presupuesto 50 %, Negociación/Licitación 70 %, Ganada 100 % (`is_won`), Perdida 0 % (`is_lost`).
- `consumables` Consumibles (divisions assisted_reproduction, consumables) with stages Prueba 20 %, Pedido inicial 60 %, Recurrente 100 % (`is_won`), En riesgo 100 % (`is_at_risk`), Perdida 0 % (`is_lost`).

Required fields and justification: `probability` (weighted forecast on the manager dashboard), `is_won` / `is_lost` (closing an opportunity, loss reason mandatory), `is_at_risk` (consumables alerting), default divisions (smart default when creating an opportunity).

#### Scenario: Seed creates both pipelines
- **WHEN** the seed runs on an empty database
- **THEN** two pipelines exist with the stages, probabilities, flags and default divisions above, and every division has exactly one default pipeline

#### Scenario: Stage invariants are enforced by the database
- **WHEN** a row is inserted with `probability = 120`, or with `is_won = true` and `is_lost = true`, or with a `sort_order` already used in the same pipeline
- **THEN** the database rejects it

#### Scenario: Advancing stages reorder freely
- **WHEN** an order swaps Demo and Presupuesto in the Equipos pipeline
- **THEN** it is accepted, the new positions are stored and the terminal stages keep the end of the pipeline

#### Scenario: A terminal stage cannot be lifted
- **WHEN** an order places Perdida before Presupuesto
- **THEN** the pipeline rejects it and the stored order is unchanged

### Requirement: Idempotent seed that respects administrator edits
Running the seed SHALL be idempotent: rows are matched by `code`, ids never change, and admin-editable columns (`name`, `name_es`, `probability`, `sort_order`, `is_active`, division links) SHALL NOT be overwritten on rows that already exist.

#### Scenario: Re-seed keeps an admin rename
- **WHEN** an administrator renames the brand `Hadeco` to `Hadeco Europe` and the seed runs again
- **THEN** the brand keeps the name `Hadeco Europe` and its id

#### Scenario: Re-seed keeps a tuned probability
- **WHEN** an administrator sets Demo to 40 % and the seed runs again
- **THEN** the stage keeps 40 %

#### Scenario: Deterministic ids across environments
- **WHEN** the seed runs on two separate empty databases
- **THEN** every seeded master row has the same `id` in both

### Requirement: Migration
Migration `0002_reference_data` SHALL create the eight tables with their constraints and indexes, SHALL be reversible, and `alembic check` SHALL report no drift against the ORM models.

#### Scenario: Round-trip
- **WHEN** `alembic upgrade head`, `alembic downgrade -1` and `alembic upgrade head` run
- **THEN** all commands succeed and `alembic check` is clean

### Requirement: Specialties master
The specialties catalogue SHALL be a reference master alongside job titles: global, seeded insert-only by `code`, **created by administrators**, editable in name, order and activation without losing its identity, and included in the reference bundle so every screen resolves specialty names from one place.

#### Scenario: Part of the masters
- **WHEN** the reference masters are enumerated
- **THEN** specialties appear with account types, activity types, divisions, brands, loss reasons, pipelines, job titles and product families

#### Scenario: Seed respects edits
- **WHEN** an administrator renames a specialty and the seed runs again
- **THEN** the rename survives and no duplicate is created

#### Scenario: Administrator adds a specialty
- **WHEN** an administrator creates "Urología"
- **THEN** it is stored with `code = "urologia"`, a `sort_order` after every existing specialty, and contacts can be assigned to it immediately

### Requirement: Reuse of an existing catalogue entry
Creating an entry in an administrator-editable catalogue (job titles, specialties, account types, loss reasons, product families) SHALL reuse an existing row instead of creating a second one whenever the requested name matches it **either** by the `code` the name derives from **or** by its stored `name_es` compared without accents and without regard to case. Both halves are required because seeded rows carry hand-written English codes that their Spanish names do not derive (`management` for "Gerencia"). A reused row that was inactive SHALL be reactivated. Two spellings of one name SHALL NOT be able to coexist.

#### Scenario: Same name in another spelling
- **WHEN** an administrator creates "GERENCIA" or "gerencia" and the seeded job title "Gerencia" (`code = "management"`) already exists
- **THEN** the existing row is returned and no second row is created

#### Scenario: An accent is the only difference
- **WHEN** an administrator creates "Ginecologo/a" and "Ginecólogo/a" already exists
- **THEN** the existing row is returned, so the catalogue never holds both spellings

#### Scenario: Reusing an inactive entry
- **WHEN** the resolved entry exists but is inactive
- **THEN** it is reactivated and returned, and the reactivation is recorded

#### Scenario: A genuinely new name
- **WHEN** no entry resolves to that code
- **THEN** a new row is created with `sort_order` after every existing entry and `is_active = true`
