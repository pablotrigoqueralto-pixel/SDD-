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
`/admin/pipelines` SHALL show both pipelines as cards with their stages in order: position, name, probability and badges (Ganada, Perdida, En riesgo, Inactiva). Each stage row SHALL offer "Subir", "Bajar" (disabled at the ends) and "Editar"; the edit form SHALL contain nombre, probabilidad (0–100) and activo. Semantic flags SHALL NOT be editable. Mobile shows the cards stacked; desktop (`lg`) shows them side by side.

#### Scenario: Reorder with buttons
- **WHEN** an admin taps "Bajar" on Contacto
- **THEN** `PUT /api/v1/pipelines/{id}/stages/order` is called with the swapped order and `If-Match` of the pipeline, and the list re-renders in the new order

#### Scenario: Edit probability
- **WHEN** an admin sets Demo to 40 and saves
- **THEN** `PATCH /api/v1/pipelines/{id}/stages/{stage_id}` is called with `If-Match` of the stage and the row shows 40 %

#### Scenario: Backend guards surface inline
- **WHEN** the API answers `last_active_stage` or `stage_probability_invalid`
- **THEN** the translated message appears in the form and nothing else changes

#### Scenario: Keyboard operation
- **WHEN** a user tabs through a pipeline card
- **THEN** every "Subir", "Bajar" and "Editar" button is reachable with a visible focus ring and an accessible name that includes the stage name

### Requirement: Spanish copy and accessibility
All strings SHALL come from the `admin` and `reference` i18n namespaces; every new page SHALL pass axe with zero serious/critical violations on desktop and mobile.

#### Scenario: No literal copy
- **WHEN** eslint runs on the new features
- **THEN** `react/jsx-no-literals` reports no error
