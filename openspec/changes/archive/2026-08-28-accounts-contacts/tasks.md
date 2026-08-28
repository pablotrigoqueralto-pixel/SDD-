## 1. Backend domain

- [x] 1.1 [BE] Write failing unit tests for the value objects `TaxId` (NIF/CIF/NIE checksums, normalisation, invalid → `tax_id_invalid`), `PhoneNumber` (E.164 with `+34` default, `phone_invalid`), `PostalCode` (`postal_code_invalid`); implement `domain/accounts/value_objects.py`
- [x] 1.2 [BE] Write failing unit tests for `VisibilityPolicy` with `division_ids` (intersection, empty set, owned outside scope) and for `ScopeFilter.for_user`; change `Scoped` protocol and implement `domain/shared/policies.py`
- [x] 1.3 [BE] Write failing unit tests for the `Account` aggregate: create with minimum fields, `Addresses` invariants (label uniqueness, max 10, `address_label_duplicated`, `too_many_addresses`), `update` field diff, `assign(owner, territory)`, `territory_mismatch(province_map)`, activate/deactivate; implement `domain/accounts/entities.py` and errors
- [x] 1.4 [BE] Write failing unit tests for `OwnerResolver` (creator rep; single compatible rep in territory; ambiguous → None; province without territory); implement `domain/accounts/owner_resolver.py`
- [x] 1.5 [BE] Write failing unit tests for the `Contact` aggregate: create, `ConsentRecord` validation (`consent_incomplete`), `preferred_channel` guard (`preferred_channel_missing_value`), `make_primary`, `anonymise` (cleared fields, `contact_anonymised` on later edits); implement `domain/contacts/entities.py`
- [x] 1.6 [BE] Write failing unit tests for `JobTitle` (create with slug code, rename, activate); implement in `domain/reference/entities.py`; define repository protocols `AccountRepository`, `ContactRepository`, `JobTitleRepository`, `PersonalDataAccessLog`; extend `UnitOfWork` and the unit-test fakes

## 2. Backend data model, migration and seed

- [x] 2.1 [BE] ORM models `accounts`, `account_addresses`, `account_divisions`, `account_brands`, `job_titles`, `contacts`, `personal_data_access_log` with enums, checks, partial uniques and indexes per design D5
- [x] 2.2 [BE] Write migration `0003_accounts_contacts` (pg_trgm extension, tables, enums, grants incl. INSERT-only on the access log); integration test round-trip `upgrade → downgrade 0002 → upgrade` and `alembic check`
- [x] 2.3 [BE] Write failing integration tests for the job titles seed (eleven titles, deterministic ids, idempotent, admin rename preserved); extend `seed.py`

## 3. Backend repositories

- [x] 3.1 [TEST] Integration tests for `SqlAlchemyAccountRepository`: add/get/save with version conflict, `tax_id_already_exists` with existing id, division/brand/address sync, `list_page` filters (`q` name/city/tax id, type, territory, owner, division, is_active, unassigned), sorting, `ScopeFilter` applied, `primary_contact_name`
- [x] 3.2 [BE] Implement `SqlAlchemyAccountRepository` and the shared `scoped_accounts(stmt, scope_filter)` helper
- [x] 3.3 [TEST]+[BE] Integration tests and implementation for `SqlAlchemyContactRepository` (get with scope join, list by account primary-first, primary swap in one transaction, save with version), `SqlAlchemyJobTitleRepository`, `SqlAlchemyPersonalDataAccessLog` (append-only; UPDATE rejected for `crm_app`); register in `SqlAlchemyUnitOfWork`
- [x] 3.4 [TEST] Policy/SQL agreement test on the fixture matrix (owned, in territory ∩ division, other division, no divisions, other territory, unassigned) for rep, manager, back office

## 4. Backend services and API

