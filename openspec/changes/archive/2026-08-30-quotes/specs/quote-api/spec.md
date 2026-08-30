## ADDED Requirements

### Requirement: Quote collection endpoints
`GET /api/v1/quotes` SHALL return a `Page[QuoteSummaryRead]` of **current versions** visible to the actor, filterable by `status`, `owner_id`, `opportunity_id`, `account_id`, `expiring` (sent and `valid_until` within 7 days) and `q` (matches `quote_number` and account name), ordered by `created_at` descending. `GET /api/v1/opportunities/{id}/quotes` SHALL return the opportunity's current versions. `GET /api/v1/quotes/{id}` SHALL return `QuoteRead` with lines, conditions, totals with VAT breakdown, `is_expired`, `display_number`, the version chain (`versions[]`: id, `revision`, status, sent_at) and the latest outbox status; cost and margin fields SHALL appear only for `sales_manager`/`admin`. Reads SHALL expose the optimistic-locking counter as `version` for `If-Match` (the document version travels as `revision`, matching the API-wide convention) and honour account scope (out-of-scope ids → 404).

#### Scenario: Expiring filter
- **WHEN** `GET /quotes?expiring=true` runs on 2026-09-01 and a sent quote has `valid_until = 2026-09-05`
- **THEN** it is returned; another with `valid_until = 2026-10-01` is not

#### Scenario: Cost hidden from reps
- **WHEN** a `sales_rep` reads a quote detail
- **THEN** the payload contains no `unit_cost` or margin fields; a `sales_manager` reading the same quote receives them

### Requirement: Draft lifecycle endpoints
`POST /api/v1/quotes` SHALL create a draft from `{opportunity_id, contact_id?}` (201, full read, number allocated). `PATCH /api/v1/quotes/{id}` SHALL update draft fields, conditions and the full `lines` array (replace semantics, like opportunity lines) under `If-Match` (428 without it, 409 on stale). `DELETE /api/v1/quotes/{id}` SHALL delete drafts only. All draft mutations SHALL accept `back_office` actors.

#### Scenario: Line replace under If-Match
- **WHEN** a PATCH sends 2 lines for a draft that has 3, with the current ETag
- **THEN** the draft ends with exactly the 2 lines, recomputed totals, and a bumped version lock

#### Scenario: Stale write
- **WHEN** a PATCH carries an outdated `If-Match`
- **THEN** it fails with 409 and the standard conflict problem body

### Requirement: Lifecycle action endpoints
`POST /api/v1/quotes/{id}/send` SHALL accept `{recipients: [{email, name?}], subject, body, valid_until?, skip_email?}` — freeze the version, store the PDF, write the outbox row and (unless skipped or mode `off`) email via Graph; it SHALL fail with `quote_recipients_required` (422) when the email path is active and no recipients are given. `POST /api/v1/quotes/{id}/accept` SHALL accept `{occurred_on?}` and run the accept transaction. `POST /api/v1/quotes/{id}/reject` SHALL accept `{note?}`. `POST /api/v1/quotes/{id}/revise` SHALL return the new draft version (201). `POST /api/v1/quotes/{id}/retry-email` SHALL re-send the stored PDF for a quote whose latest outbox row is `failed`. All five SHALL require owner/manager/admin (403 `quote_action_forbidden` for `back_office`) and SHALL use `If-Match`.

#### Scenario: Send without recipients in manual mode
- **WHEN** send is called with `skip_email = true` and no recipients
- **THEN** it succeeds: the quote is `sent`, the PDF stored, the outbox row `skipped`

#### Scenario: Retry without a failure
- **WHEN** retry-email is called and the latest outbox row is `sent` or `skipped`
- **THEN** it fails with `email_retry_not_available` (409)

### Requirement: PDF endpoints
`GET /api/v1/quotes/{id}/pdf` SHALL return `application/pdf` with `Content-Disposition: attachment; filename="{display_number}.pdf"` — the stored bytes for sent/accepted/rejected quotes and an on-the-fly preview render for drafts. Account scope applies (404 out of scope).

#### Scenario: Draft preview
- **WHEN** the PDF endpoint is called on a draft
- **THEN** a freshly rendered PDF of the current draft content is returned and nothing is stored

### Requirement: Quote settings administration
`GET /api/v1/quote-settings` SHALL return `{conditions_defaults, email_template}` to any authenticated user (the send dialog interpolates the template client-side); `PUT /api/v1/quote-settings` SHALL replace both, validating `validez_dias` ≥ 1 and non-empty subject/body, and SHALL be `admin`-only (403 otherwise).

#### Scenario: Non-admin blocked from writing
- **WHEN** a `sales_manager` calls PUT `/quote-settings`
- **THEN** it fails with 403, while their GET succeeds

### Requirement: Quote OpenAPI documentation
All quote endpoints, schemas and problem codes (`quote_not_editable`, `quote_superseded`, `quote_action_forbidden`, `quote_recipients_required`, `email_retry_not_available`, `invalid_vat_rate`, `opportunity_already_closed`) SHALL be present in the exported `api-spec.yml`.

#### Scenario: Spec export in sync
- **WHEN** the OpenAPI exporter runs
- **THEN** `ai-specs/specs/api-spec.yml` contains the `/quotes` paths and produces no CI drift
