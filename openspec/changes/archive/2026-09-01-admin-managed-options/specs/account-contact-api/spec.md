# account-contact-api (delta)

Creating a job title reuses an existing one instead of answering 409.

## MODIFIED Requirements

### Requirement: Job titles endpoints
`GET /api/v1/job-titles` SHALL return the master (all rows, `is_active` included) for any authenticated role; `POST /api/v1/job-titles { name }` and `PATCH /api/v1/job-titles/{id} { name?, is_active? }` with `If-Match` SHALL be `admin` only, derive `code` from the name and record `job_title.created` / `job_title.updated`. A `POST` whose name resolves to the `code` of an existing title SHALL **reuse** that title — reactivating it when inactive and recording `job_title.reactivated` — and answer 201 with an `outcome` of `created`, `reused` or `reactivated`, instead of 409 `job_title_name_already_exists`.

#### Scenario: Admin adds a title
- **WHEN** an admin posts `{ "name": "Farmacia hospitalaria" }`
- **THEN** the response is 201 with `code = "farmacia_hospitalaria"`, `sort_order` after the last seeded title and `outcome = "created"`

#### Scenario: Existing title is reused
- **WHEN** an admin posts a name that resolves to the code of an existing active title
- **THEN** the response is 201 with that title and `outcome = "reused"`, and no second row is created

#### Scenario: Deactivated title comes back
- **WHEN** an admin posts a name resolving to the code of a deactivated title (for example "Jefe de servicio", deactivated by change 12)
- **THEN** the response is 201 with the title active again, `outcome = "reactivated"` and audit event `job_title.reactivated`
