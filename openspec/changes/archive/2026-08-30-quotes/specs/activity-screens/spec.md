## ADDED Requirements

### Requirement: Presupuestos por caducar on Hoy
The Hoy page SHALL render a "Presupuestos por caducar" block from `/me/today`'s `expiring_quotes`: each entry shows the display number, account, total and days until `valid_until` (or "caduca hoy"), linking to the quote sheet. The block SHALL be hidden when empty.

#### Scenario: Expiring quote surfaced
- **WHEN** the user's sent quote expires in 3 days
- **THEN** Hoy shows it in the block with the remaining days

### Requirement: Quote events in the timeline UI
Timeline entries of kind `quote_sent`, `quote_accepted` and `quote_rejected` SHALL render with their own icon and the server-provided Spanish title, linking to the quote sheet, consistent with the existing stage-change entries.

#### Scenario: Accepted entry rendered
- **WHEN** the account timeline contains a `quote_accepted` entry
- **THEN** it renders with the quote icon, the server title and a link to the quote
