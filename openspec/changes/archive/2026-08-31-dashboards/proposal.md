## Why

Management currently has no consolidated view of how the business is doing: won revenue, open pipeline, forecast and sales activity live scattered across the pipeline board, quote lists and account timelines, so questions like "how is the Vascular division doing this quarter?" require manual counting. With accounts, activities, opportunities (stage probabilities included) and quotes all in place after changes 01–08, the data needed for reporting already exists — this change turns it into decision-ready dashboards before production deployment.

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- New read-only reporting endpoints that aggregate existing CRM data into KPIs: won revenue of the period (€ and count) with previous-period comparison, open pipeline by stage (€), weighted forecast (amount × current stage probability over open opportunities with expected close in the period) and win conversion rate (won / closed).
- Every KPI available as company total and broken down by division and by sales rep.
- Sales-activity metrics: activities completed per rep and type in the period, plus "centros descuidados" — accounts with no contact in more than 60 days.
- Period selector: current month, current quarter or year to date, always compared against the equivalent previous period, using the Europe/Madrid calendar.
- Scope by role: `sales_manager` and `admin` see the full company panel; each `sales_rep` sees the same panel automatically filtered to their own portfolio; `back_office` sees the full panel read-only. Territory visibility rules already enforced elsewhere apply unchanged.
- New "Informes" page at `/informes`, reached from a highlighted card in Más (the bottom navigation keeps its five fixed entries).
- Management (`sales_manager` and `admin`) additionally gets a key-figures shortcut block at the top of their Hoy page linking to Informes.
- Live data on open, within the 500 ms API budget; no exports and no snapshots.

## Capabilities

### New Capabilities
- `dashboard-api`: reporting endpoints under `/api/v1/dashboard` — KPI summary with previous-period comparison, breakdowns by division and by rep, activity metrics and neglected accounts, with period selection and role-based scoping.
- `dashboard-screens`: the Informes page — KPI cards with comparison deltas, pipeline-by-stage and breakdown visualisations, activity section and neglected-accounts list, with period selector and mobile-first layout.

### Modified Capabilities
- `app-shell`: Más SHALL show a highlighted "Informes" card for every role (navigation entries themselves do not change).
- `activity-screens`: the Hoy page for `sales_manager` and `admin` SHALL open with a key-figures block (won, forecast, open pipeline of the current month) linking to `/informes`.

## Non-goals

- No per-rep visit or revenue targets, and no traffic-light target tracking (would require configuring objectives per user; out of MVP).
- No exports (CSV/PDF) and no monthly snapshots — the dashboard is live data only; history questions are answered by the period selector.
- No free date-range selection — only month / quarter / YTD presets with their previous-period comparison.
- No new domain entities or tables: the dashboard reads existing accounts, activities, opportunities and quotes; it never writes.
- No product-level analytics (top products, margin per product) — quote line analysis is a future change.
- No scheduled email digests.

## Impact

- **Roles**: all four roles gain access to `/informes`; `sales_rep` scoped to own portfolio, `sales_manager`/`admin`/`back_office` company-wide (back office read-only, which the dashboard is by nature). The Hoy shortcut block appears only for `sales_manager` and `admin`.
- **Backend**: new `app/application/dashboard` read-model queries (SQL aggregation over existing tables — no new models, no Alembic migration expected), new `app/api/v1/dashboard.py` router and schemas. `api-spec.yml` regenerated via the exporter.
- **Frontend**: new `features/dashboard` (Informes page, KPI cards, breakdown views, period selector), a card in `MorePage`, a route in the router, a Hoy block for management, new `dashboard` i18n namespace, MSW handlers.
- **Docs**: `api-spec.yml` and `development_guide.md` updated; `data-model.md` untouched unless an index is added for aggregation performance.
- **Constitution principles served**: mobile-first and 30-second interactions (the panel answers the daily "¿cómo vamos?" at a glance), one screen one purpose (Informes is reporting only), performance budget (aggregations must stay under 500 ms), role/territory visibility respected by reusing existing scoping rules.
