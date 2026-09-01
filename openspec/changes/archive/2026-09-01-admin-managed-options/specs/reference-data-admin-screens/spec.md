# reference-data-admin-screens (delta)

The shared "+ Añadir" dialog, and a pipeline screen that will not offer to lift a terminal stage.

## ADDED Requirements

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

## MODIFIED Requirements

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
