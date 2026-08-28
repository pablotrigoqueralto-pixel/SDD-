## 1. Backend domain

- [x] 1.1 [BE] Write failing unit tests for the `Opportunity` aggregate creation (defaults per design D1/D5: derived `status`, generated name "<centre> · <division> · <month year>", `expected_close_date` +90/+30 by pipeline, `is_tender` from the account type, `stage_entered_at`), `stage_not_in_pipeline`, `pipeline_required`; implement `domain/opportunities/{entities,errors}.py` (`OpportunityStatus`, `AtRiskSource`, `StageChange`)
- [x] 1.2 [BE] Write failing unit tests for transitions: `move_stage` free among open stages (never to won/lost → `invalid_opportunity_transition`), `win` (defaults, moves to `is_won` stage), `lose` (`loss_reason_requires_brand`/`loss_reason_requires_note` from the reason flags), closed rows immutable (`opportunity_closed`), `reopen` clears closing fields, history rows with `seconds_in_previous_stage`; implement
- [x] 1.3 [BE] Write failing unit tests for lines and amount (D4: default unit price from list price, `line_duplicated`, `line_product_inactive`, amount = Σ lines else estimate, `opportunity_has_lines` on PATCH of the estimate, removal restores the estimate), tender validation (`tender_fields_require_tender`) and at-risk transitions (`at_risk_not_supported`, set/clear moving between `is_won` and `is_at_risk` stages); implement
- [x] 1.4 [BE] Define `OpportunityRepository` Protocol (get, add, save with version, list_for_account, history append, line CRUD, `list_at_risk_candidates(threshold)`), extend `UnitOfWork` and build the in-memory fakes; make `InMemoryProductRepository.is_referenced` and the activity fake aware of opportunities

## 2. Backend data model and migration

- [x] 2.1 [BE] ORM models `OpportunityModel`, `OpportunityLineModel`, `OpportunityStageHistoryModel` and `activities.opportunity_id` per design D7 (enums, checks, partial indexes)
- [x] 2.2 [BE] Write migration `0006_opportunities` (hand-reviewed, `crm_app` grants); integration test round-trip `upgrade → downgrade 0005_product_catalogue → upgrade` and `alembic check`
- [x] 2.3 [BE] `SqlAlchemyProductRepository.is_referenced` becomes a real query on `opportunity_lines`; integration test: SKU change rejected with `product_sku_locked` once a line exists

## 3. Backend repositories and queries

- [x] 3.1 [TEST]+[BE] Integration tests and implementation for `SqlAlchemyOpportunityRepository` (round trip incl. tender/at-risk fields, save conflict, history append with seconds, lines sync, `list_at_risk_candidates`)
- [x] 3.2 [TEST]+[BE] `OpportunityQueries.list_page` (account-scoped join, filters status/pipeline/stage/division/owner/account/tender/at-risk/close range/q, sorts, `days_in_stage`, embedded names) and `for_account` (open first)
- [x] 3.3 [TEST]+[BE] `OpportunityQueries.board` in two statements (aggregate per stage + `row_number` cap 50, `has_more`, `closed_this_month` in Madrid month boundaries); performance test: board under 500 ms with 500 open opportunities
- [x] 3.4 [TEST]+[BE] `TimelineQueries` union: `opportunity_stage`/`opportunity_closed` entries from the history merged with activities by `occurred_at`, kind filters additive; `ActivityQueries` filter by `opportunity_id`; `TodayQueries` blocks `tenders_due` (≤ +7 d, overdue first) and `at_risk`

## 4. Backend services and API

- [x] 4.1 [BE] Write failing unit tests for `OpportunityService.create` (account writer check, rep owner rules vs manager `owner_id`, division default pipeline, audit `opportunity.created`) and `update` (PATCH fields only, `opportunity_has_lines`, tender rules, audit diffs); implement `application/opportunities/{commands,service}.py` with `ensure_opportunity_writer`
- [x] 4.2 [BE] Write failing unit tests for `move_stage`/`win`/`lose`/`reopen` (permissions incl. `reopen_forbidden` for reps, audit `opportunity.stage_changed/won/lost/reopened`, history) and `set_at_risk`/`assign` (`opportunity.at_risk_set/at_risk_cleared/reassigned`); implement
- [x] 4.3 [BE] Write failing unit tests for line commands (audit `opportunity.line_*` with resulting amount) and the activity integration (`opportunity_not_in_account`, next action inherits the link, done activity clears an automatic at-risk flag only); implement in `OpportunityService` and `ActivityService`
- [x] 4.4 [BE] Write failing unit tests for the at-risk scan (`application/opportunities/at_risk.py`: candidates rule with fixed clock, `automatic` source, null actor, idempotence, never clears); implement plus settings `AT_RISK_AFTER_DAYS`/`AT_RISK_SCAN_INTERVAL_HOURS`, `app/tooling/at_risk_scan.py` CLI and the lifespan scheduler task (disabled at 0)
- [x] 4.5 [BE] Write failing API tests for `POST/GET /opportunities`, `GET /opportunities/{id}`, `GET /accounts/{id}/opportunities` (roles, scope 404, defaults, amounts as strings); implement `schemas/opportunities.py` and router `api/v1/opportunities.py`
- [x] 4.6 [BE] Write failing API tests for `PATCH` + `/stage|win|lose|reopen|at-risk|assignment` (428/409 locking, error-code mapping, permissions matrix incl. back office read-only and non-owner rep 403) and the lines endpoints; implement
- [x] 4.7 [BE] Write failing API tests for `GET /opportunities/board` (columns, totals, cap+`has_more`, `closed_this_month`), timeline union, `/activities?opportunity_id=` + `ActivityRead.opportunity_*`, `/me/today` new blocks; implement; register error codes and export OpenAPI

