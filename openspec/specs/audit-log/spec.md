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
