## ADDED Requirements

### Requirement: Account list
`GET /api/v1/accounts` SHALL return the paginated envelope of `AccountSummaryRead { id, name, account_type_id, city, province_code, territory_id, owner_id, is_active, territory_mismatch, primary_contact_name, updated_at }` with filters `q` (case-insensitive contains on `name`, `city`; exact normalised match on `tax_id`), `account_type_id`, `territory_id`, `owner_id`, `division_id`, `is_active` (default `true`), `unassigned` (owner null), sorting `sort=name|city|updated_at` (`-` prefix for descending, default `name`), `page` and `page_size` (max 100). Visibility: `admin`, `sales_manager`, `back_office` see all; a `sales_rep` sees accounts they own or whose `territory_id` is in their territories and whose divisions of interest are empty or intersect their divisions. Response time SHALL stay under 500 ms with 50 000 accounts.

#### Scenario: Rep list is scoped
- **WHEN** a rep of territory `Centro` / division `vascular` lists accounts and the database has an account in `Centro` with divisions `{vascular}`, one in `Centro` with `{neurology}`, one in `Norte` owned by the rep and one in `Norte` owned by someone else
- **THEN** the list contains exactly the first and the third accounts

#### Scenario: Search by tax id
- **WHEN** `q = "b-12345678"` is sent and an account has `tax_id = "B12345678"`
- **THEN** that account is returned

#### Scenario: Unassigned filter for managers
- **WHEN** a manager lists with `unassigned=true`
- **THEN** only accounts with `owner_id = null` are returned

### Requirement: Create account
`POST /api/v1/accounts` SHALL accept `AccountCreate { name, account_type_id, province_code, street?, postal_code?, city?, tax_id?, phone?, email?, website?, customer_code?, notes?, division_ids?, brand_ids? }` from `sales_rep`, `sales_manager`, `back_office` and `admin`, apply the territory and owner defaults, return 201 `AccountRead` and record `account.created`.

#### Scenario: Rep creates with three fields
- **WHEN** a rep posts `{ name, account_type_id, province_code }`
- **THEN** the response is 201 with the derived `territory_id`, `owner_id` = rep, `version = 1` and an `account.created` audit event

#### Scenario: Duplicate tax id
- **WHEN** the posted `tax_id` already exists
- **THEN** the response is 409 `tax_id_already_exists` with `existing_account_id` in the problem body

### Requirement: Read and update account
`GET /api/v1/accounts/{id}` SHALL return `AccountRead` (summary fields plus every column, `addresses[]`, `division_ids[]`, `brand_ids[]`, `version`) or 404 `not_found` when the account does not exist **or is outside the caller's scope**. `PATCH /api/v1/accounts/{id}` with `If-Match` SHALL accept `AccountUpdate` (every field optional, including `division_ids`, `brand_ids`, `is_active`) from the owner rep, any rep with the account in scope, `sales_manager` and `admin`; `back_office` SHALL only change `tax_id`, `customer_code`, `street`, `postal_code`, `city`, `province_code`, `phone`, `email`, `website`. `owner_id` and `territory_id` SHALL be rejected in PATCH with 403 `assignment_forbidden`. Updates SHALL record `account.updated` with field diffs (`account.activated` / `account.deactivated` when `is_active` changes).

#### Scenario: Out-of-scope read
- **WHEN** a rep requests an account outside their territories that they do not own
- **THEN** the response is 404 `not_found`

#### Scenario: Back office edits notes
- **WHEN** a `back_office` user patches `notes`
- **THEN** the response is 403 `permission_denied`

#### Scenario: Stale version
- **WHEN** a PATCH is sent with an `If-Match` different from the current version
- **THEN** the response is 409 `concurrent_modification`

#### Scenario: Missing precondition
- **WHEN** a PATCH is sent without `If-Match`
- **THEN** the response is 428 `precondition_required`

### Requirement: Assignment
`PUT /api/v1/accounts/{id}/assignment` with `If-Match` SHALL accept `{ owner_id?, territory_id? }` from `sales_manager` and `admin` only. `owner_id` SHALL reference an active `sales_rep` (else 422 `owner_not_sales_rep`); `territory_id` an active territory. The event `account.assigned` SHALL record before/after of both fields.

