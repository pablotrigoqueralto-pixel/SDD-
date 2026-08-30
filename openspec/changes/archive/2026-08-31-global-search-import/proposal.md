## Why

Two frictions remain before the MVP can replace the spreadsheets. First, finding things: a rep who just hung up the phone needs the centre, the contact or the quote number in front of them in seconds, but today each entity has its own list and its own filters — there is no single place to type "Tambre" or "P-2026-0003" and land on the right record. Second, getting the existing data in: the catalogue lives in Sage (change 05 already left the `ProductImportRow` / upsert-by-SKU contract waiting) and the customer base lives in an Excel file; typing hundreds of centres and contacts by hand would kill adoption on day one.

This change delivers both: a global search behind the "Buscar" slot the navigation has reserved since change 03, and two idempotent importers (Sage CSV for the catalogue, Excel for centres and contacts) with a dry-run preview so back office can migrate the real data safely and repeatedly.

Constitution principles served: 30-second interactions (one search box, grouped results, recents on the device), smart defaults (create-or-update matching by SKU/CIF, nothing to configure per run), business vocabulary (Buscar, Importar, Vista previa), territory visibility (search results honour each role's scope), audit of every import, and lists under 500 ms (search reuses the trigram indexes that already back the account and product lists).

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- **Global search API**: one scoped endpoint that searches centres, contacts, opportunities and quotes (products keep their own catalogue search) by name text with accent/typo tolerance (trigram, like the accounts list) **and** by exact identifiers — CIF, phone, email, quote number (`P-2026-0001`) and tender reference. Results come grouped by entity type with a small cap per group and honour the account-based visibility scope of the caller.
- **Buscar screen**: the reserved navigation slot becomes real — a search page with a single box, results grouped by type (each row navigates to its sheet), per-group "see all" links into the existing filtered lists, and, before typing, the device's recent searches and recently visited records (localStorage).
- **Catalogue importer**: upload the Sage CSV export against the change-05 contract (`ProductImportRow`, matching by normalised SKU). Dry-run preview reports each row as create / update / unchanged / error with the reason; confirming imports the valid rows and offers the error rows as a downloadable report to fix and re-import. Never deletes.
- **Accounts & contacts importer**: upload the customer Excel (or CSV); accounts match by CIF, falling back to normalised exact name, contacts by email within their account. Same dry-run → confirm → error-report flow, same create-or-update semantics; owners/territories resolve through the existing account defaulting rules.
- **Permissions and audit**: importing is for `admin` and `back_office` (screen under Admin for admins, under Más for back office); every confirmed import records audit events with row counts and the acting user.

## Non-goals

- No product search in the global box — the catalogue keeps its richer dedicated search.
- No search inside long text (activity notes, quote conditions) and no full-text ranking engine; matching stays names + identifiers.
- No scheduled or automatic synchronisation with Sage — importing is a manual, repeatable action (a sync can build on the same contract later).
- No export functionality; this change only brings data in.
- No import of activities, opportunities or quotes — only catalogue, centres and contacts.
- No server-side storage of recent searches — recents live on the device.

## Roles and territory visibility

| Role | Search | Import |
|---|---|---|
| `sales_rep` | Searches within their territory/division scope, exactly like the lists. | No. |
| `sales_manager` | Searches everything. | No. |
| `back_office` | Searches everything (staff visibility, read-only as today). | Yes — both importers, from Más. |
| `admin` | Searches everything. | Yes — both importers, from Admin. |

## Capabilities

### New Capabilities
- `search-api`: the scoped global search endpoint — grouped, capped results across the four entities, trigram name matching plus exact identifier matching.
- `search-screens`: the Buscar page on the reserved navigation slot, grouped results, "see all" hand-offs to the filtered lists and device-local recents.
- `import-api`: catalogue and accounts/contacts import endpoints with dry-run preview, create-or-update matching (SKU / CIF), per-row outcomes, error report and role gating.
- `import-screens`: the import screens for admin and back office — file upload, preview table with per-row outcomes, confirmation and error-report download.

### Modified Capabilities
- `app-shell`: the bottom navigation gains the real "Buscar" entry (Hoy · Centros · Pipeline · Buscar · Más/Admin).
- `product-api`: the documented-only `ProductImportRow` contract becomes the live `/products/import` endpoint.
- `account-contact-api`: gains the accounts/contacts import endpoint reusing the creation defaults (territory from province, smart owner rules).
- `audit-log`: events `import.products_executed` and `import.accounts_executed` (row counts, file name, acting user).

## Impact

- New API: `GET /api/v1/search`, `POST /api/v1/products/import`, `POST /api/v1/accounts/import` (both importers with a `dry_run` mode).
- No new tables expected: search reads existing ones (reusing the `pg_trgm` indexes; quotes/opportunities may need one or two supporting indexes) and imports write through the existing services; audit events carry the run evidence. Confirmed in design.
- Possible new backend dependency for reading `.xlsx` (e.g. `openpyxl`) — decided in design (CSV-only would avoid it).
- Frontend: `features/search` and `features/imports`, navigation update, i18n namespaces `search` and `imports`.
- Documentation: `api-spec.yml` (exporter), `data-model.md` only if indexes/tables change, `development_guide.md` (import formats and how to export from Sage/Excel).
