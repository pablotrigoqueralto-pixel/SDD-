# audit-log

## Purpose
Append-only audit trail recorded from the unit of work, readable by administrators.

## Requirements

### Requirement: Append-only audit log
The system SHALL persist every audited mutation in an `audit_log` table with `id`, `occurred_at`, `actor_id` (nullable for system actions), `entity_type`, `entity_id`, `action`, `changes` (JSON map of field → `{ "before", "after" }`), `trace_id`. Rows SHALL never be updated or deleted by the application; the application database role SHALL have only `INSERT` and `SELECT` on the table.

#### Scenario: Mutation writes an audit row in the same transaction
- **WHEN** an application service mutates an audited aggregate and commits the unit of work
- **THEN** exactly one audit row per recorded event exists with the actor, entity, action and field diff, and if the transaction rolls back no audit row remains

#### Scenario: Update attempt is rejected by the database
- **WHEN** an `UPDATE` or `DELETE` is executed on `audit_log` with the application role
- **THEN** PostgreSQL raises a permission error

#### Scenario: Sensitive fields are redacted
- **WHEN** a change involves `password_hash` or a refresh token hash
- **THEN** the field appears in `changes` with `before`/`after` set to `"[redacted]"`

### Requirement: Audit events in this change
The following events SHALL be recorded: `user.created`, `user.updated`, `user.scope_changed`, `user.password_changed`, `user.password_reset`, `user.deactivated`, `user.activated`, `territory.created`, `territory.updated`, `auth.login_succeeded`, `auth.login_failed`, `auth.locked_out`, `auth.logout`.

#### Scenario: Login failure audited without personal data leakage
- **WHEN** a login fails for an email
- **THEN** an `auth.login_failed` row is written with `entity_type = "user"`, `entity_id` = the user id when the email matches a user (otherwise null), and the IP address in `changes.ip`; the password is never stored

### Requirement: Admin reads the audit log
`GET /api/v1/audit-log` SHALL be readable by `admin` only, paginated, sorted by `occurred_at` descending, with filters `entity_type`, `entity_id`, `actor_id`, `action`, `from`, `to`.

#### Scenario: Admin filters by entity
- **WHEN** an admin calls `GET /api/v1/audit-log?entity_type=user&entity_id=<id>`
- **THEN** the response is 200 with that user's events newest first, each including the actor's `full_name`

#### Scenario: Non-admin access
- **WHEN** any other role calls `GET /api/v1/audit-log`
- **THEN** the response is 403 with code `forbidden`

### Requirement: Reference data audit events
The following events SHALL be recorded with field diffs: `brand.created`, `brand.updated`, `brand.activated`, `brand.deactivated`, `loss_reason.created`, `loss_reason.updated`, `pipeline.updated`, `pipeline_stage.updated`, `pipeline_stages.reordered` (changes `{ "order": { "before": [stage ids], "after": [stage ids] } }`).

#### Scenario: Reorder is audited
- **WHEN** an admin reorders the stages of a pipeline
- **THEN** one `pipeline_stages.reordered` row exists with `entity_type = "pipeline"`, the pipeline id and the before/after id lists

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

### Requirement: Activity audit events
The following events SHALL be recorded in the same transaction as the mutation: `activity.created` (field snapshot), `activity.updated` (field diffs), `activity.completed` (`done_at`, `outcome`), `activity.cancelled` (`cancel_reason`), `activity.rescheduled` (`scheduled_at` before/after). A next action created by `complete` SHALL produce its own `activity.created` event.

#### Scenario: Reschedule audited
- **WHEN** a planned call is moved from Monday to Wednesday
- **THEN** one `activity.rescheduled` row exists with `changes.scheduled_at = { before: Monday, after: Wednesday }`
