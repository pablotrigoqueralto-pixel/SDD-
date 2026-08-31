## Context

The activities feature already carries everything the calendar needs: `ActivityModel` with `scheduled_at`/`done_at`/`status`/`owner_id`, the `occurred_at` semantics used by the timeline (done activities count by `done_at`, otherwise `scheduled_at`), the `ix_activities_owner_agenda (owner_id, status, scheduled_at)` index, and a Hoy page that already hosts a per-rep selector for staff. What is missing is a month-shaped read: the paginated list caps at `MAX_PAGE_SIZE = 200`, which a team-month can exceed, and its `ActivityRead` payload (contacts, notes, next action) is far heavier than a calendar cell needs.

scope:
  backend: true
  frontend: true
design-linked: false

## Goals / Non-Goals

**Goals:**
- One request returns a whole month for the visible scope, light enough for mobile.
- Same visibility philosophy as the dashboard: scope derived server-side from the actor; full-scope viewers can additionally filter to one rep.
- The calendar reuses the timeline's date semantics so a day shows the same truth everywhere.
- Mobile-first: dots and tap-to-expand, never text crammed into cells.

**Non-Goals:** everything in the proposal (no rescheduling from the calendar, no week/multi-month view, no creation from cells, no external calendar sync, no schema changes).

## Decisions

### D1. Dedicated compact feed: `GET /api/v1/activities/calendar`

A new read-only route on the existing activities router: `?year=&month=` (validated ranges) plus optional `owner_id`. It returns a flat list of compact entries — `id`, `occurred_on` (Madrid-local date), `occurred_time`, `status` (`planned`/`done`), activity type (`code`, `name`, `icon`), `account_id`/`account_name`, `owner_id`/`owner_name` — capped at 1000 entries with the uncapped `total` so the UI can flag truncation (unreachable at MVP scale). The frontend buckets by day; no pagination.

- **Discarded — reusing `GET /activities`**: `MAX_PAGE_SIZE=200` forces multi-request assembly for a team month, and `ActivityRead` drags contacts/notes/next-action the calendar never shows.
- **Discarded — server-side day aggregation (counts only)**: the day expansion needs the entries anyway; counts-then-fetch doubles the requests per tap.

### D2. Date semantics: the timeline's `occurred_at`, bucketed in Madrid time

An activity appears on the day of its `occurred_at` — `done_at` when done, `scheduled_at` otherwise — converted to the Europe/Madrid date (`BUSINESS_TIMEZONE`, the change-04/09 precedent). The month's bounds are half-open Madrid-local dates converted to UTC for the SQL filter, exactly like the dashboard's `periods.py`. Cancelled activities are excluded.

- **Discarded — bucketing by `scheduled_at` always**: a visit scheduled Monday but done Tuesday would show on the wrong day and contradict the account timeline.

### D3. Scoping: actor-derived; the rep filter is a privilege, not a parameter for everyone

`admin`, `sales_manager` and `back_office` get the whole team's month and may pass `owner_id` to narrow to one rep. A `sales_rep` always receives their own month; if a rep sends `owner_id` for someone else the request fails with a 403 problem (explicit denial beats silently ignoring a parameter). This mirrors dashboard D5 with the one addition the feature demands — the team filter — kept server-checked.

- **Discarded — silently forcing reps to self while accepting the param**: hides a permission boundary inside surprising behaviour.

### D4. Frontend: Día ↔ Mes switcher inside TodayPage, CSS-grid calendar, no library

