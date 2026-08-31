# import-api (delta)

The accounts/contacts importer accepts an optional `Especialidad` column.

## MODIFIED Requirements

### Requirement: Accounts and contacts import semantics
Account rows SHALL match by normalised CIF (uppercase, separators stripped); without CIF, by exact unaccented, case-folded, space-collapsed name; no match SHALL create the account through the existing creation defaults (territory from `province_code`, owner via the territory smart-default rules — no owner column: assignment stays a manager action). The `Teléfono` column SHALL create or update the account's **primary** phone (labelled "Principal"), leaving any other phone of that centre untouched. A row MAY embed one contact via optional `contact_*` columns (first/last name, email, phone, job title by name, **specialty by name**); the contact phone column SHALL create or update that contact's primary phone labelled "Móvil"; several contacts for one account repeat the account columns. The specialty SHALL be resolved case- and accent-insensitively against the catalogue's Spanish names, and an unknown value SHALL be a **message on the row, not an error** — the contact is created without a specialty, exactly as an unknown job title behaves. Contacts SHALL match by email within their account, falling back to normalised full name; imported contacts SHALL enter with the default consent state. Fuzzy matching SHALL NOT be used: near-matches create a new account rather than silently merging.

#### Scenario: CIF match updates
- **WHEN** a row carries the CIF of an existing centre with a new phone
- **THEN** the centre is `updated`, its primary phone takes the new number and its other labelled phones are preserved

#### Scenario: Embedded contact created
- **WHEN** a matched account row fills `contact_first_name`, `contact_last_name` and `contact_email`
- **THEN** the contact is created under that account (or `updated` if the email already exists there)

#### Scenario: Specialty resolved by name
- **WHEN** a row carries `Especialidad` = "cirugia vascular"
- **THEN** the contact is created with the "Cirugía Vascular" specialty despite the missing accent and lower case

#### Scenario: Unknown specialty is a message
- **WHEN** a row carries a specialty that is not in the catalogue
- **THEN** the contact is still created without a specialty and the row carries a message explaining it, not an error

#### Scenario: Near-name is a new account
- **WHEN** a row without CIF names "Clinica Tambre SL" and only "Clínica Tambre" exists
- **THEN** a new account is created (`created`), never a silent merge

#### Scenario: Unnormalisable phone is a row error
- **WHEN** a row's `Teléfono` cannot be normalised to E.164
- **THEN** that row is reported as `error` with the reason and the rest of the file is unaffected
