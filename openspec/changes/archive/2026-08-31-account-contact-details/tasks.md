# Tasks — account-contact-details

scope: backend=true, frontend=true · design-linked: false (AI-designed UI per frontend standards)

## 1. Backend — domain and persistence

- [x] 1.1 [TEST][BE] Write failing unit tests for the `Phone` value object shared by both aggregates (label required, number normalised to E.164 with the `+34` default, `phone_invalid` when a number carries "ext" text, extension digits-only, optional note, no duplicate label+number in one list, lowest `sort_order` is primary); then implement it in the accounts and contacts domains.
- [x] 1.2 [TEST][BE] Write failing repository integration tests: phones load ordered by `sort_order`, saving replaces the whole list in one transaction, deleting the owner cascades; then add `AccountPhoneModel`/`ContactPhoneModel`, `accounts.billing_notes`, `contacts.is_head_of_department`, and extend both repositories' `_sync_children` following the `account_addresses` precedent.
- [x] 1.3 [TEST][BE] Write failing migration tests over a seeded database (existing `accounts.phone`/`contacts.mobile`/`contacts.landline` become labelled rows, blanks and anonymised contacts produce no rows, `preferred_channel` maps to email/phone, contacts with the "Jefe de servicio" job title get the flag with their job title cleared, that catalogue row ends inactive but present, downgrade restores the columns from the first phone); then write migration `0009` with the lossy-downgrade docstring.
- [x] 1.4 [TEST][BE] Write failing tests for anonymisation (phone rows deleted, audit `cleared` lists `phones` and never numbers, account phones untouched) and for `preferred_channel = phone` requiring at least one phone; then implement in the contact domain and service.
- [x] 1.5 [TEST][BE] Write failing service tests for the head-of-department flag (set on create and update independently of the job title, audited as a field) and for the back-office scope change (`phones` and `billing_notes` allowed, `notes` still forbidden); then update `ADMINISTRATIVE_FIELDS` and the account/contact services.

## 2. Backend — API and adjacent features

- [x] 2.1 [TEST][BE] Write failing API tests: account and contact payloads carry `phones[]` in order, sending the array replaces the list, omitting it leaves it untouched, an invalid entry answers 422 `phone_invalid` naming its position, `billing_notes` round-trips, summary payloads expose only the primary phone, contacts filter by `is_head_of_department=true`; then update the schemas and endpoints.
- [x] 2.2 [TEST][BE] Write a failing search test (a centre found by the digits of its non-primary "Servicio" phone; a contact found by a secondary number), then swap the phone branch of `SearchQueries` for `EXISTS` subqueries over both phone tables.
- [x] 2.3 [TEST][BE] Write failing importer tests (the `Teléfono` column creates/updates the primary phone and preserves the centre's other labelled phones; the contact phone column writes the contact's "Móvil"; an unnormalisable number is a row `error` leaving the rest of the file unaffected), then adapt both importers.
- [x] 2.4 [BE] Regenerate `ai-specs/specs/api-spec.yml` via the exporter; update `data-model.md` (both phone tables, the two new columns, migration `0009` notes) and `development_guide.md` (labelled phones, extension handling, phone search and importer behaviour).

## 3. Frontend

- [x] 3.1 [FE] Run `npm run api:types`; update `features/accounts` and `features/contacts` api/schemas/queries for `phones`, `billing_notes` and `is_head_of_department`; refresh MSW fixtures and handlers; add the `accounts`/`contacts` i18n keys for phones, labels, billing and the tick.
- [x] 3.2 [TEST][FE] Write failing component tests for `PhoneListEditor` (add row, remove row, "Hacer principal" moves a row to the front and to the front of the payload, free label accepted verbatim, suggestions offered, every control labelled), then implement it mobile-first with the `lg:` side-by-side layout.
- [x] 3.3 [TEST][FE] Write failing tests for the account form (phones inside "Más datos", billing textarea sent as `billing_notes`, `phone_invalid` rendered under the offending row), then wire the editor and the billing field in.
- [x] 3.4 [TEST][FE] Write failing tests for the contact form (phone editor replacing Móvil/Fijo, "Jefe de servicio" tick independent of the cargo, Canal preferido reduced to Email/Teléfono with disabled empty options), then implement.
- [x] 3.5 [TEST][FE] Write failing tests for the 360º page (Datos lists every labelled phone with `tel:` links and extensions, primary first; new Facturación section with its empty state; contact card shows the "Jefe de servicio" badge and calls the primary number), then implement.
- [x] 3.6 [FE] Quality gates: `npx tsc --noEmit -p tsconfig.app.json`, eslint, prettier on touched files, full Vitest suite green.

## 4. E2E and integration validation

- [x] 4.1 [E2E] Extend Playwright: create a centre with three labelled phones (one with extension) and a billing note, verify the 360º renders them with `tel:` links; create a contact with a cargo plus the head-of-department tick and verify the badge; search by the non-primary phone digits and land on the centre; axe scan on the form and the 360º page, mobile and desktop.
- [x] 4.2 [E2E] Full compose smoke plus the complete Playwright suite (desktop + mobile, rate-limit swap); additionally apply the migration over a database that already holds accounts and contacts with phones (the rehearsal data) and verify nothing is lost.
