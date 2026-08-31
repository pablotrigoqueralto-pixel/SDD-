## Context

Everything this change needs has a precedent to copy. `job_titles` is a reference catalogue with a code, a Spanish name, a sort order and an active flag, seeded insert-only so admin edits survive re-seeding, and served inside the reference bundle. `AccountQueries.list_page` already shows how a scoped, filtered, paginated list is built, and `AccountListPage` already keeps its filter state in the URL with `useSearchParams`. Contact visibility is not its own rule: a contact is visible when its account is, and `scoped_accounts` expresses exactly that.

What does not exist is any way to read contacts across accounts: there is no `GET /contacts` and no `/contactos` route. And `contacts.division_id` is presented in the UI as "Especialidad", which is the mislabel this change removes.

scope:
  backend: true
  frontend: true
design-linked: false

## Goals / Non-Goals

**Goals:**
- A specialty catalogue that reads like the job titles one, so admins meet no new concepts.
- A contact carries the specialty it actually practises; divisions stop pretending to be one.
- "All the neurologists in Madrid" answerable in two taps and shareable as a URL.
- Migrate existing data without inventing a single specialty.

**Non-Goals:** everything in the proposal (several specialties per contact, hierarchy, admin CRUD screen — change 14, specialties typed on the account, saved searches).

## Decisions

### D1. `specialties` is a catalogue table shaped exactly like `job_titles`

`id`, `code` (unique), `name_es` (CITEXT unique), `sort_order`, `is_active`, timestamps and version. Seeded insert-only by code with the twelve agreed entries, so renames and deactivations by an admin survive future seeds — the same rule `job_titles` already documents.

- **Discarded — an enum in the database**: adding a specialty would need a migration, and change 14 is about admins adding options without touching code.
- **Discarded — reusing `divisions` with a `kind` column**: divisions drive pipelines, catalogue and dashboards; overloading them with medical meaning is what created the current confusion.

### D2. `contacts.specialty_id` replaces `division_id`, and the migration never guesses

The column is dropped and replaced. Migration `0010` maps the four unambiguous divisions (`vascular` → Cirugía Vascular, `assisted_reproduction` → Reproducción asistida, `gynaecology` → Ginecología, `neurology` → Neurología) and leaves every other contact with `specialty_id = NULL` — `consumables`, `equipment` and `carts_and_arms` are not medical specialties and no plausible-looking guess is written. The migration prints how many contacts were mapped and how many were left empty, so the number is visible in the deploy log rather than silently absorbed.

- **Discarded — keeping `division_id` alongside**: two similar selects in one form is exactly the confusion we are removing, and nothing in the product reads a contact's division today.
- **Discarded — mapping the leftovers to "Enfermería" or "Dirección médica"**: fabricated data that nobody could later distinguish from real data.

### D3. `GET /api/v1/contacts`: a scoped, paginated list mirroring the accounts list

New endpoint on the contacts router: `Page[ContactSummaryRead]` with `q` (name), `specialty_id` (repeatable), `account_id` (repeatable), `job_title_id`, `is_head_of_department`, `is_active`, sorted by last name by default. Visibility reuses `user_scope_filter` + `scoped_accounts` — a contact is returned when the caller can see its account, so no new permission concept enters the system. The summary payload carries what the list row shows: name, account name and id, job title, specialty, head-of-department flag, primary phone and email.

- **Discarded — extending global search**: search answers "take me to this record" with capped groups; a filterable, paginated, sortable list is a different job (search-api's own spec says so).
- **Discarded — a contacts-per-account endpoint with a `?all=true`**: an account-scoped route that ignores its account id is a lie in the URL.

### D4. Cumulative filters: OR inside a facet, AND between facets

`specialty_id=a&specialty_id=b&account_id=c` means *(specialty a OR b) AND centre c* — which is what "que se vayan sumando" means when a user selects two specialties and one hospital. Repeated query parameters express it without inventing a filter language, FastAPI parses them natively, and the URL stays readable and shareable.

- **Discarded — a comma-separated single parameter**: needs escaping rules for names and hides the repetition from OpenAPI.
- **Discarded — AND between specialties**: with one specialty per contact that would always return nothing — a filter that can only produce emptiness is a bug, not a feature.

### D5. Filters live in the URL, chips are the visible state

The page reads and writes `useSearchParams` (the `AccountListPage` precedent). Every active filter renders as a chip with an × that removes just that one, plus "Quitar filtros" when more than one is active. Reloading, sharing or bookmarking the URL reproduces the exact list.

### D6. The centre's specialties are derived, never stored

The 360º page shows the distinct specialties of the account's contacts, computed from the contacts it already loads — no column, no denormalisation, nothing to keep in sync. If that list ever needs to be filtered on at the account level, the honest way is a subquery over contacts, not a copied field.

- **Discarded — an `account_specialties` link table**: a second source of truth for a fact that contacts already own, guaranteed to drift the first time a contact changes specialty.

### D7. The importer resolves `Especialidad` by name, like `Cargo`

Optional column, matched case- and accent-insensitively against the catalogue's Spanish names. An unknown value is a **message on the row, not an error**: the contact is still created without a specialty — the same rule the job title already follows, so a typo in one column never costs a whole import.

### D8. Frontend: a new page inside the existing contacts feature

`features/contacts/pages/ContactListPage.tsx` with a `ContactFilters` bar (chips + selects) and a card list on mobile / table on `lg:`, reusing the shared `DataList` the accounts list already uses. Más gains the "Contactos" card. The contact form swaps its division select for the specialty select, keeping its position and label so nothing moves for the user — only the meaning becomes true.

## Mobile layout (before desktop)

`/contactos`, mobile: header "Contactos" → search box → "Filtros" button opening the filter sheet (specialty, centre, cargo, jefe de servicio) → chip row of active filters with individual × and "Quitar filtros" → card list (name, specialty, job title, centre, head-of-department badge, tap-to-call on the primary phone), infinite "Cargar más". Desktop (`lg:`): filters inline above a table (Nombre, Especialidad, Cargo, Centro, Teléfono), paginated.

## Risks / Trade-offs

- [Contacts left without a specialty after the migration] → deliberate: the count is printed in the deploy log and those contacts are the ones a rep should review; guessing would hide the gap forever.
- [A list of every contact could grow large] → paginated like the accounts list, scoped by visibility, and indexed on `specialty_id` and `account_id`; the same posture that has served the accounts list since change 03.
- [Two similar catalogues (job titles and specialties) confuse admins] → they answer different questions — the job title is the person's role ("Jefe de compras"), the specialty is what they practise ("Cardiología") — and `development_guide.md` states the difference in one line.
- [Removing `division_id` breaks something unnoticed] → the codebase reads it in exactly three places (domain field list, service validation, contact form); the search, importers, dashboards and pipeline never touch it.

## Migration Plan

One revision `0010`: create `specialties`, seed the twelve entries, add `contacts.specialty_id` (FK, nullable), map the four unambiguous divisions, drop `contacts.division_id`. The downgrade recreates the column and maps back the four, losing nothing that the upgrade preserved. Backend and frontend ship together; `api-spec.yml` regenerated and `npm run api:types` rerun.

## Open Questions

None — replacement over coexistence, one specialty per contact, the new page's home and the seed list were settled in the pre-proposal round.
