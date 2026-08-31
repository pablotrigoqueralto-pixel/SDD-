# dashboard-screens

The Informes page: KPI cards with previous-period deltas, CSS-bar visualisations for pipeline and breakdowns, activity section and neglected-accounts list, with a period selector — mobile-first, live data, no exports.

## ADDED Requirements

### Requirement: Informes page
`/informes` SHALL be reachable by every authenticated role and render, on mobile as a single stacked column: a header "Informes" with a segmented period selector (Mes · Trimestre · Año, default Mes), a 2×2 KPI card grid, "Pipeline por etapa", "Por división", "Por comercial" (full-scope viewers only — the section is absent for `sales_rep`), "Actividad" and "Centros descuidados". On `lg:` and above the same sections SHALL arrange into a two-column grid with the KPI cards full-width on top. Data SHALL come from a single `GET /dashboard?period=` request per selected period; switching the selector refetches. The page SHALL show skeletons while loading and the standard error state with retry on failure.

#### Scenario: Rep opens Informes
- **WHEN** a `sales_rep` opens `/informes`
- **THEN** the panel shows their own portfolio figures, the "Por comercial" section is absent, and one dashboard request was made

#### Scenario: Switching period
- **WHEN** the user taps "Trimestre"
- **THEN** `GET /dashboard?period=quarter` is requested and every section updates to the quarter figures

### Requirement: KPI cards with comparison
The KPI grid SHALL show four cards: "Ganado" (€ and count, delta against the previous period), "Conversión" (percentage with the closed counts, e.g. "3 de 5", delta against the previous period; "—" when null), "Previsión" (€, with a hint explaining "importe × probabilidad de etapa"; no delta) and "Pipeline abierto" (€ total; no delta). Deltas SHALL render direction and the previous value; amounts SHALL use the es-ES currency formatting already used across the app.

#### Scenario: Won card with delta
- **WHEN** the period won 30000.00 against 20000.00 in the previous period
- **THEN** the "Ganado" card shows the amount, the count and an upward delta referencing the previous value

#### Scenario: Conversion without closed deals
- **WHEN** `conversion.rate` is null
- **THEN** the card shows "—" and no misleading 0%

### Requirement: Bars without a chart library
"Pipeline por etapa", "Por división" and "Por comercial" SHALL render as semantic lists with CSS-sized horizontal bars proportional to the amounts — no charting dependency. Each row SHALL carry its label and figures as real text (stage: € and count; breakdown rows: won €, forecast €, pipeline €), so the information is complete without interpreting the bar. Sections with no rows SHALL show a neutral empty state.

#### Scenario: Stage funnel
- **WHEN** the pipeline has three stages with open amounts
- **THEN** three rows render in stage order, each with name, formatted amount, count and a bar proportional to the largest stage

#### Scenario: Empty division breakdown
- **WHEN** the scope has no opportunities in the period or open
- **THEN** "Por división" shows the empty state instead of an empty chart

### Requirement: Activity and neglected accounts sections
"Actividad" SHALL list each rep with their total done activities in the period and per-type counts using the product vocabulary (Visitas, Llamadas, Demos…). "Centros descuidados" SHALL show the total as a badge and list up to 20 accounts with the days since last contact ("Nunca" when never contacted), each row navigating to the account 360º page.

#### Scenario: Neglected account navigates
- **WHEN** the user taps a neglected account row
- **THEN** the app navigates to that account's 360º page

#### Scenario: Never contacted copy
- **WHEN** an entry has null days since contact
- **THEN** the row reads "Nunca" instead of a number

### Requirement: Informes card in Más
Más SHALL show an "Informes" card for every role: first card for `sales_rep`, `sales_manager` and `back_office`; for `admin` immediately after "Administración".

#### Scenario: Manager finds Informes
- **WHEN** a `sales_manager` opens Más
- **THEN** "Informes" is the first card and navigates to `/informes`

### Requirement: Spanish copy and accessibility
All copy SHALL come from a new `dashboard` i18n namespace in Spanish business vocabulary (Ganado, Previsión, Pipeline abierto, Conversión, Centros descuidados); no literal JSX strings. The period selector SHALL be keyboard-operable with the selected option exposed to assistive technology; scrollable section containers SHALL be focusable; the page SHALL pass axe on mobile and desktop.

#### Scenario: Axe clean
- **WHEN** the E2E accessibility scan runs on `/informes` in both viewports
- **THEN** no violations are reported
