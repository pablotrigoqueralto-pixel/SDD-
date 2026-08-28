# opportunity-model

## Purpose
Persistence and invariants of opportunities: pipeline position with derived status, stage history, amount from optional product lines, tender block, the at-risk rule for recurring consumables accounts and the activity link.

## Requirements

### Requirement: Opportunity record
The system SHALL persist opportunities in `opportunities` with `id`, `account_id` (required), `pipeline_id` and `stage_id` (required; the stage SHALL belong to the pipeline), `division_id` (required), `owner_id` (required), `name` (≤ 200, auto-generated as "<centre> · <division> · <month year>" when omitted), `description` (nullable), `status` (`open` | `won` | `lost`, derived from the stage flags), `estimated_amount` and `amount` (`numeric(12,2)` ≥ 0, EUR ex VAT), `expected_close_date`, `won_amount`, `won_at`, `lost_at`, `loss_reason_id`, `competitor_brand_id`, `loss_note`, `is_tender`, `tender_reference`, `tender_deadline`, `estimated_award_date`, `is_at_risk`, `at_risk_since`, `at_risk_source` (`manual` | `automatic`), `stage_entered_at`, `created_by`, `version`, `created_at`, `updated_at`. Database checks SHALL enforce `won → won_at not null`, `lost → loss_reason_id and lost_at not null`, tender fields only when `is_tender`, and `is_at_risk = (at_risk_since is not null)`.

#### Scenario: Three-field creation with defaults
- **WHEN** an opportunity is created with only `account_id`, `division_id` and `estimated_amount = 30000`
- **THEN** it is persisted with `pipeline_id` = the division's default pipeline, `stage_id` = the pipeline's first open stage, `status = open`, `amount = 30000.00`, `owner_id` = the account owner (or the creating rep), `name` = "<centre> · <division> · <month year>", `expected_close_date` = today + 90 days for the equipment pipeline or + 30 days for consumables, `is_tender` = the account type's `buys_via_tender`, `stage_entered_at` = now, `version = 1`

#### Scenario: Division without default pipeline
- **WHEN** the division has no default pipeline and no `pipeline_id` is given
- **THEN** creation fails with `pipeline_required` (422)

#### Scenario: Stage of another pipeline
- **WHEN** a stage that belongs to a different pipeline is used at creation or in a move
- **THEN** the domain rejects it with `stage_not_in_pipeline` (422)

### Requirement: Stage transitions and closing
An open opportunity SHALL move to any other open stage of its pipeline, forward or backward, through `move_stage`; `stage_entered_at` SHALL reset on every move. Closing SHALL happen only through `win` (moves to the `is_won` stage, sets `status = won`, `won_amount` defaulting to `amount`, `won_at` defaulting to now) and `lose` (moves to the `is_lost` stage, sets `status = lost`, `lost_at`, `loss_reason_id`; `competitor_brand_id` SHALL be required when the reason has `requires_brand`, `loss_note` when it has `requires_note`). Closed opportunities SHALL reject every command except `reopen`, which SHALL move back to an open stage and clear the closing fields. Every transition SHALL append a row to `opportunity_stage_history` (`from_stage_id`, `to_stage_id`, `actor_id` nullable for the system, `occurred_at`, `seconds_in_previous_stage`).

#### Scenario: Backward move allowed
- **WHEN** an opportunity in Presupuesto is moved to Demo
- **THEN** the move succeeds, `stage_entered_at` is now and the history has a row Presupuesto → Demo with the seconds spent in Presupuesto

#### Scenario: Move to the won stage rejected
- **WHEN** `move_stage` targets the stage with `is_won = true`
- **THEN** it fails with `invalid_opportunity_transition` (409) — only `win` may do it

#### Scenario: Lose requires a brand for Competidor
- **WHEN** `lose` is called with the reason Competidor and no `competitor_brand_id`
- **THEN** it fails with `loss_reason_requires_brand` (422); with the reason Otro and no note it fails with `loss_reason_requires_note` (422)

#### Scenario: Closed opportunity is immutable
- **WHEN** a won opportunity receives `move_stage`, `update` or `add_line`
- **THEN** it fails with `opportunity_closed` (409)

#### Scenario: Reopen
- **WHEN** a lost opportunity is reopened to Negociación
- **THEN** `status = open`, `lost_at`, `loss_reason_id`, `competitor_brand_id` and `loss_note` are null, and the history records Perdida → Negociación

