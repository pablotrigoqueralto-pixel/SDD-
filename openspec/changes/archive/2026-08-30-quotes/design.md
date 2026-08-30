## Context

Change 06 delivered the `Opportunity` aggregate with editable product lines, a `win(amount, occurred_at)` command, the timeline union (`activity | opportunity_stage | opportunity_closed`) and the "Hoy" composition endpoint. Change 05 delivered the product catalogue with exact `numeric` prices and role-gated cost. Quotes build directly on both: a quote is created **from** an opportunity, copies its lines, prices them precisely, and — when accepted — closes the loop by calling `win` with the quote total.

The backend keeps the layered architecture (api → application → domain ← infrastructure), UnitOfWork + AuditCollector, RFC 7807 errors, `If-Match` optimistic locking and account-scoped visibility. The frontend keeps feature folders, TanStack Query, react-hook-form + zod, i18n namespaces and MSW-backed tests. Nothing in this change alters those foundations; the new ground is: concurrency-safe business numbering, an immutable versioned document, server-side PDF rendering, and the first outbound integration (Microsoft Graph).

scope:
  backend: true
  frontend: true
design-linked: false

## Goals / Non-Goals

**Goals:**

- Yearly, gap-free, company-wide quote numbers (`P-2026-0001`) that are concurrency-safe.
- Immutable sent versions: the PDF the customer received can always be re-downloaded byte-for-byte.
- Exact Spanish invoice arithmetic: per-line discount %, per-line VAT (21/10/4/0), totals grouped by VAT rate, `ROUND_HALF_UP` at 2 decimals per line.
- Send = freeze + PDF + email via Microsoft Graph from the rep's mailbox, with an outbox record so failures are visible and retryable — and a clean "sin email" mode for dev/E2E.
- Accept = win the opportunity with the quote total and auto-reject sibling quotes, in one transaction.
- Role gating: back office prepares drafts only; cost/margin visible to managers/admins only.

**Non-Goals:**

- Customer-facing links, e-signature, orders/invoices/Sage, discount approvals, open tracking, reminders beyond "Hoy", multi-currency (see proposal Non-goals).
- A background job queue: all sending is synchronous in the request; the outbox is a record, not a worker.
- Editing anything on a sent version — every post-send change is a new version.

## Decisions

### 1. Numbering: `quote_counters` row locked per year, number assigned at creation

A table `quote_counters(year smallint PK, last_number int)`. Creating a quote runs, inside the same transaction as the insert:

```sql
INSERT INTO quote_counters (year, last_number) VALUES (:year, 1)
ON CONFLICT (year) DO UPDATE SET last_number = quote_counters.last_number + 1
RETURNING last_number;
```

The upsert takes a row lock, so concurrent creates serialize per year and numbers are unique; if the surrounding transaction rolls back, the increment rolls back too, so there are no gaps. The year is the **Europe/Madrid** calendar year at creation. The stored fields are `year`, `number` (int) and the derived `quote_number` string `P-{year}-{number:04d}` (unique index on `(year, number)`).

- *Discarded — PostgreSQL sequence per year*: sequences are non-transactional, so any rollback leaves gaps, and yearly reset requires DDL at runtime.
- *Discarded — `max(number)+1`*: race under concurrency, needs `SERIALIZABLE` or advisory locks for correctness.
- *Discarded — UUID only*: the business requires a human quote number on the PDF and on the phone.

### 2. Versions: one row per version under a shared number; latest version is the live one

Each version is a full `quotes` row: `quote_number` + `version` (unique together), own lines, own status. `display_number` is `P-2026-0001` for version 1 and `P-2026-0001-v2` onwards. `revise` copies the latest version's content into a new `draft` row with `version + 1` and stamps `superseded_at` on the previous row. The "current" version is the row with `superseded_at IS NULL`; lists and sections show only current versions, the quote sheet shows the chain.

- *Discarded — mutable single row + history JSON*: loses line-level immutability and makes "which PDF did they get" unanswerable.
- *Discarded — separate `quote_versions` child table*: every read joins two tables for no benefit; a version IS a quote snapshot.

### 3. Status machine kept minimal: `draft → sent → accepted | rejected`

