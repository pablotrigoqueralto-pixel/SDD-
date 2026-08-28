## ADDED Requirements

### Requirement: Reference data bundle
`GET /api/v1/reference-data` SHALL return, for any authenticated role, `{ account_types[], activity_types[], divisions[], brands[], loss_reasons[], pipelines[] }` where each pipeline embeds its `stages[]` ordered by `sort_order`. Inactive rows SHALL be included with `is_active = false` so historical records still resolve their labels. The response SHALL carry an `ETag` derived from the newest `updated_at` of the masters and SHALL answer `304 Not Modified` to a matching `If-None-Match`.

Visibility: masters are global; no territory filtering applies.

#### Scenario: Sales rep loads the bundle
- **WHEN** a `sales_rep` calls `GET /api/v1/reference-data`
- **THEN** the response is 200 with six account types, six activity types, seven divisions, at least thirteen brands, six loss reasons and two pipelines with ordered stages

#### Scenario: Unchanged bundle
- **WHEN** the client repeats the request with `If-None-Match` equal to the previous `ETag`
- **THEN** the response is 304 without a body

#### Scenario: Anonymous access
- **WHEN** the request has no bearer token
- **THEN** the response is 401 `unauthenticated`

### Requirement: Per-master read endpoints
`GET /api/v1/account-types`, `GET /api/v1/activity-types`, `GET /api/v1/brands`, `GET /api/v1/loss-reasons` and `GET /api/v1/pipelines` SHALL return plain arrays (not paginated, bounded lists) sorted by `sort_order` (types, reasons, pipelines) or `name` (brands), readable by every authenticated role. `GET /brands` SHALL accept the filters `is_own`, `is_active` and `q` (prefix on name).

#### Scenario: Filter competitor brands
- **WHEN** `GET /api/v1/brands?is_own=false&is_active=true` is called
- **THEN** only active competitor brands are returned, sorted by name

#### Scenario: Pipelines with stages
- **WHEN** `GET /api/v1/pipelines` is called
- **THEN** each pipeline includes `division_ids[]`, `version` and `stages[]` with `probability`, `is_won`, `is_lost`, `is_at_risk`, `is_active`, `version`

### Requirement: Brand administration
`POST /api/v1/brands` and `PATCH /api/v1/brands/{id}` (with `If-Match`) SHALL be allowed for `admin` only. Creating derives `code` from the name; updating accepts `name`, `is_own`, `is_active`, `division_ids`.

#### Scenario: Admin creates a competitor brand
- **WHEN** an admin posts `{ "name": "Cook Medical", "is_own": false, "division_ids": [] }`
- **THEN** the response is 201 with `code = "cook_medical"`, `is_own = false`, and an audit event `brand.created` is recorded

#### Scenario: Duplicate name
- **WHEN** an admin creates a brand whose name already exists (case-insensitive)
- **THEN** the response is 409 with code `brand_name_already_exists`

#### Scenario: Rename and deactivate with version
- **WHEN** an admin patches a brand with `If-Match` equal to its version and `{ "name": "Hadeco Europe", "is_active": false }`
- **THEN** the response is 200 with `version` incremented and audit events `brand.updated` and `brand.deactivated` are recorded

#### Scenario: Non-admin write
- **WHEN** a `sales_manager`, `back_office` or `sales_rep` posts or patches a brand
- **THEN** the response is 403 `forbidden`

### Requirement: Loss reason administration
`POST /api/v1/loss-reasons` (`{ name }`, flags default to false, appended last in `sort_order`) and `PATCH /api/v1/loss-reasons/{id}` (`name`, `is_active`, with `If-Match`) SHALL be allowed for `admin` only. `requires_brand` and `requires_note` SHALL NOT be editable through the API.

#### Scenario: Admin adds a reason
- **WHEN** an admin posts `{ "name": "Cambio de proveedor" }`
- **THEN** the response is 201 with `code = "cambio_de_proveedor"`, `sort_order` greater than every existing reason, and audit event `loss_reason.created`

#### Scenario: Duplicate reason name
- **WHEN** the name already exists (case-insensitive)
- **THEN** the response is 409 `loss_reason_name_already_exists`

### Requirement: Pipeline administration
`PATCH /api/v1/pipelines/{id}` (`name`, `If-Match`) SHALL rename a pipeline. `PATCH /api/v1/pipelines/{id}/stages/{stage_id}` (`name`, `probability`, `is_active`, `If-Match` with the stage version) SHALL edit a stage. `PUT /api/v1/pipelines/{id}/stages/order` (`{ stage_ids[] }`, `If-Match` with the pipeline version) SHALL reorder the stages. All three are `admin` only.

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

#### Scenario: Invalid order
- **WHEN** the list misses a stage, repeats one or includes a stage of another pipeline
- **THEN** the response is 422 with code `stage_order_invalid`

#### Scenario: Stale pipeline version
- **WHEN** the reorder is sent with an `If-Match` that does not equal the pipeline version
- **THEN** the response is 409 `conflict`

### Requirement: OpenAPI and audit conventions
All endpoints SHALL be documented in the exported `api-spec.yml`, return problem+json errors, and every write SHALL record its audit event in the same transaction.

#### Scenario: Audit trail of a brand
- **WHEN** an admin lists `GET /api/v1/audit-log?entity_type=brand&entity_id=<id>` after creating and renaming a brand
- **THEN** the entries `brand.updated` and `brand.created` are returned newest first with field diffs