### Requirement: Amount rule with product lines
`opportunity_lines` SHALL store `opportunity_id`, `product_id` (unique per opportunity), `quantity` (`numeric(10,2)` > 0), `unit_price` (`numeric(12,2)` ≥ 0, defaulting to the product's list price when omitted), `sort_order`. When at least one line exists, `amount` SHALL equal `SUM(quantity × unit_price)` rounded to two decimals and `estimated_amount` SHALL be read-only (`opportunity_has_lines`, 409); when the last line is removed, `amount` SHALL fall back to `estimated_amount`. Retired products SHALL NOT be added (`line_product_inactive`, 422) but existing lines keep them.

#### Scenario: Lines override the estimate
- **WHEN** an opportunity estimated at 30 000 receives a line 2 × 12 500.00
- **THEN** `amount = 25000.00` and `estimated_amount` stays 30 000.00

#### Scenario: Removing the last line restores the estimate
- **WHEN** that line is removed
- **THEN** `amount = 30000.00`

#### Scenario: Duplicate product
- **WHEN** a line for a product already on the opportunity is added
- **THEN** it fails with `line_duplicated` (409)

### Requirement: Tender block
`is_tender` SHALL default to the account type's `buys_via_tender` and be editable; `tender_reference` (≤ 100), `tender_deadline` and `estimated_award_date` SHALL be accepted only when `is_tender` is true (`tender_fields_require_tender`, 422).

#### Scenario: Public hospital defaults to tender
- **WHEN** an opportunity is created on a Hospital público without `is_tender`
- **THEN** `is_tender = true`

#### Scenario: Deadline on a non-tender
- **WHEN** `tender_deadline` is set while `is_tender` is false
- **THEN** the update fails with `tender_fields_require_tender` (422)

### Requirement: At-risk rule
`set_at_risk(True)` SHALL be accepted only for opportunities whose pipeline has an `is_at_risk` stage and whose `status = won` (`at_risk_not_supported`, 422 otherwise); it SHALL set `is_at_risk`, `at_risk_since`, `at_risk_source` and move the row to the `is_at_risk` stage (history recorded). `set_at_risk(False)` SHALL clear the three fields and move back to the pipeline's `is_won` stage. The automatic scan SHALL flag, with `at_risk_source = automatic` and a null actor, every won consumables opportunity not yet at risk whose latest done activity and `updated_at` are both older than `AT_RISK_AFTER_DAYS` days; it SHALL never clear flags. Recording a done activity linked to an opportunity with `at_risk_source = automatic` SHALL clear the flag.

#### Scenario: Equipment opportunity cannot be at risk
- **WHEN** `set_at_risk(True)` is called on an equipment-pipeline opportunity
- **THEN** it fails with `at_risk_not_supported` (422)

#### Scenario: Scan flags a silent recurring account
- **WHEN** the scan runs with `AT_RISK_AFTER_DAYS = 60` and a Recurrente opportunity has no done activity and no update for 61 days
- **THEN** it is moved to En riesgo with `at_risk_source = automatic`, and running the scan again changes nothing

#### Scenario: Manual flag survives the scan
- **WHEN** a rep clears an automatic flag and a later scan finds the same inactivity
- **THEN** the scan flags it again only if `updated_at` is again older than the threshold (the clearing updated the row)

#### Scenario: Activity clears the automatic flag
- **WHEN** a done visit linked to an automatically flagged opportunity is recorded
- **THEN** the opportunity returns to Recurrente with `is_at_risk = false`; a manually flagged one is left untouched

### Requirement: Activity link
`activities.opportunity_id` SHALL be an optional FK (`ON DELETE SET NULL`); the linked opportunity SHALL belong to the activity's account (`opportunity_not_in_account`, 422).

#### Scenario: Activity of another centre
- **WHEN** an activity for account A links an opportunity of account B
- **THEN** creation fails with `opportunity_not_in_account` (422)

### Requirement: Migration and indexes
Migration `0006_opportunities` SHALL create `opportunities`, `opportunity_lines`, `opportunity_stage_history`, the enums `opportunities_status_enum` and `opportunities_at_risk_source_enum`, the column `activities.opportunity_id`, the indexes `(account_id, status)`, `(owner_id, status)`, `(pipeline_id, stage_id, status)`, `(status, expected_close_date)`, partial `(tender_deadline) WHERE is_tender AND status = 'open'`, partial `(is_at_risk) WHERE is_at_risk`, `(opportunity_id, occurred_at DESC)` on the history, `opportunity_id` on lines and activities, and the guarded `crm_app` grants; `ProductRepository.is_referenced` SHALL become a query on `opportunity_lines`.

#### Scenario: Round trip
- **WHEN** `alembic upgrade head`, `downgrade 0005_product_catalogue`, `upgrade head` and `alembic check` run
- **THEN** all succeed and no drift is reported

#### Scenario: Product referenced by a line
- **WHEN** a product is on an opportunity line and its SKU is changed
- **THEN** the change is rejected with `product_sku_locked` (409)
