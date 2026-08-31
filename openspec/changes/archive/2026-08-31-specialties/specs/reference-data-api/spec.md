# reference-data-api (delta)

The bundle carries the specialties catalogue.

## MODIFIED Requirements

### Requirement: Reference data bundle
`GET /api/v1/reference-data` SHALL return, for any authenticated role, `{ account_types[], activity_types[], divisions[], brands[], loss_reasons[], pipelines[], job_titles[], product_families[], specialties[] }` where each pipeline embeds its `stages[]` ordered by `sort_order`, `job_titles[]` and `specialties[]` are ordered by `sort_order` and `product_families[]` is ordered by division then `sort_order` and carries `division_id`. Inactive rows SHALL be included with `is_active = false` so historical records still resolve their labels. The response SHALL carry an `ETag` derived from the newest `updated_at` of the masters (job titles, product families and specialties included) and SHALL answer `304 Not Modified` to a matching `If-None-Match`.

Visibility: masters are global; no territory filtering applies.

#### Scenario: Sales rep loads the bundle
- **WHEN** a `sales_rep` calls `GET /api/v1/reference-data`
- **THEN** the response is 200 with six account types, six activity types, seven divisions, at least thirteen brands, six loss reasons, two pipelines with ordered stages, eleven job titles, at least twelve product families and twelve specialties

#### Scenario: Unchanged bundle
- **WHEN** the client repeats the request with `If-None-Match` equal to the previous `ETag`
- **THEN** the response is 304 without a body

#### Scenario: Job title edit changes the ETag
- **WHEN** an admin renames a job title and the client repeats the request with the old `ETag`
- **THEN** the response is 200 with a new `ETag`

#### Scenario: Family edit changes the ETag
- **WHEN** an admin renames a product family and the client repeats the request with the old `ETag`
- **THEN** the response is 200 with a new `ETag`

#### Scenario: Specialty edit changes the ETag
- **WHEN** an admin renames a specialty and the client repeats the request with the old `ETag`
- **THEN** the response is 200 with a new `ETag`

#### Scenario: Anonymous access
- **WHEN** the request has no bearer token
- **THEN** the response is 401 `unauthenticated`
