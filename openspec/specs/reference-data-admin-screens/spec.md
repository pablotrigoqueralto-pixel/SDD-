# reference-data-admin-screens

## Purpose
Admin lists and forms for brands, loss reasons and pipeline stages, plus the frontend reference-data cache used by later screens.

## Requirements

### Requirement: Reference data cache
The frontend SHALL load `GET /api/v1/reference-data` once per session through `useReferenceData()` (`staleTime` 5 minutes) and expose selectors `useAccountTypes()`, `useActivityTypes()`, `useDivisions()`, `useBrands()`, `useLossReasons()`, `usePipelines()`, `useJobTitles()`, `useProductFamilies()` that read from the same query. Any admin mutation on a master (job titles and product families included) SHALL invalidate the bundle.

#### Scenario: One request for many consumers
- **WHEN** three components using different selectors mount in the same screen
- **THEN** exactly one request to `/reference-data` is made

#### Scenario: Mutation refreshes consumers
- **WHEN** an admin renames a brand
- **THEN** the bundle query is invalidated and a mounted brand list shows the new name without a page reload

#### Scenario: Job titles from the bundle
- **WHEN** the contact form mounts after the bundle is loaded
- **THEN** the Cargo select is populated without an additional request

#### Scenario: Families from the bundle
- **WHEN** the product form mounts after the bundle is loaded
- **THEN** the Familia select is populated, grouped by division, without an additional request

### Requirement: Brand list and form
`/admin/marcas` SHALL list brands (name, "Propia" / "Competencia" badge, divisions, "Inactivo" badge) with a search box and a filter Propias / Competencia / Todas, plus the primary action "Nueva marca". `/admin/marcas/nueva` and `/admin/marcas/:id` SHALL open the shared sheet/dialog form with: nombre, tipo (Propia / Competencia), divisiones (checkbox list), activo (edit only). No other fields.

#### Scenario: Create competitor brand
- **WHEN** an admin fills "Cook Medical", selects Competencia and saves
- **THEN** `POST /api/v1/brands` is called with `is_own = false`, a toast "Marca creada" appears and the list shows the brand with the Competencia badge

#### Scenario: Duplicate name under the field
- **WHEN** the API answers 409 `brand_name_already_exists`
- **THEN** the message "Ya existe una marca con este nombre" is shown under the name field

#### Scenario: Conflict on edit
- **WHEN** saving returns 409 `conflict`
- **THEN** the shared conflict dialog opens and "Recargar" reloads the brand into the form

### Requirement: Loss reason list and form
`/admin/motivos-perdida` SHALL list loss reasons in order with badges "Requiere marca" / "Requiere nota" and "Inactivo", plus "Nuevo motivo". The form SHALL contain only nombre and activo (edit only); the requirement flags are displayed read-only.

#### Scenario: Add a reason
- **WHEN** an admin saves "Cambio de proveedor"
- **THEN** it appears last in the list and a toast "Motivo creado" is shown

### Requirement: Pipeline screen
`/admin/pipelines` SHALL show both pipelines as cards with their stages in order: position, name, probability and badges (Ganada, Perdida, En riesgo, Inactiva). Each stage row SHALL offer "Subir", "Bajar" (disabled at the ends **and wherever the move would place a terminal stage before an advancing one, or an advancing stage after a terminal one**) and "Editar"; the edit form SHALL contain nombre, probabilidad (0–100) and activo. Semantic flags SHALL NOT be editable. Mobile shows the cards stacked; desktop (`lg`) shows them side by side.

#### Scenario: Reorder with buttons
- **WHEN** an admin taps "Bajar" on Contacto
- **THEN** `PUT /api/v1/pipelines/{id}/stages/order` is called with the swapped order and `If-Match` of the pipeline, and the list re-renders in the new order

#### Scenario: Swapping Demo and Presupuesto
- **WHEN** an admin taps "Bajar" on Demo in the Equipos pipeline
- **THEN** Presupuesto moves above Demo, the board columns follow that order and no opportunity changes stage

#### Scenario: Terminal stages stay last
- **WHEN** an admin looks at the last advancing stage and at the first of the Ganada / Perdida / En riesgo rows
- **THEN** "Bajar" is disabled on the last advancing stage and "Subir" is disabled on the first terminal one, so the guard is never reached by clicking; the terminal stages may still be reordered among themselves, which breaks nothing

#### Scenario: Edit probability
- **WHEN** an admin sets Demo to 40 and saves
- **THEN** `PATCH /api/v1/pipelines/{id}/stages/{stage_id}` is called with `If-Match` of the stage and the row shows 40 %

#### Scenario: Backend guards surface inline
- **WHEN** the API answers `last_active_stage`, `stage_probability_invalid` or `stage_order_invalid`
- **THEN** the translated message appears in the form and nothing else changes

#### Scenario: Keyboard operation
- **WHEN** a user tabs through a pipeline card
- **THEN** every "Subir", "Bajar" and "Editar" button is reachable with a visible focus ring and an accessible name that includes the stage name

### Requirement: Spanish copy and accessibility
All strings SHALL come from the `admin` and `reference` i18n namespaces; every new page SHALL pass axe with zero serious/critical violations on desktop and mobile.

#### Scenario: No literal copy
- **WHEN** eslint runs on the new features
- **THEN** `react/jsx-no-literals` reports no error

### Requirement: Add-option dialog
A shared dialog SHALL let an `admin` create a catalogue entry without leaving the form they are filling. It SHALL be opened by a "+ Añadir" button rendered **next to** the corresponding `NativeSelect` — never as an option inside it — and SHALL be absent for every other role. It SHALL contain the name field, the extra field the catalogue requires (the "compra por licitación" tick for account types, nothing for the others) and Guardar / Cancelar. On success the created, reused or reactivated entry SHALL be **selected in the field that opened the dialog**, and the reference cache SHALL be invalidated so the entry appears in every other screen. The dialog SHALL state which of the three outcomes happened when the entry was not newly created.

#### Scenario: Create and continue
- **WHEN** an admin filling a contact opens "+ Añadir" beside Cargo, types "Farmacia hospitalaria" and saves
- **THEN** the dialog closes, the Cargo field shows the new title selected, the contact form keeps everything already typed and no navigation happens

#### Scenario: The name already exists
- **WHEN** the API answers `outcome = "reused"`
- **THEN** the dialog closes selecting the existing entry and a message explains that it already existed

#### Scenario: A deactivated entry comes back
- **WHEN** the API answers `outcome = "reactivated"`
- **THEN** the entry is selected and the message says it existed and has been reactivated

#### Scenario: Not an administrator
- **WHEN** a `sales_rep`, `sales_manager` or `back_office` opens any of the five forms
- **THEN** no "+ Añadir" button is rendered and the dropdowns behave exactly as before

#### Scenario: Backend error stays in the dialog
- **WHEN** the API answers 422 or 403
- **THEN** the message renders inside the dialog, the field keeps its previous value and the underlying form is untouched

#### Scenario: Keyboard and screen reader
- **WHEN** the dialog is opened with the keyboard
- **THEN** focus moves into it, the name field has a label, Escape closes it returning focus to the "+ Añadir" button, and axe reports no serious or critical violations
