# account-contact-api (delta)

A global contacts list with cumulative filters, and the specialty in contact payloads.

## ADDED Requirements

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

## MODIFIED Requirements

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
