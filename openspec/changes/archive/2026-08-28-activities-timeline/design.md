## Context

Change 03 delivered accounts and contacts, the `ScopeFilter` SQL predicate and the 360º page with an "Actividades" placeholder. Change 02 seeded the six activity types (`visit`, `call`, `email`, `demo`, `training`, `note`) with `icon` and `counts_as_contact` (`note` is the only type that does not count). The "Hoy" page is still a placeholder.

Confirmed product inputs: one activity record with status (planned / done / cancelled); account mandatory, contacts optional; minimum fields type + account + date with defaults "now, done"; "Hoy" shows planned today + overdue + weekly counters.

Constraints: 30-second capture on mobile (offline-first query cache, optimistic locking), audit of every mutation, lists under 500 ms, visibility inherited from the account.

## Goals / Non-Goals

**Goals:**
- Activity aggregate with a small, explicit lifecycle and an edit window.
- Timeline endpoint whose entry shape later changes reuse (opportunity stage changes, quotes).
- Denormalised `last_contact_at` / `next_activity_at` on accounts, always consistent.
- "Hoy" query that answers in one round trip.
- Form usable one-handed: three fields above the fold, everything else collapsed.

**Non-Goals:**
- Calendar sync, notifications, recurrence, geolocation, email logging, attachments, opportunity links (later changes).

## Decisions

### D1. One `activities` table with a status column, no separate tasks entity

`status` enum (`planned`, `done`, `cancelled`) on the same row: a planned visit becomes the done visit — one record, one history line, one audit trail. Planned rows feed "Hoy"; done rows feed the timeline and `last_contact_at`.
- *Discarded*: separate `tasks` table — every visit would exist twice (task + activity) and the 30-second flow would need two saves.
- *Discarded*: free `is_done` boolean — cancelled activities would be indistinguishable from never-planned ones and the "why was this dropped" question stays unanswered.

### D2. Lifecycle as explicit commands, not free PATCH of `status`

`POST /activities/{id}/complete` (`done_at?`, `outcome?`, `notes?`, `next_action?`), `POST /activities/{id}/cancel` (`reason`), `POST /activities/{id}/reschedule` (`scheduled_at`). `PATCH /activities/{id}` edits descriptive fields only (`subject`, `notes`, `contact_ids`, `duration_minutes`, `outcome`, `activity_type_id`) and never `status`. Each command validates its transition in the aggregate (`planned → done|cancelled`, `planned → planned` on reschedule, `done`/`cancelled` are terminal; `done` can still be edited within the window).
- *Discarded*: `PATCH {status: done}` — mixes validation of three different transitions into one handler, and the audit event would be a generic "updated" instead of `activity.completed` with its outcome.

### D3. Edit window: 7 days for the owner, unlimited for managers/admins

`Activity.ensure_editable(actor, now)`: owner may edit a `done` activity while `now - done_at ≤ 7 days`; `sales_manager`/`admin` always; others never. Planned activities are editable by owner/managers without time limit. Error `activity_locked` (409).
- *Discarded*: immutable once done — a typo in the notes of yesterday's visit would need a manager; too rigid for a 5-rep company.
- *Discarded*: unlimited edits — the timeline loses its value as evidence (e.g. for a lost-deal review).

### D4. Data model

| Table | Columns | Constraints / indexes |
|---|---|---|
| `activities` | `id`, `account_id FK accounts RESTRICT`, `activity_type_id FK activity_types RESTRICT`, `owner_id FK users RESTRICT`, `status activities_status_enum`, `scheduled_at timestamptz` (planned time, or the time it happened), `done_at timestamptz null`, `duration_minutes smallint null` (check 1–1440), `outcome activities_outcome_enum null` (`positive`, `neutral`, `negative`, `no_contact`), `subject text null` (≤ 120), `notes text null`, `cancel_reason text null`, `created_by FK users`, `version`, `created_at`, `updated_at` | checks: `status = 'done' → done_at NOT NULL`, `status = 'cancelled' → cancel_reason NOT NULL`, `outcome IS NULL OR status = 'done'`; indexes: `(account_id, scheduled_at DESC)` timeline, `(owner_id, status, scheduled_at)` "Hoy" and overdue, `activity_type_id`, `status` |
| `activity_contacts` | `activity_id FK CASCADE`, `contact_id FK contacts RESTRICT` | PK `(activity_id, contact_id)`; the service checks `contact.account_id == activity.account_id` |
| `accounts` (+) | `last_contact_at timestamptz null`, `next_activity_at timestamptz null` | index `(territory_id, last_contact_at)` for the coming "sin visitar" filter |

Migration `0004_activities`. `scheduled_at` doubles as the timestamp shown in the timeline for done activities recorded directly ("happened at"); `done_at` records when it was closed (usually equal).
- *Discarded*: separate `happened_at` column — three timestamps for one visit is more than any rep will fill; `scheduled_at` is edited when the visit was earlier than planned.
- *Discarded*: `contacts_summary text` instead of the link table — filtering "activities with contact X" (needed by the contact 360º later) would be impossible.

