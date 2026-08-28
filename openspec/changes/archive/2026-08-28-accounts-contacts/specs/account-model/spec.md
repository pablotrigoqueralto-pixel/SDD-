## ADDED Requirements

### Requirement: Account record
The system SHALL persist accounts ("centros") in an `accounts` table with `id` (UUIDv7), `name` (citext, required — identifies the centre in every list, search and report), `account_type_id` (required — drives tender defaults in opportunities and the type filter in dashboards), `province_code` (required — resolves territory and owner defaults and feeds territory reports), optional primary address `street`, `postal_code` (5 digits), `city`, optional `tax_id` (Spanish NIF/CIF/NIE, normalised to upper case without spaces, unique when present — matches Sage customers and prevents duplicates), `customer_code` (Sage reference for quotes), `phone`, `email`, `website`, `notes`, `territory_id` (nullable), `owner_id` (nullable, references a user), `is_active`, `version`, `created_at`, `updated_at`. Accounts SHALL link to zero or more divisions of interest (`account_divisions`) and zero or more brands in use (`account_brands`).

#### Scenario: Minimum account
- **WHEN** an account is created with only `name`, `account_type_id` and `province_code`
- **THEN** it is persisted with every optional field null, `is_active = true` and `version = 1`

#### Scenario: Invalid tax id
- **WHEN** an account is created with `tax_id = "B1234567X"` (wrong check digit)
- **THEN** a validation error with code `tax_id_invalid` is raised and nothing is persisted

#### Scenario: Duplicate tax id
- **WHEN** an account is created with a `tax_id` that already exists (case-insensitive, ignoring spaces and hyphens)
- **THEN** a conflict error `tax_id_already_exists` referencing the existing account id is raised

#### Scenario: Invalid postal code or phone
- **WHEN** `postal_code` is not five digits or `phone` cannot be normalised to E.164 with the `+34` default
- **THEN** validation errors `postal_code_invalid` / `phone_invalid` are raised naming the field

### Requirement: Territory and owner defaults
On creation the system SHALL set `territory_id` to the territory that owns `province_code` (null when no territory claims the province) and SHALL set `owner_id` as follows: the creator when the creator is a `sales_rep`; otherwise the single active `sales_rep` assigned to the resolved territory whose divisions overlap the account's divisions of interest (any rep when the account declares none) if exactly one such rep exists; otherwise null. Changing `province_code` later SHALL NOT change `territory_id`; the account SHALL expose `territory_mismatch = true` when the province's territory differs from `territory_id`.

#### Scenario: Rep creates an account
- **WHEN** a `sales_rep` assigned to territory `Centro` creates an account in province `28`
- **THEN** `territory_id` is `Centro` and `owner_id` is the rep

#### Scenario: Manager creates in a one-rep territory
- **WHEN** a `sales_manager` creates an account in province `48` and territory `Norte` has exactly one active rep compatible with the account's divisions
- **THEN** `owner_id` is that rep

#### Scenario: Manager creates in an ambiguous territory
- **WHEN** a `sales_manager` creates an account in a territory with two compatible reps
- **THEN** `owner_id` is null and the account appears in the "sin comercial" filter

#### Scenario: Province without territory
- **WHEN** an account is created in a province no territory claims
- **THEN** `territory_id` and `owner_id` (unless the creator is a rep) are null and creation succeeds

#### Scenario: Province edited after creation
- **WHEN** the primary province of an account in `Centro` is changed to `08` (territory `Cataluña`)
- **THEN** `territory_id` stays `Centro` and `territory_mismatch` is true

### Requirement: Additional addresses
An account SHALL hold up to 10 additional addresses in `account_addresses` with `label` (unique per account, case-insensitive), `street`, `postal_code`, `city`, `province_code` and optional `notes`. Additional addresses SHALL NOT affect territory derivation.

#### Scenario: Duplicate label
- **WHEN** two addresses with label `Laboratorio` (any case) are saved for the same account
- **THEN** a validation error `address_label_duplicated` is raised

#### Scenario: Too many addresses
- **WHEN** an eleventh additional address is saved
- **THEN** a validation error `too_many_addresses` is raised

### Requirement: Job titles master
The system SHALL provide a `job_titles` master (`code` unique, `name_es` unique case-insensitive, `sort_order`, `is_active`, `version`) seeded idempotently with deterministic ids for: `gynaecologist` Ginecólogo/a, `embryologist` Embriólogo/a, `ivf_lab_director` Director/a de laboratorio FIV, `vascular_surgeon` Cirujano/a vascular, `neurologist` Neurólogo/a, `head_of_department` Jefe/a de servicio, `nursing_supervisor` Supervisor/a de enfermería, `purchasing` Compras / suministros, `management` Gerencia, `clinical_engineering` Electromedicina / ingeniería clínica, `other` Otro. Re-running the seed SHALL preserve admin edits to `name_es`, `sort_order` and `is_active`.

#### Scenario: Seed twice
- **WHEN** the seed runs on a database where an admin renamed `purchasing` to "Compras"
- **THEN** eleven job titles exist and `purchasing` keeps the name "Compras"

### Requirement: Search performance indexes
The `accounts` table SHALL have indexes supporting the list endpoint: trigram GIN indexes on `name` and `city`, btree indexes on `tax_id`, `customer_code`, `territory_id`, `owner_id`, `account_type_id`, `province_code`, `is_active`; `account_divisions` SHALL be indexed by `division_id`. Listing 50 000 accounts with a text filter SHALL complete under 500 ms.

#### Scenario: Name search uses the trigram index
- **WHEN** 5 000 accounts exist and the list is queried with `q = "tam"`
- **THEN** the query plan uses the trigram index on `name` and the response is under 500 ms

### Requirement: Migration
Alembic migration `0003_accounts_contacts` SHALL create `accounts`, `account_addresses`, `account_divisions`, `account_brands`, `job_titles`, `contacts`, `personal_data_access_log`, the enums `preferred_channel`, `consent_status`, `consent_source`, the `pg_trgm` extension and the `crm_app` grants (INSERT-only on `personal_data_access_log`). Downgrade SHALL drop them in reverse order.

#### Scenario: Round trip
- **WHEN** `alembic upgrade head` then `downgrade 0002` then `upgrade head` run on an empty database
- **THEN** every step succeeds and the final schema matches the ORM metadata
