# Tasks — specialties

scope: backend=true, frontend=true · design-linked: false (AI-designed UI per frontend standards)

## 1. Backend — catalogue and contact link

- [x] 1.1 [TEST][BE] Write failing tests for the specialties catalogue (unique case/accent-insensitive `name_es`, ordering by `sort_order`, inactive entries still resolvable, seed inserts the twelve entries insert-only by code and survives renames/deactivations); then add the domain entity, `SpecialtyModel`, the repository and the seed block following the job-titles precedent.
- [x] 1.2 [TEST][BE] Write failing tests for `contacts.specialty_id` replacing `division_id` (persisted and returned, optional, `unknown_reference` naming `specialty_id`, contacts no longer accept a division); then update the contact entity, model, repository and service validation.
- [x] 1.3 [TEST][BE] Write failing migration tests over seeded data (the four unambiguous divisions map to their specialty, non-medical divisions leave `specialty_id` null, mapped/unmapped counts are reported, downgrade restores `division_id` for the mapped four); then write migration `0010`.

## 2. Backend — API

- [x] 2.1 [TEST][BE] Write failing tests for `GET /api/v1/specialties` and the reference bundle carrying `specialties[]` with the ETag changing when one is renamed; then add the endpoint, the bundle field and the ETag input.
- [x] 2.2 [TEST][BE] Write failing tests for `GET /api/v1/contacts`: a rep sees only contacts of accounts in scope, staff see everything, the summary carries account name, specialty, job title, head flag and only the primary phone, default sort by last name, pagination; then add the query, schema and route.
- [x] 2.3 [TEST][BE] Write failing tests for the cumulative filters (two `specialty_id` values return either; adding an `account_id` narrows to that centre; `is_head_of_department=true` across centres; `q` matches accent-insensitively; an unknown filter value yields an empty page, never an error); then implement them.
- [x] 2.4 [TEST][BE] Write failing importer tests (`Especialidad` resolved case- and accent-insensitively; an unknown value is a row message, not an error, and the contact is still created); then add the column.
- [x] 2.5 [BE] Regenerate `api-spec.yml`; update `data-model.md` (specialties table, the replaced column, migration `0010`) and `development_guide.md` (specialty vs division in one line, the contacts list and its filters).

## 3. Frontend

- [x] 3.1 [FE] Run `npm run api:types`; add specialties to the reference feature, `fetchContacts`/`useContacts` with filter params to `features/contacts`, MSW handlers and fixtures, and the `contacts` i18n keys for the page, filters and chips.
- [x] 3.2 [TEST][FE] Write failing tests for the contact form (Especialidad now lists catalogue specialties, no divisions appear, saving sends `specialty_id`); then swap the select.
- [x] 3.3 [TEST][FE] Write failing tests for `/contactos` (cards on mobile with specialty, cargo, centre and head badge; a row opens the contact's account; one request; empty state with a clear-filters action); then implement the page and its route.
- [x] 3.4 [TEST][FE] Write failing tests for the filters (two specialties add up and produce two chips; adding a centre narrows; removing one chip keeps the rest; the URL carries the state and reopening it reproduces the list); then implement the filter bar with chips and URL state.
- [x] 3.5 [TEST][FE] Write failing tests for the derived specialty badges on the 360º (distinct specialties of its contacts, nothing rendered when none) and the "Contactos" card in Más; then implement both.
- [x] 3.6 [FE] Quality gates: `npx tsc --noEmit -p tsconfig.app.json`, eslint, `npx prettier --check --end-of-line auto e2e src`, full Vitest suite green.

## 4. E2E and integration validation

- [x] 4.1 [E2E] Extend Playwright: seed contacts of two specialties across two centres via API fixtures; open Más → Contactos, filter by one specialty, add a second (both appear), narrow by centre, remove a chip, reload the URL and check the list survives; axe scan mobile and desktop.
- [x] 4.2 [E2E] Full compose smoke plus the complete Playwright suite (desktop + mobile, rate-limit swap); additionally apply migration `0010` over a copy of the rehearsal demo database and verify the mapped/unmapped counts.
