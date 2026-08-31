# account-contact-api (delta)

Phone lists, the billing note and the head-of-department flag reach the API; back office's administrative scope moves with them.

## MODIFIED Requirements

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

## ADDED Requirements

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
