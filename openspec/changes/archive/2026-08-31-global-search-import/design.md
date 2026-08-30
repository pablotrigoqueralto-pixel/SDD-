## Context

Change 03 left a trigram-indexed account search and a navigation comment reserving a "Buscar" slot; change 05 left the import contract (`ProductImportRow`, `ProductService.upsert_by_sku`) documented in the OpenAPI but with no endpoint; change 07 added quotes whose printed numbers reps will read over the phone. The backend keeps the layered architecture, `ScopeFilter`/`scoped_accounts` visibility, RFC 7807 errors and the audit collector; the frontend keeps feature folders, TanStack Query and MSW-backed tests.

The new ground here is modest on purpose: a read-only cross-entity query and two file parsers. No new aggregates, and — if the design below holds — no new tables.

scope:
  backend: true
  frontend: true
design-linked: false

## Goals / Non-Goals

**Goals:**

- One search request answers with grouped, capped, scope-filtered results across accounts, contacts, opportunities and quotes in well under 500 ms.
- Accent- and typo-tolerant name matching, plus exact-identifier routing (CIF, phone, email, quote number, tender reference).
- Idempotent importers: re-running the same file is safe (create-or-update, never delete), with a dry-run preview and a per-row report.
- Excel in, no infrastructure out: parse the user's real files without adding job queues, storage buckets or search engines.

**Non-Goals:**

- Full-text search over notes/conditions, relevance ranking, or a search engine service.
- Async/background imports, stored upload files, or server-side import history beyond audit events.
- Automatic Sage synchronisation (the manual importer is the contract a future sync reuses).

## Decisions

### 1. Search is four scoped SELECTs behind one endpoint — no search table, no engine

`GET /api/v1/search?q=` runs one bounded query per entity (accounts, contacts, opportunities, quotes), each reusing the exact visibility predicate the lists already use (`scoped_accounts`; contacts/opportunities/quotes join through their account) and each capped server-side (5 per group; contacts 10). The response is typed groups with `total` and `has_more` per group, so the screen can offer "ver todas" into the existing filtered lists. Four small index-backed queries stay comfortably under the 500 ms budget at Quermed's volumes.

- *Discarded — one `UNION ALL` over a common shape*: loses per-group caps and typed payloads, and forces the least-common-denominator row.
- *Discarded — a `search_documents` table maintained by triggers*: a second copy of the truth that can drift, for a dataset that fits in four indexed queries.
- *Discarded — an external engine (Meilisearch/Typesense)*: a whole service to operate for a four-entity CRM search.

### 2. Accent tolerance via `unaccent` expression indexes; identifiers routed by pattern

Name matching uses `pg_trgm` ILIKE (as the account list does) over a new IMMUTABLE wrapper `f_unaccent(text)` (plain `unaccent()` is only STABLE, so it cannot be indexed), with expression GIN indexes on `accounts.name`, `contacts.first_name || ' ' || last_name` and `opportunities.name` — migration `0008_search_import`, which also creates the `unaccent` extension (core contrib, same caveat as `pg_trgm` on managed PostgreSQL).

Before the name search runs, the query is inspected once:
- `P-YYYY-NNNN(-vN)?` (also partial `P-YYYY-…`) → quotes by `year`/`number` directly;
- contains `@` → exact/prefix on `contacts.email` and `accounts.email`;
- looks like a CIF/NIF (letter+digits pattern) → normalised comparison against `accounts.tax_id`;
- 7+ digits after stripping separators → digit-only comparison against `accounts.phone`, `contacts.mobile`, `contacts.landline` (regexp-stripped; a sequential scan over thousands of contacts is fine, no index needed);
- anything else, and always additionally → trigram name matching; opportunities also match `tender_reference` ILIKE.

