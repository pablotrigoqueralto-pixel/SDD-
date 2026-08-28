## Context

Changes 01 and 02 delivered the foundation (users, roles, territories with `territory_provinces`, divisions, audit log, optimistic locking, `VisibilityPolicy` + `Scope`) and every reference master (account types, brands, divisions, …). This change introduces the first **business** entities: accounts ("centros") and contacts, plus the 360º account page that later changes (activities, opportunities, quotes) extend. It is also the first time the territory visibility rule filters real data, so the SQL scoping pattern decided here is reused by every later entity.

Confirmed product inputs: minimum account = name + type + province; one primary address + additional labelled addresses; a single commercial-communications consent with date, source and recorder; contact fields = name, job title (short admin-editable list), speciality (division), email, mobile, landline, preferred channel.

Current state: `Scoped` protocol exposes `owner_id`, `territory_id`, `division_id` (single division); `resolve_scope(user, territories)` builds the user's `Scope`; no business tables exist yet.

## Goals / Non-Goals

**Goals:**
- Account and contact persistence with indexes that keep list/search under 500 ms at 50 k accounts / 200 k contacts.
- Territory/owner smart defaults derived from the primary address province.
- SQL-level scoping (`scoped_to(user)`) reusable by later entities, consistent with `VisibilityPolicy`.
- GDPR: consent evidence, anonymisation, personal-data access log, audit of every mutation.
- Mobile-first account list, account form, contact form and 360º page skeleton with placeholders for later changes.

**Non-Goals:**
- Activities, opportunities, quotes, equipment (only reserved sections).
- Global search, CSV import, duplicate merge, account hierarchy, maps.
- Physical deletion of accounts or contacts.

## Decisions

### D1. Account is the scoped record; contacts inherit the account's scope

Visibility is evaluated on the account (`owner_id`, `territory_id`, divisions of interest). A contact is visible iff its account is. Contacts carry no owner/territory of their own.
- *Discarded*: per-contact owner/territory — duplicates data that must stay consistent with the account and doubles the reassignment logic; contacts in Quermed's business always belong to a centre.

### D2. Multi-division scoping: `Scoped.division_ids` replaces `division_id`

An account can declare several divisions of interest. The `Scoped` protocol changes to `division_ids: frozenset[UUID]` (empty = "unrestricted": visible to every rep of the territory); `_rep_can_access` passes when the intersection with the user's divisions is non-empty. Change 01 entities that exposed a single `division_id` do not exist (the protocol was unused by data so far), so no migration of callers is needed.
- *Discarded*: keeping a single `division_id` and denormalising the "main division" — a FIV clinic buying gynaecology equipment and consumables would be hidden from one of the two reps.
- *Discarded*: ignoring divisions and scoping by territory only — contradicts the mixed geography + speciality territory model confirmed in the briefing.

### D3. SQL scoping through a single reusable predicate

`AccountRepository.list_page(scope_filter=...)` receives a `ScopeFilter` value object built by `ScopeFilter.for_user(user, scope)`: `None` for roles with full visibility, otherwise `(owner_id = :user) OR (territory_id IN :territories AND (NOT EXISTS account_divisions OR EXISTS account_divisions ∩ :divisions))`. The infrastructure layer translates it to SQLAlchemy once (`scoped_accounts(stmt, scope_filter)`), used by list, detail (`404` when out of scope — no existence leak) and the contact endpoints via a join.
- *Discarded*: loading candidates and filtering in Python with `VisibilityPolicy.can_read` — O(n) per page and breaks pagination totals. `VisibilityPolicy` stays the single source of truth and is still applied to single records on write (`can_write`), and a unit test asserts both implementations agree on a fixture matrix.
- *Discarded*: PostgreSQL row-level security — hides the rule from application tests and needs per-request `SET` of session variables; revisit if a reporting tool reads the DB directly.

### D4. Owner and territory smart defaults

On create: `territory_id = territory_provinces[province]` (nullable when the province has no territory, e.g. Ceuta before configuration). `owner_id`:
1. creator is `sales_rep` → the creator;
2. otherwise, if exactly one active `sales_rep` is assigned to the territory whose divisions overlap the account's divisions (or any rep when the account declares none) → that rep;
3. otherwise `NULL` ("Sin comercial") — the list has a "sin comercial" filter and managers assign through `PUT /accounts/{id}/assignment`.

