# activity-screens (delta)

The Hoy page gains a Día ↔ Mes switcher and a mobile-first month calendar of activities.

## ADDED Requirements

### Requirement: Día ↔ Mes switcher on Hoy
The Hoy page SHALL offer a two-option keyboard-operable segmented control switching between the existing day plan (**Día**, the default and landing view) and the month calendar (**Mes**), without a route change. The day plan, its selector and its blocks SHALL behave exactly as before when the Día view is active.

#### Scenario: Landing unchanged
- **WHEN** any user opens `/hoy`
- **THEN** the day plan renders as today, with the switcher showing Día selected

#### Scenario: Switch to the month
- **WHEN** the user selects Mes
- **THEN** the month calendar replaces the day plan and one calendar request is made for the current month

### Requirement: Month calendar grid
The Mes view SHALL render a Monday-first 7-column grid of the selected month with es-ES month and weekday names, previous/next month navigation and a "hoy" shortcut returning to the current month. Each day cell SHALL be a button with an accessible label including the date and its activity count, showing up to 4 colored dots plus a "+N" overflow — colored per rep in the team view and per activity type in the own view — with today's cell highlighted. Navigating months SHALL load each month with a single request.

#### Scenario: Dots and overflow
- **WHEN** a day holds six activities in scope
- **THEN** its cell shows four dots and "+2", and its accessible label announces six activities

#### Scenario: Previous month loads once
- **WHEN** the user taps ‹ from September
- **THEN** August renders after exactly one calendar request for August

### Requirement: Day expansion with planned and done distinguished
Tapping a day SHALL select it and render that day's activity list below the grid (docked beside it on `lg:`): each row with time, type icon and name, centre, and — in the team view — the owner's name, navigating to the existing activity flow. Done activities SHALL render visually distinguished (dimmed with a check) from planned ones; the distinction SHALL also be conveyed as text, never by style alone. An empty selected day SHALL show a neutral empty state.

#### Scenario: Expand a day
- **WHEN** the user taps a day with a planned call and a done visit
- **THEN** the list below shows both rows, the visit marked done, and tapping the call opens its activity flow

#### Scenario: Done is not only a color
- **WHEN** a done activity renders in the day list
- **THEN** its state is available as text/accessible content in addition to the dimmed styling

### Requirement: Team view, rep filter and legend
For `admin`, `sales_manager` and `back_office` the Mes view SHALL show the whole team by default with a "Comercial" selector defaulting to **Todos** (independent from the day view's selector) and a color legend mapping each visible rep to their dot color. A `sales_rep` SHALL see only their own month, with no rep selector and dots colored per activity type. Back office SHALL have no activity actions from the calendar (navigation only), as on the day view.

#### Scenario: Manager filters the month
- **WHEN** a manager picks one rep in the selector
- **THEN** the grid re-renders with only that rep's activities and the legend hides (one owner needs no color key)

#### Scenario: Rep sees no selector
- **WHEN** a `sales_rep` opens the Mes view
- **THEN** no rep selector renders and the dots reflect activity types

### Requirement: Month view copy and accessibility
All Mes-view copy SHALL come from the `activities` i18n namespace with product vocabulary; the switcher and the grid SHALL be keyboard-operable; the Hoy page with the Mes view active SHALL pass axe on mobile and desktop.

#### Scenario: Axe clean in month view
- **WHEN** the E2E accessibility scan runs on `/hoy` with Mes selected in both viewports
- **THEN** no serious violations are reported
