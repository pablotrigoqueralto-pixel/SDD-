# opportunity-screens

## Purpose
Mobile-first pipeline screens: filterable list, accessible desktop kanban with drag and drop, three-field creation, the opportunity sheet with win/lose/at-risk actions, lines and history.

## Requirements

### Requirement: Pipeline navigation and page
"Pipeline" SHALL be the third navigation entry (`/oportunidades`) for every role. Below `lg` the page SHALL render a filterable list (pipeline, stage, division, owner for staff, state chips Abiertas / Ganadas / Perdidas, "Licitación" and "En riesgo" toggles, search), each card showing name, centre, stage badge, amount, days in stage, expected close date and the badges "Licitación" / "En riesgo"; at `lg` and above it SHALL render the kanban of the selected pipeline (default: the first pipeline of the user's divisions) with one column per open stage (count and total in the header), the closed summary line and the same filters. Filters SHALL live in the URL query string.

#### Scenario: Mobile list
- **WHEN** a rep opens `/oportunidades` on a phone
- **THEN** open opportunities are listed with amount and days in stage, and choosing "Perdidas" requests `status=lost`

#### Scenario: Desktop board
- **WHEN** a manager opens `/oportunidades` on desktop
- **THEN** `GET /opportunities/board?pipeline_id=` is requested and the columns show counts and totals formatted in euros

### Requirement: Kanban drag and drop
Cards SHALL be draggable between open columns with pointer and keyboard (Space lifts, arrows move between columns, Space drops) with Spanish live announcements; dropping on an open column SHALL call `POST /opportunities/{id}/stage` optimistically and roll back with the conflict dialog on 409; dropping on the Ganada or Perdida column SHALL open the win or lose form instead of moving. Cards of opportunities the user cannot write SHALL not be draggable.

#### Scenario: Keyboard move
- **WHEN** the user focuses a card in Contacto, presses Space, ArrowRight and Space
- **THEN** the card is announced as moved to Demo and `/stage` is called with the Demo stage id

#### Scenario: Drop on Perdida
- **WHEN** a card is dropped on the Perdida column
- **THEN** no request is sent until the lose form is saved

### Requirement: Opportunity creation form
`/oportunidades/nueva` and `/centros/:id/oportunidades/nueva` SHALL open a `ResponsiveFormContainer` with Centro (pre-filled or searched over `GET /accounts?q=`), División (account divisions first, showing the default pipeline as a hint) and Importe estimado above the fold, and a collapsed "Más datos" with Nombre (placeholder = the generated name), Fecha de cierre estimada (default +90/+30 days by pipeline), Licitación (checked when the centre buys via tender) with Expediente, Fecha límite and Adjudicación estimada, Descripción and, for managers, Comercial. Saving SHALL navigate to the opportunity sheet.

#### Scenario: Three fields
- **WHEN** a rep opens the form from a centre, picks Vascular, types "30.000" and saves
- **THEN** `POST /opportunities` is sent with `{ account_id, division_id, estimated_amount: "30000.00" }` and the sheet opens

#### Scenario: Tender defaults
- **WHEN** the centre is a Hospital público
- **THEN** "Licitación" is pre-checked and the tender fields are visible

### Requirement: Opportunity sheet
`/oportunidades/:id` SHALL render a header (name, centre link, amount, stage picker among open stages, days in stage, badges) with the actions "Ganar", "Perder", "En riesgo" (consumables, won only), "Editar" and, for managers, "Reasignar" and "Reabrir" (closed only); sections Datos (close date, tender block, description), Productos (lines editor: product search over the catalogue, quantity, unit price, line total, amount recomputed after each save; hidden estimate when lines exist), Actividades (timeline filtered by the opportunity with "Nueva actividad" pre-linked) and Historial (stage history with dates and actors). Win form: importe final (default amount) and fecha; lose form: motivo, marca (shown and required when the reason requires it), nota (required for Otro). Closed opportunities SHALL show the closing block and disable every write action except "Reabrir". Users without write rights SHALL see the sheet read-only.

#### Scenario: Lose with Competidor
- **WHEN** the owner taps "Perder", picks Competidor and saves without a brand
- **THEN** the form shows "Indica la marca competidora" without sending the request

#### Scenario: Lines change the amount
- **WHEN** the owner adds a line 2 × Doppler ES-100
- **THEN** `POST /opportunities/{id}/lines` is sent with `If-Match` and the header amount becomes 25.000,00 €

#### Scenario: Read-only for back office
- **WHEN** back office opens the sheet
- **THEN** no action button is rendered and the stage picker is disabled

### Requirement: Spanish copy and accessibility
All copy SHALL live in the `opportunities` i18n namespace with business vocabulary (Oportunidad, Etapa, Ganada, Perdida, Licitación, En riesgo, Importe estimado); list, board, sheet and forms SHALL pass axe on desktop and mobile with no serious or critical violations; the board SHALL be operable without a pointer.

#### Scenario: axe passes
- **WHEN** the board and the opportunity sheet are scanned on desktop and the list on the Pixel 7 profile
- **THEN** no serious or critical violations are reported

### Requirement: Presupuestos section on the opportunity sheet
The opportunity sheet SHALL show a Presupuestos section listing the opportunity's current quote versions (display number, estado badge with expiry visual, total, validez) linking to each sheet, with a "Nuevo presupuesto" action for eligible roles on open opportunities. When a quote is accepted the sheet SHALL reflect the won state after refresh.

#### Scenario: Create from the opportunity
- **WHEN** the owner clicks Nuevo presupuesto on an open opportunity
- **THEN** a draft is created from the opportunity's lines and the user lands on the new quote

#### Scenario: Closed opportunity
- **WHEN** the opportunity is won or lost
- **THEN** the section lists existing quotes but offers no creation action