Changing the primary address province after creation does **not** move the territory automatically (it may be a deliberate exception set by a manager); the UI shows a hint "el territorio no coincide con la provincia" and managers fix it in one tap.
- *Discarded*: a "default rep per territory" column — new concept, extra admin work; rule 2 covers the common one-rep-per-territory case without configuration.
- *Discarded*: forbidding province/territory mismatch — the briefing explicitly asks for manual overrides.

### D5. Data model

Common columns: `id` UUIDv7, `created_at`, `updated_at`; `version` on aggregates (`accounts`, `contacts`, `job_titles`).

| Table | Columns | Constraints / indexes |
|---|---|---|
| `accounts` | `name citext`, `account_type_id FK account_types RESTRICT`, `tax_id citext null` (normalised upper, no spaces), `street text null`, `postal_code varchar(5) null`, `city citext null`, `province_code char(2)`, `territory_id FK territories SET NULL null`, `owner_id FK users SET NULL null`, `customer_code text null`, `phone text null`, `email citext null`, `website text null`, `notes text null`, `is_active bool`, `version` | unique `tax_id` (partial, `where tax_id is not null`); check province format (reuse `PROVINCE_CODE_CHECK`); check postal code `^\d{5}$`; indexes: `territory_id`, `owner_id`, `account_type_id`, `province_code`, `is_active`; trigram GIN on `name` and `city` (`pg_trgm`) for `ILIKE '%q%'`; btree on `tax_id`, `customer_code` |
| `account_addresses` | `account_id FK CASCADE`, `label citext`, `street`, `postal_code`, `city`, `province_code`, `notes null` | unique `(account_id, label)`; index `account_id`. The primary address lives on `accounts` (D6) |
| `account_divisions` | `account_id FK CASCADE`, `division_id FK RESTRICT` | PK `(account_id, division_id)`; index `division_id` (scope predicate) |
| `account_brands` | `account_id FK CASCADE`, `brand_id FK RESTRICT` | PK `(account_id, brand_id)` |
| `job_titles` | `code text unique`, `name_es citext unique`, `sort_order int`, `is_active bool`, `version` | seeded with the 11 agreed titles (`gynaecologist`, `embryologist`, `ivf_lab_director`, `vascular_surgeon`, `neurologist`, `head_of_department`, `nursing_supervisor`, `purchasing`, `management`, `clinical_engineering`, `other`), deterministic uuid5 ids, same upsert policy as brands |
| `contacts` | `account_id FK RESTRICT`, `first_name text`, `last_name text`, `job_title_id FK job_titles RESTRICT null`, `division_id FK divisions RESTRICT null`, `email citext null`, `mobile text null`, `landline text null`, `preferred_channel enum(email, mobile, landline) null`, `notes text null`, `is_primary bool`, `is_active bool`, `consent_status enum(unknown, granted, denied)` default `unknown`, `consent_at timestamptz null`, `consent_source enum(verbal, email, form, imported) null`, `consent_recorded_by FK users SET NULL null`, `anonymised_at timestamptz null`, `version` | unique partial `(account_id) where is_primary`; check "consent_at and consent_source required when status ≠ unknown"; check "preferred_channel requires the matching field"; indexes `account_id`, `email`, trigram on `(first_name || ' ' || last_name)` |
| `personal_data_access_log` | `id`, `occurred_at`, `user_id FK users`, `contact_id FK contacts`, `trace_id text null` | append-only like `audit_log` (INSERT-only grant to `crm_app`); index `(contact_id, occurred_at)` |

Phone numbers are stored as entered but normalised to E.164 when parseable with a fixed `+34` default (pure-Python normaliser, no new dependency); `tax_id` validated with the Spanish NIF/CIF/NIE checksum algorithm in the domain (`TaxId` value object).
- *Discarded*: `phonenumbers` dependency — 2 MB for a Spanish-only MVP; can be added later behind the same value object.
- *Discarded*: JSONB `addresses` column — cannot index province or enforce label uniqueness, and later quotes need a stable address id for delivery.

Migration `0003_accounts_contacts` creates the tables, enums, `pg_trgm` extension and grants; the seed adds job titles.

### D6. Primary address on the account row

The primary address columns live on `accounts` because they drive territory derivation, list rendering and search (single-table query, no join for the hot path). Additional addresses are a child collection.
- *Discarded*: all addresses in `account_addresses` with `is_primary` — every list query joins; the invariant "exactly one primary" needs a deferrable constraint and two-step updates.

### D7. GDPR mechanics