- [x] 4.1 [BE] Write failing unit tests for `AccountService.create/update/assign/replace_addresses/activate` (defaults via `OwnerResolver`, back-office field restriction, `assignment_forbidden`, `owner_not_sales_rep`, audit events `account.*`); implement `application/accounts/`
- [x] 4.2 [BE] Write failing unit tests for `ContactService.create/update/anonymise` (primary swap audit, consent recorded_by, `contact.consent_changed`, `contact.anonymised` without values, access-log rule for non-owner readers) and `JobTitleService`; implement `application/contacts/` and job titles in `application/reference/`
- [x] 4.3 [BE] Write failing API tests for `GET /accounts` (scoped list per role, filters, sort, `unassigned`, 100-page cap) and `POST /accounts` (201 with defaults, 409 tax id with `existing_account_id`, 422 validations); implement schemas and router `api/v1/accounts.py`
- [x] 4.4 [BE] Write failing API tests for `GET/PATCH /accounts/{id}` (404 out of scope, back office restrictions 403, `assignment_forbidden`, 428/409 locking), `PUT /accounts/{id}/assignment`, `PUT /accounts/{id}/addresses`; implement
- [x] 4.5 [BE] Write failing API tests for `GET/POST /accounts/{id}/contacts`, `GET/PATCH /contacts/{id}`, `POST /contacts/{id}/anonymise` (roles, primary swap versions, access log rows only for non-owner readers, 409 anonymised); implement `api/v1/contacts.py`
- [x] 4.6 [BE] Write failing API tests for `GET/POST/PATCH /job-titles`, the bundle including `job_titles[]` with ETag change, and `GET /audit-log/personal-data-access` (admin only, filters, pagination); implement
- [x] 4.7 [TEST] Extend the authorization matrix with every new endpoint; add the trigram plan / <500 ms sanity test with 5 000 seeded accounts
- [x] 4.8 [BE] Export OpenAPI (`api-spec.yml`) and regenerate `frontend/src/api/schema.d.ts`

## 5. Frontend foundations

- [x] 5.1 [FE] MSW fixtures and handlers for accounts, contacts, job titles and the extended bundle; `accountKeys`/`contactKeys` in `query-keys.ts`; new error codes in `errors.json` + `ERROR_CODES`; i18n namespaces `accounts`, `contacts`, admin "Cargos" keys
- [x] 5.2 [FE] Write failing tests for `features/reference` `useJobTitles()` selector and `features/accounts` queries (list with URL params, detail, create/update/assign/addresses with `If-Match`, invalidation); implement `api.ts`, `queries.ts`, `schemas.ts`
- [x] 5.3 [FE] Write failing tests for `features/contacts` queries (list by account, create, update, anonymise, invalidation of the account detail); implement

## 6. Frontend screens

- [x] 6.1 [FE] Write failing component tests for `AccountListPage` (cards/table, search debounce + URL sync, filters sheet on mobile, "Cargar más", badges, empty state, "Nuevo centro"); implement page and route `/centros`
- [x] 6.2 [FE] Write failing component tests for `AccountForm` / `AccountFormRoute` (three fields above the fold, collapsed "Más datos", territory/comercial hints from province, backend field errors incl. duplicate CIF link, conflict dialog, navigate to detail on create); implement
- [x] 6.3 [FE] Write failing component tests for `AccountPage` (header + sticky actions, sections order, placeholders without requests, localStorage section state, 404 → ErrorState, role-gated "Reasignar"/"Anonimizar"); implement `AccountSection`, `AccountHeader`, `PlaceholderSection`, contact cards with `tel:`/`mailto:` and consent badge
- [x] 6.4 [FE] Write failing tests for `AssignmentFormRoute` and `AddressesFormRoute` (max 10 rows, label duplicate message, `If-Match`, refresh); implement
- [x] 6.5 [FE] Write failing component tests for `ContactForm` / `ContactFormRoute` (names above the fold, cargo from bundle, speciality default, channel radio disabled without value, consent date default + origin required, primary toggle, inline backend errors); implement
- [x] 6.6 [FE] Write failing tests for `features/admin/job-titles` (list, create, rename, activate, `If-Match`, bundle invalidation) and the hub "Cargos" card; implement and register routes
- [x] 6.7 [FE] Navigation: bottom bar Hoy · Centros · Más, sidebar "Centros"; update shell tests and the jargon/i18n test

## 7. End-to-end, docs and validation

- [x] 7.1 [E2E] Playwright `accounts.spec.ts` (desktop + mobile, axe): rep creates a centre with three fields → 360º page → adds a contact with consent → edits it; manager reassigns owner; rep of another territory gets "Centro no encontrado" on the direct URL; admin adds a job title
- [x] 7.2 [TEST] Run all quality gates: backend ruff/mypy/pytest with coverage, frontend lint/prettier/tsc/vitest/build, pre-commit
- [x] 7.3 Update `ai-specs/specs/data-model.md` (seven new tables, ER diagram), `development_guide.md` (pg_trgm on managed PostgreSQL, job titles seed, personal data access log, E2E seed additions) and `api-spec.yml`
- [x] 7.4 Compose stack smoke test and E2E suite against it; tear down