### D5. Denormalised `last_contact_at` / `next_activity_at` recomputed by the service

After every activity command, the `AccountRepository` runs `refresh_activity_summary(account_id)`: `last_contact_at = MAX(scheduled_at) WHERE status = done AND type.counts_as_contact`, `next_activity_at = MIN(scheduled_at) WHERE status = planned`. Two aggregate queries per write, no triggers, no drift (recomputed, never incremented). Both columns are read-only through the API and exposed on `AccountSummaryRead` / `AccountRead`.
- *Discarded*: PostgreSQL trigger — hides business logic (`counts_as_contact`) in the database, invisible to unit tests and to the `crm_app` grants.
- *Discarded*: computing on read — the account list would need two correlated subqueries on a table that grows by thousands of rows per year; the columns also feed the future "centros sin visitar en 90 días" alert cheaply.

### D6. Timeline entry shape and endpoint

`GET /accounts/{id}/timeline?kind=&activity_type_id=&status=&page=` returns a paginated list of `TimelineEntryRead { id, kind: "activity", occurred_at, title, activity: ActivityRead }` newest first (`occurred_at` = `done_at` for done, `scheduled_at` otherwise). `kind` is a discriminator so changes 06/07 add `opportunity_stage` and `quote` entries (with their own payload key) without breaking clients; the frontend renders unknown kinds as a plain line.
- *Discarded*: returning `ActivityRead[]` directly — every later change would add another endpoint and the 360º page would merge N lists client-side by date.
- *Discarded*: a persisted `timeline_events` table written by every service — duplicated data and a second thing to keep consistent; the union query is cheap per account.

### D7. "Hoy" as one read endpoint

