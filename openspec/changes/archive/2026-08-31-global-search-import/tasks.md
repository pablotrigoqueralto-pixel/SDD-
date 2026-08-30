## 1. Backend — search (TDD)

- [x] 1.1 [BE] Migration `0008_search_import`: `CREATE EXTENSION IF NOT EXISTS unaccent`, IMMUTABLE SQL wrapper `f_unaccent(text)`, expression GIN trigram indexes on `f_unaccent(accounts.name)`, `f_unaccent(contacts.first_name || ' ' || last_name)`, `f_unaccent(opportunities.name)`; downgrade drops indexes + function (extension stays, like pg_trgm)
- [x] 1.2 [TEST] Write failing unit tests for the query router (`app/application/search/router.py` helpers): `P-2026-0003`/`P-2026-0003-v2`/partial `P-2026` → quote route, `@` → email route, CIF/NIF shapes → tax-id route with normalisation, `612 34 56 78`/`+34-612...` → phone digits route, plain text → name route; min-length rule
- [x] 1.3 [BE] Implement the router helpers — until 1.2 passes
- [x] 1.4 [TEST] Write failing integration tests for `SearchQueries` (`tests/integration/api/test_search_api.py` covers most; queries-level test in `tests/integration/repositories/test_search_queries.py`): accent tolerance both ways ("perez" ↔ "Pérez"), per-group caps + `total`/`has_more`, scope filtering (rep vs manager), quote-number hit, phone-with-separators hit, tender reference hit, current-versions-only for quotes
- [x] 1.5 [BE] Implement `app/application/search/queries.py` (four bounded scoped SELECTs, ordering: accounts by similarity, rest by recency) — until 1.4 passes

## 2. Backend — search API

- [x] 2.1 [TEST] Write failing API tests: `GET /search?q=` grouped response shape, empty groups under 2 chars, scope 404-equivalent (empty groups for out-of-scope), auth required
- [x] 2.2 [BE] Implement `app/schemas/search.py` + `app/api/v1/search.py`, wire router — until 2.1 passes

## 3. Backend — import infrastructure (TDD)

- [x] 3.1 [TEST] Write failing unit tests for `TabularReader` (`app/infrastructure/imports/reader.py`): CSV `;` and `,` sniffing, UTF-8/BOM and cp1252 fallback, `.xlsx` via openpyxl, header alias mapping (case/accent-insensitive, `código`→`sku`, `pvp`→`list_price`, `cif`→`tax_id`), missing-required-header error, empty-row skipping, value trimming, row cap enforcement
- [x] 3.2 [BE] Add `openpyxl` to the **main** dependency group; implement the reader — until 3.1 passes
- [x] 3.3 [TEST] Write failing unit tests for the product row mapper: Spanish decimal commas in prices, brand/family resolution by case-insensitive name (unknown → row error), `ProductImportRow` construction
- [x] 3.4 [BE] Implement `app/application/imports/products.py` (loop over `upsert_by_sku`, per-row outcomes `created|updated|unchanged|error`, dry-run mode, single-transaction apply, audit event with counts) — until 3.3 passes plus service-level fakes tests
- [x] 3.5 [TEST] Write failing service tests for the accounts importer: CIF match (normalisation), name fallback (unaccent+casefold+collapse), create path uses account defaults (territory from province, owner by rep email), embedded `contact_*` columns (create/update by email, fallback full name, repeat-account rows), row errors reuse form validation messages, never-delete, idempotent re-run → `unchanged`
- [x] 3.6 [BE] Implement `app/application/imports/accounts.py` — until 3.5 passes

## 4. Backend — import API

- [x] 4.1 [TEST] Write failing API tests: multipart upload to both endpoints, `dry_run=true` writes nothing, `dry_run=false` applies valid rows + report, 422 on oversized/unreadable/missing-header files, 403 for `sales_rep`/`sales_manager`, audit rows only on confirmed runs (`import.products_executed`/`import.accounts_executed` with counts + filename)
- [x] 4.2 [BE] Implement `app/schemas/imports.py` + endpoints (`/products/import` in the products router, `/accounts/import` in the accounts router), role dependency — until 4.1 passes
- [x] 4.3 [BE] Export OpenAPI (`uv run python -m app.tooling.export_openapi ../ai-specs/specs/api-spec.yml`) and verify no drift

## 5. Frontend — search

- [x] 5.1 [FE] Regenerate API types (`npm run api:types`); scaffold `features/search` (`api.ts`, `queries.ts`, `recents.ts` with try/catch localStorage helpers, `index.ts`); i18n namespace `search`
- [x] 5.2 [FE] `SearchPage` (`/buscar`): autofocused box, min 2 chars + 300 ms debounce, grouped sections reusing badge/amount components via feature indexes, "Ver todas" links with `q`, empty state; recents block (8 searches + 8 records) shown before typing
- [x] 5.3 [FE] Navigation swap: "Buscar" takes the fifth slot for every role; "Administración" becomes the first card in Más (admins); route `/buscar` in the router
- [x] 5.4 [TEST] Component tests (MSW): grouped rendering + row navigation, "Ver todas" URL with the term, debounce fires one request, recents persist/restore from localStorage and survive a failing localStorage, nav shows Buscar for rep and Admin card in Más for admin

## 6. Frontend — imports

- [x] 6.1 [FE] Scaffold `features/imports` (`api.ts` multipart upload with `dry_run`, `queries.ts`, `index.ts`); i18n namespace `imports`; error codes if new ones exist
- [x] 6.2 [FE] Shared `ImportFlow` component (file picker → preview: outcome totals + row table with error rows first → confirm with pending counts → summary + client-generated error CSV download) and pages `/importar/catalogo`, `/importar/centros` with the expected-columns help text
- [x] 6.3 [FE] Entries: Admin hub card (admin) and Más cards (back office); role gates on the routes
- [x] 6.4 [TEST] Component tests (MSW): preview renders outcomes without confirming, confirm posts `dry_run=false` and shows applied totals, error CSV Blob content, rep sees "Sin permiso", back office sees the Más entries

## 7. E2E and quality gates

- [x] 7.1 [E2E] `e2e/search-import.spec.ts` (desktop + mobile + axe): back office imports a small catalogue CSV (preview → confirm → counts); rep searches the imported product's centre by partial accented name → opens the 360º; searches a quote number → opens the sheet; recents show the visited record
- [x] 7.2 [TEST] Full gates: backend `ruff` + `mypy --strict` + `pytest`; frontend `eslint` + `tsc -p tsconfig.app.json` + `vitest` + `prettier --write` on touched files
- [x] 7.3 [BE] Compose smoke: `docker compose up -d --build`, health + `/api/v1/search` auth-gated + frontend serve, full Playwright suite with the rate-limit env, `docker compose down`

## 8. Documentation

- [x] 8.1 [BE] Update `development_guide.md` (import file formats with the Spanish header aliases, how to export from Sage/Excel, the `unaccent` managed-PG note next to the pg_trgm one) and `data-model.md` (migration note for `0008_search_import`, new expression indexes)
- [x] 8.2 [BE] Confirm `api-spec.yml` committed from the exporter (never hand-edited)
