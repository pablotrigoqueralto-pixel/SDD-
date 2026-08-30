## 1. Backend — domain (TDD)

- [x] 1.1 [TEST] Write failing unit tests for the `Quote` aggregate: creation from opportunity data (line copy defaults: discount 0, VAT 21, snapshots), line math per the spec vector (3 × 33.33 − 10% → base 89.99, VAT 18.90), totals recompute on line mutations, VAT-rate whitelist, status machine (`send`/`accept`/`reject` transitions, `quote_not_editable` on sent mutations and draft-only delete), `revise` copy + `superseded_at` rules (`quote_superseded`, accepted not revisable), `valid_until` default from `conditions.validez_dias`, `display_number`
- [x] 1.2 [BE] Implement `app/domain/quotes/` (`entities.py`, `errors.py`, `repository.py` protocol): `Quote` aggregate with `QuoteLine`, commands `update_draft`/`sync_lines`/`send`/`accept`/`reject`/`revise_snapshot`, `round_half_up` money helpers, derived `is_expired`, VAT breakdown by rate — until 1.1 passes
- [x] 1.3 [TEST] Extend the money tests with a shared rounding vector fixture (JSON in `tests/` mirrored later by the frontend) covering discounts, each VAT rate and sums-by-rate

## 2. Backend — persistence

- [x] 2.1 [BE] Add models `QuoteModel`, `QuoteLineModel`, `QuoteCounterModel`, `QuotePdfModel`, `MailOutboxModel`, `AppSettingModel` in `app/infrastructure/db/models/quotes.py` (status enum, checks: vat_rate whitelist, discount 0–100, quantity > 0, `(year, number, version)` unique, timestamps consistent with status)
- [x] 2.2 [BE] Migration `0007_quotes`: tables, enum, partial indexes (current versions per opportunity/account lookup, `status = 'sent'` + `valid_until` for expiring), named FKs, grants, seed `app_settings` defaults (`quote_conditions_defaults`, `quote_email_template`)
- [x] 2.3 [TEST] Write failing integration tests for `QuoteRepository`: atomic counter upsert (two sessions → consecutive numbers; savepoint rollback leaves no gap), persist/load round-trip with lines, `_sync_lines` replace semantics, current-version filtering
- [x] 2.4 [BE] Implement `app/infrastructure/db/repositories/quotes.py` (+ counter allocation with Europe/Madrid year, PDF store, outbox writes, settings repo) — until 2.3 passes
- [x] 2.5 [BE] Extend catalogue `is_referenced` to `quote_lines` and adjust its integration test

## 3. Backend — application services (TDD)

- [x] 3.1 [TEST] Write failing service tests with in-memory fakes: create-from-opportunity (defaults, closed opportunity 409, back_office allowed), draft update/delete permissions, `ensure_quote_writer` matrix (back_office 403 on lifecycle), send (freeze + PDF stored + outbox `sent`/`failed`/`skipped`; Graph failure keeps quote sent; recipients required unless skipping), accept (wins opportunity with total, rejects siblings with note, `opportunity_already_closed`), reject, revise, retry-email (`email_retry_not_available`), settings service (admin only, copy-not-reference on create)
- [x] 3.2 [BE] Implement `app/application/quotes/` (`commands.py`, `service.py`, `queries.py`) composing `OpportunityService.win`, audit events (`quote.*` per spec), and the mailer protocol — until 3.1 passes
- [x] 3.3 [BE] Implement `PdfRenderer` (ReportLab platypus fixed template) in `app/infrastructure/pdf/quotes.py`; [TEST] golden-content test extracting text from the generated PDF (number, lines, totals by rate, conditions)
- [x] 3.4 [BE] Implement `GraphMailer` in `app/infrastructure/mail/graph.py` (httpx client-credentials + `sendMail` with base64 attachment, 10 s timeout) plus `NullMailer` for mode `off`; settings `GRAPH_TENANT_ID/CLIENT_ID/CLIENT_SECRET/SENDER_MODE`; [TEST] unit test the request building and error mapping with a mocked transport

## 4. Backend — API

