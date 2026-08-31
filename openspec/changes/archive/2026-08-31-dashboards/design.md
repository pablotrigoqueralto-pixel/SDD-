## Context

Changes 01–08 delivered every dataset the dashboards need: opportunities carry `status`, `amount`, `won_amount`, `won_at`, `lost_at`, `expected_close_date`, `division_id` and `owner_id`; pipeline stages carry `probability` (0–100) and `sort_order`; activities carry `status`, `done_at`, `activity_type_id` and `owner_id`; accounts carry `last_contact_at`, `owner_id` and `is_active`. The change is purely a read model plus a page: aggregate those tables into KPIs with period comparison and role scoping, expose them under `/api/v1/dashboard`, and render them at `/informes` (plus a key-figures block on Hoy for management).

scope:
  backend: true
  frontend: true
design-linked: false

## Goals / Non-Goals

**Goals:**
- One authoritative definition of every KPI (won, conversion, open pipeline, weighted forecast, activity counts, neglected accounts), computed server-side and identical for every consumer (Informes page and Hoy block).
- Period presets (month / quarter / YTD) with previous-period comparison, Europe/Madrid calendar.
- Server-side role scoping that cannot be bypassed by the client.
- Live responses within the 500 ms API budget at MVP data volumes.

**Non-Goals:**
- No snapshots, exports, free date ranges, per-rep targets or product-level analytics (see proposal non-goals).
- No caching layer or precomputation; revisit only if measured latency demands it.
- No writes of any kind: no new tables, no domain entities, no audit entries (viewing a dashboard is not an auditable business action).

## Decisions

### D1. Live SQL read model, no new tables and no migration

A `DashboardQueries` class in `app/application/dashboard/queries.py` (mirroring the `SearchQueries` pattern from change 08) runs a fixed set of aggregate SELECTs per request. No Alembic migration: MVP volumes (thousands of rows) keep grouped aggregates over existing indexed columns far below the 500 ms budget, and the tables already carry indexes on the join/filter columns used.

- **Discarded — materialized views or snapshot tables**: adds refresh orchestration and staleness for zero benefit at this scale, and the user explicitly chose live data over snapshots.
- **Discarded — new covering indexes (e.g. partial on `won_at`)**: premature; nothing measured is slow. If production data ever pushes past the budget, an index-only migration is a trivial follow-up.

### D2. Single endpoint returning the whole panel

`GET /api/v1/dashboard?period=month|quarter|year` returns one payload: summary KPIs with comparison, stage breakdown, division breakdown, rep breakdown, activity metrics and the neglected-accounts list. The page needs all of it at once; one round trip beats five on mobile, and TanStack Query caches the single object cleanly. List sections are capped (neglected accounts: 20; breakdown rows are naturally bounded by divisions/reps).

- **Discarded — one endpoint per widget** (`/dashboard/summary`, `/dashboard/activity`…): chattier on mobile, five auth/scope evaluations instead of one, and no consumer ever wants a partial panel.
- **Discarded — GraphQL-ish field selection**: over-engineering for two consumers.

`period` is a Pydantic enum; anything else is a 422. Errors are the standard RFC 7807 set (401 unauthenticated, 422 invalid period). No new domain error codes — the endpoint is read-only and never conflicts.

### D3. Period arithmetic in Python, comparisons in UTC

`app/application/dashboard/periods.py` computes `[start, end)` bounds: the selected preset and its previous equivalent (previous calendar month, previous quarter, previous year-through-same-date for YTD), in Europe/Madrid, then converted to UTC-aware datetimes for `won_at`/`lost_at`/`done_at` filters. `expected_close_date` is a plain date and is compared against the Madrid-local date bounds directly. This mirrors the quote-numbering precedent (Madrid year) from change 07 and keeps the logic unit-testable without a database.

- **Discarded — SQL `date_trunc ... AT TIME ZONE` per query**: splits calendar logic across many statements, is harder to test (needs a DB), and repeats the timezone expression in every filter.

