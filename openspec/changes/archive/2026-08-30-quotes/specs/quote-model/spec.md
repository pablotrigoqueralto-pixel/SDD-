## ADDED Requirements

### Requirement: Quote record and yearly numbering
The system SHALL persist quotes in `quotes` with `id`, `opportunity_id` (required; the account is reached through it), `year` (smallint), `number` (int), `quote_number` (`P-{year}-{number:04d}`), `version` (int ≥ 1), `status` (`draft` | `sent` | `accepted` | `rejected`), `owner_id` (defaulting to the opportunity owner), `contact_id` (nullable), `conditions` (jsonb: `validez_dias`, `plazo_entrega`, `forma_pago`, `garantia`), `total_base`, `total_vat`, `total` (`numeric(12,2)`), `valid_until` (date, nullable until sent), `sent_at`, `accepted_at`, `rejected_at`, `rejection_note`, `superseded_at`, `created_by`, `version_lock` (optimistic-locking counter), `created_at`, `updated_at`. `(year, number, version)` SHALL be unique. Numbers SHALL be assigned at creation from `quote_counters(year, last_number)` via an atomic upsert in the creating transaction, using the Europe/Madrid calendar year; numbers are never reused and never have gaps. `display_number` SHALL be `quote_number` for version 1 and `quote_number-v{version}` afterwards.

#### Scenario: Concurrent creations get consecutive numbers
- **WHEN** two quotes are created concurrently in 2026
- **THEN** they receive distinct consecutive numbers (e.g. `P-2026-0007` and `P-2026-0008`) and `quote_counters` ends with `last_number = 8`

#### Scenario: Rolled-back creation leaves no gap
- **WHEN** a quote creation fails after allocating a number and the transaction rolls back
- **THEN** the counter increment rolls back too and the next creation receives the same number

#### Scenario: Year from Madrid calendar
- **WHEN** a quote is created at `2026-12-31T23:30` Europe/Madrid
- **THEN** it is numbered in year 2026 even if sent in January 2027

### Requirement: Quote lines with discount and VAT
Quote lines SHALL be persisted in `quote_lines` with `id`, `quote_id`, `position`, `product_id` (nullable FK, `ON DELETE SET NULL`), `description` (required, ≤ 300; snapshot of the product name, editable), `product_code` (nullable snapshot), `quantity` (`numeric(12,2)` > 0), `unit_price` (`numeric(12,2)` ≥ 0), `discount_percent` (`numeric(5,2)` in [0, 100]), `vat_rate` (`numeric(4,2)` in {21.00, 10.00, 4.00, 0.00}), `unit_cost` (nullable snapshot). Per line the domain SHALL compute `base = round_half_up(quantity × unit_price × (1 − discount_percent/100), 2)` and `vat = round_half_up(base × vat_rate/100, 2)`. Quote totals SHALL be `total_base = Σ base`, `total_vat = Σ vat`, `total = total_base + total_vat`, recomputed on every line mutation, with a VAT breakdown by rate computed on read. Lines with `product_id IS NULL` are free-text lines.

#### Scenario: Spanish invoice rounding per line
- **WHEN** a line has quantity 3, unit price 33.33, discount 10% and VAT 21%
- **THEN** its base is 89.99 (3 × 33.33 × 0.9 = 89.991 rounded), its VAT is 18.90, and the quote totals equal the sum of the printed per-line values

#### Scenario: Invalid VAT rate rejected
- **WHEN** a line is written with `vat_rate = 15`
- **THEN** it fails with `invalid_vat_rate` (422)

#### Scenario: Product deleted from catalogue
- **WHEN** a product referenced by a quote line is hard-deleted
- **THEN** the line keeps `description` and `product_code` and `product_id` becomes null

### Requirement: Creation from an opportunity
A quote SHALL always be created from an open opportunity. Creation SHALL copy the opportunity's lines (product reference, name snapshot as `description`, list price as `unit_price`, current cost as `unit_cost`, quantity, `discount_percent = 0`, `vat_rate = 21.00`) — or start empty when the opportunity has none — and seed `conditions` from the admin defaults. Multiple quotes (distinct numbers) MAY exist for one opportunity.

#### Scenario: Lines copied with defaults
- **WHEN** a quote is created from an opportunity with a line of 2 × Doppler at list price 13 000
- **THEN** the quote has one draft line: description = the product name, quantity 2, unit price 13000.00, discount 0, VAT 21, and `total = 31460.00` (26 000 base + 5 460 VAT)

#### Scenario: Closed opportunity rejected
- **WHEN** a quote is created on a won or lost opportunity
- **THEN** it fails with `opportunity_closed` (409)

### Requirement: Status machine and freezing
Quotes SHALL transition only `draft → sent → accepted | rejected`. `send` SHALL stamp `sent_at` and default `valid_until = sent date + conditions.validez_dias` (30 when unset) when not explicitly provided. Once sent, the quote's fields and lines SHALL be immutable — any mutation fails with `quote_not_editable` (409). `accept` SHALL stamp `accepted_at`; `reject` SHALL stamp `rejected_at` and an optional `rejection_note`. Drafts MAY be deleted; sent, accepted and rejected versions SHALL never be deleted. A quote whose `status = sent` and `valid_until < today` is **expired** — a derived read-time flag with no stored state and no automatic transition.

#### Scenario: Editing a sent quote
- **WHEN** a line update or field update targets a sent quote
- **THEN** it fails with `quote_not_editable` (409)

#### Scenario: Validity default from conditions
- **WHEN** a draft with `conditions.validez_dias = 15` is sent on 2026-09-01 without an explicit `valid_until`
- **THEN** `valid_until = 2026-09-16`

