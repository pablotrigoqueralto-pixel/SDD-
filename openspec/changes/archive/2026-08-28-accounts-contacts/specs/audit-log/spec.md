## ADDED Requirements

### Requirement: Account and contact audit events
The following events SHALL be recorded with field diffs in the same transaction as the mutation: `account.created`, `account.updated`, `account.activated`, `account.deactivated`, `account.assigned` (before/after `owner_id` and `territory_id`), `account.addresses_replaced` (before/after address lists), `contact.created`, `contact.updated`, `contact.primary_changed` (previous and new primary ids), `contact.consent_changed` (before/after consent record), `contact.anonymised` (cleared field names only), `job_title.created`, `job_title.updated`. Personal data of anonymised contacts SHALL NOT be recoverable from the audit log.

#### Scenario: Assignment audited
- **WHEN** a manager reassigns an account from rep A to rep B
- **THEN** one `account.assigned` row exists with `entity_type = "account"` and `changes.owner_id = { before: A, after: B }`

#### Scenario: Anonymisation leaves no values
- **WHEN** a contact with email `x@y.es` is anonymised
- **THEN** no audit row for that contact created by the anonymisation contains the string `x@y.es`

### Requirement: Personal data access log
Reads of contact personal data by users other than the account owner, `sales_manager` or `admin` SHALL append rows to `personal_data_access_log` (user, contact, timestamp, trace id); the application role SHALL only be able to INSERT into it. Admins SHALL be able to query it through `GET /api/v1/audit-log/personal-data-access?contact_id=&user_id=&from=&to=` (paginated, newest first).

#### Scenario: Admin lists accesses to a contact
- **WHEN** an admin queries the access log for a contact read twice by a back-office user
- **THEN** two rows are returned with the back-office user id and timestamps
