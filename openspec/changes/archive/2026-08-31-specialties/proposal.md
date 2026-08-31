## Why

Second round of the sales director's feedback. Two problems, one root cause: the CRM has no idea what a doctor actually practises. The contact form shows a field labelled "Especialidad" that in fact stores the **commercial division** (Vascular, FIV, Consumibles) — a label that lies about its data since change 03. And even if it were right, there is no way to answer "dame todos los cardiólogos de Levante": contacts only exist inside one account, with no global list and no listing endpoint.

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- **New `specialties` catalogue** (mirroring the job-titles pattern: code, Spanish name, sort order, active flag), seeded with the twelve that match Quermed's business — Ginecología, Reproducción asistida, Embriología, Cirugía Vascular, Angiología, Neurología, Neurofisiología, Radiología, Anestesiología, Podología, Enfermería, Dirección médica.
- **Contacts carry one medical specialty**, replacing `division_id`. The commercial division stays where it belongs (accounts, products, pipeline) and disappears from the contact form, which stops calling a division a speciality.
- Existing contact divisions migrate to the equivalent specialty where the mapping is unambiguous (vascular → Cirugía Vascular, assisted_reproduction → Reproducción asistida, gynaecology → Ginecología, neurology → Neurología); divisions with no medical equivalent (consumables, equipment, carts_and_arms) leave the contact without a specialty rather than inventing one, and the migration reports how many.
- **New global contacts page** at `/contactos`, reached from Más, listing every contact the actor may see (the account's visibility rule, applied through the contact's account) with a paginated, sortable list.
- **Cumulative, combinable filters** on that page: several specialties at once (OR between them), narrowed by centre, job title and the head-of-department tick (AND between different filters), rendered as removable chips with a "quitar todos". The URL carries the filter state so a filtered list can be shared or bookmarked.
- The account 360º shows the **specialties present among its contacts**, derived automatically — no field to maintain.
- The accounts/contacts importer gains an optional `Especialidad` column resolved by name, consistent with how `Cargo` already works.

## Capabilities

### New Capabilities
- `specialty-model`: the specialties catalogue — table, seed, uniqueness, activation rules and the contact link, plus the migration away from the contact's division.

### Modified Capabilities
- `contact-model`: `specialty_id` replaces `division_id` on contacts.
- `account-contact-api`: contact payloads carry the specialty; a new global `GET /api/v1/contacts` with cumulative filters, pagination and sorting under the account visibility rule; the specialties reference endpoint.
- `reference-data-model`: the specialties catalogue joins the reference data bundle and its seed.
- `reference-data-api`: specialties are exposed in the reference bundle (admin CRUD arrives in change 14).
- `account-screens`: the contact form swaps the division select for the specialty select; the 360º shows the derived specialties of the centre.
- `import-api`: the optional `Especialidad` column on the accounts/contacts import.
- `app-shell`: Más gains the "Contactos" card.

## Non-goals

- No multiple specialties per contact (one each, per the agreed decision).
- No sub-specialties or hierarchy.
- No admin CRUD screen for specialties in this change — creating catalogue entries from the dropdown is change 14; the seed covers the launch set.
- No specialty on accounts as an editable field: the centre's specialties are derived from its contacts, never typed twice.
- No saved searches; the URL is the shareable state.
- No change to how divisions work anywhere else (accounts, products, pipeline, dashboards keep them untouched).

## Impact

- **Roles**: no permission change. The contacts page shows exactly what each role can already see through accounts — a rep sees the contacts of their territory's centres, staff see everything; back office keeps its read-only posture (no actions from the list).
- **Backend**: new `specialties` table + seed, `contacts.specialty_id` replacing `division_id`, migration `0010` with the mapped conversion, a new paginated contacts query with cumulative filters, the reference bundle extension and the importer column. `api-spec.yml` regenerated.
- **Frontend**: new `features/contacts` list page with the chip-based filter bar and URL state, contact form field swap, derived specialties on the 360º, a card in Más, `contacts` i18n growth, MSW handlers and Playwright coverage.
- **Docs**: `data-model.md` (new table, the replaced column, migration notes), `development_guide.md` (specialties vs divisions — why both exist and what each answers), `api-spec.yml`.
- **Constitution principles served**: data honesty (a field named "Especialidad" will finally hold a specialty), 30-second interactions ("todos los cardiólogos de Madrid" becomes two taps), one screen one purpose (a contacts list that lists contacts, instead of overloading Buscar), and mobile-first (chips and a card list rather than a wide table).
