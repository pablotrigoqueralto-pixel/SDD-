# specialty-model

The medical specialties catalogue and the migration that frees contacts from carrying a commercial division as if it were a speciality.

## ADDED Requirements

### Requirement: Specialties catalogue
The system SHALL persist medical specialties in a `specialties` table with `id` (UUIDv7), `code` (unique, stable identifier used by the seed), `name_es` (unique, case-insensitive — what every screen shows), `sort_order` (drives the order of every selector) and `is_active`, plus `version` and timestamps. The catalogue SHALL be global: no territory or division filtering applies.

#### Scenario: Uniqueness
- **WHEN** a specialty is created with a `name_es` that already exists ignoring case and accents
- **THEN** a conflict error is raised and nothing is persisted

#### Scenario: Inactive entries still resolve
- **WHEN** a specialty is deactivated while contacts still reference it
- **THEN** those contacts keep the reference and screens still render its name, marked inactive

### Requirement: Seeded specialties
The seed SHALL insert twelve specialties matching Quermed's business — Ginecología, Reproducción asistida, Embriología, Cirugía Vascular, Angiología, Neurología, Neurofisiología, Radiología, Anestesiología, Podología, Enfermería and Dirección médica — insert-only by `code`, so an administrator's renames, reorderings and deactivations survive every later seed run, exactly as job titles already behave.

#### Scenario: First seed
- **WHEN** the seed runs on an empty database
- **THEN** the twelve specialties exist, ordered by `sort_order`, all active

#### Scenario: Administrator edits survive
- **WHEN** an administrator renames "Podología" and deactivates "Radiología", and the seed runs again
- **THEN** the rename and the deactivation remain, and no duplicate rows are created

### Requirement: Contacts carry one specialty
A contact SHALL reference at most one specialty through `specialty_id` (nullable foreign key). The commercial `division_id` SHALL be removed from contacts: divisions continue to describe accounts, products and pipelines, never people.

#### Scenario: Contact with a specialty
- **WHEN** a contact is saved with the specialty "Cirugía Vascular"
- **THEN** the reference is persisted and returned in the contact payload

#### Scenario: Unknown specialty
- **WHEN** a contact is saved with a `specialty_id` that does not exist
- **THEN** a validation error `unknown_reference` naming `specialty_id` is raised

#### Scenario: Specialty is optional
- **WHEN** a contact is saved without a specialty
- **THEN** it persists with `specialty_id = null`

### Requirement: Division to specialty migration without invention
The migration introducing the catalogue SHALL convert existing contact divisions only where the medical meaning is unambiguous — `vascular` → Cirugía Vascular, `assisted_reproduction` → Reproducción asistida, `gynaecology` → Ginecología, `neurology` → Neurología — and SHALL leave `specialty_id` null for every other division (`consumables`, `equipment`, `carts_and_arms`, and any custom one), because those are not medical specialties. It SHALL NOT write a plausible-looking specialty for them. The migration SHALL report how many contacts were mapped and how many were left without a specialty. The downgrade SHALL restore `division_id` for the four mapped specialties.

#### Scenario: Unambiguous division mapped
- **WHEN** a contact held the `vascular` division before the migration
- **THEN** afterwards it references the "Cirugía Vascular" specialty and has no division column

#### Scenario: Non-medical division left empty
- **WHEN** a contact held the `consumables` division
- **THEN** afterwards its `specialty_id` is null — no specialty is invented for it

#### Scenario: Counts reported
- **WHEN** the migration runs over a database with contacts of both kinds
- **THEN** the number of mapped contacts and the number left without a specialty are printed in the migration output
