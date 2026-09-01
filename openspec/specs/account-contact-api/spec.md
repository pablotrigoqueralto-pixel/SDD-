# account-contact-api

## Purpose
REST endpoints for accounts and contacts under the territory visibility rule: scoped lists and reads, creation with smart defaults, updates with optimistic locking, assignment, addresses, anonymisation and job titles.

## Requirements

### Requirement: Account list
`GET /api/v1/accounts` SHALL return the paginated envelope of `AccountSummaryRead { id, name, account_type_id, city, province_code, territory_id, territory_name, owner_id, owner_name, is_active, territory_mismatch, primary_contact_name, last_contact_at, next_activity_at, updated_at }` with filters `q` (case-insensitive contains on `name`, `city`; exact normalised match on `tax_id`), `account_type_id`, `territory_id`, `owner_id`, `division_id`, `is_active` (default `true`), `unassigned` (owner null), sorting `sort=name|city|updated_at|last_contact_at` (`-` prefix for descending, default `name`; nulls last), `page` and `page_size` (max 100). Visibility: `admin`, `sales_manager`, `back_office` see all; a `sales_rep` sees accounts they own or whose `territory_id` is in their territories and whose divisions of interest are empty or intersect their divisions. `AccountRead` SHALL carry the same two timestamps. Response time SHALL stay under 500 ms with 50 000 accounts.

#### Scenario: Rep list is scoped
- **WHEN** a rep of territory `Centro` / division `vascular` lists accounts and the database has an account in `Centro` with divisions `{vascular}`, one in `Centro` with `{neurology}`, one in `Norte` owned by the rep and one in `Norte` owned by someone else
- **THEN** the list contains exactly the first and the third accounts

#### Scenario: Search by tax id
- **WHEN** `q = "b-12345678"` is sent and an account has `tax_id = "B12345678"`
- **THEN** that account is returned

#### Scenario: Unassigned filter for managers
- **WHEN** a manager lists with `unassigned=true`
- **THEN** only accounts with `owner_id = null` are returned

#### Scenario: Sort by last contact
- **WHEN** `sort=last_contact_at` is requested and one account was never contacted
- **THEN** contacted accounts come first (oldest contact first) and the never-contacted account last

### Requirement: Create account
`POST /api/v1/accounts` SHALL accept `AccountCreate { name, account_type_id, province_code, street?, postal_code?, city?, tax_id?, phone?, email?, website?, customer_code?, notes?, division_ids?, brand_ids? }` from `sales_rep`, `sales_manager`, `back_office` and `admin`, apply the territory and owner defaults, return 201 `AccountRead` and record `account.created`.

#### Scenario: Rep creates with three fields
- **WHEN** a rep posts `{ name, account_type_id, province_code }`
- **THEN** the response is 201 with the derived `territory_id`, `owner_id` = rep, `version = 1` and an `account.created` audit event

#### Scenario: Duplicate tax id
- **WHEN** the posted `tax_id` already exists
- **THEN** the response is 409 `tax_id_already_exists` with `existing_account_id` in the problem body

### Requirement: Read and update account
`GET /api/v1/accounts/{id}` SHALL return `AccountRead` (summary fields plus every column, `phones[]`, `billing_notes`, `addresses[]`, `division_ids[]`, `brand_ids[]`, `version`) or 404 `not_found` when the account does not exist **or is outside the caller's scope**. `PATCH /api/v1/accounts/{id}` with `If-Match` SHALL accept `AccountUpdate` (every field optional, including `phones`, `billing_notes`, `division_ids`, `brand_ids`, `is_active`) from the owner rep, any rep with the account in scope, `sales_manager` and `admin`; `back_office` SHALL only change `tax_id`, `customer_code`, `street`, `postal_code`, `city`, `province_code`, `phones`, `email`, `website` and `billing_notes` — invoicing data and the accounting contact are administrative by nature and back office maintains them. `owner_id` and `territory_id` SHALL be rejected in PATCH with 403 `assignment_forbidden`. Updates SHALL record `account.updated` with field diffs (`account.activated` / `account.deactivated` when `is_active` changes); a changed phone list SHALL be diffed as the single field `phones`, never as the numbers themselves.

#### Scenario: Out-of-scope read
- **WHEN** a rep requests an account outside their territories that they do not own
- **THEN** the response is 404 `not_found`

#### Scenario: Back office edits notes
- **WHEN** a `back_office` user patches `notes`
- **THEN** the response is 403 `permission_denied`

#### Scenario: Back office maintains billing data
- **WHEN** a `back_office` user patches `billing_notes` and `phones`
- **THEN** the change is accepted and audited

#### Scenario: Stale version
- **WHEN** a PATCH is sent with an `If-Match` different from the current version
- **THEN** the response is 409 `concurrent_modification`

