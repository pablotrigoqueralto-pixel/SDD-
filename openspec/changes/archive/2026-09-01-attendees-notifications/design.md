## Context

Three precedents carry most of this change. `activity_contacts` is already a plain link table hanging off the activity aggregate (composite primary key, `ON DELETE CASCADE` from the activity), so a second link table for internal users needs no new pattern. `TodayQueries.for_user` and `ActivityQueries.calendar` both filter on `ActivityModel.owner_id`, which is exactly the predicate that has to widen to "owned **or** attended". And the audit log shows how a write records something on the side of the operation that caused it: `uow.audit.record(...)` collects an event inside the same transaction and the unit of work flushes it on commit.

What does not exist is any per-user inbox. The audit log is close but is the wrong tool: it is append-only, immutable, global and read by administrators for accountability — a notification is personal, gets read, and then must leave the screen.

scope:
  backend: true
  frontend: true
design-linked: false

## Goals / Non-Goals

**Goals:**
- Two people on one visit, with the second one seeing it in their day without owning it.
- Nothing lands on somebody's plate silently: if another person assigns it, they are told.
- "¿Qué hizo Andrés del 1 al 15?" answerable in one screen.
- No new permission concept anywhere.

**Non-Goals:** everything in the proposal (email/push, free-text attendees, attendees completing activities, notification preferences, notification history, exporting the listado).

## Decisions

### D1. `activity_attendees`: a link table, and the owner is never one of them

`activity_attendees (activity_id, user_id)` with a composite primary key, cascading from the activity exactly like `activity_contacts`. Two invariants live in the `Activity` entity: the **owner cannot also be an attendee** (they are already on it — a row saying otherwise would double them in every list), and an attendee must be an **active user**. Attendees are replaced wholesale when the activity is saved, the same delete-and-reinsert the account's child collections use.

- **Discarded — a second `co_owner_id` column**: caps the guest list at one and invites the question "who completes it?" the moment there are two owners.
- **Discarded — reusing `activity_contacts` with a nullable `user_id`**: one table meaning two different things (a doctor at the hospital, a colleague at Quermed), so every query would have to remember which half it wants.
- **Discarded — letting the owner be an attendee too**: harmless-looking, then "Hoy" shows the activity twice for the owner and every count is off by one.

### D2. "Hoy" and the calendar select **owned or attended**, and say which

The `owner_id ==` predicate in `TodayQueries.for_user` and `ActivityQueries.calendar` becomes "owner is me **OR** an `activity_attendees` row is mine", and every activity view gains `is_attendee` (true when the activity reached me because I am invited). The frontend renders an "Invitado" badge and hides the write actions on those cards — but the truth of who may act is enforced where it always was, in the service that checks ownership.

- **Discarded — a separate "Invitaciones" list on Hoy**: the point is that the day is one plan; a visit you attend is part of your Tuesday whoever owns it.
- **Discarded — copying the activity for each attendee**: two rows drifting apart the first time one is rescheduled.
- **Discarded — flagging it only in the UI by comparing `owner_id`**: the client would have to know the current user in every list; the server already knows and can say it once.

### D3. `notifications` is its own table, written by the services that cause them

