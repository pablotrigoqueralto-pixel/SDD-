## Why

First round of feedback from the sales director after seeing the CRM: the contact data model is too narrow for how hospitals actually work. A centre has many phone numbers (secretaría, servicio, consulta, despacho, extensión) and today it holds exactly one; a contact holds a mobile and a landline and nothing else. "Jefe de servicio" is currently a job title, which forces a false choice — a doctor is a vascular surgeon **and** head of department, not one or the other. And the billing details that back office needs (invoicing data, accounting contact, the explanation of how a given hospital wants to be invoiced) have nowhere to live.

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- **Labelled phone lists** replace the single fields: an account and a contact can each hold any number of phones, every one with a label (from a suggested list — Principal, Secretaría, Servicio, Consulta, Despacho, Extensión, Móvil, Fax — or typed freely) and an optional note. The first entry is the primary one and is what lists, cards and the tap-to-call action use.
- Existing data migrates without loss: `accounts.phone` becomes the account's first phone, `contacts.mobile` becomes "Móvil" and `contacts.landline` becomes "Fijo".
- Phone search keeps working across the whole list, not just the old columns, so searching a switchboard extension finds the centre.
- The account importer keeps its `Teléfono` column (creating the primary phone) and the contact columns keep behaving as today.
- **"Jefe de servicio" stops being a job title** and becomes an independent tick on the contact: a contact can be Cirujano/a vascular *and* head of department. Contacts currently holding that job title are migrated to the tick with their job title cleared, and the catalogue entry is deactivated (not deleted — the audit history keeps its meaning).
- The account 360º header and contact cards show the head-of-department badge, and contacts can be filtered by it.
- **Billing block on the account**: a free-text "Datos de facturación y contacto de contabilidad" note, editable by roles that can already edit the account (back office included, since it is administrative data), shown as its own section on the 360º page.

## Capabilities

### New Capabilities

(None — this deepens the existing account and contact capabilities.)

### Modified Capabilities
- `account-model`: labelled phone list replacing the single phone column, plus the billing/accounting note field.
- `contact-model`: labelled phone list replacing mobile/landline, plus the independent head-of-department flag and the migration away from the job title.
- `account-contact-api`: phone lists in account and contact payloads (create, update, read), the billing note, the head-of-department flag and its filter.
- `account-screens`: phone editors in both forms, the billing section on the 360º page, the head-of-department tick and badge, and the contact filter.
- `search-api`: phone matching over the phone lists instead of the old columns.
- `import-api`: the importers write the primary phone into the new structure with unchanged column names.

## Non-goals

- No phone validation or normalisation beyond what exists today (no international format enforcement, no carrier lookup): Spanish hospital switchboards come with extensions and notes that any strict format would reject.
- No structured billing fields (VAT regime, payment terms, SEPA data) — the director asked for a note that can be written and explained; structured invoicing belongs with a future ERP integration.
- No phone list on users (internal staff) — only accounts and contacts.
- No change to the job-title catalogue beyond deactivating "Jefe de servicio"; adding new job titles from the dropdown is change 14.
- No specialties: change 13 owns that.

## Impact

- **Roles**: unchanged permissions. Reps edit their own accounts' phones and contacts as today; `back_office` keeps its administrative-fields scope and gains the billing note within it (it is administrative data by nature); `admin` and `sales_manager` unchanged. Territory visibility untouched.
- **Backend**: new `account_phones` and `contact_phones` tables (or one polymorphic table — design decides), migration moving existing values and converting the job title to the flag, `contacts.is_head_of_department` column, `accounts.billing_notes` column. Repositories, schemas and services updated; `api-spec.yml` regenerated.
- **Frontend**: phone list editors (add/remove/reorder rows with label + number) in the account and contact forms, billing section on the 360º page, head-of-department tick and badge, contact filter; `accounts`/`contacts` i18n namespaces grow.
- **Docs**: `data-model.md` gains the new tables and columns with the migration note; `development_guide.md` records the phone-search and importer behaviour; `api-spec.yml` regenerated via the exporter.
- **Constitution principles served**: zero useless fields (the phone list replaces guessing which of two fields a number belongs in), 30-second interactions (tap-to-call on the right number without opening a note), one screen one purpose (billing lives in its own section instead of polluting general notes), and data honesty (a doctor's role and their department headship are different facts).