One enum, four states, plus derived flags: **expired** is `status = 'sent' AND valid_until < today` (visual only, computed in queries, never stored) and **superseded** is `superseded_at IS NOT NULL`. Transitions are domain commands: `send` (draft→sent; stamps `sent_at`, `valid_until` default sent + 30 days if not set), `accept` (sent→accepted; stamps `accepted_at`), `reject` (sent→rejected; stamps `rejected_at`, optional `rejection_note`), `revise` (any sent/rejected current version → new draft version). Drafts can be deleted; sent versions never.

- *Discarded — `expired` / `superseded` as enum states*: they are time- and chain-derived, storing them needs a scanner job and invites drift (the at-risk scanner exists because at-risk is genuinely stateful; expiry is pure arithmetic).

### 4. Money: `numeric` everywhere, per-line rounding, totals grouped by VAT rate

Lines store `quantity numeric(12,2)`, `unit_price numeric(12,2)`, `discount_percent numeric(5,2)` (0–100), `vat_rate numeric(4,2)` constrained to {21.00, 10.00, 4.00, 0.00}, and role-gated `unit_cost` snapshot. Domain computes per line: `base = round2(quantity × unit_price × (1 − discount/100))`, `vat = round2(base × rate/100)` with `ROUND_HALF_UP` — the Spanish invoice convention. Quote totals (`total_base`, `total_vat`, `total`) are stored denormalized on the quote row (recomputed by the domain on every line change) so lists and the "Hoy" block never touch lines. VAT breakdown by rate is computed on read for the sheet and the PDF.

- *Discarded — floats or cents-as-int*: the project already standardized on `numeric` + two-decimal-string serialization (`Price`); deviating here would be gratuitous.
- *Discarded — rounding only on totals*: line-level rounding is what appears printed per line; totals must equal the sum of printed lines or the PDF looks wrong to an accountant.

### 5. Line snapshots: quotes denormalize product identity

Quote lines store `product_id` (nullable FK, `ON DELETE SET NULL`) plus snapshot columns `description` (product name at copy time, editable), `product_code` (nullable). Free-text lines are simply lines with `product_id IS NULL`. The catalogue's `is_referenced` check extends to `quote_lines`, so referenced products deactivate instead of delete. Copying from the opportunity maps product lines 1:1 (list price → `unit_price`, current cost → `unit_cost`, discount 0, VAT 21).

- *Discarded — always joining the catalogue for names*: a renamed or deactivated product must not rewrite history on a sent quote.

### 6. PDF: ReportLab (platypus), rendered at send time, bytes stored in `quote_pdfs`

The PDF is generated server-side with **ReportLab** — pure Python, no system libraries, identical output on Windows dev, CI and the container. The layout is a fixed code template (logo, Quermed fiscal data, account + contact block, numbered line table with discount/VAT columns, totals-by-rate box, conditions block, rep signature footer); the only variable content is data plus the editable conditions text. Bytes are written at `send` time to `quote_pdfs(quote_id PK/FK, content bytea, generated_at)` — a separate table so quote queries never drag blob bytes — and served by `GET /quotes/{id}/pdf` (`application/pdf`, filename `P-2026-0001-v2.pdf`). Drafts get an on-the-fly preview render from the same code path (not stored).

- *Discarded — WeasyPrint*: nicest authoring model (HTML/CSS + Jinja2) but requires Pango/Cairo/GTK system libraries — painful on the Windows dev machine and a heavier image; the template is fixed anyway, so HTML flexibility buys little.
- *Discarded — headless Chromium print-to-PDF*: hundreds of MB in the image for one template.
- *Discarded — filesystem/S3 storage*: new infrastructure and backup surface; at Quermed's volume (thousands of quotes/year × ~50–100 KB) bytea rides the existing Postgres backups.

### 7. Email: Microsoft Graph client-credentials via httpx; outbox record; failure never un-sends

`GraphMailer` (infrastructure) does the OAuth2 client-credentials flow against `login.microsoftonline.com/{tenant}` and calls `POST /v1.0/users/{sender_upn}/sendMail` with the PDF as base64 attachment, using `httpx.AsyncClient`. The sender is the acting user's email (their M365 mailbox), which requires tenant-admin consent for application `Mail.Send` plus an application access policy scoping it to the sales mailboxes — documented in `development_guide.md`. Settings: `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, `GRAPH_SENDER_MODE` (`graph` | `off`, default `off`).