TodayPage gains a two-option segmented control (same real-radio pattern as the dashboard's `PeriodSelector`), default **Día**; the view state is component state, not a route. The month view is a `MonthCalendar` component in `features/activities`: a 7-column CSS grid, Monday-first, es-ES month/weekday names via `Intl.DateTimeFormat`, previous/next month buttons plus a "hoy" shortcut, and `useActivityCalendar(year, month, ownerId)` (TanStack query keyed by the triple) feeding it. Each day cell is a `<button>` with an accessible label ("martes 2, 3 actividades"); tapping selects the day and renders its activity list *below* the grid (mobile-first — no popovers), each row linking to the existing activity sheet. Done entries render dimmed with a check; today's cell is highlighted.

- **Discarded — a calendar library (FullCalendar/react-big-calendar)**: heavy dependencies, their own styling systems and a11y stories; a month grid of buttons is small, testable and consistent with the no-chart-library precedent.
- **Discarded — a `/agenda` route**: the user chose the switcher; Hoy remains the single home for "my time".

### D5. Dots and colors: per rep in team view, per type in own view, deterministic palette

Cells show up to 4 dots plus a "+N" overflow. In the team view each rep gets a color from a fixed 8-color palette assigned deterministically (hash of user id → palette index) with a legend above the grid; in the own view dots use the activity type as the differentiator. Color is never the only carrier: the day list spells out owner and type as text (a11y baseline).

- **Discarded — arbitrary per-user color persistence**: nothing to store or administer; a deterministic hash is stable across sessions and devices for free.

### D6. Rep filter in month view defaults to "Todos"

The month view carries its own rep selector (same `useUsers` source as Hoy's existing one) defaulting to **Todos** — the team overview is the point of the view for management. The day view's existing selector semantics ("Mi día" default, `?user_id=` switch) stay untouched; the two selectors are independent state.

- **Discarded — sharing one selector state across both views**: Hoy-day defaults to "me" and month defaults to "all"; coupling them makes one of the two views open wrong.

### D7. No migration

`ix_activities_owner_agenda` serves the rep-month query; the team-month query is a date-range scan acceptable at MVP volumes (thousands of rows). If production data ever makes it slow, a single index on `scheduled_at` is an additive follow-up — same posture as dashboard D1.

## Mobile layout (before desktop)

Hoy, vista **Mes** (stacked, one column):
1. Día ↔ Mes segmented control (under the existing page header).
2. Month header: ‹ month name year › + "hoy" shortcut; rep selector (staff only, default Todos) and color legend when in team view.
3. 7-column grid, Monday-first, compact cells: day number, up to 4 dots, count badge when > 4; today outlined; selected day filled.
4. Selected day's list below: time · type icon · centre · owner (team view) · done check, each row navigating to the activity.

Desktop (`lg:`): the grid widens (taller cells, dots plus count) and the selected-day list docks to the right of the grid; same components, layout via grid classes only.

## Risks / Trade-offs

- [Team month grows beyond comfortable payloads] → compact entries (~120 bytes each) keep even 600 activities ≈ 75 KB; the 1000 cap plus `total` makes truncation visible instead of silent, and D7's index note covers the query side.
- [Two "current rep" selectors on one page confuse] → they never render together (each belongs to one view) and both use the same control and vocabulary; component tests pin the defaults.
- [Deterministic palette collides with many reps] → 8 colors cover the current team size; collisions degrade to shared colors while the legend and day list keep owners unambiguous as text.
- [Timezone drift between calendar and timeline] → both derive from the same `occurred_at` expression and `BUSINESS_TIMEZONE`; the API test asserts a done-Tuesday-scheduled-Monday activity lands on Tuesday.

## Migration Plan

No migration, additive endpoint and UI. Ships as one PR; `api-spec.yml` regenerated and `npm run api:types` rerun. Rollback is a plain revert.

## Open Questions

None — placement, visibility, cell content and planned/done inclusion were settled in the pre-proposal questions.

## Implementation notes (recorded during /opsx:apply)

- The route is registered before `GET /activities/{activity_id}` — otherwise "calendar" parses as a UUID and 422s; the MSW handler needed the same ordering.
- The E2E team-view assertion could not pin an exact per-day count: the desktop and mobile Playwright projects run the spec concurrently and the admin's shared team view accumulates both runs' activities. Exact counts are asserted only under an owner scope (the rep filter and the rep's own view); the team view asserts presence. The spec claims stay covered by the API tests.
- Free-province slice `/8` claimed for this spec (the coordination table in the env-quirks memory grew).
- The month grid uses proper grid semantics (grid > row > columnheader/gridcell > button) and passed axe on both viewports with no adjustments.
- `Intl.DateTimeFormat('es-ES')` weekday/month names drive both headers and accessible day labels, so component tests derive expectations from the same formatter instead of hardcoding month names.