- **Consent** is a value object on the contact (`ConsentRecord(status, at, source, recorded_by)`), changed only through `PATCH /contacts/{id}` with the whole record; every change emits `contact.consent_changed` with before/after in the audit log.
- **Anonymisation** (`POST /contacts/{id}/anonymise`, manager/admin): `first_name`/`last_name` → `"Contacto"`/`"anonimizado"`, `email`/`mobile`/`landline`/`notes` → `NULL`, `consent_status` → `denied`, `is_active` → `false`, `anonymised_at` set; the row and its future FK references (activities, quotes) survive. The audit event stores only field names, not previous values (`changes: {"fields": [...]}`), so the audit log does not retain the erased data. Anonymised contacts reject further edits (`contact_anonymised`, 409).
- **Access log**: reading `GET /contacts/{id}` or listing `/accounts/{id}/contacts` by a user who is neither the account owner nor `sales_manager`/`admin` inserts one `personal_data_access_log` row per contact returned, in the same transaction as the read (unit of work `commit` after a query). Owner and management reads are not logged to keep the table meaningful (their access is expected); list endpoints of accounts expose no contact data.
- *Discarded*: logging every read — the table would dwarf the data and add a write to each rep's own workflow.
- *Discarded*: hard delete with `ON DELETE SET NULL` — loses history attached to activities and quotes and cannot prove the erasure happened.

### D8. API contract

All under `/api/v1`, authenticated; scoping per D3; `If-Match` mandatory on every PATCH/PUT/POST-action (428/409 as in change 01); paginated lists use the existing envelope.

| Method & path | Roles | Notes |
|---|---|---|
| `GET /accounts?q=&account_type_id=&territory_id=&owner_id=&division_id=&is_active=&unassigned=&sort=` | auth (scoped) | `AccountSummaryRead{id, name, account_type_id, city, province_code, territory_id, owner_id, is_active, primary_contact_name?, updated_at}`; `q` matches `name`, `tax_id`, `city`; sort `name` (default), `city`, `updated_at` |
| `POST /accounts` | rep, manager, admin, back_office | `AccountCreate{name, account_type_id, province_code, street?, postal_code?, city?, tax_id?, phone?, email?, website?, customer_code?, notes?, division_ids?, brand_ids?}` → 201 `AccountRead` (applies D4) |
| `GET /accounts/{id}` | auth (scoped) | `AccountRead` = summary + all fields + `addresses[]`, `division_ids[]`, `brand_ids[]`, `version`, `territory_mismatch: bool` |
| `PATCH /accounts/{id}` | owner rep / manager / admin; back_office only administrative fields | `AccountUpdate` (all optional); rep or back_office sending `owner_id`/`territory_id` → 403 `assignment_forbidden` |
| `PUT /accounts/{id}/assignment` | manager, admin | `AccountAssignment{owner_id?, territory_id?}`; validates the owner is an active `sales_rep` |
| `PUT /accounts/{id}/addresses` | writers | full replacement `AddressWrite[]` (labelled, ≤ 10) — simpler than per-address CRUD for a small collection |
| `GET /accounts/{id}/contacts` | auth (scoped) | `ContactRead[]` (not paginated, ordered primary first then last name); logs access per D7 |
| `POST /accounts/{id}/contacts` | writers | `ContactCreate{first_name, last_name, job_title_id?, division_id?, email?, mobile?, landline?, preferred_channel?, notes?, is_primary?, consent?}` → 201 |
| `GET /contacts/{id}` | auth (scoped) | `ContactRead` (+ `account_id`, `account_name`); logs access |
| `PATCH /contacts/{id}` | writers | `ContactUpdate`; setting `is_primary=true` demotes the current primary in the same transaction |
| `POST /contacts/{id}/anonymise` | manager, admin | 200 `ContactRead` anonymised |
| `GET /job-titles` | auth | array; also included in `GET /reference-data` bundle (`job_titles[]`) |
| `POST /job-titles`, `PATCH /job-titles/{id}` | admin | `{name}` / `{name?, is_active?}`, same shape as loss reasons |

Error codes introduced: `tax_id_invalid` (422), `tax_id_already_exists` (409, includes the existing account id so the UI can link to it), `province_without_territory` (never an error — territory nullable; documented for clarity), `postal_code_invalid` (422), `phone_invalid` (422), `address_label_duplicated` (422), `too_many_addresses` (422), `assignment_forbidden` (403), `owner_not_sales_rep` (422), `contact_anonymised` (409), `consent_incomplete` (422), `preferred_channel_missing_value` (422), `job_title_name_already_exists` (409), plus the shared `unknown_reference` (422) and `not_found` (404 for out-of-scope records).

