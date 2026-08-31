# search-api (delta)

Phone lookup searches the whole phone list instead of the two old columns.

## MODIFIED Requirements

### Requirement: Identifier routing
Before name matching, the query SHALL be inspected once and routed: `P-YYYY-NNNN` (full or partial number, optional `-vN`) → quotes by `year`/`number`; a term containing `@` → exact/prefix on contact and account emails; a CIF/NIF-shaped term → normalised comparison against `accounts.tax_id`; 7 or more digits after stripping spaces, dots, dashes and `+` → digit-only comparison against every entry of the account and contact phone lists, whatever its label. Identifier matches SHALL appear in their entity's group alongside any name matches.

#### Scenario: Quote number
- **WHEN** a user searches "P-2026-0003"
- **THEN** the quotes group contains that quote's current version and other groups stay name-matched

#### Scenario: Phone with separators
- **WHEN** a user searches "612 34 56 78"
- **THEN** the contact whose mobile is stored as "+34612345678" is found

#### Scenario: Any labelled phone matches
- **WHEN** a user searches the number stored as the centre's "Servicio de vascular" phone, not its primary one
- **THEN** the centre appears in the accounts group

#### Scenario: CIF
- **WHEN** a user searches "b-12345678"
- **THEN** the account with `tax_id` "B12345678" is found
