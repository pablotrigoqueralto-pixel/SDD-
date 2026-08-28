## Why

The CRM exists to give every sales rep a single, always-current picture of their customers. Accounts ("centros") and contacts are the anchor of everything that follows — activities, opportunities, quotes — and today that information lives in loose Excel files per rep. This change delivers the account and contact records, the territory-scoped visibility rule applied for the first time to business data, and the 360º account page that later changes fill with activities, opportunities and quotes.

Constitution principles served: 30-second rule (an account is created with three fields, a contact with two), zero useless fields (every field is justified below), smart defaults (province → territory → owner; division from account interests), one screen one purpose (the account page is one scrollable view with collapsible sections), mobile-first, business vocabulary (Centro, Contacto, Comercial), GDPR (consent with evidence, anonymisation, access log), audit.

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- **Accounts (centros)**: `name`, `account_type`, primary address (`street`, `postal_code`, `city`, `province_code`) and optional `tax_id` (CIF/NIF, validated), `phone`, `email`, `website`, `customer_code` (Sage reference, free text), `notes`. Derived on creation: `territory` from the province (smart default, editable by manager/admin), `owner` (the creating rep, or the territory's default rep when created by a manager). Many-to-many `divisions_of_interest` and `brands_in_use` (own and competitor brands the centre already uses). Soft state `is_active`.
- **Additional addresses**: labelled addresses (e.g. "Laboratorio FIV", "Almacén") besides the primary one; the primary one drives territory.
- **Contacts**: linked to one account, `first_name`, `last_name`, `job_title` (short admin-editable list seeded with the clinical roles Quermed deals with), `speciality` (division, optional), `email`, `mobile`, `landline`, `preferred_channel` (email / móvil / fijo), `notes`, `is_primary` (one per account), `is_active`.
- **GDPR**: commercial-communications consent on the contact (`consent_status` granted/denied/unknown, `consent_at`, `consent_source` verbal/email/form/imported, `consent_recorded_by`); right to erasure through `POST /contacts/{id}/anonymise` (personal fields replaced by placeholders, row kept for history); every read of a contact's personal data by a user other than its owner's team is recorded in `personal_data_access_log`.
- **Territory visibility applied to data**: lists and detail endpoints for accounts and contacts use the `VisibilityPolicy` from change 01 at SQL level; `sales_rep` sees owned accounts and accounts in their territories (division filter applies when the account has divisions of interest); managers, back office and admins see all. Reassigning owner/territory is restricted to `sales_manager` and `admin`.
- **Job titles master**: seeded, admin-editable list (`Ginecólogo/a`, `Embriólogo/a`, `Director/a de laboratorio FIV`, `Cirujano/a vascular`, `Neurólogo/a`, `Jefe/a de servicio`, `Supervisor/a de enfermería`, `Compras / suministros`, `Gerencia`, `Electromedicina / ingeniería clínica`, `Otro`), added to the reference bundle.
- **Search and lists**: paginated account list with search by name/CIF/city, filters by type, territory, owner, division, active; contact list per account; global search of accounts and contacts arrives with the search change, but the account list search must already be < 500 ms on 50 k rows (indexes on `name`, `tax_id`, `city`, `territory_id`, `owner_id`).
- **Account 360º page** (`/centros/:id`): header (name, type, territory, owner, badges), collapsible sections in fixed order — Datos, Contactos, Oportunidades (placeholder), Actividades (placeholder), Presupuestos (placeholder), Equipos (placeholder), Notas — with primary actions "Nuevo contacto" and "Editar" always visible; later changes populate the placeholders.
- **Account list page** (`/centros`) with cards/table, search and filters; **account form** (3 required fields, smart defaults) and **contact form** (2 required fields) in the shared sheet/dialog.
- Navigation gains "Centros" in the bottom bar / sidebar.

## Non-goals

- Activities, opportunities, quotes, equipment on loan (later changes; this change only reserves their sections on the 360º page).
- Global search and CSV import (change 08); duplicate detection beyond the CIF uniqueness rule.
- Account hierarchy (group → centre) and merging accounts.
- Deleting accounts or contacts (deactivation and anonymisation only).
- Editing job titles from a dedicated screen (admin CRUD via API + reuse of the reference admin pattern is included; no new hub entry beyond "Cargos").
- Geocoding or maps.

## Roles and territory visibility

| Role | Accounts and contacts |
|---|---|
| `sales_rep` | Read/write accounts they own or that belong to their territories (∩ their divisions when the account declares divisions of interest); create accounts (owner = self); cannot change owner/territory; read/write contacts of visible accounts. |
| `sales_manager` | Read/write all; reassign owner and territory; anonymise contacts. |
| `back_office` | Read all; edit administrative fields (`tax_id`, `customer_code`, addresses, `phone`, `email`); cannot change owner/territory. |
| `admin` | Everything, plus job titles master. |

Personal data access by any user outside the owning rep, their manager or admin is recorded in `personal_data_access_log` (user, contact, timestamp, trace id).

## Capabilities

### New Capabilities
- `account-model`: account aggregate (primary + additional addresses, divisions of interest, brands in use, territory/owner derivation, tax id validation), job titles master, migration and indexes.
- `contact-model`: contact aggregate (job title, speciality, channels, consent evidence, primary contact rule, anonymisation).
- `account-contact-api`: scoped list/detail/create/update endpoints for accounts and contacts, reassignment, anonymisation, personal-data access logging, audit events.
- `account-screens`: account list, account form, account 360º page with collapsible sections and placeholders, contact form, navigation entry.

### Modified Capabilities
- `territory-scope`: the scope rule is applied to accounts and contacts through SQL filtering (`scoped_to(user)`), and the "record" in the visibility rule is defined as the account.
- `audit-log`: new events `account.*`, `contact.*` (including `contact.anonymised`, `contact.consent_changed`) and the personal data access log.
- `reference-data-api` / `reference-data-admin-screens`: the bundle and the admin hub include job titles.

## Impact

- New tables: `accounts`, `account_addresses`, `account_divisions`, `account_brands`, `contacts`, `job_titles`, `personal_data_access_log`. Migration `0003_accounts_contacts`; seed extended with job titles.
- New API: `/api/v1/accounts` (list, create), `/accounts/{id}` (read, patch), `/accounts/{id}/assignment` (owner/territory), `/accounts/{id}/addresses`, `/accounts/{id}/contacts` (list, create), `/contacts/{id}` (read, patch), `/contacts/{id}/anonymise`, `/job-titles` (+ admin create/patch), `reference-data` bundle extended.
- Frontend: `features/accounts`, `features/contacts`, navigation, i18n `accounts`/`contacts` namespaces.
- Documentation: `api-spec.yml`, `data-model.md`, `development_guide.md` (job titles seed, access log).
- No new dependencies.