### D4. KPI definitions (single source of truth)

- **Won**: opportunities with `status = won` and `won_at` within the period; € = `sum(won_amount)`, count = rows. Comparison delta against the previous period.
- **Conversion**: `won_count / (won_count + lost_count)` for the period (`lost_at` for losses); `null` when nothing closed — the UI shows "—", never a fake 0%. Comparison against the previous period.
- **Open pipeline by stage**: snapshot of now — `status = open`, `sum(amount)` and count grouped by stage, ordered by `sort_order`. No period filter and no comparison (a snapshot has no "previous period").
- **Weighted forecast**: `sum(amount × probability / 100)` over open opportunities with `expected_close_date` inside the selected period. Current-state metric: no previous-period delta (past periods have no open opportunities left, so a comparison would always read as collapse).
- **Breakdown rows** (by division via `opportunities.division_id`; by rep via `opportunities.owner_id`): won € and count, forecast €, open pipeline €, conversion — the same definitions restricted to the group. Ordered by won € descending.
- **Activity**: activities with `status = done` and `done_at` in the period, grouped by owner and by type (the per-type counts come with each owner row). Owner ordering by total descending.
- **Neglected accounts**: `is_active` accounts whose `last_contact_at` is older than 60 days or `NULL` with `created_at` older than 60 days, ordered oldest-contact first, capped at 20 with a total count.

Money follows the established `Price` pattern: two-decimal strings computed with `Decimal` and `ROUND_HALF_UP`; deltas are returned as absolute values plus the previous-period value, letting the UI render sign and percentage without re-deriving business rules.

- **Discarded — forecast weighted by stage-at-close-date history**: far more complex (stage history reconstruction) with no added decision value for an MVP forecast; current-stage probability is the number management already reasons with on the board.

### D5. Server-side scoping by ownership, rep breakdown only for full-scope viewers

Scope is derived from the authenticated actor, never from a query parameter: `sales_rep` gets every query filtered by `owner_id = actor.id` (opportunities and activities by their owner, neglected accounts by `accounts.owner_id`); `sales_manager`, `admin` and `back_office` get the unfiltered company view. The rep breakdown section is returned only to full-scope viewers — a rep's panel omits it (a one-row ranking of yourself is noise) and keeps the division breakdown of their own portfolio.

- **Discarded — `owner_id` query parameter with permission check**: widens the surface for scope bugs; the MVP has no "manager inspects one rep's panel" requirement, and if it arrives it can be added additively.

### D6. Frontend: one query hook, CSS-only visualisations, no chart library

`features/dashboard` exposes `useDashboard(period)` (single TanStack query keyed by period) and the page composes sections from the one payload. Visualisations are semantic HTML with Tailwind-sized horizontal bars (stage funnel, breakdown bars): accessible by construction (real text, list semantics), zero bundle cost, and trivially theme-consistent.

- **Discarded — recharts/chart.js**: heavy dependency for four bar groups, canvas/SVG accessibility work, and clashes with the CDN-free build; nothing in the agreed UX needs axes, tooltips or curves.

Period selector is a three-option segmented control held in component state (default: month) — no querystring persistence; the default answers the daily question and recents-style persistence adds state for no articulated need.

### D7. Hoy key-figures block reuses the same endpoint through the feature boundary

The management block on Hoy is a `DashboardTeaser` component exported from `features/dashboard/index.ts` and rendered by the Hoy page only for `sales_manager`/`admin` (role check via the existing session store). It calls the same `useDashboard('month')` hook — same cache entry as a later visit to Informes — and shows won €, forecast € and open pipeline € with a link to `/informes`. This respects the cross-feature import rule (only via feature `index.ts`) and avoids a second "mini summary" endpoint.

- **Discarded — extending `/me/today` with dashboard figures**: would duplicate KPI logic in a second read model and couple the activities feature to reporting definitions.

### D8. Placement and navigation

