# search-screens

## Purpose
The Buscar page on the fifth navigation slot: one box with debounce, results grouped by type with hand-offs to the filtered lists, and device-local recent searches and visited records.

## Requirements

### Requirement: Buscar page
`/buscar` SHALL render a single search box (autofocused, min 2 characters, 300 ms debounce, one in-flight request) and the grouped results: one titled section per entity type with the group's rows — reusing the established badge and amount presentation — where every row navigates to the record's sheet. Groups with `has_more` SHALL offer "Ver todas" linking to the corresponding filtered list (`/centros?q=`, `/oportunidades?q=&status=all`, `/presupuestos?q=&status=all`); the contacts group, having no global list, SHALL show up to its cap without a link. Empty results SHALL show the localized empty state naming what can be searched. All copy SHALL live in the `search` i18n namespace.

#### Scenario: Row navigates
- **WHEN** the user taps the quote row "P-2026-0003"
- **THEN** they land on `/presupuestos/:id`

#### Scenario: See all hand-off
- **WHEN** the accounts group shows `has_more`
- **THEN** "Ver todas" opens `/centros?q=<término>` with the same term applied

#### Scenario: Nothing found
- **WHEN** a search returns four empty groups
- **THEN** the page shows the empty state and no section titles

### Requirement: Device-local recents
Before typing (and after clearing the box) the page SHALL show the device's last 8 submitted searches and last 8 opened results (kind, id, label), stored in `localStorage` when the user opens a result or submits a search. Tapping a recent search re-runs it; tapping a recent record opens its sheet. Nothing SHALL be sent to the server, and a missing/failing `localStorage` SHALL simply show the empty help text.

#### Scenario: Recent record shortcut
- **WHEN** the user opened "Clínica Tambre" from a search yesterday and returns to `/buscar`
- **THEN** the centre appears under "Recientes" and one tap opens its 360º page

#### Scenario: Recents are per device
- **WHEN** the same user opens the app on another device
- **THEN** the recents list starts empty
