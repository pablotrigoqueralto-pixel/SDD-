# account-model (delta)

The single `phone` column becomes a labelled phone list, and accounts gain the free-text billing/accounting note.

## MODIFIED Requirements

### Requirement: Account record
The system SHALL persist accounts ("centros") in an `accounts` table with `id` (UUIDv7), `name` (required — identifies the centre in every list, search and report), `account_type_id` (required — drives tender defaults in opportunities and the type filter in dashboards), `province_code` (required — resolves territory and owner defaults and feeds territory reports), optional primary address `street`, `postal_code` (5 digits), `city`, optional `tax_id` (Spanish NIF/CIF/NIE, normalised to upper case without spaces, unique when present — matches Sage customers and prevents duplicates), `customer_code` (Sage reference for quotes), `email`, `website`, `notes`, `billing_notes` (free text — invoicing data and the accounting contact, written and explained in prose because every hospital invoices differently), `territory_id` (nullable), `owner_id` (nullable, references a user), `last_contact_at` and `next_activity_at` (nullable, maintained by the activity service — feed the list column "Último contacto", the sort and the coming "sin visitar" alert; never written through the API), `is_active`, `version`, `created_at`, `updated_at`. Telephone numbers SHALL live in the `account_phones` child collection, not in a column. Accounts SHALL link to zero or more divisions of interest (`account_divisions`) and zero or more brands in use (`account_brands`).

#### Scenario: Minimum account
- **WHEN** an account is created with only `name`, `account_type_id` and `province_code`
- **THEN** it is persisted with every optional field null (including `last_contact_at`, `next_activity_at` and `billing_notes`), no phone rows, `is_active = true` and `version = 1`

#### Scenario: Invalid tax id
- **WHEN** an account is created with `tax_id = "B1234567X"` (wrong check digit)
- **THEN** a validation error with code `tax_id_invalid` is raised and nothing is persisted

#### Scenario: Duplicate tax id
- **WHEN** an account is created with a `tax_id` that already exists (case-insensitive, ignoring spaces and hyphens)
- **THEN** a conflict error `tax_id_already_exists` referencing the existing account id is raised

#### Scenario: Invalid postal code or phone
- **WHEN** `postal_code` is not five digits, or a phone in the list cannot be normalised to E.164 with the `+34` default
- **THEN** validation errors `postal_code_invalid` / `phone_invalid` are raised naming the field

#### Scenario: Summary columns are read-only
- **WHEN** a PATCH sends `last_contact_at`
- **THEN** the field is ignored and the stored value is unchanged

## ADDED Requirements

### Requirement: Account phone list
The system SHALL persist account telephone numbers in an `account_phones` table with `id`, `account_id` (cascade delete), `label` (required, free text — suggestions offered by the UI: Principal, Secretaría, Servicio, Consulta, Despacho, Extensión, Móvil, Fax), `number` (required, normalised to E.164 with the `+34` default exactly as the old column was), optional `extension` (digits, for switchboards), optional `note`, and `sort_order`. An account MAY hold any number of phones. The entry with the lowest `sort_order` SHALL be the primary one and is what lists, cards, importers and reports read. Saving an account SHALL replace the whole list atomically with what the caller sent. The same `label` and `number` SHALL NOT repeat within one account.

#### Scenario: Several labelled phones
- **WHEN** a centre is saved with "Centralita +34915550000", "Secretaría +34915550001 ext. 4021" and "Servicio de vascular +34915550002"
- **THEN** all three persist in order, the first is the primary one, and the extension is stored in its own field

#### Scenario: Extension is not part of the number
- **WHEN** a phone is saved with number "915550001" and extension "4021"
- **THEN** the number normalises to "+34915550001" and the extension stays "4021" — a number containing "ext" text SHALL be rejected with `phone_invalid`

#### Scenario: Replacing the list
- **WHEN** an account with three phones is saved with a list of one
- **THEN** the other two rows are deleted in the same transaction

#### Scenario: Duplicate entry rejected
- **WHEN** the same label and number are sent twice in one list
- **THEN** a validation error naming the field is raised and nothing is persisted

#### Scenario: Deleting the account
- **WHEN** an account row is deleted
- **THEN** its phone rows are removed by the cascade

### Requirement: Phone and head-of-department migration
The migration introducing the phone lists SHALL move every existing value without loss: `accounts.phone` becomes that account's first phone labelled "Principal", `contacts.mobile` becomes "Móvil" and `contacts.landline` becomes "Fijo", skipping nulls and blanks; the old columns are then dropped. It SHALL also add `accounts.billing_notes` and `contacts.is_head_of_department`, set that flag for every contact holding the "Jefe de servicio" job title while clearing their `job_title_id`, and deactivate that job-title row instead of deleting it. The downgrade SHALL restore the dropped columns from each owner's first phone and reactivate the job title, and its docstring SHALL state plainly that phones beyond the first are lost.

#### Scenario: Existing values survive
- **WHEN** the migration runs over a database with accounts and contacts carrying phones
- **THEN** every non-blank value exists as a phone row with its label, and no account or contact loses its number

#### Scenario: Job title converted
- **WHEN** a contact held the "Jefe de servicio" job title
- **THEN** after the migration the contact has `is_head_of_department = true` and no job title, and the catalogue row is inactive but still present

#### Scenario: Anonymised contacts stay clean
- **WHEN** a contact was anonymised before the migration (null phone columns)
- **THEN** no phone rows are created for them