Route `/informes` guarded only by authentication (all four roles). `MorePage` gains an "Informes" card, highlighted and placed first for `sales_manager` (admins keep "Administración" first, with Informes immediately after; reps and back office see it first). The bottom navigation keeps its five fixed entries.

- **Discarded — replacing a navigation entry with Informes**: the five entries were just rebalanced in change 08 and are role-uniform; churning them again for a page visited a few times a day is worse than a first-position card.

## Mobile layout (before desktop)

`/informes`, mobile (stacked, one column):
1. Header "Informes" + segmented period selector (Mes · Trimestre · Año).
2. KPI cards 2×2 grid: Ganado (€ + nº, delta vs anterior), Conversión (% or "—", delta), Previsión (€), Pipeline abierto (€ total).
3. "Pipeline por etapa" — horizontal bars, one per stage in order, € and count.
4. "Por división" — bar list with won/forecast/pipeline per division.
5. "Por comercial" — same shape (full-scope viewers only).
6. "Actividad" — per-rep rows with per-type counts.
7. "Centros descuidados" — list of account links with days since contact, total badge.

Desktop: same sections in a two-column grid (KPIs full-width on top; stage funnel + divisions left, reps + activity right; neglected accounts full-width). Hoy block (management, mobile-first): a compact three-figure strip above today's plan linking to `/informes`.

## Risks / Trade-offs

- [Aggregates slow down as data grows] → definitions live in one `DashboardQueries` class, so adding indexes or precomputed rollups later touches infrastructure only; the 500 ms budget is asserted by an integration test today and can be re-measured on production data before change 10.
- [Weighted forecast misread as a promise] → the UI labels it "Previsión ponderada" with the formula in a hint (importe × probabilidad de etapa); no comparison delta is shown for it, avoiding false trend signals.
- [Conversion on tiny samples is noisy] → the payload carries won/lost counts alongside the ratio so the UI always shows "3 de 5" next to the percentage.
- [Rep-filtered and company payloads share one endpoint] → scoping is decided server-side from the JWT actor and covered by role-matrix API tests (rep vs manager vs back office), the same pattern already proven in accounts/opportunities.
- [Divisions or reps with zero data disappear from breakdowns] → accepted for MVP: rows are driven by opportunity data, not by the full catalogue of divisions/users; an empty division simply isn't ranked.

## Migration Plan

No database migration. Backend and frontend ship together in one PR; the endpoint is additive, so deploy order is irrelevant and rollback is a plain revert. `api-spec.yml` regenerated via the exporter; `development_guide.md` gains a short "Dashboards" note; `data-model.md` unchanged (no schema change).

## Open Questions

None — business decisions were settled in the pre-proposal question rounds (audience, KPIs, breakdowns, activity metrics, periods, forecast formula, placement, live-only).

## Implementation notes (recorded during /opsx:apply)

- Opportunity ownership rule (change 06) bit twice: a new opportunity defaults its owner to the account's territory rep, and only an active `sales_rep` may own one — a manager cannot. Tests that need a "foreign" deal pin `owner_id` to a second rep explicitly.
- `by_rep` is a typed nullable field (`list | null`), not an omitted key: FastAPI's `response_model_exclude_none` would also strip the meaningful `conversion.rate: null`. The dashboard-api delta was amended to say "null" instead of "omits".
- The breakdown query is one grouped SELECT with `FILTER` aggregates shared by division and rep views; mypy needed `InstrumentedAttribute[...]` (not `ColumnElement`) for the group/name column parameters.
- Neglected accounts cannot be produced through the public API (no backdating), so the integration test backdates `last_contact_at`/`created_at` with a direct UPDATE; the E2E spec asserts the section renders (empty state included) and leaves row navigation to component tests.
- The period selector is a fieldset of real radio inputs (`sr-only`) styled as a segmented control — keyboard and AT come free; Playwright clicks the visible label text because the hidden input fails its visibility check.
- Local `prettier --check` flags every checked-out file on Windows (CRLF vs `endOfLine: lf` default); `--end-of-line auto` confirms real formatting is clean and git normalizes on commit.
