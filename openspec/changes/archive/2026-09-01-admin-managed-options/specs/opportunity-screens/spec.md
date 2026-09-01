# opportunity-screens (delta)

"+ Añadir" beside Motivo in the lose form.

## MODIFIED Requirements

### Requirement: Opportunity sheet
`/oportunidades/:id` SHALL render a header (name, centre link, amount, stage picker among open stages, days in stage, badges) with the actions "Ganar", "Perder", "En riesgo" (consumables, won only), "Editar" and, for managers, "Reasignar" and "Reabrir" (closed only); sections Datos (close date, tender block, description), Productos (lines editor: product search over the catalogue, quantity, unit price, line total, amount recomputed after each save; hidden estimate when lines exist), Actividades (timeline filtered by the opportunity with "Nueva actividad" pre-linked) and Historial (stage history with dates and actors). Win form: importe final (default amount) and fecha; lose form: motivo, marca (shown and required when the reason requires it), nota (required for Otro). For an `admin`, the lose form's motivo SHALL offer "+ Añadir", which creates a loss reason and selects it; a reason created this way SHALL require neither brand nor note, since those flags are not editable through the API. Closed opportunities SHALL show the closing block and disable every write action except "Reabrir". Users without write rights SHALL see the sheet read-only.

#### Scenario: Lose with Competidor
- **WHEN** the owner taps "Perder", picks Competidor and saves without a brand
- **THEN** the form shows "Indica la marca competidora" without sending the request

#### Scenario: Admin adds a loss reason while losing
- **WHEN** an admin taps "Perder", finds no suitable motivo, opens "+ Añadir", creates "Cambio de proveedor" and saves the dialog
- **THEN** the motivo field shows it selected, neither brand nor note becomes required, and saving the lose form sends that `loss_reason_id`

#### Scenario: An owner who is not admin
- **WHEN** a `sales_rep` owner opens the lose form
- **THEN** the motivo select shows the catalogue reasons without "+ Añadir"

#### Scenario: Lines change the amount
- **WHEN** the owner adds a line 2 × Doppler ES-100
- **THEN** `POST /opportunities/{id}/lines` is sent with `If-Match` and the header amount becomes 25.000,00 €

#### Scenario: Read-only for back office
- **WHEN** back office opens the sheet
- **THEN** no action button is rendered and the stage picker is disabled