Audit events: `account.created`, `account.updated`, `account.assigned`, `account.addresses_replaced`, `account.activated`/`deactivated`, `contact.created`, `contact.updated`, `contact.primary_changed`, `contact.consent_changed`, `contact.anonymised`, `job_title.created`, `job_title.updated`.

### D9. Domain and application layout

`app/domain/accounts/` — `Account` aggregate (primary address value object `Address`, `Addresses` collection with label uniqueness and max 10, `TaxId`, `PhoneNumber`, `assign(owner, territory)`, `territory_mismatch(province_map)`), `AccountRepository`; `app/domain/contacts/` — `Contact` aggregate (`ConsentRecord`, `PreferredChannel`, `anonymise()`, `make_primary()`), `ContactRepository`, `PersonalDataAccessLog` writer protocol; `app/domain/reference/` gains `JobTitle` (copy of the loss-reason shape). Application services: `AccountService` (create with `OwnerResolver` querying `UserRepository`/`TerritoryRepository`), `ContactService`, `JobTitleService`; queries module for lists. Unit of work gains `accounts`, `contacts`, `job_titles`, `personal_data_access`.
- *Discarded*: one `crm` module with both aggregates — accounts and contacts evolve separately (activities attach to both) and the module would be the largest in the codebase.

### D10. Frontend

Routes (Spanish segments): `/centros` (list), `/centros/nuevo`, `/centros/:id` (360º), `/centros/:id/editar`, `/centros/:id/direcciones`, `/centros/:id/contactos/nuevo`, `/centros/:id/contactos/:contactId/editar`; admin `/admin/cargos`. Forms open in `ResponsiveFormContainer` over the underlying page (sheet on mobile, dialog on desktop), as in admin.

Feature structure: `features/accounts/{api.ts, queries.ts, schemas.ts, pages/AccountListPage, AccountPage, AccountFormRoute, AddressesFormRoute, components/AccountForm, AccountHeader, AccountSection (collapsible, memorised open state in localStorage), AddressesForm, PlaceholderSection}` and `features/contacts/{api.ts, queries.ts, schemas.ts, pages/ContactFormRoute, components/ContactForm, ContactCard, ConsentBadge}`; `features/admin/job-titles` cloned from loss reasons; query keys `accountKeys`, `contactKeys`.

Account list: `DataList` with search input (debounced 300 ms, `q`), filter chips (tipo, territorio, comercial, división, sin comercial, inactivos) inside a `Sheet` "Filtros" on mobile and inline on desktop; infinite "Cargar más" on mobile, paginated table on desktop. Filters persist in the URL (`useSearchParams`) so the back button returns to the same list.

Account form (mobile first, three fields above the fold):

```
┌──────────────────────────┐
│ Nuevo centro          ✕  │
├──────────────────────────┤
│ Nombre*                  │
│ [                      ] │
│ Tipo*         Provincia* │
│ [▾ Clínica FIV] [▾ Madrid]│
│ ─ Más datos (opcional) ▸ │  ← collapsed: CIF, dirección, CP, ciudad,
│                          │     teléfono, email, web, código Sage,
│                          │     divisiones, marcas en uso, notas
│ Territorio: Centro (auto)│  ← read-only hint derived from province
│ Comercial: Tú            │
├──────────────────────────┤
│        [ Guardar ]       │
└──────────────────────────┘
```

Account 360º page (mobile):

```
┌──────────────────────────┐
│ ◀ Clínica Tambre         │
│ Clínica FIV · Madrid     │
│ Territorio Centro · Ana  │
│ [Nuevo contacto] [Editar]│  ← sticky actions
├──────────────────────────┤
│ ▾ Contactos (3)          │
│   Dra. Pérez · Ginecóloga│
│   ☎ 6xx · ✉ · Consent ✓ │
│ ▸ Datos                  │
│ ▸ Oportunidades  próxim. │  ← placeholders: EmptyState "Disponible
│ ▸ Actividades    próxim. │     en una próxima versión"
│ ▸ Presupuestos   próxim. │
│ ▸ Equipos        próxim. │
│ ▸ Notas                  │
├──────────────────────────┤
│  Hoy  Centros  Más       │
└──────────────────────────┘
```

Desktop: header spans the width; two columns (`lg:grid-cols-3`): left column Datos + Notas, right two columns Contactos then the placeholders; sections remain collapsible. Contact card taps `tel:`/`mailto:` links directly (30-second rule).