`send` is one transaction that freezes the version, stores the PDF and writes a `mail_outbox` row (`quote_id`, `recipients jsonb`, `subject`, `body`, `status`, `error`, `sent_at`); the Graph call happens after commit. Outcomes: `sent`, `failed` (error recorded; quote **stays** sent — the content is correct, only delivery failed; the sheet shows the failure and offers `POST /quotes/{id}/retry-email`, which re-sends the same frozen PDF without creating a version), or `skipped` when mode is `off` (dev/E2E and the explicit "sin email" checkbox in the send dialog — the rep downloads the PDF and sends it manually). A mailer protocol + in-memory fake keeps unit tests offline; integration tests run with mode `off`.

- *Discarded — transactional send (roll back on Graph failure)*: punishes the rep for a transient mail problem and loses the frozen version they still want to download.
- *Discarded — background worker/queue*: real infrastructure (worker, retries, monitoring) for an action the rep triggers interactively and can retry with a button.
- *Discarded — Microsoft Graph SDK dependency*: two HTTPS calls don't justify a heavyweight SDK; `httpx` is already in the stack.

### 8. Accept wins the opportunity and rejects siblings in one transaction

`QuoteService.accept` (application layer) loads the quote, transitions it, then calls `OpportunityService.win(opportunity_id, won_amount=quote.total, occurred_at=accepted date)` and rejects sibling quotes — other quote numbers of the same opportunity whose current version is `draft` or `sent` — stamping `rejection_note = 'superseded by accepted quote P-…'`; every mutation goes through the audit collector (`quote.accepted`, `quote.auto_rejected`, plus the existing `opportunity.won`). Import direction stays clean: `application/quotes` imports `application/opportunities`, never the reverse; opportunity code gains no knowledge of quotes except read-model queries. If the opportunity is already closed, accept fails 409 `opportunity_already_closed` (the rep reopens first — explicit over magical).

- *Discarded — accepting also reopening or double-winning silently*: hides state from the user and creates surprise stage history.
- *Discarded — DB triggers for sibling rejection*: business rules live in the application layer where they are audited and tested.

### 9. Timeline and "Hoy" derive quote events from status timestamps

The timeline union gains three branches — `quote_sent`, `quote_accepted`, `quote_rejected` — selected straight from `quotes` (`sent_at` / `accepted_at` / `rejected_at` of every version, joined to the account through the opportunity), rendered with a `QuoteEventView` (display number, total, opportunity name) following the `StageChangeView` pattern with server-side Spanish titles. "Hoy" gains `expiring_quotes`: current versions with `status = 'sent'`, owned (via opportunity owner) by the user, `valid_until` within 7 days — composed in the `/me/today` router like `tenders_due`.

- *Discarded — a `quote_events` table*: the status timestamps already are the events; a second table would need synchronization for zero new information.

### 10. Condition defaults and email template in `app_settings`

A generic `app_settings(key text PK, value jsonb, updated_at)` table with two keys: `quote_conditions_defaults` ({validez_dias, plazo_entrega, forma_pago, garantia}) and `quote_email_template` ({subject, body} with `{numero}`, `{centro}`, `{comercial}` placeholders). Admin-only `GET/PUT /api/v1/quote-settings` (both keys in one payload). Quote creation copies the defaults into the quote's own `conditions jsonb`; the send dialog interpolates the template client-side so the rep sees and edits the final text.

- *Discarded — env settings*: the requirement is admin-editable at runtime, not deploy-time.
- *Discarded — dedicated columns/table per setting*: two structured values don't warrant schema churn per future setting; jsonb with Pydantic validation at the edge keeps it typed where it matters.

### 11. Permissions: writer helper + role-gated serialization

`ensure_quote_writer(actor, opportunity, action)`: `create`/`update_draft`/`delete_draft` allow owner, manager, admin **and back_office**; `send`/`accept`/`reject`/`revise` allow owner, manager, admin only (back_office gets 403 `quote_action_forbidden`). Visibility is the account scope, exactly like opportunities. Cost/margin (`unit_cost`, per-line and total margin) are serialized only for `sales_manager`/`admin`, reusing the catalogue's role-gated field pattern; other roles receive the schema without those fields.

### 12. Frontend: `features/quotes`, routes `/presupuestos`, PDF via authenticated blob

