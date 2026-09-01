# product-screens (delta)

"+ Añadir" beside Familia in the product form, creating the family in the division already in play.

## MODIFIED Requirements

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
