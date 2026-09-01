# reference-data-api (delta)

Creation endpoints for specialties and account types, reuse-and-reactivate instead of 409, and a reorder that keeps terminal stages last.

## ADDED Requirements

### Requirement: Specialty administration
`POST /api/v1/specialties { name }` SHALL be allowed for `admin` only, derive `code` from the name, append the entry last in `sort_order` and record `specialty.created`. The response SHALL be 201 with the specialty and an `outcome` of `created`, `reused` or `reactivated` so the caller can tell the administrator what happened.

#### Scenario: Admin adds a specialty
- **WHEN** an admin posts `{ "name": "Urología" }`
- **THEN** the response is 201 with `code = "urologia"`, `sort_order` after every seeded specialty, `outcome = "created"` and audit event `specialty.created`

#### Scenario: Non-admin write
- **WHEN** a `sales_manager`, `back_office` or `sales_rep` posts a specialty
- **THEN** the response is 403 `forbidden`

#### Scenario: Empty name
- **WHEN** the name is blank or contains no letters or digits
- **THEN** the response is 422 `validation_error`

### Requirement: Account type administration
`POST /api/v1/account-types { name, buys_via_tender? }` SHALL be allowed for `admin` only, derive `code` from the name, default `buys_via_tender` to `false`, append the entry last in `sort_order` and record `account_type.created`. The response SHALL be 201 with the account type and its `outcome`.

#### Scenario: Admin adds a tendering type
- **WHEN** an admin posts `{ "name": "Consorcio sanitario", "buys_via_tender": true }`
- **THEN** the response is 201 with `code = "consorcio_sanitario"`, `buys_via_tender = true` and audit event `account_type.created`

#### Scenario: Flag defaults to false
- **WHEN** an admin posts `{ "name": "Residencia" }` without the flag
- **THEN** the response is 201 with `buys_via_tender = false`

#### Scenario: New type usable at once
- **WHEN** an account is created with the new type
- **THEN** it is accepted and the type appears in the reference bundle with a new `ETag`

## MODIFIED Requirements

### Requirement: Loss reason administration
`POST /api/v1/loss-reasons` (`{ name }`, flags default to false, appended last in `sort_order`) and `PATCH /api/v1/loss-reasons/{id}` (`name`, `is_active`, with `If-Match`) SHALL be allowed for `admin` only. `requires_brand` and `requires_note` SHALL NOT be editable through the API. A `POST` whose name resolves to the `code` of an existing reason SHALL **reuse** that reason — reactivating it when inactive — and answer 201 with the corresponding `outcome`, instead of 409.

#### Scenario: Admin adds a reason
- **WHEN** an admin posts `{ "name": "Cambio de proveedor" }`
- **THEN** the response is 201 with `code = "cambio_de_proveedor"`, `sort_order` greater than every existing reason, `outcome = "created"` and audit event `loss_reason.created`

#### Scenario: Existing reason is reused
- **WHEN** the name resolves to the code of an existing active reason
- **THEN** the response is 201 with that reason, `outcome = "reused"`, and no audit event is recorded because nothing changed

#### Scenario: Inactive reason is reactivated
- **WHEN** the name resolves to the code of a deactivated reason
- **THEN** the response is 201 with that reason active again, `outcome = "reactivated"` and audit event `loss_reason.reactivated` recording `is_active` false → true

### Requirement: Pipeline administration
`PATCH /api/v1/pipelines/{id}` (`name`, `If-Match`) SHALL rename a pipeline. `PATCH /api/v1/pipelines/{id}/stages/{stage_id}` (`name`, `probability`, `is_active`, `If-Match` with the stage version) SHALL edit a stage. `PUT /api/v1/pipelines/{id}/stages/order` (`{ stage_ids[] }`, `If-Match` with the pipeline version) SHALL reorder the stages, **rejecting any order that places a terminal stage (`is_won`, `is_lost` or `is_at_risk`) before an advancing one**. All three are `admin` only.

#### Scenario: Tune a probability
- **WHEN** an admin patches the Demo stage with `{ "probability": 40 }`
- **THEN** the response is 200, the stage version increments and audit event `pipeline_stage.updated` records `probability` 30 → 40

#### Scenario: Probability out of range
- **WHEN** `probability` is 120 or negative
- **THEN** the response is 422 with code `stage_probability_invalid`

#### Scenario: Semantic flags are immutable
- **WHEN** the patch body contains `is_won`, `is_lost` or `is_at_risk`
- **THEN** the response is 400 with code `stage_flag_immutable`

#### Scenario: Deactivating the last open stage
- **WHEN** an admin deactivates a stage and no other active stage that is neither won nor lost would remain in the pipeline
- **THEN** the response is 400 with code `last_active_stage`

#### Scenario: Reorder
- **WHEN** an admin sends every stage id of the pipeline exactly once in a new order
- **THEN** the response is 200 with the pipeline (stages in the new order), the pipeline version increments and audit event `pipeline_stages.reordered` records the order before and after

#### Scenario: Swapping Demo and Presupuesto
- **WHEN** an admin sends the Equipos stages with Presupuesto before Demo, the terminal stages still last
- **THEN** the response is 200 and opportunities keep the stage they were in: only the position of the columns changes

#### Scenario: Terminal stage lifted
- **WHEN** the order places Perdida, Ganada or En riesgo before an advancing stage
- **THEN** the response is 422 with code `stage_order_invalid` and the stored order is unchanged

#### Scenario: Invalid order
- **WHEN** the list misses a stage, repeats one or includes a stage of another pipeline
- **THEN** the response is 422 with code `stage_order_invalid`

#### Scenario: Stale pipeline version
- **WHEN** the reorder is sent with an `If-Match` that does not equal the pipeline version
- **THEN** the response is 409 `conflict`
