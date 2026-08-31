## Context

The pieces this change touches all have precedents in the codebase: `account_addresses` is already a labelled child collection with a unique label per account and a delete-and-reinsert `_sync_children` in the repository; contacts already carry a GDPR surface (`ANONYMISED_FIELDS` including `mobile` and `landline`, cleared on anonymisation); back office edits are gated by `ADMINISTRATIVE_FIELDS`, which contains `phone`; and change-08 search matches phone digits directly against `accounts.phone` and `contacts.mobile`.

Two couplings make this bigger than "add a table": `contacts.preferred_channel` is an enum whose values are literally `mobile` and `landline` — the columns being removed — and contact phone numbers are personal data, so the anonymisation path must delete them, not just null a column.

scope:
  backend: true
  frontend: true
design-linked: false

## Goals / Non-Goals

**Goals:**
- Any number of labelled phones per account and per contact, with the first one acting as primary everywhere (lists, cards, tap-to-call, search).
- Migrate every existing value without loss and without leaving fields that name things that no longer exist.
- Keep GDPR behaviour correct: anonymising a contact removes their phones.
- Head of department as an independent fact, with existing data converted.

**Non-Goals:** relaxing the existing E.164 normalisation (see D10), structured billing fields, phones on users, catalogue editing from dropdowns (change 14), specialties (change 13).

## Decisions

### D1. Two child tables mirroring `account_addresses`

`account_phones` and `contact_phones`, each with `id`, owner FK (`ON DELETE CASCADE`), `label`, `number`, `extension`, `note`, `sort_order`, and a unique constraint on (owner, `sort_order`) plus (owner, `label`, `number`) to stop accidental duplicates. Repositories load them with `selectinload` and persist them with the same delete-and-reinsert `_sync_children` the addresses already use, so the whole list is replaced atomically on save — the API contract is "send the list you want".

- **Discarded — one polymorphic `phones` table** (`owner_type` + `owner_id`): PostgreSQL cannot enforce a foreign key on a polymorphic column, so cascade deletes and orphan prevention become application code; two small tables cost one migration and keep referential integrity for free.
- **Discarded — a JSONB column on each row**: labels and numbers need to be searched (phone lookup is a first-class search route) and a JSONB scan is worse than a join over a narrow table; per-row constraints would also be lost.

### D2. Primary phone is position, not a flag

The first entry (`sort_order` 0) is the primary one. Lists, the account card, the contact card and the importers read `phones[0]`. Reordering is an explicit "Hacer principal" action that moves a row to the front.

- **Discarded — an `is_primary` boolean**: two sources of truth (order and flag) that drift, plus a partial unique index to enforce exactly one; ordering already expresses priority and matches how a rep reads the list.

### D3. `preferred_channel` collapses to `email` / `phone`

The enum's `mobile` and `landline` values name columns this change deletes. They become a single `phone` value; the migration maps both old values to it. Which number to call is answered by the list's primary entry, not by the enum.

- **Discarded — keeping `mobile`/`landline` values**: they would name fields that no longer exist — data that lies about itself.
- **Discarded — a foreign key from the contact to its preferred phone row**: deleting that phone would break the contact, and no rep has ever needed "call this specific number by default" beyond "the first one".

### D4. One migration `0009` doing schema and data, reversible

Single Alembic revision: create both tables; copy `accounts.phone` into `account_phones` with label "Principal", `contacts.mobile` with "Móvil" and `contacts.landline` with "Fijo" (skipping nulls and blanks); map `preferred_channel`; add `contacts.is_head_of_department` and `accounts.billing_notes`; set the flag true and clear `job_title_id` for contacts holding the "Jefe de servicio" job title; deactivate that catalogue row; drop the old columns. Downgrade restores the columns from the first phone of each owner and re-activates the catalogue row — lossy for the second phone onward, which the migration docstring states plainly.

