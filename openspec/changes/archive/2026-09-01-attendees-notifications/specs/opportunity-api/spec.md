# opportunity-api (delta)

Reassigning an opportunity tells its new owner.

## MODIFIED Requirements

### Requirement: Update and lifecycle endpoints
`PATCH /api/v1/opportunities/{id}` (requires `If-Match`) SHALL accept `name`, `description`, `estimated_amount`, `expected_close_date`, `is_tender`, `tender_reference`, `tender_deadline`, `estimated_award_date` and reject `stage_id`, `status` and `owner_id`. `POST /{id}/stage { stage_id }`, `POST /{id}/win { won_amount?, won_at? }`, `POST /{id}/lose { loss_reason_id, competitor_brand_id?, note? }`, `POST /{id}/reopen { stage_id }` (managers/admins), `POST /{id}/at-risk { flag }`, `PUT /{id}/assignment { owner_id }` (managers/admins) SHALL require `If-Match`, be allowed to the opportunity owner and managers/admins (back office and other reps → 403), and map the domain errors of `opportunity-model` to their status codes. A stale `If-Match` SHALL return 409 `conflict`; a missing one 428. When `PUT /{id}/assignment` moves an opportunity to a user other than the caller, the new owner SHALL receive an `opportunity_assigned` notification in the same transaction; the previous owner SHALL NOT be notified, because nothing was put on their plate.

#### Scenario: Move and win
- **WHEN** the owner posts `/stage` to Presupuesto and then `/win` with `won_amount: "24000"`
- **THEN** both return 200; the final `OpportunityRead` has `status = won`, `stage_name = "Ganada"`, `won_amount = "24000.00"` and two history rows

#### Scenario: Reassignment notifies the new owner
- **WHEN** a manager reassigns an opportunity to a rep
- **THEN** the response is 200 and that rep has an `opportunity_assigned` notification naming the opportunity

#### Scenario: Lose with competitor
- **WHEN** `/lose` is posted with the reason Competidor and `competitor_brand_id` of a competitor brand
- **THEN** the response is 200 with `status = lost` and `competitor_brand_id` set; without the brand it is 422 `loss_reason_requires_brand`

#### Scenario: Another rep cannot move it
- **WHEN** a rep who sees the centre but does not own the opportunity posts `/stage`
- **THEN** the response is 403 `forbidden`

#### Scenario: Reopen by a rep
- **WHEN** the owner (a rep) posts `/reopen`
- **THEN** the response is 403 `reopen_forbidden`; the same call by a manager returns 200
