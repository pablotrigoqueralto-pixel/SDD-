# activity-api

## Purpose
REST endpoints for activities, the account timeline and the rep's day (Hoy) under the account visibility rule.

## Requirements

### Requirement: Create and read activities
`POST /api/v1/activities` SHALL accept `ActivityCreate { account_id, activity_type_id, status? (default done), scheduled_at? (default now), contact_ids?, duration_minutes?, outcome?, subject?, notes?, owner_id? (managers/admins only), next_action? }` from account writers (`sales_rep` in scope, `sales_manager`, `admin`; `back_office` → 403), return 201 `ActivityRead { id, account_id, account_name, activity_type_id, owner_id, owner_name, status, scheduled_at, done_at, duration_minutes, outcome, subject, notes, cancel_reason, contact_ids, contacts[{id, name}], next_activity_id, version, created_at, updated_at }` and record `activity.created`. `GET /api/v1/activities/{id}` SHALL return `ActivityRead` under the account's visibility (404 out of scope). `GET /api/v1/activities?account_id=&owner_id=&status=&activity_type_id=&from=&to=&sort=` SHALL return the paginated envelope, scoped like accounts.

#### Scenario: Rep records a visit in three fields
- **WHEN** a rep posts `{ account_id, activity_type_id: visit }`
- **THEN** the response is 201 with `status = done`, `owner_id` = the rep and `scheduled_at` within the last minute

#### Scenario: Rep sets another owner
- **WHEN** a rep posts an activity with `owner_id` of a colleague
- **THEN** the response is 403 `assignment_forbidden`

#### Scenario: Out-of-scope account
- **WHEN** a rep posts an activity for an account outside their scope
- **THEN** the response is 404 `not_found`

#### Scenario: Back office cannot write
- **WHEN** a `back_office` user posts an activity
- **THEN** the response is 403 `forbidden`

### Requirement: Update and lifecycle endpoints
`PATCH /api/v1/activities/{id}` (`If-Match`) SHALL accept `ActivityUpdate { activity_type_id?, contact_ids?, duration_minutes?, outcome?, subject?, notes? }` and never `status`; `POST /activities/{id}/complete` (`If-Match`, `{ done_at?, outcome?, notes?, duration_minutes?, next_action? }`), `POST /activities/{id}/cancel` (`If-Match`, `{ reason }`) and `POST /activities/{id}/reschedule` (`If-Match`, `{ scheduled_at }`) SHALL apply the aggregate transitions and record `activity.completed`, `activity.cancelled`, `activity.rescheduled` (before/after `scheduled_at`) respectively. Writers are the owner and managers; edit-window and transition errors map to 409.

#### Scenario: Complete with next action
- **WHEN** the owner posts `complete` with `outcome = positive` and a `next_action` for next Monday
- **THEN** the response is 200 with `status = done` and `next_activity_id` set, and both `activity.completed` and `activity.created` are audited

#### Scenario: Cancel requires a reason
- **WHEN** `cancel` is posted with an empty reason
- **THEN** the response is 422 `cancel_reason_required`

#### Scenario: Stale version
- **WHEN** `reschedule` is posted with an `If-Match` different from the current version
- **THEN** the response is 409 `conflict`

#### Scenario: Edit outside the window
- **WHEN** the owner patches the notes of a visit done 10 days ago
- **THEN** the response is 409 `activity_locked`

### Requirement: Account timeline
`GET /api/v1/accounts/{id}/timeline?kind=&activity_type_id=&status=&page=&page_size=` SHALL return, under the account's visibility, the paginated envelope of `TimelineEntryRead { id, kind: "activity", occurred_at, title, activity: ActivityRead }` ordered by `occurred_at` descending (`done_at` for done activities, `scheduled_at` otherwise). Unknown `kind` values SHALL be ignored by filters so later event kinds are additive.

#### Scenario: Timeline order
- **WHEN** an account has a visit done yesterday, a call planned tomorrow and a note done today
- **THEN** the entries come as call (tomorrow), note (today), visit (yesterday)

#### Scenario: Filter by status
- **WHEN** `status = planned` is requested
- **THEN** only planned activities are returned

### Requirement: Today endpoint
`GET /api/v1/me/today?user_id=` SHALL return `TodayRead { date, today: ActivityRead[], overdue: ActivityRead[], week: { done_by_type: { activity_type_id: count }, planned_remaining: count } }` for the signed-in user; `user_id` SHALL be accepted only from `sales_manager`, `admin` and `back_office` (403 otherwise). Day boundaries SHALL be computed in `Europe/Madrid`; `today` SHALL contain planned activities of the day ordered by time, `overdue` planned activities before today ordered oldest first, `week` counters from Monday to Sunday of the current week.

#### Scenario: Rep's day
- **WHEN** a rep has a planned visit today at 09:30, a planned call from last Monday and three visits done this week
- **THEN** `today` has the visit, `overdue` has the call and `week.done_by_type[visit] = 3`

#### Scenario: Manager views a rep
- **WHEN** a manager requests `?user_id=<rep>`
- **THEN** the payload is the rep's day; the same request by another rep is 403

#### Scenario: Midnight boundary
- **WHEN** an activity is planned at 23:30 Madrid time today
- **THEN** it appears in `today`, and one planned at 00:30 tomorrow does not

### Requirement: OpenAPI and audit conventions
Every endpoint SHALL be exported to `ai-specs/specs/api-spec.yml`, use RFC 7807 errors with the codes `invalid_activity_transition`, `activity_locked`, `contact_not_in_account`, `note_cannot_be_planned`, `cancel_reason_required`, `next_action_in_past`, and require `If-Match` on PATCH and lifecycle commands.

#### Scenario: Export is current
- **WHEN** `export_openapi` runs
- **THEN** `api-spec.yml` contains `/activities`, `/activities/{id}`, `/activities/{id}/complete`, `/activities/{id}/cancel`, `/activities/{id}/reschedule`, `/accounts/{id}/timeline`, `/me/today`
