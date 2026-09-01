## Why

Sixth item of the sales director's feedback: "que el administrador pueda añadir opciones a los desplegables". Today a missing cargo, especialidad, tipo de centro, motivo de pérdida or familia de producto stops the person in the middle of the form they were filling: they must abandon it, walk to Administración (if a screen exists at all), create the entry and start again — and for **specialties and account types no screen exists**, so the only way in is a new deployment. The catalogues that grow with the business are exactly the ones a rep meets first.

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- **"+ Añadir" beside five business dropdowns**, for `admin` only: Cargo and Especialidad (contact form), Tipo de centro (account form), Motivo de pérdida (losing an opportunity) and Familia (product form). The new entry is created and **selected straight away**, so the interrupted form continues where it was.
- **A repeated name reuses the existing entry instead of duplicating it**: matching is case- and accent-insensitive, and an entry that was deactivated is reactivated and the screen says so. Two spellings of the same cargo never coexist.
- **Two catalogues gain creation endpoints they never had**: `POST /api/v1/specialties` (left out of change 13 on purpose) and `POST /api/v1/account-types`, which until now was seed-only. A new account type asks for its "compra por licitación" flag, because that flag is what makes the tender fields appear on an opportunity — a type created without it would be quietly incomplete.
- **A new familia created from the product form belongs to the division already chosen there**, the same rule the families admin screen applies.
- **Terminal stages are pinned to the end of a pipeline**: `Ganada`, `Perdida` and `En riesgo` can no longer be moved above an advancing stage, in the API and in the screen. Reordering the advancing stages (which is how Demo and Presupuesto are swapped) already works today with "Subir"/"Bajar" and stays as it is.
- Creating an option from a dropdown records the same audit event as creating it from Administración; nothing new appears in the audit vocabulary.

## Capabilities

### Modified Capabilities
- `reference-data-model`: account types and specialties become administrator-editable masters (creation, uniqueness and reactivation rules), and stage ordering gains the terminal-stages-last invariant.
- `reference-data-api`: `POST /api/v1/specialties` and `POST /api/v1/account-types`; loss reason creation reuses-and-reactivates an existing name instead of answering 409; reordering rejects an order that lifts a terminal stage above an advancing one.
- `account-contact-api`: job title creation reuses-and-reactivates an existing name instead of answering 409 (the job titles endpoints belong to this capability, not to reference-data-api).
- `product-api`: creating a product family reuses an existing name within the same division instead of answering 409.
- `reference-data-admin-screens`: the shared "+ Añadir" dialog, its behaviour when the name already exists, and the pipeline screen no longer offering to move a terminal stage.
- `account-screens`: "+ Añadir" next to Cargo and Especialidad in the contact form and next to Tipo de centro in the account form.
- `product-screens`: "+ Añadir" next to Familia in the product form, creating it in the division already selected.
- `opportunity-screens`: "+ Añadir" next to Motivo de pérdida in the lose dialog.

## Non-goals

- No renaming or deactivating from the dropdown: those stay in Administración. A field is not an administration screen, and renaming an entry silently rewrites how every other record reads.
- No new administration screens for specialties or account types in this change (the dropdown covers creation; the full CRUD screens can follow if they are ever needed).
- No permission change: only `admin` sees the button, exactly as with every other reference write.
- No change to activity types, brands, divisions or territories — brands and loss reasons already have their screens, and divisions/territories are structural, not "opciones de un desplegable".
- No merging of duplicates that already exist in a catalogue; this change stops new ones appearing.
- No drag-and-drop for stages: the existing "Subir"/"Bajar" buttons already reorder them, work on mobile and are keyboard-accessible.

## Impact

- **Roles**: unchanged. `admin` gains a shortcut to what it could already do (and, for specialties and account types, what nobody could do without a deployment); every other role sees the dropdowns exactly as today.
- **Backend**: `SpecialtyService` and `AccountTypeService` (create only), the reuse-and-reactivate rule shared by the catalogue create services, the terminal-stage guard in the reorder command, and `api-spec.yml` regenerated.
- **Frontend**: one shared `CreateOptionDialog` used by five forms (never five copies), the reference cache invalidated so the new entry appears everywhere at once, the pipeline screen's move buttons disabled for terminal stages, and `admin`/`contacts`/`accounts`/`catalogue`/`opportunities` i18n growth.
- **Docs**: `data-model.md` (which masters are administrator-editable and the reactivation rule), `development_guide.md` (the seeded-masters table gains the "editable by administrators" truth for specialties and account types), `api-spec.yml`.
- **Constitution principles served**: 30-second interactions (a missing option costs one dialog, not a lost form), data honesty (reuse instead of a second spelling of the same thing), and one screen one purpose (the dropdown adds, Administración governs).
