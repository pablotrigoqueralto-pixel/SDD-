## ADDED Requirements

### Requirement: Opportunity audit events
The following events SHALL be recorded in the same transaction as the mutation: `opportunity.created` (field snapshot), `opportunity.updated` (field diffs), `opportunity.stage_changed` (`stage_id` before/after), `opportunity.won` (`won_amount`, `won_at`), `opportunity.lost` (`loss_reason_id`, `competitor_brand_id`, `loss_note`), `opportunity.reopened` (`stage_id`), `opportunity.at_risk_set` / `opportunity.at_risk_cleared` (`at_risk_source`; the automatic scan records a null actor), `opportunity.reassigned` (`owner_id` before/after), `opportunity.line_added` / `line_updated` / `line_removed` (line snapshot and the resulting `amount`).

#### Scenario: Win audited
- **WHEN** an opportunity is won for 24 000
- **THEN** one `opportunity.won` row exists with `changes.won_amount = { before: null, after: "24000.00" }` and one `opportunity.stage_changed` row for the move to Ganada

#### Scenario: Automatic at-risk audited without actor
- **WHEN** the scan flags an opportunity
- **THEN** an `opportunity.at_risk_set` row exists with `actor_id = null` and `changes.at_risk_source.after = "automatic"`
