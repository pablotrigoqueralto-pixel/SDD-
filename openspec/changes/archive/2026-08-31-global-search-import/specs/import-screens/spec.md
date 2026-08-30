## ADDED Requirements

### Requirement: Import screens
`/importar/catalogo` and `/importar/centros` SHALL share one flow: pick a `.csv`/`.xlsx` file → automatic dry-run preview → confirm → result summary. The preview SHALL show the totals per outcome and a row table (row number, label, outcome chip, error message), with error rows first. Confirming SHALL re-post with `dry_run=false` and show the applied totals; when errors remain, a "Descargar informe de errores" action SHALL download a client-generated CSV of the failing rows. The screens SHALL be reachable from the Admin hub (admins) and from Más (back office), be role-gated accordingly, state the expected columns with their Spanish aliases, and use the `imports` i18n namespace.

#### Scenario: Preview before writing
- **WHEN** back office picks their Excel on `/importar/centros`
- **THEN** the preview appears without importing anything and the confirm button names the pending counts ("Importar 97 filas")

#### Scenario: Error report download
- **WHEN** a confirmed import ends with 3 error rows
- **THEN** the summary offers the error CSV containing those rows with their messages

#### Scenario: Hidden from sales roles
- **WHEN** a `sales_rep` navigates to `/importar/catalogo`
- **THEN** the "Sin permiso" page renders and no import entry is visible in their navigation
