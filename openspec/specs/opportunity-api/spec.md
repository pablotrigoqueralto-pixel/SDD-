# opportunity-api

## Purpose
REST endpoints for opportunities under the account visibility rule: scoped list and board, creation with smart defaults, explicit lifecycle commands with optimistic locking, product lines, timeline and today integrations and the at-risk scan.

## Requirements

### Requirement: Create and read opportunities
`POST /api/v1/opportunities` SHALL accept `OpportunityCreate { account_id, division_id, estimated_amount, pipeline_id?, name?, expected_close_date?, description?, is_tender?, tender_reference?, tender_deadline?, estimated_award_date?, owner_id? (managers/admins only) }` from users who can write the account (`sales_rep` in scope, `sales_manager`, `admin`; `back_office` → 403), return 201 `OpportunityRead { id, account_id, account_name, pipeline_id, pipeline_name, stage_id, stage_name, division_id, owner_id, owner_name, name, description, status, estimated_amount, amount, expected_close_date, won_amount, won_at, lost_at, loss_reason_id, competitor_brand_id, loss_note, is_tender, tender_reference, tender_deadline, estimated_award_date, is_at_risk, at_risk_since, at_risk_source, stage_entered_at, days_in_stage, lines[], stage_history[], version, created_at, updated_at }` and record `opportunity.created`. `GET /api/v1/opportunities/{id}` SHALL return it under the account's visibility (404 out of scope). Amounts SHALL travel as two-decimal strings.

#### Scenario: Rep creates in three fields
- **WHEN** a rep posts `{ account_id, division_id: vascular, estimated_amount: "30000" }` for a centre in scope
- **THEN** the response is 201 with `pipeline_name = "Equipos"`, `stage_name = "Contacto"`, `amount = "30000.00"`, `days_in_stage = 0` and `owner_id` = the rep

#### Scenario: Rep sets another owner
- **WHEN** a rep posts with `owner_id` of a colleague
- **THEN** the response is 403 `assignment_forbidden`

#### Scenario: Out of scope
- **WHEN** a rep posts for an account outside their scope or reads such an opportunity
- **THEN** the response is 404 `not_found`

### Requirement: Update and lifecycle endpoints
`PATCH /api/v1/opportunities/{id}` (requires `If-Match`) SHALL accept `name`, `description`, `estimated_amount`, `expected_close_date`, `is_tender`, `tender_reference`, `tender_deadline`, `estimated_award_date` and reject `stage_id`, `status` and `owner_id`. `POST /{id}/stage { stage_id }`, `POST /{id}/win { won_amount?, won_at? }`, `POST /{id}/lose { loss_reason_id, competitor_brand_id?, note? }`, `POST /{id}/reopen { stage_id }` (managers/admins), `POST /{id}/at-risk { flag }`, `PUT /{id}/assignment { owner_id }` (managers/admins) SHALL require `If-Match`, be allowed to the opportunity owner and managers/admins (back office and other reps → 403), and map the domain errors of `opportunity-model` to their status codes. A stale `If-Match` SHALL return 409 `conflict`; a missing one 428.

#### Scenario: Move and win
- **WHEN** the owner posts `/stage` to Presupuesto and then `/win` with `won_amount: "24000"`
- **THEN** both return 200; the final `OpportunityRead` has `status = won`, `stage_name = "Ganada"`, `won_amount = "24000.00"` and two history rows

#### Scenario: Lose with competitor
- **WHEN** `/lose` is posted with the reason Competidor and `competitor_brand_id` of a competitor brand
- **THEN** the response is 200 with `status = lost` and `competitor_brand_id` set; without the brand it is 422 `loss_reason_requires_brand`

#### Scenario: Another rep cannot move it
- **WHEN** a rep who sees the centre but does not own the opportunity posts `/stage`
- **THEN** the response is 403 `forbidden`

#### Scenario: Reopen by a rep
- **WHEN** the owner (a rep) posts `/reopen`
- **THEN** the response is 403 `reopen_forbidden`; the same call by a manager returns 200

### Requirement: Product lines endpoints
`POST /api/v1/opportunities/{id}/lines { product_id, quantity, unit_price? }` (201), `PATCH /{id}/lines/{line_id} { quantity?, unit_price? }` and `DELETE /{id}/lines/{line_id}` (204) SHALL require `If-Match` with the opportunity version, follow the writer rule, return the updated `OpportunityRead` (except `DELETE`) and record `opportunity.line_added` / `line_updated` / `line_removed`.

#### Scenario: Line with default price
- **WHEN** a line `{ product_id, quantity: "2" }` is added to an opportunity whose product lists at 12 500.00
- **THEN** the response is 201 with the line `unit_price = "12500.00"` and `amount = "25000.00"`

#### Scenario: Retired product
- **WHEN** a line references a product with `is_active = false`
- **THEN** the response is 422 `line_product_inactive`