- *Discarded — plain ILIKE without `unaccent`*: "perez" would miss "Pérez", breaking the agreed behaviour.
- *Discarded — normalised shadow columns*: write-path complexity and drift; the expression index gives the same plan without touching writes.
- *Discarded — full fuzzy ranking*: caps + type grouping make ordering obvious (accounts by similarity, the rest by recency); tuning a ranker buys little at this scale.

### 3. Recents live on the device

The Buscar page stores the last 8 submitted searches and the last 8 opened results (`{kind, id, label}`) in `localStorage`, written when the user opens a result. Nothing is sent to or stored on the server.

- *Discarded — server-side recents*: personal navigation history in the DB adds a GDPR surface and scope questions for a convenience feature; the decision was explicitly device-local.

### 4. Imports are synchronous multipart uploads with a hard row cap

`POST /api/v1/products/import` and `POST /api/v1/accounts/import` take a multipart file plus `dry_run` (default `true`). The service parses, validates and matches every row, and answers with the full per-row report: `{row, outcome: created|updated|unchanged|error, message?, label}` plus counts. With `dry_run=false` the valid rows are applied inside one transaction (errors are skipped, valid rows commit together) and the same report comes back; the client builds the downloadable error CSV from the response. Files are capped (2 000 data rows, 5 MB) — over the cap the request fails fast with a clear message telling the user to split the file.

- *Discarded — async job + polling/progress*: a queue, a jobs table and a progress UI for files that parse in seconds under the cap.
- *Discarded — storing the uploaded file*: retention/GDPR surface with no need — the report returns everything the user must keep.
- *Discarded — all-or-nothing commits*: one bad row would block a 500-row migration; the agreed flow imports the valid rows and reports the rest.

### 5. File parsing: a small `TabularReader` over CSV and `.xlsx` (openpyxl)

`app/infrastructure/imports/` gains a reader that sniffs CSV delimiter (`;` or `,`) and encoding (UTF-8/BOM, falling back to cp1252 — Sage exports and Spanish Excels) and reads `.xlsx` via **openpyxl** (`read_only=True`, first worksheet). Headers are matched case-insensitively with accents stripped, against both English canonical names and the Spanish aliases the user's files actually carry (e.g. `sku`/`código`, `name`/`nombre`, `list_price`/`pvp`). The header map per importer is documented in `development_guide.md`.

- *Discarded — CSV-only*: forces the user to convert their Excel by hand every time — the exact friction this change removes.
- *Discarded — pandas*: a heavyweight dependency for reading two flat tables.

### 6. Product rows go through the change-05 contract untouched

The catalogue importer is a thin loop over `ProductImportRow` → `ProductService.upsert_by_sku`: match by normalised SKU, update the fields present in the file, `unchanged` when nothing differs, never delete or deactivate. Unknown brand/family names in the file resolve by case-insensitive name lookup; misses are row errors (the importer never creates reference data).

- *Discarded — a parallel import path*: the contract exists precisely so import and API writes share validation and audit.

### 7. Account rows may embed one contact; matching is CIF-first

One sheet, one row per account — or per account+contact when the optional `contact_*` columns are filled (repeat the account columns to add several contacts). Accounts match by normalised CIF (uppercase, separators stripped); without CIF, by normalised exact name (`f_unaccent` + casefold + collapsed spaces); no match → created through the existing `AccountService` defaults (territory from province, owner optional by rep email column, else the territory rules). Contacts match by email within their account, falling back to normalised full name; imported contacts enter with the form's default consent state (pending) — the import is audited and personal data handling follows the change-03 rules.

- *Discarded — two files (accounts, then contacts)*: two uploads and a foreign-key dance for the user; the embedded columns mirror how their Excel already looks.
- *Discarded — fuzzy account matching*: silently merging "Clínica Tambre" into "Clinica Tambre SL" is how imports corrupt data; only CIF and exact normalised name match, everything else creates a row the user can merge by hand.

### 8. Permissions and audit

