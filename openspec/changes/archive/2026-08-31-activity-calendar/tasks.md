# Tasks — activity-calendar

scope: backend=true, frontend=true · design-linked: false (AI-designed UI per frontend standards)

## 1. Backend — calendar feed

- [x] 1.1 [TEST][BE] Write failing integration tests for `GET /api/v1/activities/calendar`: 401 anonymous, 422 invalid month, one-request month with compact entries, done-Tuesday-scheduled-Monday lands on Tuesday, late-night Madrid boundary, cancelled excluded; then implement the calendar query (occurred_at expression, Madrid half-open bounds) in `app/application/activities/queries.py`, the schema and the route.
- [x] 1.2 [TEST][BE] Write failing scoping tests: manager sees the team and can filter one rep via `owner_id`; rep gets only their own month; rep with a colleague's `owner_id` receives 403; then implement the actor-derived scope with the explicit denial. Cover the 1000-cap + `total` contract at unit or API level.
- [x] 1.3 [BE] Regenerate `ai-specs/specs/api-spec.yml` via the exporter and note the calendar feed in `development_guide.md` (no `data-model.md` change — no schema change).

## 2. Frontend — month view

- [x] 2.1 [FE] Run `npm run api:types`; add `fetchActivityCalendar` + `useActivityCalendar(year, month, ownerId)` to `features/activities`, the MSW handler with a representative month payload, and the `activities` i18n keys for the month view.
- [x] 2.2 [TEST][FE] Write failing component tests for the Día ↔ Mes switcher (Día default and day plan untouched; Mes triggers exactly one calendar request for the current month), then implement the segmented control in TodayPage rendering `MonthCalendar` when Mes is active.
- [x] 2.3 [TEST][FE] Write failing component tests for the grid (Monday-first es-ES headers, dots capped at 4 with "+N", accessible day labels with counts, today highlighted, ‹ › month navigation issuing one request per month, "hoy" shortcut), then implement `MonthCalendar` as a CSS-grid of buttons with the deterministic 8-color rep palette and per-type dots in own view.
- [x] 2.4 [TEST][FE] Write failing component tests for the day expansion (list below the grid with time/type/centre/owner, done dimmed AND stated as text, rows navigate to the activity flow, empty-day state) and the team controls (manager: selector default Todos + legend, filtering re-renders; rep: no selector), then implement them.
- [x] 2.5 [FE] Quality gates: `npx tsc --noEmit -p tsconfig.app.json`, eslint, prettier on touched files, full Vitest suite green.

## 3. E2E and integration validation

- [x] 3.1 [E2E] Extend Playwright: seed a rep with activities on two days (one done, one planned) via API fixtures; as manager open Hoy → Mes, assert dots/count on the right days, expand a day, filter by the rep, and axe-scan the Mes view mobile + desktop; as the rep assert only their own month and no selector.
- [x] 3.2 [E2E] Full compose smoke + complete Playwright suite (desktop + mobile, rate-limit swap); fix regressions until green.
