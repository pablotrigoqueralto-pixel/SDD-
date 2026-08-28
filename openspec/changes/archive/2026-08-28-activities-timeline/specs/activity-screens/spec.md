## ADDED Requirements

### Requirement: Activity form
The activity form SHALL open in `ResponsiveFormContainer` from the 360º page ("Nueva actividad", centre pre-filled), from the timeline page and from "Hoy" (`/hoy/nueva`, where the centre is chosen first with a search box over `GET /accounts?q=`). Above the fold: activity type as segmented buttons with the master icons, centre, date/time (default now) and a "Hecha / Planificada" toggle (default Hecha; "Planificada" defaults the date to tomorrow 09:00 and is disabled for Nota). Collapsed "Más datos": contactos (checkbox list of the account's active contacts, primary pre-checked), duración, resultado, asunto, notas, próxima acción (tipo + fecha). Managers SHALL see a "Comercial" selector defaulting to themselves. Backend errors (`note_cannot_be_planned`, `contact_not_in_account`, `next_action_in_past`) SHALL render inline.

#### Scenario: Three-tap visit
- **WHEN** a rep opens the form from a centre, taps "Visita" and "Guardar"
- **THEN** one `POST /activities` is sent with `{ account_id, activity_type_id, status: "done", scheduled_at: now, contact_ids: [primary] }` and the timeline section shows the visit

#### Scenario: Plan with next action
- **WHEN** the rep selects "Planificada", picks a date and saves
- **THEN** the payload has `status: "planned"` and the new activity appears in "Hoy" when the date is today

#### Scenario: Nota cannot be planned
- **WHEN** the rep selects "Nota"
- **THEN** the "Planificada" option is disabled

### Requirement: Timeline section and page
The "Actividades" section of `/centros/:id` SHALL render the five most recent `TimelineEntryRead` items (icon, title, relative date, owner, outcome badge, contacts) with "Ver todas" → `/centros/:id/actividades`, a page with the full paginated list and filters by type and status. Planned entries SHALL show "Hecha" and "Reprogramar" actions; done entries SHALL open the edit sheet when the user may edit them.

#### Scenario: Section content
- **WHEN** the 360º page loads for an account with seven activities
- **THEN** the section shows five entries newest first, a count of seven and "Ver todas"

#### Scenario: Locked activity
- **WHEN** a rep opens a visit done 10 days ago
- **THEN** the sheet is read-only and shows "Solo dirección comercial puede editar esta actividad"

### Requirement: Hoy page
`/hoy` SHALL render the header with the date and "Nueva actividad", the weekly summary line, the "Atrasadas" list (warning style, oldest first) and the "Hoy" list (by time), each card with type icon, time, centre, subject and the actions "Hecha" (opens a compact sheet: resultado, notas, próxima acción; "Guardar" completes) and "Reprogramar" (date-time picker calling `/reschedule`). Managers, admins and back office SHALL see a "Comercial" selector that switches the payload (`?user_id=`); back office actions SHALL be hidden. Empty states SHALL read "Nada planificado para hoy" / "Sin actividades atrasadas". A rep without territory or division SHALL still see the scope warning from change 01.

#### Scenario: Complete from Hoy
- **WHEN** the rep taps "Hecha" on a planned visit and saves with resultado "Positiva"
- **THEN** `POST /activities/{id}/complete` is sent with `If-Match`, the card leaves the list and the weekly counter increases

#### Scenario: Reschedule an overdue call
- **WHEN** the rep taps "Reprogramar" on an overdue call and picks tomorrow 10:00
- **THEN** `POST /activities/{id}/reschedule` is sent and the card leaves "Atrasadas"

#### Scenario: Manager switches rep
- **WHEN** a manager selects another rep in the selector
- **THEN** `GET /me/today?user_id=<rep>` is requested and the lists show that rep's day

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
