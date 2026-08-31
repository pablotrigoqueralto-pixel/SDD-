# Tasks — dashboards

scope: backend=true, frontend=true · design-linked: false (AI-designed UI per frontend standards)

## 1. Backend — periods and read model

- [x] 1.1 [TEST][BE] Write failing unit tests for `app/application/dashboard/periods.py`: month/quarter/YTD bounds and previous equivalents in Europe/Madrid (half-open, UTC conversion, YTD-vs-same-fraction, month rollover across DST/New Year), then implement `resolve_period(period, today)`.
- [x] 1.2 [TEST][BE] Write failing integration tests for `DashboardQueries.summary`: won €/count with previous-period delta, conversion with counts and null-when-no-closed, weighted forecast (amount × probability/100, HALF_UP two-decimal strings), open pipeline total; then implement the summary aggregation in `app/application/dashboard/queries.py`.
- [x] 1.3 [TEST][BE] Write failing integration tests for `pipeline_by_stage` (snapshot of open by stage in `sort_order`) and the division/rep breakdowns (same KPI definitions per group, ordered by won € desc, groups without data omitted); then implement.
- [x] 1.4 [TEST][BE] Write failing integration tests for activity metrics (done in period, per owner with per-type counts, total desc) and neglected accounts (>60 days or never with old `created_at`, oldest first, cap 20 + uncapped total, null days for never); then implement.
- [x] 1.5 [TEST][BE] Write failing integration tests for role scoping: rep gets owner-filtered figures everywhere and no `by_rep`; manager/admin/back_office get company view with `by_rep`; then implement the actor-derived scope filter.

## 2. Backend — API

- [x] 2.1 [TEST][BE] Write failing API tests for `GET /api/v1/dashboard`: 401 anonymous, 422 invalid period, 200 default month with echoed Madrid bounds, payload shape per spec; then add `app/schemas/dashboard.py` and `app/api/v1/dashboard.py` and register the router.
- [x] 2.2 [TEST][BE] Write the role-matrix API test (rep vs manager vs back office on seeded data) and the 500 ms budget integration test over the seeded test database.
- [x] 2.3 [BE] Regenerate `ai-specs/specs/api-spec.yml` via the exporter and add the "Dashboards" section to `development_guide.md` (no `data-model.md` change — no schema change).

## 3. Frontend — feature scaffold and page

- [x] 3.1 [FE] Create `features/dashboard` scaffold: `api.ts` (typed `fetchDashboard(period)` from generated types after `npm run api:types`), `queries.ts` (`useDashboard(period)` keyed by period), `index.ts`; add MSW handlers with a representative payload and register them.
- [x] 3.2 [TEST][FE] Write failing component tests for the Informes page (rep: no "Por comercial"; period switch refetches quarter; skeleton and error-with-retry states), then implement `pages/InformesPage.tsx` with header + segmented period selector (default Mes) and stacked mobile layout / `lg:` two-column grid.
- [x] 3.3 [TEST][FE] Write failing component tests for the KPI cards (Ganado delta up, Conversión "—" when null and "3 de 5" counts, Previsión hint, es-ES formatting), then implement the KPI grid.
- [x] 3.4 [TEST][FE] Write failing component tests for the CSS-bar sections (stage rows in order with real-text figures, proportional widths, empty states) and the activity + neglected sections ("Nunca", navigation to the 360º page, total badge), then implement them.

## 4. Frontend — placement and Hoy block

- [x] 4.1 [TEST][FE] Update MorePage tests for the "Informes" card ordering per role (first for rep/manager/BO, after "Administración" for admin), then add the card and the `/informes` route (auth-only, all roles) and the `dashboard` i18n namespace.
- [x] 4.2 [TEST][FE] Write failing tests for the Hoy key-figures block (manager sees won/forecast/pipeline linking to `/informes`; rep and back office see nothing; dashboard error leaves Hoy intact), then implement `DashboardTeaser` in `features/dashboard`, export it via `index.ts` and render it from the Hoy page for `sales_manager`/`admin`.
- [x] 4.3 [FE] Quality gates: `npx tsc --noEmit -p tsconfig.app.json`, eslint (no `jsx-no-literals` in `features/dashboard`), prettier, full Vitest suite green.

## 5. E2E and integration validation

- [x] 5.1 [E2E] Extend the Playwright suite: seed data via API fixtures (won + open opportunities, done activities, neglected account), then as admin verify Más → Informes, KPI figures, period switch, neglected-account navigation; as manager verify the Hoy block; axe scan on `/informes` mobile + desktop.
- [x] 5.2 [E2E] Run the full compose smoke + complete Playwright suite (desktop + mobile) with the rate-limit env swap; fix regressions until green.