#### Scenario: Missing precondition
- **WHEN** a PATCH is sent without `If-Match`
- **THEN** the response is 428 `precondition_required`

### Requirement: Assignment
`PUT /api/v1/accounts/{id}/assignment` with `If-Match` SHALL accept `{ owner_id?, territory_id? }` from `sales_manager` and `admin` only. `owner_id` SHALL reference an active `sales_rep` (else 422 `owner_not_sales_rep`); `territory_id` an active territory. The event `account.assigned` SHALL record before/after of both fields. When `owner_id` changes to a user other than the caller, the new owner SHALL receive an `account_assigned` notification in the same transaction; assigning a centre to oneself SHALL notify nobody.

#### Scenario: Manager reassigns
- **WHEN** a manager assigns an account to another active rep
- **THEN** the response is 200 with the new `owner_id`, `version` incremented, `account.assigned` audited and the rep notified

#### Scenario: Manager takes it themselves
- **WHEN** a manager assigns the account to themselves
- **THEN** the assignment succeeds and no notification is created

#### Scenario: Rep attempts assignment
- **WHEN** a rep calls the assignment endpoint
- **THEN** the response is 403 `permission_denied`

### Requirement: Addresses
`PUT /api/v1/accounts/{id}/addresses` with `If-Match` SHALL replace the additional addresses with `AddressWrite[] { label, street, postal_code, city, province_code, notes? }` (max 10) for any writer of the account, return `AccountRead` and record `account.addresses_replaced` with before/after lists.

#### Scenario: Replace addresses
- **WHEN** a rep sends two addresses for an account that had one
- **THEN** the account has exactly those two addresses and the audit event lists the previous and the new addresses

### Requirement: Contacts of an account
`GET /api/v1/accounts/{id}/contacts` SHALL return `ContactRead[]` (primary first, then `last_name`, `first_name`; `include_inactive` defaults to false, `is_head_of_department=true` narrows to department heads) for visible accounts, appending personal-data access rows when required. `POST /api/v1/accounts/{id}/contacts` SHALL accept `ContactCreate { first_name, last_name, job_title_id?, specialty_id?, is_head_of_department?, email?, phones?, preferred_channel?, notes?, is_primary?, consent? }` from account writers, return 201 `ContactRead` and record `contact.created`.

#### Scenario: Create primary contact with consent
- **WHEN** a rep posts a contact with `is_primary = true` and `consent = { status: granted, at, source: verbal }`
- **THEN** the response is 201, the contact is primary, `consent_recorded_by` is the rep and events `contact.created` and `contact.consent_changed` exist

#### Scenario: Create with a specialty
- **WHEN** a rep posts a contact with a `specialty_id` from the catalogue
- **THEN** the response carries it and the global contacts list can filter by it

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
`GET /api/v1/job-titles` SHALL return the master (all rows, `is_active` included) for any authenticated role; `POST /api/v1/job-titles { name }` and `PATCH /api/v1/job-titles/{id} { name?, is_active? }` with `If-Match` SHALL be `admin` only, derive `code` from the name and record `job_title.created` / `job_title.updated`. A `POST` whose name resolves to the `code` of an existing title SHALL **reuse** that title — reactivating it when inactive and recording `job_title.reactivated` — and answer 201 with an `outcome` of `created`, `reused` or `reactivated`, instead of 409 `job_title_name_already_exists`.

#### Scenario: Admin adds a title
- **WHEN** an admin posts `{ "name": "Farmacia hospitalaria" }`
- **THEN** the response is 201 with `code = "farmacia_hospitalaria"`, `sort_order` after the last seeded title and `outcome = "created"`

#### Scenario: Existing title is reused
- **WHEN** an admin posts a name that resolves to the code of an existing active title
- **THEN** the response is 201 with that title and `outcome = "reused"`, and no second row is created

#### Scenario: Deactivated title comes back
- **WHEN** an admin posts a name resolving to the code of a deactivated title (for example "Jefe de servicio", deactivated by change 12)
- **THEN** the response is 201 with the title active again, `outcome = "reactivated"` and audit event `job_title.reactivated`

### Requirement: OpenAPI and shared conventions
Every endpoint in this capability SHALL be present in `ai-specs/specs/api-spec.yml` (exported from the app), use RFC 7807 errors with the codes listed in the design, and require `If-Match` on PATCH/PUT/POST actions.

#### Scenario: Export is current
- **WHEN** `export_openapi` runs
- **THEN** `api-spec.yml` contains `/accounts`, `/accounts/{id}`, `/accounts/{id}/assignment`, `/accounts/{id}/addresses`, `/accounts/{id}/contacts`, `/contacts/{id}`, `/contacts/{id}/anonymise`, `/job-titles`, `/job-titles/{id}`

