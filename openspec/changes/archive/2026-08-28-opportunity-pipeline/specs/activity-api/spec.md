## MODIFIED Requirements

### Requirement: Create and read activities
`POST /api/v1/activities` SHALL accept `ActivityCreate { account_id, activity_type_id, status? (default done), scheduled_at? (default now), opportunity_id?, contact_ids?, duration_minutes?, outcome?, subject?, notes?, owner_id? (managers/admins only), next_action? }` from account writers (`sales_rep` in scope, `sales_manager`, `admin`; `back_office` → 403), return 201 `ActivityRead { id, account_id, account_name, activity_type_id, owner_id, owner_name, status, scheduled_at, done_at, duration_minutes, outcome, subject, notes, cancel_reason, opportunity_id, opportunity_name, contact_ids, contacts[{id, name}], next_activity_id, version, created_at, updated_at }` and record `activity.created`. `GET /api/v1/activities/{id}` SHALL return `ActivityRead` under the account's visibility (404 out of scope). `GET /api/v1/activities?account_id=&opportunity_id=&owner_id=&status=&activity_type_id=&from=&to=&sort=` SHALL return the paginated envelope, scoped like accounts. A next action created from an activity SHALL inherit its `opportunity_id`.

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

#### Scenario: Activity linked to an opportunity
- **WHEN** a rep posts `{ account_id, activity_type_id: call, opportunity_id }` of the same account
- **THEN** the response is 201 with `opportunity_name` filled and `GET /activities?opportunity_id=` lists it; an opportunity of another account yields 422 `opportunity_not_in_account`

### Requirement: Account timeline
`GET /api/v1/accounts/{id}/timeline?kind=&activity_type_id=&status=&page=&page_size=` SHALL return, under the account's visibility, the paginated envelope of `TimelineEntryRead { id, kind: "activity" | "opportunity_stage" | "opportunity_closed", occurred_at, title, activity?: ActivityRead, stage_change?: StageChangeRead { opportunity_id, opportunity_name, from_stage_name, to_stage_name, actor_name, amount } }` ordered by `occurred_at` descending (`done_at` for done activities, `scheduled_at` otherwise, the history timestamp for stage entries). Unknown `kind` values SHALL be ignored by filters so later event kinds are additive.

#### Scenario: Timeline order
- **WHEN** an account has a visit done yesterday, a call planned tomorrow and a note done today
- **THEN** the entries come as call (tomorrow), note (today), visit (yesterday)

#### Scenario: Filter by status
- **WHEN** `status = planned` is requested
- **THEN** only planned activities are returned

#### Scenario: Stage changes in the timeline
- **WHEN** an opportunity of the account was moved to Demo today and won yesterday afternoon
- **THEN** the timeline contains an `opportunity_stage` entry titled "Oportunidad → Demo" and an `opportunity_closed` entry "Ganada · 24.000,00 €", and `kind=activity` excludes both

### Requirement: Today endpoint
`GET /api/v1/me/today?user_id=` SHALL return `TodayRead { date, today: ActivityRead[], overdue: ActivityRead[], week: { done_by_type: { activity_type_id: count }, planned_remaining: count }, tenders_due: OpportunitySummaryRead[], at_risk: OpportunitySummaryRead[] }` for the signed-in user; `user_id` SHALL be accepted only from `sales_manager`, `admin` and `back_office` (403 otherwise). Day boundaries SHALL be computed in `Europe/Madrid`; `today` SHALL contain planned activities of the day ordered by time, `overdue` planned activities before today ordered oldest first, `week` counters from Monday to Sunday of the current week, `tenders_due` the user's open tender opportunities with `tender_deadline` ≤ today + 7 days (overdue first) and `at_risk` their at-risk opportunities (oldest first).

#### Scenario: Rep's day
- **WHEN** a rep has a planned visit today at 09:30, a planned call from last Monday and three visits done this week
- **THEN** `today` has the visit, `overdue` has the call and `week.done_by_type[visit] = 3`

#### Scenario: Manager views a rep
- **WHEN** a manager requests `?user_id=<rep>`
- **THEN** the payload is the rep's day; the same request by another rep is 403

#### Scenario: Midnight boundary
- **WHEN** an activity is planned at 23:30 Madrid time today
- **THEN** it appears in `today`, and one planned at 00:30 tomorrow does not

#### Scenario: Tenders and at-risk blocks
- **WHEN** the rep owns a tender opportunity due in 5 days, another due in 20 days and a consumables opportunity at risk
- **THEN** `tenders_due` has only the first and `at_risk` has the consumables one
