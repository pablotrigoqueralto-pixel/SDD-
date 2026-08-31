# activity-api (delta)

A compact month-calendar feed for activities, scoped by role on the server.

## ADDED Requirements

### Requirement: Calendar feed
`GET /api/v1/activities/calendar` SHALL require authentication and accept `year` and `month` (validated; anything out of range is a 422 RFC 7807 problem) plus an optional `owner_id`. It SHALL return, without pagination, the month's activities as compact entries — `id`, `occurred_on` (Europe/Madrid local date), `occurred_time`, `status` (`planned` or `done`), activity type (`code`, `name`, `icon`), `account_id`, `account_name`, `owner_id`, `owner_name` — capped at 1000 entries with the uncapped `total` alongside. Cancelled activities SHALL be excluded.

#### Scenario: One request, one month
- **WHEN** a manager requests `year=2026&month=9`
- **THEN** the response contains every non-cancelled team activity whose occurrence date falls inside September 2026, with `total` equal to the number of entries when under the cap

#### Scenario: Invalid month
- **WHEN** a client requests `month=13`
- **THEN** the response is a 422 problem naming the parameter

#### Scenario: Cap with visible truncation
- **WHEN** the month holds more than 1000 activities in scope
- **THEN** the response carries exactly 1000 entries and a larger `total`

### Requirement: Calendar date semantics match the timeline
An activity SHALL appear on the Madrid-local date of its occurrence: `done_at` when the activity is done, `scheduled_at` otherwise — the same `occurred_at` rule the account timeline uses. Month bounds SHALL be half-open Madrid-local dates converted to UTC for the filter.

#### Scenario: Done on a different day than planned
- **WHEN** a visit scheduled for Monday was completed on Tuesday
- **THEN** the calendar entry's `occurred_on` is Tuesday and the entry's status is `done`

#### Scenario: Late-night boundary
- **WHEN** an activity's occurrence timestamp is 23:30 UTC on the last day of the month (00:30 on the 1st in Madrid summer time)
- **THEN** it appears in the following month

### Requirement: Calendar scoping by role
`admin`, `sales_manager` and `back_office` SHALL receive the whole team's month and MAY pass `owner_id` to narrow the feed to one rep. A `sales_rep` SHALL always receive only their own activities; a `sales_rep` passing an `owner_id` other than their own SHALL receive a 403 problem.

#### Scenario: Manager filters one rep
- **WHEN** a `sales_manager` requests the month with a rep's `owner_id`
- **THEN** only that rep's activities are returned

#### Scenario: Rep gets their own month
- **WHEN** a `sales_rep` requests the month without parameters while a colleague has activities in it
- **THEN** the colleague's activities are absent

#### Scenario: Rep cannot spy on a colleague
- **WHEN** a `sales_rep` requests the month with a colleague's `owner_id`
- **THEN** the response is a 403 problem and no entries are returned