Both import endpoints require `admin` or `back_office` (403 otherwise). A confirmed run records one audit event — `import.products_executed` / `import.accounts_executed` — with the file name and the created/updated/unchanged/error counts; dry runs record nothing. Search adds no events (reads are not audited, consistent with the rest of the API; contact-detail GDPR logging stays where it is, on the contact read).

### 9. Navigation: Buscar takes the fifth slot; Admin moves into Más

The bottom navigation becomes Hoy · Centros · Pipeline · Buscar · Más for every role. The Admin entry leaves the bar and becomes the first card inside Más (admins only), keeping the five-entry cap that change 03 fixed and matching its "a later change swaps in Buscar" note.

- *Discarded — six entries for admins*: breaks the touch-target budget on small phones.
- *Discarded — Buscar only for non-admins*: admins search too; hiding the primary shortcut from one role is arbitrary.

### 10. Frontend: `features/search` and `features/imports`

Search: an omnibox page (min 2 characters, 300 ms debounce, one in-flight query via TanStack Query) rendering grouped results with the existing badge/amount components via feature `index.ts` imports only, plus the localStorage recents. Imports: one screen per importer sharing an upload → preview table (per-row outcome chips) → confirm → summary flow; the error report downloads as a client-generated CSV Blob. Routes `/buscar`, `/importar/catalogo`, `/importar/centros`; entries from Admin hub (admin) and Más (back office). No new frontend dependencies.

## Risks / Trade-offs

- **`unaccent` on managed PostgreSQL**: like `pg_trgm`, the extension may need a one-off superuser `CREATE EXTENSION`; documented next to the existing note in `development_guide.md`.
- **Phone matching scans contacts**: acceptable at thousands of rows; if it ever shows in latency, a digits expression index is a one-line follow-up.
- **Synchronous imports block the request for a few seconds** on a 2 000-row file: acceptable for an intentional back-office action; the cap keeps the worst case bounded.
- **Header aliases can miss a user's column name**: the preview makes it visible immediately (every row errors on the missing field) and the guide documents the expected headers; aliases are a constant, easy to extend.
- **Duplicate accounts when CIF is absent and names differ slightly**: accepted deliberately (see decision 7) — safer than fuzzy merging; the search screen makes duplicates easy to spot afterwards.
- **`openpyxl` is a new runtime dependency**: pure Python, no system libraries; added to the main dependency group (lesson from `httpx` in change 07).

### Implementation notes (recorded during /opsx:apply)

- **Row-by-row commits instead of one apply transaction**: the importers reuse the existing services untouched (`upsert_by_sku`, `AccountService.create/update`), and those commit per operation by design. The delta spec was amended: idempotent matching (SKU/CIF) is the real safety — a partially applied file is recovered by re-importing.
- **Embedded contacts are written at domain level by the importer** (with `contact.*` audit events): `ContactService` enforces the account-writer rule, which excludes back office; the import endpoint's role gate is the authorisation. Manual contact endpoints keep their rules; the delta spec records this.
- **No owner column in the accounts file**: `AccountService.create`'s territory smart-default already assigns the right rep, and assignment stays a manager action (delta amended). Imports also never rename an account (name is identity when CIF is absent; back office cannot rename anyway).
- **Missing `Tipo` column defaults to the first account type by `sort_order`**; a provided but unknown type is a row error. Unknown `Cargo` values are a per-row message, not an error — the contact imports without a job title.
- **Quotes also match by account name in the search** (delta amended): the quotes group would otherwise only answer to `P-YYYY-NNNN` routes, and a centre search should surface its paperwork.
- **Contact results and recents navigate to the account 360º page** — contacts have no standalone page in the MVP.
- **Alembic autogenerate exclusion**: the raw-SQL `*_unaccent_trgm` expression indexes are filtered via `include_object` in `alembic/env.py`, otherwise `alembic check` proposes dropping them (they exist only in the migration, not in the ORM metadata).
- **Products importer caches brands/families once per run; the accounts importer resolves reference data per row** — fine under the 2 000-row cap, and a straightforward optimisation if imports ever grow.
