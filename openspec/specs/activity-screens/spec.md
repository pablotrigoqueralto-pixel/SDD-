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