- **Discarded — splitting schema and backfill into two revisions**: this deployment applies migrations in one shot before the app starts (change 10's `migrate` service); two revisions add ceremony without a window where partial state is useful.

### D5. Anonymisation deletes contact phones

Phone numbers of a person are personal data. `ANONYMISED_FIELDS` loses `mobile`/`landline` and the anonymisation path gains an explicit "delete all phones of this contact" step, executed in the same transaction and covered by a test asserting zero rows remain. Account phones are business contact data (switchboards, departments) and are untouched by contact anonymisation.

### D6. Head of department: boolean column, catalogue entry deactivated

`contacts.is_head_of_department` (boolean, default false). The "Jefe de servicio" job title is **deactivated**, never deleted: audit entries and the personal-data access log reference it by id, and deleting the row would either break those references or rewrite history.

- **Discarded — deleting the catalogue row**: destroys the meaning of past audit entries.
- **Discarded — keeping the job title alongside the tick**: two ways to record the same fact guarantee contradictory data.

### D7. Search matches with an `EXISTS` over the phone tables

The phone branch of `SearchQueries` swaps its direct column comparison for an `EXISTS (SELECT 1 FROM account_phones WHERE owner = account.id AND digits(number) LIKE '%…%')`, same for contacts. Cost profile is unchanged (the current implementation already scans a text expression); the tables are narrow and MVP-sized. If phone lookup ever gets slow, a trigram index on the digits expression is an additive follow-up — the same posture as the dashboard's aggregation.

### D8. Back office scope widens explicitly

`ADMINISTRATIVE_FIELDS` swaps `phone` for `phones` and gains `billing_notes`: invoicing data and the accounting contact are administrative by nature and back office is exactly who maintains them. This is a deliberate permission widening, stated in the spec so it is reviewable rather than incidental.

### D9. Frontend: one `PhoneListEditor` used by both forms

A single component renders rows of *label + number + optional extension + optional note* with "Añadir teléfono", "Quitar" and "Hacer principal" per row. The label input is a text field with a datalist of suggestions (Principal, Secretaría, Servicio, Consulta, Despacho, Extensión, Móvil, Fax) — typed values are accepted verbatim, which is what "etiqueta libre" means. Mobile-first: rows stack vertically; on `lg:` label and number sit side by side. The primary number renders as a `tel:` link on the account 360º header and contact cards.

- **Discarded — drag-and-drop reordering**: an accessibility and testing cost for lists of three or four items; an explicit "Hacer principal" button says what it does and works with a screen reader.

### D10. Number stays E.164; the extension is its own field

The existing `account-model` spec mandates E.164 normalisation with a `+34` default and a `phone_invalid` error — typing "915 550 000 ext. 4021" into the number would be rejected today. Rather than relaxing that (which would break tap-to-call and the digit search that change 08 relies on), each phone row gains an optional `extension` field: `label` + `number` (E.164, as today) + `extension` + `note`. The UI renders `tel:+34915550000;ext=4021`, the standards-compliant form, and search matches the number's digits as before.

- **Discarded — free-text numbers**: kills `tel:` links, makes phone search unreliable ("91-555 00 00" vs "915550000") and silently drops the validation the model already promises.
- **Discarded — extension inside the label**: "Despacho ext. 4021" is a human label, not data; the dialer could not use it and two centres would write it three different ways.

## Mobile layout (before desktop)

Account form: existing fields, then a "Teléfonos" block — one row per phone (etiqueta, número, extensión y nota opcionales, botones Quitar / Hacer principal), then "Añadir teléfono"; then the new "Datos de facturación y contacto de contabilidad" textarea with its hint. Contact form: same phone block plus the "Jefe de servicio" tick under the job title. Account 360º: phones listed in the header block (primary first, each a `tel:` link with its label) and a collapsible "Facturación" section showing the note. Contact cards show the primary phone and, when set, a "Jefe de servicio" badge.

Desktop (`lg:`): phone rows lay label and number side by side; the billing section sits in the right column of the 360º grid.

## Risks / Trade-offs

- [Free-text labels drift into chaos ("Secre", "secretaria", "SECRETARÍA")] → the datalist offers the canonical set first and the list is short per account; normalising labels into a catalogue is a change-14 conversation, not a silent constraint here.
- [Downgrade loses phones beyond the first] → stated in the migration docstring; the nightly dump is the real recovery path (change 10) and forward-only migrations are already the documented policy.
- [Widening back-office scope to `billing_notes`] → explicit in the spec and covered by a permission test; the field is administrative data by definition.
- [Phone search over a join could slow down] → same scan profile as today over narrower tables; trigram index noted as an additive follow-up.
- [Contacts anonymised before this change kept null columns; now rows must be absent] → the migration copies only non-null values, so anonymised contacts simply get no phone rows.

## Migration Plan

One revision `0009`, applied by the existing `migrate` service before the app starts. Backend and frontend ship together; `api-spec.yml` regenerated and `npm run api:types` rerun. Rollback is `alembic downgrade` (lossy beyond the first phone, as documented) plus a plain revert; the nightly dump covers the rest.

## Open Questions

None — phone shape, billing as free text, and the head-of-department tick were settled in the pre-proposal question rounds.

## Implementation notes (recorded during /opsx:apply)

- **D10 was found while writing the specs, not while coding**: the existing `account-model` spec already mandated E.164 normalisation, which would reject "ext. 4021" typed into a number. The extension became its own column instead of relaxing the rule.
- The old `ck_contacts_preferred_channel_value` CHECK named the phone columns, so the migration must drop it *before* the type change and recreate it without the phone clause. A CHECK cannot span tables, so "the phone channel needs at least one number" now lives in `Contact.validate_channels()` — stated in the model as a comment.
- `ALTER COLUMN ... TYPE text` on an enum column needs an explicit `USING preferred_channel::text`, and the phone tables must NOT carry `created_at`/`updated_at` (the `account_addresses` precedent has none) or the model-drift test fails.
- `SqlAlchemyAccountRepository.add()` built child collections inline and did not go through `_sync_children`; phones had to be added there too, which the idempotent-import test caught immediately.
- An `<input list="...">` (datalist suggestions) has the implicit ARIA role **combobox**, not textbox — component and E2E tests query the label field accordingly.
- The 360º page renders every section twice (mobile and desktop layouts): E2E assertions need `.locator('visible=true')`, and component tests take the first match.
- `phoneRowSchema` lives next to the shared `PhoneListEditor`, not in a feature: the contacts feature may not import from the accounts feature (the `no-restricted-imports` rule caught the first attempt).
- Verify warnings closed before archiving: the account summary now carries `primary_phone` (a correlated subquery over the first row, mirroring `primary_contact_subquery`) and the accounts list renders it as a `tel:` link — one tap to call from the list; `phone_invalid` now names the offending row (`phones.1`) via a `field_name` threaded from the schema; and the three uncovered scenarios (unnormalisable phone in the importer, duplicate label+number at API level, FK cascade) gained tests.
- Migration rehearsed against a **real copy of the rehearsal demo database**: 2 account phones became "Principal" rows, 2 contacts holding the "Jefe de servicio" job title moved to the flag with their title cleared, the catalogue row stayed present but inactive, and all 12 accounts / 16 contacts survived.