#### Scenario: Expiry is visual only
- **WHEN** a sent quote's `valid_until` passes
- **THEN** its stored status remains `sent` and reads expose `is_expired = true`

#### Scenario: Deleting a sent version
- **WHEN** a delete targets a sent quote
- **THEN** it fails with `quote_not_editable` (409); deleting a draft succeeds

### Requirement: Versions under a shared number
`revise` SHALL be allowed on the current version (`superseded_at IS NULL`) of a sent or rejected quote: it SHALL create a new `draft` row with the same `year`/`number`, `version + 1`, a full copy of the previous version's lines and conditions, and stamp `superseded_at` on the previous row. Lists SHALL show only current versions; the version chain SHALL remain readable. Accepted quotes SHALL not be revised.

#### Scenario: Revision copies content
- **WHEN** `P-2026-0001` (sent, 3 lines) is revised
- **THEN** a draft `P-2026-0001-v2` exists with the same 3 lines and conditions, the v1 row has `superseded_at` set, and only v2 appears in lists

#### Scenario: Revising a superseded version
- **WHEN** `revise` targets a version that already has `superseded_at`
- **THEN** it fails with `quote_superseded` (409)

#### Scenario: Revising an accepted quote
- **WHEN** `revise` targets an accepted quote
- **THEN** it fails with `quote_not_editable` (409)

### Requirement: Acceptance wins the opportunity
`accept` SHALL, in one transaction: transition the quote to `accepted`, call the opportunity `win` command with `won_amount = quote.total` and the acceptance date, and reject sibling quotes — other quote numbers of the same opportunity whose current version is `draft` or `sent` — stamping `rejection_note = "superseded by accepted quote {display_number}"`. If the opportunity is already closed, `accept` SHALL fail with `opportunity_already_closed` (409).

#### Scenario: Accept wins and cleans siblings
- **WHEN** `P-2026-0002` (total 31 460.00) on an open opportunity with a second sent quote `P-2026-0003` is accepted
- **THEN** the opportunity is won with `won_amount = 31460.00`, `P-2026-0003` becomes `rejected` with the superseded note, and the stage history records the move to Ganada

#### Scenario: Accept on a closed opportunity
- **WHEN** the opportunity was already won or lost
- **THEN** `accept` fails with `opportunity_already_closed` (409) and the quote stays `sent`

### Requirement: PDF document storage
Sending SHALL render the quote as a PDF (fixed ReportLab template: Quermed logo and fiscal data, account and contact block, numbered line table with discount and VAT columns, totals grouped by VAT rate, conditions block, owner signature footer) and store the exact bytes in `quote_pdfs(quote_id PK/FK, content bytea, generated_at)`. The stored bytes SHALL be immutable and re-downloadable for the life of the record. Draft previews SHALL render on the fly from the same code path without storing.

#### Scenario: Sent PDF is frozen
- **WHEN** a quote is sent and the referenced product is later renamed
- **THEN** downloading the quote's PDF returns the original bytes with the original product name

### Requirement: Mail outbox
Every send SHALL write one `mail_outbox` row (`id`, `quote_id`, `recipients` jsonb of `{email, name}`, `subject`, `body`, `status` `sent` | `failed` | `skipped`, `error` nullable, `created_at`, `sent_at` nullable). The Graph call SHALL happen after the freezing transaction commits; a Graph failure SHALL mark the row `failed` with the error and SHALL NOT revert the quote's `sent` status. When `GRAPH_SENDER_MODE = off` or the sender chose manual sending, the row SHALL be `skipped`. A retry SHALL re-send the stored PDF with a new outbox row and no new version.

#### Scenario: Graph failure keeps the quote sent
- **WHEN** Graph returns 500 during send
- **THEN** the quote is `sent` with its PDF stored, the outbox row is `failed` with the error text, and a retry can succeed later

#### Scenario: Send without email
- **WHEN** a quote is sent with mode `off`
- **THEN** the quote is frozen and `sent`, the PDF is stored, and the outbox row is `skipped`

### Requirement: Application settings
The system SHALL persist admin-editable settings in `app_settings(key text PK, value jsonb, updated_at)` with two seeded keys: `quote_conditions_defaults` (`validez_dias` = 30, `plazo_entrega`, `forma_pago`, `garantia`) and `quote_email_template` (`subject`, `body` supporting `{numero}`, `{centro}`, `{comercial}` placeholders). Quote creation SHALL copy the current defaults into the quote's own `conditions`.

#### Scenario: Defaults copied, not referenced
- **WHEN** the admin changes `plazo_entrega` after a draft was created
- **THEN** the existing draft keeps its copied conditions; only new quotes get the new default

### Requirement: Quote permissions
Visibility SHALL be the account scope, inherited through the opportunity, exactly like opportunities. Draft actions (`create`, `update`, `delete`) SHALL be allowed for the opportunity owner, `sales_manager`, `admin` and `back_office`. Lifecycle actions (`send`, `accept`, `reject`, `revise`, email retry) SHALL be allowed for the opportunity owner, `sales_manager` and `admin` only; `back_office` SHALL receive `quote_action_forbidden` (403). `unit_cost` and margin values SHALL be exposed only to `sales_manager` and `admin`.

#### Scenario: Back office prepares but cannot send
- **WHEN** a back-office user creates and edits a draft and then calls send
- **THEN** the draft mutations succeed and send fails with `quote_action_forbidden` (403)

#### Scenario: Rep outside the territory
- **WHEN** a rep lists quotes and one belongs to an account outside their scope
- **THEN** that quote is absent from lists and its detail returns 404
