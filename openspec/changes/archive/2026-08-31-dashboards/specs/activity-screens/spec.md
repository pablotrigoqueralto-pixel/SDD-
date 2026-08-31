# activity-screens (delta)

The Hoy page for management opens with a key-figures block sourced from the dashboard.

## ADDED Requirements

### Requirement: Key figures on Hoy for management
The Hoy page SHALL render, for `sales_manager` and `admin` only, a compact key-figures block above the day plan showing the current month's won €, weighted forecast € and open pipeline €, sourced from the same `GET /dashboard?period=month` read model as the Informes page (component provided by the dashboard feature through its public index). The block SHALL link to `/informes` and SHALL NOT render for `sales_rep` or `back_office`. While loading it SHALL show a skeleton; on error it SHALL disappear without breaking the day plan.

#### Scenario: Manager sees the block
- **WHEN** a `sales_manager` opens `/hoy`
- **THEN** the key-figures block shows the month's won, forecast and open pipeline and navigates to `/informes` on tap

#### Scenario: Rep does not see the block
- **WHEN** a `sales_rep` opens `/hoy`
- **THEN** no key-figures block is rendered and the day plan starts at the top

#### Scenario: Dashboard error does not break Hoy
- **WHEN** the dashboard request fails for a manager
- **THEN** the block is simply absent and the rest of the Hoy page renders normally