## 5. Frontend foundation

- [x] 5.1 [FE] Install `@dnd-kit/core` + `@dnd-kit/sortable`; regenerate `src/api/schema.d.ts`; add `opportunityKeys` to `query-keys.ts`, error codes and `errors.json` entries, i18n namespace `opportunities` (Oportunidad, Etapa, Ganada, Perdida, Licitación, En riesgo, Importe estimado, form/validation keys) and the "Pipeline" nav entry (`/oportunidades`, `KanbanSquare`) in `navigation.ts`/`routes.ts`/`router.tsx`
- [x] 5.2 [FE]+[TEST] `features/opportunities/{api,queries,schemas,hooks}`: typed calls (list, board, detail, create, patch, stage, win, lose, reopen, at-risk, assignment, lines) with `ifMatch`, query hooks with invalidation (board+lists+detail+account section+today), `useCanWriteOpportunity`, zod schemas reusing `parsePrice`; MSW `opportunities-fixtures.ts` + `handlers/opportunities.ts`; unit tests for schemas and invalidation
- [x] 5.3 [FE]+[TEST] Shared components `StageBadge`, `AmountText`, `OpportunityCard`, `TenderFields`, `StageHistory`; tests for badge variants and card content

## 6. Frontend screens

- [x] 6.1 [FE]+[TEST] `PipelinePage` at `/oportunidades`: mobile filterable list (state chips, pipeline/stage/division/owner filters in URL, badges, days in stage) with `DataList`; tests: default `status=open`, chips switch, badges render
- [x] 6.2 [FE]+[TEST] Desktop kanban `Board` (dnd-kit): columns per open stage with count/total, closed summary line, optimistic `/stage` with rollback + conflict dialog, drop on Ganada/Perdida opens win/lose form, keyboard sensor with Spanish announcements, non-writable cards not draggable; tests: keyboard move calls `/stage`, drop on Perdida opens the form, totals rendered
- [x] 6.3 [FE]+[TEST] `OpportunityForm` (three fields + "Más datos" per spec, division→pipeline hint, tender defaults) at `/oportunidades/nueva` and `/centros/:id/oportunidades/nueva`; tests: minimal payload, tender pre-checked for public hospitals, close date defaults
- [x] 6.4 [FE]+[TEST] `OpportunityPage` sheet: header with stage picker and actions, `WinForm`, `LoseForm` (brand/note requirements inline), `LinesEditor` (product search over the catalogue, amount recomputation, `If-Match`), Actividades block (timeline filtered + "Nueva actividad" pre-linked), `StageHistory`; closed and read-only states; tests: lose validation, line add updates the amount, back office read-only
- [x] 6.5 [FE]+[TEST] Integrations: `OpportunitiesSection` in the account 360º (cards + closed count + "Ver todas"), activity form opportunity select (pre-filled, hidden without open opportunities), "Hoy" blocks "Licitaciones esta semana" / "Centros en riesgo", timeline renders `opportunity_stage`/`opportunity_closed` entries; update affected MSW fixtures and existing tests (AppShell nav, Hoy, timeline, 360º placeholders)

## 7. Documentation

- [x] 7.1 Update `ai-specs/specs/api-spec.yml` via the exporter (opportunity endpoints, board, lines, today/timeline/activity extensions, error codes) and regenerate frontend types
- [x] 7.2 Update `ai-specs/specs/data-model.md` (three tables, activities column, ER, indexes, principles) and `development_guide.md` (at-risk job + settings, pipeline rules, navigation, new routes)

## 8. Quality gates and E2E

- [x] 8.1 [TEST] Backend gates: `ruff`, `mypy --strict`, full pytest green, coverage not below the current threshold
- [x] 8.2 [TEST] Frontend gates: `eslint`, `prettier --check`, `tsc -p tsconfig.app.json`, vitest green
- [x] 8.3 [E2E] Extend `e2e/fixtures/app.ts` (`createAccount`, `createOpportunity` helpers as needed) and write `e2e/opportunities.spec.ts` (desktop + mobile, axe on list/board/sheet): rep creates an opportunity from the 360º page → moves stage (drag on desktop, picker on mobile) → adds a product line (amount changes) → loses it with Competidor + brand → timeline shows the stage entries; manager sees board totals and reopens
- [x] 8.4 [E2E] Run the compose smoke procedure (`AUTH_RATE_LIMIT=1000/minute`, `up -d --build`, e2e seed, `npx playwright test`, `down`, restore the rate limit) and record implementation deviations in `design.md` "Implementation notes"
