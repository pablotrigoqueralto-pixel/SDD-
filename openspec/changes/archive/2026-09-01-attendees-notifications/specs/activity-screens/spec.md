# activity-screens (delta)

Attendees in the activity form, the invited badge, the notifications block and the third agenda view.

## MODIFIED Requirements

### Requirement: Activity form
The activity form SHALL open in `ResponsiveFormContainer` from the 360º page ("Nueva actividad", centre pre-filled), from the timeline page, from the opportunity sheet (centre and opportunity pre-filled) and from "Hoy" (`/hoy/nueva`, where the centre is chosen first with a search box over `GET /accounts?q=`). Above the fold: activity type as segmented buttons with the master icons, centre, date/time (default now) and a "Hecha / Planificada" toggle (default Hecha; "Planificada" defaults the date to tomorrow 09:00 and is disabled for Nota). Collapsed "Más datos": oportunidad (select of the centre's open opportunities, pre-selected when opened from the sheet, hidden when the centre has none), contactos (checkbox list of the account's active contacts, primary pre-checked), **acompañantes** (checkbox list of active Quermed colleagues who can see the centre, the owner absent from it), duración, resultado, asunto, notas, próxima acción (tipo + fecha). Managers SHALL see a "Comercial" selector defaulting to themselves. Backend errors (`note_cannot_be_planned`, `contact_not_in_account`, `opportunity_not_in_account`, `attendee_out_of_scope`, `owner_cannot_attend`, `next_action_in_past`) SHALL render inline.

#### Scenario: Three-tap visit
- **WHEN** a rep opens the form from a centre, taps "Visita" and "Guardar"
- **THEN** one `POST /activities` is sent with `{ account_id, activity_type_id, status: "done", scheduled_at: now, contact_ids: [primary] }` and the timeline section shows the visit

#### Scenario: Invite a colleague
- **WHEN** the rep opens "Más datos", ticks a colleague under "Acompañantes" and saves
- **THEN** the payload carries `attendee_ids` with that colleague and the activity shows both names

#### Scenario: The owner is not offered as a companion
- **WHEN** the companions list renders
- **THEN** the activity's own owner is absent from it, so `owner_cannot_attend` cannot be triggered by clicking

#### Scenario: Plan with next action
- **WHEN** the rep selects "Planificada", picks a date and saves
- **THEN** the payload has `status: "planned"` and the new activity appears in "Hoy" when the date is today

#### Scenario: Nota cannot be planned
- **WHEN** the rep selects "Nota"
- **THEN** the "Planificada" option is disabled

#### Scenario: Visit from the opportunity sheet
- **WHEN** the rep opens "Nueva actividad" from an opportunity, taps "Visita" and saves
- **THEN** the payload includes `opportunity_id` and the activity appears in the sheet's Actividades section

### Requirement: Hoy page
`/hoy` SHALL render the header with the date and "Nueva actividad", **the notifications block when the user has unread notices**, the weekly summary line, the "Atrasadas" list (warning style, oldest first), the "Hoy" list (by time), each card with type icon, time, centre, subject and the actions "Hecha" (opens a compact sheet: resultado, notas, próxima acción; "Guardar" completes) and "Reprogramar" (date-time picker calling `/reschedule`), and, when non-empty, the blocks "Licitaciones esta semana" (opportunity cards with deadline, overdue in warning style) and "Centros en riesgo" (opportunity cards with days at risk), both linking to the opportunity sheet. Cards of activities the user attends rather than owns SHALL carry an "Invitado" badge and SHALL NOT offer "Hecha" or "Reprogramar". Managers, admins and back office SHALL see a "Comercial" selector that switches the payload (`?user_id=`); back office actions SHALL be hidden. Empty states SHALL read "Nada planificado para hoy" / "Sin actividades atrasadas". A rep without territory or division SHALL still see the scope warning from change 01.

