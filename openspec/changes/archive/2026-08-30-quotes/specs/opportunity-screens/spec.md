## ADDED Requirements

### Requirement: Presupuestos section on the opportunity sheet
The opportunity sheet SHALL show a Presupuestos section listing the opportunity's current quote versions (display number, estado badge with expiry visual, total, validez) linking to each sheet, with a "Nuevo presupuesto" action for eligible roles on open opportunities. When a quote is accepted the sheet SHALL reflect the won state after refresh.

#### Scenario: Create from the opportunity
- **WHEN** the owner clicks Nuevo presupuesto on an open opportunity
- **THEN** a draft is created from the opportunity's lines and the user lands on the new quote

#### Scenario: Closed opportunity
- **WHEN** the opportunity is won or lost
- **THEN** the section lists existing quotes but offers no creation action
