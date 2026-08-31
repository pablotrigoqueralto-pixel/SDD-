# search-api

## Purpose
The scoped global search endpoint: grouped, capped results across accounts, contacts, opportunities and quotes, accent-tolerant trigram name matching and exact identifier routing (CIF, phone, email, quote number, tender reference).

## Requirements

### Requirement: Global search endpoint
`GET /api/v1/search?q=` SHALL answer with typed groups — `accounts`, `contacts`, `opportunities`, `quotes` — each carrying items, a `total` and `has_more`, capped server-side at 5 items per group (10 for contacts). Queries shorter than 2 characters SHALL return empty groups without querying. Every group SHALL be filtered by the caller's account-based visibility scope exactly as the corresponding list endpoints are, and quote results SHALL be current versions only. Each item SHALL carry what its row needs: id, label, and per type the account name, status/stage badge data and amount or quote number.

#### Scenario: Grouped and capped
- **WHEN** a manager searches a term matching 8 accounts and 2 quotes
- **THEN** the response has 5 accounts with `total = 8` and `has_more = true`, the 2 quotes with `has_more = false`, and empty contact/opportunity groups

#### Scenario: Scope honoured
- **WHEN** a rep searches the name of a centre outside their territory
- **THEN** every group comes back empty, exactly as the lists would hide it

#### Scenario: Too short
- **WHEN** `q` is one character
- **THEN** the endpoint returns empty groups and performs no search

### Requirement: Name matching with accent tolerance
Name matching SHALL use trigram `ILIKE` over unaccented expressions (an IMMUTABLE `f_unaccent` wrapper with expression GIN indexes on account names, contact full names and opportunity names, created by the change's migration together with the `unaccent` extension), so accented and unaccented spellings find each other. Opportunities SHALL additionally match `tender_reference`, and quotes SHALL match through their account's name (so a centre search also surfaces its current quotes). Accounts SHALL order by similarity; other groups by recency.

#### Scenario: Accents ignored both ways
- **WHEN** a user searches "perez"
- **THEN** the contact "Ana Pérez" is found; searching "Pérez" also finds a contact stored as "Perez"

#### Scenario: Tender reference
- **WHEN** a user searches "EXP-2026"
- **THEN** open tenders whose `tender_reference` contains it appear in the opportunities group

### Requirement: Identifier routing
Before name matching, the query SHALL be inspected once and routed: `P-YYYY-NNNN` (full or partial number, optional `-vN`) → quotes by `year`/`number`; a term containing `@` → exact/prefix on contact and account emails; a CIF/NIF-shaped term → normalised comparison against `accounts.tax_id`; 7 or more digits after stripping spaces, dots, dashes and `+` → digit-only comparison against every entry of the account and contact phone lists, whatever its label. Identifier matches SHALL appear in their entity's group alongside any name matches.

#### Scenario: Quote number
- **WHEN** a user searches "P-2026-0003"
- **THEN** the quotes group contains that quote's current version and other groups stay name-matched

#### Scenario: Phone with separators
- **WHEN** a user searches "612 34 56 78"
- **THEN** the contact whose mobile is stored as "+34612345678" is found

#### Scenario: Any labelled phone matches
- **WHEN** a user searches the number stored as the centre's "Servicio de vascular" phone, not its primary one
- **THEN** the centre appears in the accounts group

#### Scenario: CIF
- **WHEN** a user searches "b-12345678"
- **THEN** the account with `tax_id` "B12345678" is found

### Requirement: Search OpenAPI documentation
The search endpoint and its response schemas SHALL be present in the exported `api-spec.yml` with no CI drift.

#### Scenario: Spec export in sync
- **WHEN** the OpenAPI exporter runs
- **THEN** `ai-specs/specs/api-spec.yml` contains `/search` and the grouped result schemas
