## ADDED Requirements

### Requirement: Import audit events
Each confirmed import run SHALL record one event in the same transaction as the imported rows — `import.products_executed` or `import.accounts_executed` — carrying the file name and the per-outcome counts (created, updated, unchanged, errors) with the acting user. Dry runs SHALL record nothing. Individual imported rows SHALL additionally produce their normal per-entity audit events through the services they flow through.

#### Scenario: Run recorded with counts
- **WHEN** back office confirms a catalogue import with 40 created, 12 updated, 45 unchanged and 3 errors
- **THEN** one `import.products_executed` row exists with those counts and the file name, plus the per-product `product.*` events

#### Scenario: Dry run leaves no trace
- **WHEN** a preview is generated and the user never confirms
- **THEN** the audit log gains no rows
