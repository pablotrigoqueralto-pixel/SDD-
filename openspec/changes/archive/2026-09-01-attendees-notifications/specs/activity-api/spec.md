# activity-api (delta)

Attendees in the payloads, "Hoy" and the calendar widened to what you attend, and a date range on the calendar feed.

## MODIFIED Requirements

### Requirement: Create and read activities
`POST /api/v1/activities` SHALL accept `ActivityCreate { account_id, activity_type_id, status? (default done), scheduled_at? (default now), opportunity_id?, contact_ids?, attendee_ids?, duration_minutes?, outcome?, subject?, notes?, owner_id? (managers/admins only), next_action? }` from account writers (`sales_rep` in scope, `sales_manager`, `admin`; `back_office` → 403), return 201 `ActivityRead { id, account_id, account_name, activity_type_id, owner_id, owner_name, status, scheduled_at, done_at, duration_minutes, outcome, subject, notes, cancel_reason, opportunity_id, opportunity_name, contact_ids, contacts[{id, name}], attendee_ids, attendees[{id, name}], is_attendee, next_activity_id, version, created_at, updated_at }` and record `activity.created`. `GET /api/v1/activities/{id}` SHALL return `ActivityRead` under the account's visibility (404 out of scope). `GET /api/v1/activities?account_id=&opportunity_id=&owner_id=&status=&activity_type_id=&from=&to=&sort=` SHALL return the paginated envelope, scoped like accounts. A next action created from an activity SHALL inherit its `opportunity_id`. Every attendee SHALL be able to see the activity's account (else 422 `attendee_out_of_scope`), so an invitation can never become a way into another territory.

#### Scenario: Rep records a visit in three fields
- **WHEN** a rep posts `{ account_id, activity_type_id: visit }`
- **THEN** the response is 201 with `status = done`, `owner_id` = the rep, `attendee_ids = []` and `scheduled_at` within the last minute

#### Scenario: Rep sets another owner
- **WHEN** a rep posts an activity with `owner_id` of a colleague
- **THEN** the response is 403 `assignment_forbidden`

#### Scenario: Rep invites a colleague
- **WHEN** a rep posts an activity with `attendee_ids` of a colleague who can see the centre
- **THEN** the response is 201 with that colleague in `attendees`, and the colleague is notified

#### Scenario: Attendee outside the centre's scope
- **WHEN** `attendee_ids` includes a rep whose territory does not cover the centre
- **THEN** the response is 422 `attendee_out_of_scope`

#### Scenario: Out-of-scope account
- **WHEN** a rep posts an activity for an account outside their scope
- **THEN** the response is 404 `not_found`

#### Scenario: Back office cannot write
- **WHEN** a `back_office` user posts an activity
- **THEN** the response is 403 `forbidden`

#### Scenario: Activity linked to an opportunity
- **WHEN** a rep posts `{ account_id, activity_type_id: call, opportunity_id }` of the same account
- **THEN** the response is 201 with `opportunity_name` filled and `GET /activities?opportunity_id=` lists it; an opportunity of another account yields 422 `opportunity_not_in_account`

### Requirement: Today endpoint
`GET /api/v1/me/today?user_id=` SHALL return `TodayRead { date, today: ActivityRead[], overdue: ActivityRead[], week: { done_by_type: { activity_type_id: count }, planned_remaining: count }, tenders_due: OpportunitySummaryRead[], at_risk: OpportunitySummaryRead[] }` for the signed-in user; `user_id` SHALL be accepted only from `sales_manager`, `admin` and `back_office` (403 otherwise). Day boundaries SHALL be computed in `Europe/Madrid`; `today` SHALL contain planned activities of the day ordered by time, `overdue` planned activities before today ordered oldest first, `week` counters from Monday to Sunday of the current week, `tenders_due` the user's open tender opportunities with `tender_deadline` ≤ today + 7 days (overdue first) and `at_risk` their at-risk opportunities (oldest first).

`today` and `overdue` SHALL contain the activities the user **owns or attends**, each carrying `is_attendee` so the client can mark the invited ones. The `week` counters SHALL keep counting only what the user **completed**, which only an owner can do: attending changes what you see, not what you achieved.

#### Scenario: Rep's day
- **WHEN** a rep has a planned visit today at 09:30, a planned call from last Monday and three visits done this week
- **THEN** `today` has the visit, `overdue` has the call and `week.done_by_type[visit] = 3`

#### Scenario: Invited to a colleague's visit
- **WHEN** a rep is an attendee of a visit planned today and owned by a colleague
- **THEN** it appears in their `today` with `is_attendee = true`, and their weekly counters are unchanged

#### Scenario: Manager views a rep
- **WHEN** a manager requests `?user_id=<rep>`
- **THEN** the payload is the rep's day; the same request by another rep is 403

#### Scenario: Midnight boundary
- **WHEN** an activity is planned at 23:30 Madrid time today
- **THEN** it appears in `today`, and one planned at 00:30 tomorrow does not

#### Scenario: Tenders and at-risk blocks
- **WHEN** the rep owns a tender opportunity due in 5 days, another due in 20 days and a consumables opportunity at risk
- **THEN** `tenders_due` has only the first and `at_risk` has the consumables one

### Requirement: Calendar feed
`GET /api/v1/activities/calendar` SHALL require authentication and accept **either** `year` and `month` **or** `from` and `to` (inclusive Madrid-local dates) — never both, and a range longer than 92 days SHALL answer 422 `range_too_long` — plus an optional `owner_id`. It SHALL return, without pagination, the matching activities as compact entries — `id`, `occurred_on` (Europe/Madrid local date), `occurred_time`, `status` (`planned` or `done`), activity type (`code`, `name`, `icon`), `account_id`, `account_name`, `owner_id`, `owner_name`, `is_attendee` — capped at 1000 entries with the uncapped `total` alongside. Cancelled activities SHALL be excluded. The feed SHALL include the activities the caller **owns or attends** when it is not narrowed to another rep.

#### Scenario: One request, one month
- **WHEN** a manager requests `year=2026&month=9`
- **THEN** the response contains every non-cancelled team activity whose occurrence date falls inside September 2026, with `total` equal to the number of entries when under the cap

#### Scenario: A date range instead of a month
- **WHEN** a manager requests `from=2026-09-01&to=2026-09-15`
- **THEN** the response contains the activities occurring in that inclusive range

#### Scenario: Both windows at once
- **WHEN** a request carries `year`, `month` and `from`
- **THEN** the response is 422 naming the conflicting parameters

#### Scenario: Range too long
- **WHEN** a request asks for 200 days
- **THEN** the response is 422 `range_too_long`

#### Scenario: Invalid month
- **WHEN** a client requests `month=13`
- **THEN** the response is a 422 problem naming the parameter

#### Scenario: Cap with visible truncation
- **WHEN** the month holds more than 1000 activities in scope
- **THEN** the response carries exactly 1000 entries and a larger `total`

### Requirement: Calendar scoping by role
`admin`, `sales_manager` and `back_office` SHALL receive the whole team's month and MAY pass `owner_id` to narrow the feed to one rep. A `sales_rep` SHALL always receive only their own activities — **those they own and those they attend** — and a `sales_rep` passing an `owner_id` other than their own SHALL receive a 403 problem.

#### Scenario: Manager filters one rep
- **WHEN** a `sales_manager` requests the month with a rep's `owner_id`
- **THEN** only that rep's activities are returned

#### Scenario: Rep gets their own month
- **WHEN** a `sales_rep` requests the month without parameters while a colleague has activities in it
- **THEN** the colleague's activities are absent, except any the rep attends, which carry `is_attendee = true`
