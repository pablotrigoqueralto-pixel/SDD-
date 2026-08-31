## Why

First real-use feedback from the production rehearsal: the Hoy page answers "what do I do today?" but not "how does the month look?". Management wants to see the whole team's activity at a glance — who is visiting whom and when, what got done — and each rep wants their own month for planning. Today that view simply does not exist; the closest substitutes (per-account timelines, the Informes activity section) answer different questions.

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- The Hoy page gains a **Día ↔ Mes view switcher**: the current day plan (overdue + today + blocks) remains the landing view; one tap shows a full month calendar. No new route and no navigation change.
- **Scope by role**: `admin` and `sales_manager` see the whole team's month with a per-rep filter (consistent with the existing "Comercial" selector on Hoy); `back_office` the same, read-only; a `sales_rep` sees only their own activities.
- **Day cells** show colored dots plus a count — color per rep in the team view, per activity type in the own view. Tapping a day expands its activity list (time, type, centre, status) with each entry linking to the activity.
- The calendar shows **both planned and done** activities, visually distinguished (done dimmed/checked); cancelled activities are excluded.
- Month navigation: previous/next month and a "hoy" shortcut; the calendar loads one month of data per request.
- Backend: a month-calendar feed for activities — either a thin aggregation endpoint or a spec'd reuse of the existing list filters (`from`/`to`/`owner_id` already exist); decided in design with the payload/pagination limits in view.

## Capabilities

### New Capabilities

(None — this extends the existing activities capability pair.)

### Modified Capabilities
- `activity-api`: a calendar feed requirement — one request returns a month of activities for the visible scope (team for full-scope viewers, own for reps), bounded and role-scoped on the server.
- `activity-screens`: the Hoy page requirement gains the Día ↔ Mes switcher, and a new month-calendar requirement covers cells, dots, day expansion, rep filter and the planned/done distinction.

## Non-goals

- No drag-and-drop rescheduling or editing from the calendar — tapping opens the existing activity flows; changes keep going through them.
- No week view and no multi-month view — one month, mobile-first, is the agreed scope.
- No creation from an empty day cell (considered and not chosen); "Nueva actividad" stays in the header.
- No external calendar integration (Outlook/ICS sync, invitations) — a candidate for its own future change.
- No new domain entities or schema changes: the calendar reads existing activities.

## Impact

- **Roles**: `admin`/`sales_manager` gain the team month view with rep filter; `back_office` the same without actions (as on Hoy today); `sales_rep` gains their own month. Territory/account visibility rules are untouched — the calendar filters by activity owner, mirroring the dashboard precedent that personal views are ownership-based.
- **Backend**: `app/application/activities` gains the calendar query (or the list contract is extended); a route/schema addition under `app/api/v1/activities.py`. `api-spec.yml` regenerated via the exporter. No migration expected (existing indexes on `scheduled_at`/`owner_id` to be confirmed in design).
- **Frontend**: `features/activities` gains the calendar components and query hook; the Hoy page adds the switcher; `activities` i18n namespace grows; MSW handlers and Playwright coverage extended.
- **Docs**: `api-spec.yml` and `development_guide.md` updated; `data-model.md` untouched unless an index is added.
- **Constitution principles served**: one screen one purpose (Hoy keeps answering "my day"; the month view is an explicit switch, not clutter), 30-second interactions (the month answers "¿cómo va el mes del equipo?" in one tap), mobile-first (dots + tap-to-expand instead of dense cells), role visibility respected server-side.