### Requirement: Opportunity lists and board
`GET /api/v1/opportunities?status=&pipeline_id=&stage_id=&division_id=&owner_id=&account_id=&is_tender=&is_at_risk=&close_from=&close_to=&q=&sort=&page=&page_size=` SHALL return `Page[OpportunitySummaryRead { id, account_id, account_name, name, pipeline_id, stage_id, stage_name, division_id, owner_id, owner_name, status, amount, expected_close_date, is_tender, tender_deadline, is_at_risk, stage_entered_at, days_in_stage, version, updated_at }]` scoped through the account predicate, `status` defaulting to `open`, sorted by `expected_close_date` (also `amount`, `stage_entered_at`, `updated_at`, `name`). `GET /api/v1/accounts/{id}/opportunities` SHALL return the account's opportunities (all statuses, open first). `GET /api/v1/opportunities/board?pipeline_id=&division_id=&owner_id=` SHALL return `BoardRead { pipeline: PipelineRead, columns: [{ stage: PipelineStageRead, count, total_amount, items: OpportunitySummaryRead[], has_more }], closed_this_month: { won_count, won_amount, lost_count } }` with open items per stage ordered by `stage_entered_at` and capped at 50, computed in at most two statements and answering under 500 ms with 500 open opportunities.

#### Scenario: Scoped list
- **WHEN** a rep lists opportunities
- **THEN** only those of accounts they can see are returned, open ones by default, oldest close date first

#### Scenario: Board totals
- **WHEN** a manager requests the equipment board with three opportunities in Demo worth 10 000, 20 000 and 30 000
- **THEN** the Demo column has `count = 3`, `total_amount = "60000.00"` and three items; `closed_this_month` counts the wins and losses of the current Madrid month

#### Scenario: Column cap
- **WHEN** a stage has 60 open opportunities
- **THEN** its column returns 50 items, `count = 60` and `has_more = true`

### Requirement: Activities and timeline integration
`ActivityCreate`/`ActivityUpdate` SHALL accept `opportunity_id` and `ActivityRead` SHALL expose `opportunity_id` and `opportunity_name`; `GET /activities?opportunity_id=` SHALL filter by it. The account timeline SHALL emit `TimelineEntryRead { kind: "opportunity_stage" | "opportunity_closed", occurred_at, title, stage_change: { opportunity_id, opportunity_name, from_stage_name, to_stage_name, actor_name, amount } }` for every history row, merged by `occurred_at` with activities; `kind` filters SHALL accept the new values.

#### Scenario: Timeline merges stage changes
- **WHEN** an account has a visit done yesterday and an opportunity moved to Demo today
- **THEN** the timeline returns the stage entry first, then the visit

#### Scenario: Activity linked to an opportunity
- **WHEN** a visit is posted with `opportunity_id`
- **THEN** `ActivityRead.opportunity_name` is filled and `GET /activities?opportunity_id=` returns it

### Requirement: Today additions
`TodayRead` SHALL gain `tenders_due: OpportunitySummaryRead[]` (open tender opportunities of the user — or the selected rep — with `tender_deadline` ≤ today + 7 days, overdue first) and `at_risk: OpportunitySummaryRead[]` (their at-risk opportunities, oldest `at_risk_since` first).

#### Scenario: Tender due this week
- **WHEN** the rep owns a tender opportunity with a deadline in 5 days and another in 20 days
- **THEN** `tenders_due` contains only the first

### Requirement: At-risk scan command and setting
`AT_RISK_AFTER_DAYS` (default 60) and `AT_RISK_SCAN_INTERVAL_HOURS` (default 6; 0 disables the in-process scheduler) SHALL be settings. `python -m app.tooling.at_risk_scan` SHALL run the scan once and print the number of flagged opportunities; the backend lifespan SHALL run it at start and every interval when enabled. Each flag SHALL record `opportunity.at_risk_set` with a null actor.

#### Scenario: CLI run
- **WHEN** the command runs against a database with two silent recurring opportunities
- **THEN** it exits 0, prints `2` and a second run prints `0`

### Requirement: OpenAPI and audit conventions
All endpoints SHALL be documented in `ai-specs/specs/api-spec.yml` with RFC 7807 problems and the error codes `pipeline_required`, `stage_not_in_pipeline`, `invalid_opportunity_transition`, `opportunity_closed`, `loss_reason_requires_brand`, `loss_reason_requires_note`, `opportunity_has_lines`, `tender_fields_require_tender`, `at_risk_not_supported`, `line_product_inactive`, `line_duplicated`, `reopen_forbidden`, `opportunity_not_in_account`.

#### Scenario: Types regenerated
- **WHEN** `npm run api:types` runs
- **THEN** `OpportunityRead`, `OpportunitySummaryRead`, `OpportunityCreate`, `OpportunityUpdate`, `OpportunityLineRead`, `BoardRead` and `StageChangeRead` are generated
