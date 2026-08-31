# activity-screens

## Purpose
Mobile-first screens for activities: two-tap form, one-tap lifecycle actions, account timeline and the Hoy page.

## Requirements

### Requirement: Activity form
The activity form SHALL open in `ResponsiveFormContainer` from the 360º page ("Nueva actividad", centre pre-filled), from the timeline page, from the opportunity sheet (centre and opportunity pre-filled) and from "Hoy" (`/hoy/nueva`, where the centre is chosen first with a search box over `GET /accounts?q=`). Above the fold: activity type as segmented buttons with the master icons, centre, date/time (default now) and a "Hecha / Planificada" toggle (default Hecha; "Planificada" defaults the date to tomorrow 09:00 and is disabled for Nota). Collapsed "Más datos": oportunidad (select of the centre's open opportunities, pre-selected when opened from the sheet, hidden when the centre has none), contactos (checkbox list of the account's active contacts, primary pre-checked), duración, resultado, asunto, notas, próxima acción (tipo + fecha). Managers SHALL see a "Comercial" selector defaulting to themselves. Backend errors (`note_cannot_be_planned`, `contact_not_in_account`, `opportunity_not_in_account`, `next_action_in_past`) SHALL render inline.

#### Scenario: Three-tap visit
- **WHEN** a rep opens the form from a centre, taps "Visita" and "Guardar"
- **THEN** one `POST /activities` is sent with `{ account_id, activity_type_id, status: "done", scheduled_at: now, contact_ids: [primary] }` and the timeline section shows the visit

#### Scenario: Plan with next action
- **WHEN** the rep selects "Planificada", picks a date and saves
- **THEN** the payload has `status: "planned"` and the new activity appears in "Hoy" when the date is today

#### Scenario: Nota cannot be planned
- **WHEN** the rep selects "Nota"
- **THEN** the "Planificada" option is disabled

#### Scenario: Visit from the opportunity sheet
- **WHEN** the rep opens "Nueva actividad" from an opportunity, taps "Visita" and saves
- **THEN** the payload includes `opportunity_id` and the activity appears in the sheet's Actividades section

### Requirement: Timeline section and page
The "Actividades" section of `/centros/:id` SHALL render the five most recent `TimelineEntryRead` items — activities (icon, title, relative date, owner, outcome badge, contacts) and opportunity stage entries (stage icon, "<oportunidad> → <etapa>" or "Ganada / Perdida · importe", actor, link to the opportunity) — with "Ver todas" → `/centros/:id/actividades`, a page with the full paginated list and filters by kind (actividades / etapas), type and status. Planned entries SHALL show "Hecha" and "Reprogramar" actions; done entries SHALL open the edit sheet when the user may edit them.

#### Scenario: Section content
- **WHEN** the 360º page loads for an account with seven activities
- **THEN** the section shows five entries newest first, a count of seven and "Ver todas"

#### Scenario: Locked activity
- **WHEN** a rep opens a visit done 10 days ago
- **THEN** the sheet is read-only and shows "Solo dirección comercial puede editar esta actividad"

#### Scenario: Stage entry
- **WHEN** the timeline contains an `opportunity_closed` entry
- **THEN** it renders "Ganada · 24.000,00 €" with the opportunity name linking to `/oportunidades/:id`

### Requirement: Hoy page
`/hoy` SHALL render the header with the date and "Nueva actividad", the weekly summary line, the "Atrasadas" list (warning style, oldest first), the "Hoy" list (by time), each card with type icon, time, centre, subject and the actions "Hecha" (opens a compact sheet: resultado, notas, próxima acción; "Guardar" completes) and "Reprogramar" (date-time picker calling `/reschedule`), and, when non-empty, the blocks "Licitaciones esta semana" (opportunity cards with deadline, overdue in warning style) and "Centros en riesgo" (opportunity cards with days at risk), both linking to the opportunity sheet. Managers, admins and back office SHALL see a "Comercial" selector that switches the payload (`?user_id=`); back office actions SHALL be hidden. Empty states SHALL read "Nada planificado para hoy" / "Sin actividades atrasadas". A rep without territory or division SHALL still see the scope warning from change 01.

#### Scenario: Complete from Hoy
- **WHEN** the rep taps "Hecha" on a planned visit and saves with resultado "Positiva"
- **THEN** `POST /activities/{id}/complete` is sent with `If-Match`, the card leaves the list and the weekly counter increases

#### Scenario: Reschedule an overdue call
- **WHEN** the rep taps "Reprogramar" on an overdue call and picks tomorrow 10:00
- **THEN** `POST /activities/{id}/reschedule` is sent and the card leaves "Atrasadas"

#### Scenario: Manager switches rep
- **WHEN** a manager selects another rep in the selector
- **THEN** `GET /me/today?user_id=<rep>` is requested and the lists show that rep's day

#### Scenario: Tender block
- **WHEN** `tenders_due` contains a tender overdue by two days
- **THEN** the "Licitaciones esta semana" block renders the card in warning style; when both blocks are empty neither heading is rendered

### Requirement: Account list and header show contact recency
The account list SHALL show "Último contacto" (relative date or "Nunca") and support `sort=last_contact_at`; the 360º header SHALL show "Último contacto" and "Próxima actividad".

#### Scenario: Never contacted
- **WHEN** an account has no done contact-counting activity
- **THEN** the list shows "Nunca"

### Requirement: Spanish copy and accessibility
All copy SHALL come from the `activities` i18n namespace with product vocabulary (Visita, Llamada, Demo, Formación, Nota, Hecha, Planificada, Atrasadas); the type picker SHALL be a radio group operable by keyboard; the form, the timeline page and "Hoy" SHALL pass axe on mobile and desktop.

#### Scenario: No literal copy
- **WHEN** ESLint runs
- **THEN** no `jsx-no-literals` violation exists in `features/activities`

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