### Requirement: Accounts import endpoint
`POST /api/v1/accounts/import` SHALL implement the dry-run/confirm flow of `import-api` for accounts with optionally embedded contacts. Account rows write through the existing account service, so creation defaults (territory from province, owner rules), validations (CIF, province, postal code, phone) and audit events apply exactly as in manual creation; back-office updates stay limited to the administrative fields and imports never rename an account. Embedded contacts are written by the importer itself with the same domain validation and `contact.*` audit events — the endpoint's role gate (admin/back office) is the authorisation, and the manual contact endpoints keep their account-writer rule unchanged.

#### Scenario: Same validation as the form
- **WHEN** an imported row carries an invalid province code
- **THEN** the row is an `error` with the same validation message the account form would show, and no account is written

### Requirement: Phone lists in payloads
Account and contact payloads SHALL carry `phones` as an ordered array of `{label, number, extension?, note?}`; sending the array SHALL replace the stored list in full, and omitting it SHALL leave the list untouched. Responses SHALL return the list in `sort_order`, the primary phone first. Summary payloads used by lists and cards SHALL expose the primary number as `primary_phone` (a plain string) and not the whole list.

#### Scenario: Replace the list
- **WHEN** a PATCH sends two phones for an account that had three
- **THEN** the response returns exactly those two in the order sent

#### Scenario: Omitted list untouched
- **WHEN** a PATCH sends only `city`
- **THEN** the stored phones are unchanged

#### Scenario: Primary phone in the list
- **WHEN** a centre with several phones appears in the account list
- **THEN** its summary carries `primary_phone` with the first number and no `phones` array

#### Scenario: Invalid number rejected as a whole
- **WHEN** one entry of the array carries an unnormalisable number
- **THEN** the response is 422 `phone_invalid` whose error field names the entry's position (`phones.1`) and nothing is persisted

### Requirement: Head of department in the contact API
Contact create and update SHALL accept `is_head_of_department`, contact payloads SHALL return it, and `GET /accounts/{id}/contacts` SHALL accept `is_head_of_department=true` to list only department heads.

#### Scenario: Set on creation
- **WHEN** a contact is created with `is_head_of_department = true`
- **THEN** the response carries the flag and the audit records the field

#### Scenario: Filter department heads
- **WHEN** the contacts of an account are requested with `is_head_of_department=true`
- **THEN** only contacts carrying the flag are returned

### Requirement: Global contacts list
`GET /api/v1/contacts` SHALL return `Page[ContactSummaryRead]` for any authenticated role, containing every contact whose **account is visible to the caller** — the account visibility rule applied through the contact, introducing no new permission concept. Each summary SHALL carry `id`, `first_name`, `last_name`, `account_id`, `account_name`, `job_title_id`, `specialty_id`, `is_head_of_department`, `primary_phone`, `email` and `is_active`. The default sort SHALL be last name then first name; `sort` SHALL also accept the account name. Pagination SHALL follow the shared `Page` conventions.

#### Scenario: Rep sees only their scope
- **WHEN** a `sales_rep` lists contacts while another territory holds contacts
- **THEN** only contacts of accounts in their scope are returned

#### Scenario: Staff see everything
- **WHEN** a `sales_manager`, `admin` or `back_office` lists contacts
- **THEN** contacts of every account are returned

#### Scenario: Summary shape
- **WHEN** a contact with a specialty, a job title and two phones appears in the list
- **THEN** its row carries the specialty and job title ids, the account name and only the primary phone

### Requirement: Cumulative contact filters
The contacts list SHALL accept `q` (matches first name, last name or the full name), repeatable `specialty_id`, repeatable `account_id`, `job_title_id`, `is_head_of_department` and `is_active`. Repeated values of the same filter SHALL combine with **OR**; different filters SHALL combine with **AND**. Unknown filter values SHALL yield an empty page, never an error.

#### Scenario: Two specialties add up
- **WHEN** the list is requested with two `specialty_id` values
- **THEN** contacts of either specialty are returned

#### Scenario: Specialty narrowed by centre
- **WHEN** the request carries two `specialty_id` values and one `account_id`
- **THEN** only contacts of that centre holding either specialty are returned

#### Scenario: Heads of department across centres
- **WHEN** the request carries `is_head_of_department=true`
- **THEN** only contacts with the tick are returned, from every visible centre

#### Scenario: Search by name
- **WHEN** the request carries `q=serrano`
- **THEN** contacts whose first or last name matches are returned, accent-insensitively

### Requirement: Specialties reference endpoint
`GET /api/v1/specialties` SHALL return the catalogue ordered by `sort_order` for any authenticated role, inactive entries included with `is_active = false` so historical references still resolve their names.

#### Scenario: Rep loads the catalogue
- **WHEN** a `sales_rep` requests the specialties
- **THEN** the twelve seeded entries are returned in order
