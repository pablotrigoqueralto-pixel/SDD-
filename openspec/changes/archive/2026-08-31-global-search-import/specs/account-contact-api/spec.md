## ADDED Requirements

### Requirement: Accounts import endpoint
`POST /api/v1/accounts/import` SHALL implement the dry-run/confirm flow of `import-api` for accounts with optionally embedded contacts. Account rows write through the existing account service, so creation defaults (territory from province, owner rules), validations (CIF, province, postal code, phone) and audit events apply exactly as in manual creation; back-office updates stay limited to the administrative fields and imports never rename an account. Embedded contacts are written by the importer itself with the same domain validation and `contact.*` audit events — the endpoint's role gate (admin/back office) is the authorisation, and the manual contact endpoints keep their account-writer rule unchanged.

#### Scenario: Same validation as the form
- **WHEN** an imported row carries an invalid province code
- **THEN** the row is an `error` with the same validation message the account form would show, and no account is written
