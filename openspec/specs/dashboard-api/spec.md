# dashboard-api

## Purpose
The read-only reporting endpoint: won revenue with previous-period comparison, conversion, weighted forecast and open pipeline by stage, breakdowns by division and rep, activity metrics and neglected accounts — Madrid-calendar periods, server-side role scoping, 500 ms budget.

## Requirements

### Requirement: Dashboard endpoint
`GET /api/v1/dashboard` SHALL require authentication and accept a single query parameter `period` with values `month`, `quarter` or `year` (default `month`); any other value SHALL return a 422 RFC 7807 error. The response SHALL contain, in one payload: `period` echo with the resolved date bounds, `summary` (won, conversion, weighted forecast, open pipeline total), `pipeline_by_stage`, `by_division`, `by_rep` (a list for full-scope viewers, null for a `sales_rep`), `activity` and `neglected_accounts`. The endpoint SHALL be read-only: it performs no writes and records no audit events. Every monetary field SHALL be a two-decimal string following the established Price pattern, computed with decimal arithmetic and ROUND_HALF_UP.

#### Scenario: Default period
- **WHEN** an authenticated user calls `GET /api/v1/dashboard` without parameters
- **THEN** the response is 200 with the current-month panel and the echoed bounds of the month in the Europe/Madrid calendar

#### Scenario: Invalid period
- **WHEN** a client calls `GET /api/v1/dashboard?period=week`
- **THEN** the response is a 422 RFC 7807 problem detailing the allowed values

#### Scenario: Unauthenticated
- **WHEN** an anonymous client calls the endpoint
- **THEN** the response is 401

### Requirement: Period presets and previous-period comparison
Periods SHALL be computed on the Europe/Madrid calendar as half-open ranges: `month` = current calendar month, `quarter` = current calendar quarter, `year` = January 1st through today (YTD). Each period SHALL have a previous equivalent — previous calendar month, previous calendar quarter, and for `year` the previous year through the same date — used for the comparison deltas on won and conversion. Timestamp filters (`won_at`, `lost_at`, `done_at`) SHALL compare against the UTC conversion of the Madrid bounds; `expected_close_date` SHALL compare against the Madrid-local dates.

#### Scenario: Month boundaries in Madrid time
- **WHEN** an opportunity was won at 23:30 UTC on the last day of the previous month (00:30 on the 1st in Madrid, UTC+1)
- **THEN** it counts in the current month, not the previous one

#### Scenario: YTD compares to the same fraction of last year
- **WHEN** `period=year` is requested on 31 August
- **THEN** the previous-period figures cover 1 January to 31 August of the previous year, not the full year

### Requirement: KPI definitions
`summary.won` SHALL be the sum of `won_amount` and the count of opportunities with won status and `won_at` in the period, with the previous-period value alongside. `summary.conversion` SHALL be won count divided by closed count (won plus lost, by `won_at`/`lost_at` in the period), carrying the won and closed counts, and SHALL be null when nothing closed in the period; the previous-period ratio is included. `summary.forecast` SHALL be the sum of `amount × stage probability / 100` over open opportunities whose `expected_close_date` falls inside the selected period, with no previous-period delta. `pipeline_by_stage` SHALL be a snapshot of now: open opportunities grouped by stage ordered by stage `sort_order`, each with amount sum and count, plus the overall open total in `summary.open_pipeline`, with no period filter and no delta.

#### Scenario: Weighted forecast
- **WHEN** two open opportunities close inside the period: 10000.00 at a 40% stage and 5000.00 at a 10% stage
- **THEN** `summary.forecast` is "4500.00"

#### Scenario: Conversion with no closed opportunities
- **WHEN** nothing was won or lost in the period
- **THEN** `summary.conversion.rate` is null and the counts are zero — never a fabricated 0%

#### Scenario: Won excludes lost and open
- **WHEN** the period contains one won opportunity (won_amount 2000.00), one lost and one still open
- **THEN** `summary.won` is "2000.00" with count 1, and conversion is one of two closed

### Requirement: Breakdowns by division and by rep
`by_division` SHALL group the summary KPIs by `opportunities.division_id` and `by_rep` by `opportunities.owner_id`: each row carries the name, won € and count, forecast €, open pipeline € and conversion for that group under the same definitions as the summary, ordered by won € descending. Rows exist only for groups with data in scope; divisions or reps with no opportunities are omitted.

#### Scenario: Division ranking
- **WHEN** Vascular won 30000.00 and FIV won 12000.00 in the period
- **THEN** `by_division` lists Vascular first, each row with its own forecast and open pipeline

#### Scenario: Rep breakdown only for full-scope viewers
- **WHEN** a `sales_rep` requests the dashboard
- **THEN** `by_rep` is null while `by_division` reflects only that rep's portfolio

### Requirement: Activity metrics and neglected accounts
`activity` SHALL count activities with done status and `done_at` in the period, grouped per owner with per-type counts and a total, ordered by total descending. `neglected_accounts` SHALL list active accounts whose `last_contact_at` is older than 60 days — or null with `created_at` older than 60 days — ordered oldest contact first, capped at 20 entries with the uncapped total count; each entry carries the account id, name and days since last contact (null when never contacted).

#### Scenario: Activity per rep and type
- **WHEN** a rep completed 3 visits and 2 calls in the period
- **THEN** their activity row shows total 5 with visits 3 and calls 2

#### Scenario: Never-contacted account
- **WHEN** an active account was created 90 days ago and has no contact-counting activity
- **THEN** it appears in `neglected_accounts` with null days since contact

#### Scenario: Cap with total
- **WHEN** 35 accounts qualify as neglected
- **THEN** the list contains the 20 oldest and `total` is 35

### Requirement: Role scoping on the server
Scope SHALL be derived from the authenticated actor only, never from a client parameter. A `sales_rep` SHALL receive every section filtered to their ownership: opportunities and activities by `owner_id`, neglected accounts by `accounts.owner_id`. `sales_manager`, `admin` and `back_office` SHALL receive the unfiltered company view including `by_rep`.

#### Scenario: Rep sees only their portfolio
- **WHEN** a `sales_rep` requests the dashboard while another rep won an opportunity this month
- **THEN** the other rep's win is absent from every figure in the response

#### Scenario: Back office sees the company panel
- **WHEN** a `back_office` user requests the dashboard
- **THEN** the payload matches the manager's company-wide figures including `by_rep`

### Requirement: Performance budget
The dashboard endpoint SHALL respond within the 500 ms API budget at MVP data volumes, asserted by an integration test against the seeded test database.

#### Scenario: Budget assertion
- **WHEN** the integration suite times the endpoint over seeded data
- **THEN** the measured latency is below 500 ms
