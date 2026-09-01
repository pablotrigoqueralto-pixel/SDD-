# product-screens

## Purpose
Mobile-first catalogue screens: searchable list with division chips and filters, six-field product form with Spanish prices, families administration and navigation from Más.

## Requirements

### Requirement: Catalogue navigation
"Catálogo" SHALL be reachable from the "Más" screen for every role at `/catalogo`; "Familias" SHALL appear in the admin hub at `/admin/familias` for `admin` only.

#### Scenario: Rep opens the catalogue
- **WHEN** a rep taps Más → Catálogo
- **THEN** the catalogue list renders with the search box visible above the results

### Requirement: Catalogue list
`/catalogo` SHALL show a search box ("Nombre o código Sage", debounced 300 ms), division chips, a "Filtros" control with brand (own brands first), type and — for managers/admins — state, and a list of product cards showing kind icon, name, brand, family, SKU and list price formatted `es-ES` EUR. The list SHALL paginate through `DataList`, keep filters in the URL query string, and show `EmptyState` when nothing matches. Users with write rights SHALL see a "Nuevo producto" action.

#### Scenario: Search by SKU
- **WHEN** the user types "HAD-10"
- **THEN** after the debounce the list requests `q=HAD-10` and shows matching cards

#### Scenario: Filters survive navigation
- **WHEN** the user filters by Cardiología, opens a product and returns
- **THEN** the Cardiología filter is still applied

#### Scenario: Rep sees no create action
- **WHEN** a rep opens the catalogue
- **THEN** no "Nuevo producto" action is rendered

### Requirement: Product form
`/catalogo/nuevo` and `/catalogo/:id` SHALL open a `ResponsiveFormContainer` form with Código Sage, Nombre, Marca (select), Familia (select grouped by division), Tipo (segmented Equipo / Consumible / Servicio, no default) and Precio de lista above the fold, and a collapsed "Más datos" with Unidad (default `ud`), Descripción, Coste (only for cost viewers) and Activo. For an `admin`, Familia SHALL offer "+ Añadir", which creates a family **in the division of the family currently selected** — or, with none selected, asks for the division — and selects the result. Validation messages SHALL be i18n keys; price inputs SHALL use `inputMode="decimal"` and accept comma or dot decimals, sending two-decimal strings. Saving SHALL send `If-Match` on edit and open the `ConflictDialog` on 409 `conflict`; `product_sku_exists` SHALL be shown inline on the SKU field with a link to the existing product. Roles without write rights SHALL see the form read-only.

#### Scenario: Minimal create
- **WHEN** back office fills SKU, name, brand, family, type and "1.250,50" and saves
- **THEN** a POST is sent with `list_price = "1250.50"`, `unit = "ud"` and the list shows the new product

#### Scenario: Admin adds a family mid-form
- **WHEN** an admin has a Vascular family selected, opens "+ Añadir" beside Familia and creates "Láser"
- **THEN** the family is created in the Vascular division, appears selected in the field and the rest of the product form is untouched

#### Scenario: Back office sees no add button
- **WHEN** back office opens the product form
- **THEN** Familia shows the catalogue families without "+ Añadir"

#### Scenario: Duplicate SKU inline
- **WHEN** the API answers 409 `product_sku_exists`
- **THEN** the SKU field shows the duplicate message with a link to `/catalogo/{existing_product_id}`

#### Scenario: Cost hidden for back office
- **WHEN** back office opens the form
- **THEN** no Coste field is rendered

#### Scenario: Manager read-only
- **WHEN** a manager opens `/catalogo/:id`
- **THEN** the fields are disabled and no save button is rendered

### Requirement: Families admin screen
`/admin/familias` SHALL list families grouped by division with name, order and state, and SHALL offer create and edit forms (name, division — locked on edit — order, active) following the loss-reasons screen pattern; mutations SHALL invalidate the reference bundle.

#### Scenario: Create a family
- **WHEN** an admin creates "Láser" in Cardiología
- **THEN** it appears under Cardiología and the product form's family select offers it without a reload

### Requirement: Catalogue Spanish copy and accessibility
All catalogue copy SHALL live in the `catalogue` i18n namespace using business vocabulary ("Código Sage", never "SKU" or "item" in the UI); list, form and admin screens SHALL pass axe on desktop and mobile with no serious or critical violations; the segmented type control SHALL be a radio group operable by keyboard.

#### Scenario: axe passes
- **WHEN** the catalogue list and the product form are scanned on the Pixel 7 profile
- **THEN** no serious or critical violations are reported
