## MODIFIED Requirements

### Requirement: Account record
The system SHALL persist accounts ("centros") in an `accounts` table with `id` (UUIDv7), `name` (required — identifies the centre in every list, search and report), `account_type_id` (required — drives tender defaults in opportunities and the type filter in dashboards), `province_code` (required — resolves territory and owner defaults and feeds territory reports), optional primary address `street`, `postal_code` (5 digits), `city`, optional `tax_id` (Spanish NIF/CIF/NIE, normalised to upper case without spaces, unique when present — matches Sage customers and prevents duplicates), `customer_code` (Sage reference for quotes), `phone`, `email`, `website`, `notes`, `territory_id` (nullable), `owner_id` (nullable, references a user), `last_contact_at` and `next_activity_at` (nullable, maintained by the activity service — feed the list column "Último contacto", the sort and the coming "sin visitar" alert; never written through the API), `is_active`, `version`, `created_at`, `updated_at`. Accounts SHALL link to zero or more divisions of interest (`account_divisions`) and zero or more brands in use (`account_brands`).

#### Scenario: Minimum account
- **WHEN** an account is created with only `name`, `account_type_id` and `province_code`
- **THEN** it is persisted with every optional field null (including `last_contact_at` and `next_activity_at`), `is_active = true` and `version = 1`

#### Scenario: Invalid tax id
- **WHEN** an account is created with `tax_id = "B1234567X"` (wrong check digit)
- **THEN** a validation error with code `tax_id_invalid` is raised and nothing is persisted

#### Scenario: Duplicate tax id
- **WHEN** an account is created with a `tax_id` that already exists (case-insensitive, ignoring spaces and hyphens)
- **THEN** a conflict error `tax_id_already_exists` referencing the existing account id is raised

#### Scenario: Invalid postal code or phone
- **WHEN** `postal_code` is not five digits or `phone` cannot be normalised to E.164 with the `+34` default
- **THEN** validation errors `postal_code_invalid` / `phone_invalid` are raised naming the field

#### Scenario: Summary columns are read-only
- **WHEN** a PATCH sends `last_contact_at`
- **THEN** the field is ignored and the stored value is unchanged
