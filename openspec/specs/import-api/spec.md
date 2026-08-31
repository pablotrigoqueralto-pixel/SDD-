# import-api

## Purpose
Catalogue and accounts/contacts import endpoints: multipart CSV/xlsx upload with Spanish header aliases, dry-run preview with per-row outcomes, idempotent create-or-update matching by SKU and CIF, row caps and role gating.

## Requirements

### Requirement: Import endpoints and flow
`POST /api/v1/products/import` and `POST /api/v1/accounts/import` SHALL accept a multipart file (`.csv` or `.xlsx`) plus a `dry_run` flag defaulting to `true`, and answer with the full per-row report — `{row, outcome, label, message?}` where `outcome` is `created` | `updated` | `unchanged` | `error` — plus totals per outcome. With `dry_run=true` nothing SHALL be written. With `dry_run=false` valid rows SHALL be applied row by row through the same services a manual API call uses (each row commits with its own audit trail; error rows are skipped) and the same report SHALL come back — idempotent matching makes re-running a partially applied file safe. Files over 2 000 data rows or 5 MB, unreadable files and files missing required headers SHALL fail fast with a 422 naming the problem. Both endpoints SHALL require `admin` or `back_office` (403 otherwise). Imports SHALL never delete or deactivate records.

#### Scenario: Dry run writes nothing
- **WHEN** a valid catalogue file is posted with `dry_run=true`
- **THEN** the report shows the would-be outcomes and no product row changes

#### Scenario: Valid rows import, errors are reported
- **WHEN** a 100-row file with 3 invalid rows is posted with `dry_run=false`
- **THEN** the 97 valid rows are applied and the report lists the 3 errors with row numbers and reasons; re-importing the corrected file leaves the 97 as `unchanged`

#### Scenario: Oversized file
- **WHEN** a file with 5 000 rows is posted
- **THEN** the request fails with 422 telling the user to split the file, and nothing is parsed row by row

#### Scenario: Role gate
- **WHEN** a `sales_rep` or `sales_manager` posts to either endpoint
- **THEN** it fails with 403

### Requirement: Tabular file parsing
The reader SHALL accept CSV with `;` or `,` (sniffed) in UTF-8 (with or without BOM) falling back to cp1252, and `.xlsx` via openpyxl (first worksheet, read-only). Headers SHALL match case-insensitively with accents stripped against the canonical names and their Spanish aliases (e.g. `sku`/`código`, `name`/`nombre`, `list_price`/`pvp`, `tax_id`/`cif`), documented in `development_guide.md`. Empty rows SHALL be skipped silently; values SHALL be trimmed.

#### Scenario: Spanish Excel accepted
- **WHEN** an `.xlsx` with headers "Código, Nombre, PVP" is uploaded to the catalogue importer
- **THEN** the columns map to `sku`, `name`, `list_price` and the preview shows real outcomes

#### Scenario: Missing required header
- **WHEN** a catalogue file lacks any column mapping to `sku`
- **THEN** the request fails with 422 naming the missing column

### Requirement: Catalogue import semantics
Product rows SHALL flow through the change-05 contract (`ProductImportRow` → `upsert_by_sku`): match by normalised SKU; update the fields present in the file when they differ; report `unchanged` when nothing differs; create otherwise. Brand and family SHALL resolve by case-insensitive name lookup; an unknown brand or family SHALL make that row an `error` (imports never create reference data). Prices SHALL accept Spanish decimal commas.

#### Scenario: Idempotent re-import
- **WHEN** the same Sage export is imported twice
- **THEN** the second run reports every row as `unchanged`

#### Scenario: Unknown brand
- **WHEN** a row names a brand that does not exist
- **THEN** the row is an `error` with a message naming the brand, and no brand is created

### Requirement: Accounts and contacts import semantics
Account rows SHALL match by normalised CIF (uppercase, separators stripped); without CIF, by exact unaccented, case-folded, space-collapsed name; no match SHALL create the account through the existing creation defaults (territory from `province_code`, owner via the territory smart-default rules — no owner column: assignment stays a manager action). The `Teléfono` column SHALL create or update the account's **primary** phone (labelled "Principal"), leaving any other phone of that centre untouched. A row MAY embed one contact via optional `contact_*` columns (first/last name, email, phone, job title by name, **specialty by name**); the contact phone column SHALL create or update that contact's primary phone labelled "Móvil"; several contacts for one account repeat the account columns. The specialty SHALL be resolved case- and accent-insensitively against the catalogue's Spanish names, and an unknown value SHALL be a **message on the row, not an error** — the contact is created without a specialty, exactly as an unknown job title behaves. Contacts SHALL match by email within their account, falling back to normalised full name; imported contacts SHALL enter with the default consent state. Fuzzy matching SHALL NOT be used: near-matches create a new account rather than silently merging.

#### Scenario: CIF match updates
- **WHEN** a row carries the CIF of an existing centre with a new phone
- **THEN** the centre is `updated`, its primary phone takes the new number and its other labelled phones are preserved

#### Scenario: Embedded contact created
- **WHEN** a matched account row fills `contact_first_name`, `contact_last_name` and `contact_email`
- **THEN** the contact is created under that account (or `updated` if the email already exists there)

#### Scenario: Specialty resolved by name
- **WHEN** a row carries `Especialidad` = "cirugia vascular"
- **THEN** the contact is created with the "Cirugía Vascular" specialty despite the missing accent and lower case

#### Scenario: Unknown specialty is a message
- **WHEN** a row carries a specialty that is not in the catalogue
- **THEN** the contact is still created without a specialty and the row carries a message explaining it, not an error

#### Scenario: Near-name is a new account
- **WHEN** a row without CIF names "Clinica Tambre SL" and only "Clínica Tambre" exists
- **THEN** a new account is created (`created`), never a silent merge

#### Scenario: Unnormalisable phone is a row error
- **WHEN** a row's `Teléfono` cannot be normalised to E.164
- **THEN** that row is reported as `error` with the reason and the rest of the file is unaffected

### Requirement: Import OpenAPI documentation
Both import endpoints, the report schemas and their error codes SHALL be present in the exported `api-spec.yml` with no CI drift.

#### Scenario: Spec export in sync
- **WHEN** the OpenAPI exporter runs
- **THEN** `ai-specs/specs/api-spec.yml` contains `/products/import` and `/accounts/import`