Contact form: nombre y apellidos above the fold; cargo (`NativeSelect` from `useJobTitles()`), especialidad (division select defaulted to the account's single division of interest when there is one), email/móvil/fijo, canal preferido (segmented radio), consentimiento (estado + origen; fecha defaults to today when status changes), contacto principal toggle.
- *Discarded*: a wizard for account creation — more taps; the collapsed "Más datos" keeps the 30-second rule while allowing full data entry.
- *Discarded*: kanban-like tabs on the 360º page — tabs hide information on mobile; collapsible sections keep one scroll.

Navigation: bottom bar becomes Hoy · Centros · Más (Admin lives under Más for admins); sidebar adds "Centros". The "Hoy" placeholder remains until dashboards.

### D11. Testing

- Backend unit: `TaxId` checksum (NIF/CIF/NIE valid and invalid), `PhoneNumber` normalisation, `Addresses` invariants, owner resolution rules, `Contact.anonymise()`/`make_primary()`, consent validation, `VisibilityPolicy` with `division_ids`, and the policy/SQL agreement matrix with fakes.
- Backend integration: migration round trip; every endpoint × role matrix (rep in scope / rep out of scope → 404 / manager / back office admin fields / admin); scoping with mixed divisions; tax id conflict; primary contact swap; anonymisation; access log rows created only for non-owner readers; audit events; list performance sanity (EXPLAIN uses trigram index on `name`, asserted in a test seeded with 5 k rows).
- Frontend: list filters and URL sync, form smart-default hints, collapsed "Más datos", 360º sections and placeholders, contact form consent defaults, conflict dialog on stale version, MSW handlers for all endpoints.
- E2E (desktop + mobile, axe): rep creates an account with three fields → lands on the 360º page → adds a contact with consent → edits the contact; manager reassigns owner; rep of another territory gets "no encontrado" on the direct URL.

## Risks / Trade-offs

- **[Scope predicate in two places (Python policy + SQL)]** → agreement test on a fixture matrix; SQL predicate lives in one helper.
- **[`pg_trgm` extension needs superuser on first creation]** → the migration runs `CREATE EXTENSION IF NOT EXISTS pg_trgm` with the migration role (already superuser in compose/CI); documented for managed PostgreSQL in `development_guide.md`.
- **[Unassigned accounts (`owner_id NULL`) invisible to every rep]** → "Sin comercial" filter for managers and a badge on the dashboard change; managers are expected to assign.
- **[Spanish-only tax id and phone validation]** → value objects isolate the rules; foreign distributors can be stored without `tax_id`.
- **[Access log growth]** → only non-owner reads are logged; index on `(contact_id, occurred_at)`; retention policy deferred to the production change.
- **[Replacing addresses wholesale]** → bounded to 10 addresses and audited with before/after; adequate for the MVP.
- **[Province change does not move territory]** → `territory_mismatch` flag surfaced in list badge and 360º header for managers.

## Migration Plan

1. Deploy migration `0003_accounts_contacts` (new tables only, no data changes) and run the seed (job titles).
2. Deploy backend and frontend together (new routes; no existing contract changes except the extended `GET /reference-data` bundle, which is additive).
3. Rollback: `alembic downgrade 0002` drops the new tables (acceptable before real data exists); the frontend without the backend routes shows `ErrorState` on Centros.

## Open Questions

- None blocking. Excel import of the existing customer list is change 08; the `customer_code` and `tax_id` uniqueness rules here are designed so that import can match by either.

### Implementation notes (recorded during /opsx:apply)

- `AccountSummaryRead` and `AccountRead` carry `territory_name` and `owner_name` (not in D8): sales reps cannot list users or territories, so the list and the 360º header would otherwise show raw ids.
- The contact full-name trigram index was dropped: Alembic cannot round-trip an expression index (`alembic check` reported permanent drift) and per-account contact lists are tiny; the global search change will add it if needed.
- `account.name`, `city` and `tax_id` are `text`, not `citext`: `gin_trgm_ops` does not accept `citext` and `ILIKE` already gives case-insensitive search.
- The `contact.anonymised` audit payload is `{"fields": {"cleared": [...]}}` (the audit `changes` type is a map of maps); the spec scenario was aligned.
- Admins read the personal-data access log through `GET /audit-log/personal-data-access` (added by the specs; a GDPR log nobody can query is useless).
- The `Scoped` protocol changed from `division_id` to `division_ids`; the policy and the SQL predicate are covered by an agreement test over a six-account fixture matrix.
- E2E specs assert on `visible=true` copies because the 360º page renders the mobile and desktop layouts together, and pick free provinces through the API so repeated runs on a persistent database keep passing; the admin spec now searches for the created user (the list is paginated at 50).