#### Scenario: Manager reassigns
- **WHEN** a manager assigns an account to another active rep
- **THEN** the response is 200 with the new `owner_id`, `version` incremented and `account.assigned` audited

#### Scenario: Rep attempts assignment
- **WHEN** a rep calls the assignment endpoint
- **THEN** the response is 403 `permission_denied`

### Requirement: Addresses
`PUT /api/v1/accounts/{id}/addresses` with `If-Match` SHALL replace the additional addresses with `AddressWrite[] { label, street, postal_code, city, province_code, notes? }` (max 10) for any writer of the account, return `AccountRead` and record `account.addresses_replaced` with before/after lists.

#### Scenario: Replace addresses
- **WHEN** a rep sends two addresses for an account that had one
- **THEN** the account has exactly those two addresses and the audit event lists the previous and the new addresses

### Requirement: Contacts of an account
`GET /api/v1/accounts/{id}/contacts` SHALL return `ContactRead[]` (primary first, then `last_name`, `first_name`; `include_inactive` query defaults to false) for visible accounts, appending personal-data access rows when required. `POST /api/v1/accounts/{id}/contacts` SHALL accept `ContactCreate { first_name, last_name, job_title_id?, division_id?, email?, mobile?, landline?, preferred_channel?, notes?, is_primary?, consent? }` from account writers, return 201 `ContactRead` and record `contact.created`.

#### Scenario: Create primary contact with consent
- **WHEN** a rep posts a contact with `is_primary = true` and `consent = { status: granted, at, source: verbal }`
- **THEN** the response is 201, the contact is primary, `consent_recorded_by` is the rep and events `contact.created` and `contact.consent_changed` exist

#### Scenario: Contacts of an out-of-scope account
- **WHEN** a rep lists contacts of an account outside their scope
- **THEN** the response is 404 `not_found`

### Requirement: Contact detail, update and anonymisation
`GET /api/v1/contacts/{id}` SHALL return `ContactRead` (with `account_id`, `account_name`) under the account's visibility rule. `PATCH /api/v1/contacts/{id}` with `If-Match` SHALL accept `ContactUpdate` (all fields optional, `consent` as a whole record) from account writers and record `contact.updated` (plus `contact.primary_changed`, `contact.consent_changed` when applicable). `POST /api/v1/contacts/{id}/anonymise` with `If-Match` SHALL be allowed to `sales_manager` and `admin`, return 200 with the anonymised `ContactRead` and record `contact.anonymised`.

#### Scenario: Promote to primary
- **WHEN** a rep patches `{ is_primary: true }` on a non-primary contact
- **THEN** the previous primary is demoted and both contacts' versions are incremented

#### Scenario: Rep anonymises
- **WHEN** a rep calls the anonymise endpoint
- **THEN** the response is 403 `permission_denied`

#### Scenario: Manager anonymises
- **WHEN** a manager anonymises a contact
- **THEN** the response is 200 with `first_name = "Contacto"`, `email = null`, `anonymised_at` set

### Requirement: Job titles endpoints
`GET /api/v1/job-titles` SHALL return the master (all rows, `is_active` included) for any authenticated role; `POST /api/v1/job-titles { name }` and `PATCH /api/v1/job-titles/{id} { name?, is_active? }` with `If-Match` SHALL be `admin` only, derive `code` from the name, reject duplicate names with 409 `job_title_name_already_exists`, and record `job_title.created` / `job_title.updated`.

#### Scenario: Admin adds a title
- **WHEN** an admin posts `{ "name": "Farmacia hospitalaria" }`
- **THEN** the response is 201 with `code = "farmacia_hospitalaria"` and `sort_order` after the last seeded title

### Requirement: OpenAPI and shared conventions
Every endpoint in this capability SHALL be present in `ai-specs/specs/api-spec.yml` (exported from the app), use RFC 7807 errors with the codes listed in the design, and require `If-Match` on PATCH/PUT/POST actions.

#### Scenario: Export is current
- **WHEN** `export_openapi` runs
- **THEN** `api-spec.yml` contains `/accounts`, `/accounts/{id}`, `/accounts/{id}/assignment`, `/accounts/{id}/addresses`, `/accounts/{id}/contacts`, `/contacts/{id}`, `/contacts/{id}/anonymise`, `/job-titles`, `/job-titles/{id}`