- [x] 4.1 [TEST] Write failing API integration tests: list with filters (`status`, `expiring`, `q`, scope 404), detail with version chain + `is_expired` + role-gated cost, create/PATCH lines under `If-Match` (428/409), send (skip_email path; recipients 422), accept full trail (opportunity won + sibling rejected + audit rows), reject, revise 201, retry 409 without failure, PDF endpoints (draft preview vs stored bytes, filename), quote-settings admin gate
- [x] 4.2 [BE] Implement `app/schemas/quotes.py` (role-gated cost serialization) and `app/api/v1/quotes.py` (+ `/opportunities/{id}/quotes`, `/quote-settings`); wire router — until 4.1 passes
- [x] 4.3 [BE] Extend `OpportunityRead.quotes_count`, timeline union with `quote_sent|quote_accepted|quote_rejected` (`QuoteEventView`, Spanish titles), `/me/today` `expiring_quotes`; [TEST] extend timeline/today integration tests
- [x] 4.4 [BE] Export OpenAPI (`python -m app.tooling.export_openapi ../ai-specs/specs/api-spec.yml`) and verify no drift

## 5. Frontend — feature quotes

- [x] 5.1 [FE] Regenerate API types (`npm run api:types`); create `features/quotes` scaffold (`api.ts`, `queries.ts`, `schemas.ts`, `hooks.ts`, `index.ts`) with zod schemas (quote form, lines with discount/VAT, send dialog) and the shared rounding helper `computeQuoteTotals`
- [x] 5.2 [TEST] Component test: `computeQuoteTotals` against the shared backend vector fixture (values must match exactly)
- [x] 5.3 [FE] MSW fixtures + handlers for quotes (list, detail with versions, send/accept/reject/revise, settings, outbox states)
- [x] 5.4 [FE] Components: `QuoteStatusBadge` (with Caducado visual), `QuoteLinesEditor` (product picker/free text, discount, VAT select, live per-line base), `ConditionsFields`, `TotalsBox` (VAT breakdown), `QuoteForm`
- [x] 5.5 [FE] `SendQuoteDialog` (recipients from account contacts, template interpolation `{numero}/{centro}/{comercial}`, sin-email checkbox, validity date, PDF preview link) and `AcceptDialog`/`RejectDialog` with the consequence copy
- [x] 5.6 [FE] Pages: `QuotesListPage` (`/presupuestos`, filters + search, table/cards), `QuoteSheetPage` (`/presupuestos/:quoteId`: versions chain, email status + retry, role/status-gated actions, authenticated PDF download helper), routes + navigation entry, i18n namespace `quotes`, error codes
- [x] 5.7 [FE] Integrations: `QuotesSection` on opportunity sheet (Nuevo presupuesto on open only) and account 360º; Hoy "Presupuestos por caducar" block; timeline rendering for `quote_*` kinds; admin `QuoteSettingsPage`
- [x] 5.8 [TEST] Component tests (MSW): list + expired badge, sheet actions per role/status, form live totals, send dialog validation + interpolation, accept consequence + request body, settings page; back_office sees no lifecycle actions

## 6. E2E and quality gates

- [x] 6.1 [BE] Extend `e2e_seed` with a quote-ready opportunity (lines) and Graph mode off
- [x] 6.2 [E2E] `e2e/quotes.spec.ts` (desktop + mobile + axe): create quote from opportunity → edit lines with discount/VAT → send (sin email) → verify PDF download responds → accept → opportunity shows Ganada; reject path on a second quote
- [x] 6.3 [TEST] Full quality gates: backend `ruff` + `mypy --strict` + `pytest`; frontend `eslint` + `tsc` + `vitest` + `prettier --write` on touched files
- [x] 6.4 [BE] Compose smoke: `docker compose up -d --build`, health + `/api/v1/quotes` + CORS + frontend serve, run Playwright suite with rate-limit env, then `docker compose down`

## 7. Documentation

- [x] 7.1 [BE] Update `ai-specs/specs/data-model.md` (models 31+: quotes, quote_lines, quote_counters, quote_pdfs, mail_outbox, app_settings; ER; numbering + rounding principles) and `development_guide.md` (numbering, PDF rendering, Graph setup + application access policy, outbox/retry, GRAPH_* env)
- [x] 7.2 [BE] Confirm `api-spec.yml` committed from the exporter (never hand-edited)