`GET /me/today?user_id=` (the parameter only for `sales_manager`/`admin`/`back_office`, else 403) returns `TodayRead { date, today: ActivityRead[], overdue: ActivityRead[], week: { done_by_type: {type_id: count}, planned_remaining: count } }`. Times are interpreted in `Europe/Madrid` server-side (the rep's day, not UTC). The query is three statements on the `(owner_id, status, scheduled_at)` index.
- *Discarded*: three client-side queries — three spinners on a 4G connection; one payload is also easier to cache offline.
- *Discarded*: browser-local timezone — a rep travelling never changes timezone in practice and the server rule keeps "today" identical in reports.

### D8. Next action shortcut

`complete` and `create` accept `next_action { activity_type_id, scheduled_at, subject? }`; the service creates the planned follow-up in the same transaction with the same account, contacts and owner, and returns it alongside the completed activity (`ActivityRead.next_activity_id`). This is the Quermed habit "cierro la visita y dejo apuntada la próxima" without a second form.
- *Discarded*: a mandatory next action — the briefing's "zero useless fields": a note or a lost-deal visit has no next step.

### D9. Domain and application layout

`app/domain/activities/` — `Activity` aggregate (`plan`, `record_done`, `complete`, `cancel`, `reschedule`, `update_details`, `ensure_editable`), `ActivityStatus`, `ActivityOutcome`, errors (`invalid_activity_transition` 409, `activity_locked` 409, `contact_not_in_account` 422, `note_cannot_be_planned` 422, `cancel_reason_required` 422, `next_action_in_past` 422), `ActivityRepository`. `app/application/activities/` — `ActivityService` (loads the account through `load_visible_account`, checks writer rights with `ensure_account_writer` from change 03, records audit events `activity.created`, `activity.completed`, `activity.cancelled`, `activity.rescheduled`, `activity.updated`), `TimelineQueries`, `TodayQueries`. `AccountRepository` gains `refresh_activity_summary`.
- *Discarded*: putting timeline/today inside `AccountService` — reads with their own filters and pagination belong to query modules, as `AccountQueries` already does.

### D10. Frontend

Routes: `/hoy` (real page), `/centros/:id/actividades` (full timeline list with filters), `/centros/:id/actividades/nueva`, `/centros/:id/actividades/:activityId` (edit / complete / cancel / reschedule in one sheet), `/hoy/nueva` (asks the centre first).

Feature `features/activities/{api,queries,schemas}` + `components/ActivityForm`, `ActivityTypePicker` (segmented buttons with the master icons), `ActivityCard`, `TimelineList`, `TodayList`, `WeekSummary`, `RepSelector`; pages `TodayPage` (replaces the placeholder in `app/pages`), `TimelinePage`, `ActivityFormRoute`. Query keys `activityKeys` (`today(userId)`, `timeline(accountId, filters)`, `detail(id)`); every activity mutation invalidates the account detail and list (`last_contact_at`) and the today/timeline keys.

Activity form (mobile first):

```
┌──────────────────────────┐
│ Nueva actividad       ✕  │
├──────────────────────────┤
│ [📍Visita][📞Llamada][✉Email]
│ [🖥Demo][🎓Formación][📝Nota]│ ← segmented, one tap
│ Centro: Clínica Tambre   │ ← pre-filled from the 360º; search box from Hoy
│ Fecha  [28/08/2026 10:30]│ ← defaults now
│ (●) Hecha  ( ) Planificada│
│ ─ Más datos ▸            │ ← contactos (principal marcado), duración,
│                          │    resultado, asunto, notas, próxima acción
├──────────────────────────┤
│        [ Guardar ]       │
└──────────────────────────┘
```

"Hoy" (mobile):

```
┌──────────────────────────┐
│ Hoy · jue 28 ago    [+]  │
│ Esta semana: 6 visitas · 4 llamadas · 3 pendientes
├──────────────────────────┤
│ ⚠ Atrasadas (2)          │
│  📞 Hospital La Paz · lun│ [Hecha] [Reprogramar]
│ Hoy (3)                  │
│  09:30 📍 Clínica Tambre │ [Hecha] [Reprogramar]
│  12:00 🖥 Demo · IVI     │
│  …                       │
├──────────────────────────┤
│  Hoy  Centros  Más       │
└──────────────────────────┘
```

"Hecha" opens a compact sheet (resultado + notas + próxima acción, all optional) so the close stays one tap plus "Guardar". Desktop: "Hoy" in two columns (atrasadas + hoy | resumen de la semana); the timeline in the 360º shows the last five entries with "Ver todas" → `/centros/:id/actividades`.
- *Discarded*: calendar/week grid view — reps work from a list; a grid on a phone hides everything but two hours.
- *Discarded*: inline editing of notes on the card — accidental taps while scrolling in the car.

### D11. Testing

- Backend unit: transitions and errors, edit window, `note_cannot_be_planned`, next-action creation, contact/account consistency, today bucketing (today / overdue / week) with a fixed clock in `Europe/Madrid`.
- Backend integration: migration round trip; endpoints × roles (rep in scope, out of scope → 404, back office read-only, manager `user_id`), `refresh_activity_summary` after each command, timeline pagination and filters, audit events, `/me/today` payload.
- Frontend: form defaults and payloads (done vs planned, next action), type picker accessibility, today lists with one-tap complete/reschedule, timeline section and page, invalidation of account list after completion.
- E2E (desktop + mobile, axe): rep records a visit from the 360º page with a next action → appears in "Hoy" → marks it done → timeline shows both; manager views the rep's "Hoy".

## Risks / Trade-offs

- **[Denormalised timestamps drift]** → recomputed from scratch on every command; integration test asserts equality with a raw aggregate after a sequence of commands.
- **[Timezone edge at midnight]** → server-side `Europe/Madrid` day boundaries; tests pin 23:30 and 00:30 cases.
- **[Edit window bypass through `reschedule` on done rows]** → transitions validated in the aggregate; `reschedule` only accepts `planned`.
- **[Timeline union grows with later changes]** → `kind` discriminator and per-kind payload keep the contract additive.
- **[Offline capture]** → out of scope beyond the existing query cache; an explicit outbox arrives with the production change if field usage demands it.

## Migration Plan

1. Migration `0004_activities` (new tables, two nullable columns on `accounts`, enums, indexes); no backfill needed (no activities exist).
2. Deploy backend and frontend together (additive API; `AccountRead` gains two nullable fields).
3. Rollback: `alembic downgrade 0003_accounts_contacts` drops tables, enums and the two columns.

## Open Questions

- None blocking. Whether "Hoy" should also list accounts without contact for 90 days is deferred to the dashboards change (the `last_contact_at` index is already in place).

### Implementation notes (recorded during /opsx:apply)

- `ActivityRead` carries `account_name`, `owner_name`, `activity_type_name` and `contacts[{id, name}]` (D6/D7 only listed ids): "Hoy" and the timeline render without extra lookups, and reps cannot list users.
- The `activities` list endpoint (`GET /activities` with filters) and `ActivityQueries` exist next to the timeline/today queries so later screens (contact 360º, dashboards) reuse the same scoped read.
- `tzdata` was added as a runtime dependency: `ZoneInfo("Europe/Madrid")` fails on Windows and slim containers without it.
- `duration_invalid` (422) joins the error codes: the 1–1440 check is enforced in the aggregate, not only by the database.
- Account header actions are icon-only below `sm`: with four actions the title collapsed to zero width on a 412 px viewport (caught by the mobile E2E run).
- The E2E login helper matches the `Hoy` h1 by level: the page now has an "Hoy (n)" h2 too; the admin spec forces the province checkbox because the long list inside the animated dialog is intermittently "unstable" for Playwright.