`notifications (id, user_id, kind, entity_type, entity_id, actor_id, payload, read_at, created_at)`, indexed on `(user_id, read_at, created_at DESC)` — the exact shape of "my unread, newest first". `kind` is one of `activity_assigned`, `activity_attending`, `account_assigned`, `opportunity_assigned`. The payload carries what the block needs to render a line without joining four tables (the subject, the centre's name, the date), because a notification describes **what happened then**, not what the record looks like now.

Writes go through a small `NotificationCollector` on the unit of work — `uow.notifications.notify(...)` — mirroring `uow.audit.record`, so a notice is committed in the same transaction as the change that caused it and can never announce something that was rolled back.

- **Discarded — deriving the block from the audit log**: it has no read state, no per-user targeting, and it is append-only by design; adding a `read_at` to an immutable ledger is a contradiction.
- **Discarded — a background job that scans for changes**: a scheduler to run, a window to miss, and duplicates to defend against, for something the writing service already knows.
- **Discarded — computing "what is new for you" on read** (comparing timestamps against a last-seen marker): cheap to start, then every new event type needs its own query and "mark this one read" becomes impossible.

### D4. The actor never notifies themselves

Every `notify` call is skipped when `user_id == actor_id`. Assigning an account to yourself, adding yourself to your own visit or creating your own activity produces nothing. This is the rule that decides whether the block is worth looking at: a rep plans their own week, and if their own planning filled the block, the one notice that came from the boss would be lost in it.

### D5. Read means gone, and the counter is the same query

`GET /api/v1/notifications` returns the unread ones (newest first, capped) **and** `unread_count`; `POST /notifications/{id}/read` and `POST /notifications/read-all` mark them. One endpoint feeds both the bell and the block, so they can never disagree. The frontend refetches on window focus rather than polling on a timer: the case to serve is "I come back to the CRM and see what happened", not "a badge that ticks while I stare at it".

- **Discarded — WebSockets/SSE**: infrastructure to run and keep alive for a message whose value does not decay in seconds.
- **Discarded — a fixed poll every 30 s**: constant traffic for a screen most people leave open all day.

### D6. The "Listado" view reuses the calendar feed with a date range

`GET /api/v1/activities/calendar` gains optional `from` and `to` (inclusive dates, Madrid calendar) as an alternative to `year`/`month`, capped at 92 days so one request cannot ask for a year. The existing role scoping is unchanged: staff may pass `owner_id`, a rep always gets their own. The frontend adds a third segment beside Día and Mes rather than a new route, because it is the same data answering the same question over a different window.

- **Discarded — a new `/activities` list endpoint with pagination**: a second way to read activities that would drift from the calendar's date semantics (`done_at` when done, `scheduled_at` otherwise).
- **Discarded — no cap**: an unbounded range is a slow query waiting for the first person who types 2020.

## Mobile layout (before desktop)

Hoy, mobile: the notifications block sits **above** "Atrasadas" — a short list of one-line notices with the actor, what happened and when, each tappable, plus "Marcar todo como leído"; absent entirely when nothing is unread. The header keeps the bell with its count. Agenda: the Día / Mes segmented control gains **Listado**; choosing it shows Desde, Hasta and Comercial stacked, then the activities as cards grouped by day. Desktop (`lg`): the filters sit inline on one row and the activities render as a table (Fecha, Hora, Tipo, Centro, Asunto, Estado, Comercial).

## Risks / Trade-offs

- [The notifications block becomes noise and people stop reading it] → four events, all of them "somebody else put this on you", and read ones leave. If it ever grows, the honest next step is preferences, not more events.
- [A rep is added as attendee to an activity of a centre outside their scope] → the service validates that every attendee can see the activity's account before saving, so an invitation can never become a back door into another territory.
- [Notifications table grows without bound] → rows are small and per-user; read ones stay in the database (they only leave the block). If volume ever matters, a retention job is a later, separate decision.
- [Widening "Hoy" to attended activities changes the weekly counters] → deliberately not: the counters count what **you completed**, which only the owner can do. Only the planned and overdue lists widen.
- [The 92-day cap frustrates a quarterly review] → 92 days is a quarter; anything longer is a report, which is what `/informes` is for.

## Migration Plan

One revision `0011`: create `activity_attendees` and `notifications` with their indexes and grants. No backfill — there is nothing to convert, since neither concept existed. The downgrade drops both tables, losing only notices, which are ephemeral by design. Backend and frontend ship together; `api-spec.yml` regenerated and `npm run api:types` rerun.

## Open Questions

None — attendees limited to Quermed users, invited activities visible in the guest's agenda, the four notification events, read-and-gone, bell plus block, no email and the range-and-rep listado were all settled with the user before this design.