New feature folder with the established shape (api/queries/schemas/hooks/components/pages/index). Routes: `/presupuestos` (list with status/owner/expiring filters), `/presupuestos/:quoteId` (sheet: status + versions chain + lines + totals + conditions + email status + actions), `nueva` is always contextual from an opportunity (`/oportunidades/:id` section button), edit only for drafts. The send dialog (recipients multi-select pre-filled from account contacts with email, subject/body from the interpolated template, "sin email" checkbox) lives over the sheet. Totals recompute live in the form with the same rounding rules as the backend (shared pure helper, unit-tested against backend vectors). PDF download/preview uses an authenticated `fetch` → `URL.createObjectURL` helper since `<a href>` can't carry the JWT. Opportunity sheet and account 360º render a `QuotesSection`; "Hoy" renders the expiring block; admin settings screen extends the existing admin area. No new frontend dependencies.

## Risks / Trade-offs

- **Graph tenant setup is external**: application `Mail.Send` needs admin consent and an application access policy; until IT grants it, production runs with `GRAPH_SENDER_MODE=off` (manual PDF sending) — the feature degrades, it doesn't block. Setup steps go in `development_guide.md`.
- **Synchronous Graph call in the request**: a slow Graph adds latency to `send` (bounded by httpx timeout, 10 s); acceptable for an interactive, occasional action. Mitigation if it ever hurts: move the call behind the outbox with a scanner, without schema change.
- **ReportLab layout is code**: template tweaks need a developer. Accepted: the business chose a fixed template; a golden-file PDF test (text extraction, not pixels) keeps regressions visible.
- **bytea growth**: ~100 KB × thousands of quotes/year is tens of MB/year — trivial now; `quote_pdfs` is a clean seam to move to object storage later.
- **Counter serialization**: concurrent quote creates briefly queue on the year row; at Quermed's volume contention is negligible.
- **Duplicate rounding logic FE/BE**: the live totals in the form must match the backend; mitigated with one shared vector test fixture asserted on both sides.
- **Year boundary**: a quote created 31-Dec 23:59 Europe/Madrid gets that year's number even if sent in January — matches how the business numbers paper quotes today.

### Implementation notes (recorded during /opsx:apply)

- **Input rounding unified to HALF UP**: `_money`/`_quantity` normalise raw values with `ROUND_HALF_UP` (not Decimal's default HALF EVEN) so the frontend `toHundredths` mirror produces identical cents for 3+ decimal inputs; the shared vector fixture (`backend/tests/fixtures/quote_totals_vectors.json`, mirrored at `frontend/src/features/quotes/__fixtures__/`) asserts both sides.
- **API versioning names**: the optimistic-locking counter is exposed as `version` (used with `If-Match`, consistent with every other aggregate) and the document version as `revision`; `display_number` carries the printed `-vN`. No `ETag` headers on quote reads — the project-wide pattern is the `version` field in the body.
- **`GET /quote-settings` is open to any authenticated user** (PUT stays admin-only): the send dialog interpolates the email template client-side, so reps must read it. The delta spec was amended accordingly.
- **Domain gained `supersede_by_accept`**: sibling auto-rejection on accept also covers `draft` siblings, which the plain `reject` command (sent-only) refuses by design.
- **Settings service split**: `QuoteSettingsService` lives beside `QuoteService` instead of inside it — the admin screen needs neither mailer nor renderer.
- **Task 6.1 satisfied via API fixtures, not the seed**: `e2e_seed` still only creates the admin; `e2e/fixtures/app.ts` gained `createAccount`/`createOpportunity`/`addOpportunityLine`/`fetchQuotePdf`/`listTerritories`, and `quotes.spec.ts` reuses an existing territory when the persistent local DB has no free provinces. Graph mode `off` is the settings default, so compose needs no extra env.
- **Counter concurrency test uses savepoints**: the integration test proves transactional gaplessness (allocation + rollback) inside the single-session test fixture; true cross-session serialisation rests on the `ON CONFLICT` row lock, which cannot be exercised under the savepoint fixture without deadlocking it.
- **`httpx` promoted to a runtime dependency** (it was dev-only; only the Docker build caught it) and axe fixes: scrollable regions (`ResponsiveFormContainer`, the quote lines table) carry `tabIndex={0}`.