#### Scenario: Complete from Hoy
- **WHEN** the rep taps "Hecha" on a planned visit and saves with resultado "Positiva"
- **THEN** `POST /activities/{id}/complete` is sent with `If-Match`, the card leaves the list and the weekly counter increases

#### Scenario: Invited card is read-only
- **WHEN** a card carries `is_attendee = true`
- **THEN** it shows the "Invitado" badge, offers neither "Hecha" nor "Reprogramar", and tapping it opens the activity

#### Scenario: Reschedule an overdue call
- **WHEN** the rep taps "Reprogramar" on an overdue call and picks tomorrow 10:00
- **THEN** `POST /activities/{id}/reschedule` is sent and the card leaves "Atrasadas"

#### Scenario: Manager switches rep
- **WHEN** a manager selects another rep in the selector
- **THEN** `GET /me/today?user_id=<rep>` is requested and the lists show that rep's day

#### Scenario: Tender block
- **WHEN** `tenders_due` contains a tender overdue by two days
- **THEN** the "Licitaciones esta semana" block renders the card in warning style; when both blocks are empty neither heading is rendered

### Requirement: Día ↔ Mes switcher on Hoy
The Hoy page SHALL offer a **three-option** keyboard-operable segmented control switching between the day plan (**Día**, the default and landing view), the month calendar (**Mes**) and the date-range list (**Listado**), without a route change. The day plan, its selector and its blocks SHALL behave exactly as before when the Día view is active.

#### Scenario: Landing unchanged
- **WHEN** any user opens `/hoy`
- **THEN** the day plan renders as today, with the switcher showing Día selected

#### Scenario: Switch to the month
- **WHEN** the user selects Mes
- **THEN** the month calendar replaces the day plan and one calendar request is made for the current month

#### Scenario: Switch to the list
- **WHEN** the user selects Listado
- **THEN** the range list replaces the calendar and one calendar request is made for the default range

## ADDED Requirements

### Requirement: Notifications block on Hoy
When the signed-in user has unread notifications, `/hoy` SHALL render a block above "Atrasadas" listing them newest first: who did it, what happened and when, each row tappable to the activity, centre or opportunity it refers to, plus "Marcar todo como leído". Opening a notice SHALL mark it read; the block SHALL disappear when nothing is unread, without an empty state — an empty inbox is not news.

#### Scenario: A manager assigns something
- **WHEN** a manager adds the rep to a visit and the rep opens Hoy
- **THEN** the block shows one row naming the manager, the centre and the date

#### Scenario: Opening a notice
- **WHEN** the rep taps the row
- **THEN** the app navigates to the activity and the notice is marked read

#### Scenario: Mark all
- **WHEN** the rep taps "Marcar todo como leído"
- **THEN** the block disappears and the header counter clears

#### Scenario: Nothing unread
- **WHEN** the user has no unread notices
- **THEN** no block and no empty state are rendered

### Requirement: Listado view with range and rep
The Listado view SHALL offer Desde and Hasta date fields (defaulting to the current month) and, for `admin`, `sales_manager` and `back_office`, a "Comercial" selector; a `sales_rep` SHALL see their own activities with no selector. It SHALL list the activities by date — on mobile as cards grouped by day, from `lg:` as a table with Fecha, Hora, Tipo, Centro, Asunto, Estado and Comercial — each row opening the activity. A range longer than 92 days SHALL be refused inline with the backend's message, and an empty range SHALL show a neutral empty state.

#### Scenario: Two weeks of one rep
- **WHEN** a manager sets 1 to 15 September and picks a rep
- **THEN** one calendar request is made with that range and owner, and the activities are listed by date

#### Scenario: A rep lists their own fortnight
- **WHEN** a `sales_rep` opens Listado
- **THEN** no rep selector renders and the list holds their own activities, including those they attend

#### Scenario: Too long a range
- **WHEN** the user asks for a whole year
- **THEN** the translated `range_too_long` message renders under the fields and no list is shown

#### Scenario: Empty range
- **WHEN** the chosen range holds no activities
- **THEN** a neutral empty state is shown instead of an empty table
