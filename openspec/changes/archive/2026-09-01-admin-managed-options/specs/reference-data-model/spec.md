# reference-data-model (delta)

Account types and specialties become administrator-editable masters, and stage ordering gains the terminal-stages-last invariant.

## MODIFIED Requirements

### Requirement: Account types
The system SHALL store account types with `id`, `code` (unique, immutable), `name_es`, `sort_order`, `buys_via_tender` and `is_active`, and SHALL seed exactly six: `ivf_clinic`, `public_hospital` (`buys_via_tender = true`), `private_hospital`, `private_practice`, `podiatry_center`, `distributor`. Administrators SHALL be able to **create** further types, whose `code` is derived from the name and whose `buys_via_tender` is stated explicitly at creation (default `false`); the seeded six SHALL remain untouched by a re-seed.

Required fields and justification: `code` (stable reference from code and imports), `name_es` (label in every account form and report), `sort_order` (dropdown order), `buys_via_tender` (defaults the tender stage for opportunities of public hospitals — a type created without stating it would silently behave like a private clinic).

#### Scenario: Seed creates the six types
- **WHEN** the seed runs on an empty database
- **THEN** six account types exist in `sort_order` with the Spanish names Clínica FIV / laboratorio, Hospital público, Hospital privado, Clínica o consulta privada, Centro de podología / pie diabético, Distribuidor, and only Hospital público has `buys_via_tender = true`

#### Scenario: Administrator adds a type
- **WHEN** an administrator creates the type "Consorcio sanitario" with `buys_via_tender = true`
- **THEN** it is stored with `code = "consorcio_sanitario"`, a `sort_order` after every existing type, `is_active = true`, and the tender fields become available to opportunities of centres of that type

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

## ADDED Requirements

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
