## Context

Changes 02–05 left every master the pipeline needs: two seeded pipelines with ordered stages, probabilities and `is_won` / `is_lost` / `is_at_risk` flags, one default pipeline per division, loss reasons with `requires_brand` / `requires_note`, account types with `buys_via_tender`, accounts with owner/territory and the `ScopeFilter` SQL predicate, activities with a discriminated timeline (`TimelineEntry.kind = "activity"`), and products with exact prices. The app shell reserves a fifth navigation slot ("Later changes add Pipeline").

Confirmed product inputs: manual estimate + optional product lines; tender block with reference and deadlines; consumables "En riesgo" automatic after N days plus manual; three-field mobile creation; free movement among open stages with explicit Ganar/Perder; winning records amount and date only; visibility inherited from the account; list on mobile, kanban on desktop.

Constraints: the kanban must stay under 500 ms for a few hundred open opportunities; every stage change is evidence (audit + history); no external scheduler exists in the MVP stack; the frontend adds at most one dependency.

## Goals / Non-Goals

**Goals:**
- One `Opportunity` aggregate whose invariants encode the pipeline rules (stage of the same pipeline, closing only through commands, loss reason requirements, at-risk only where the pipeline allows it).
- Stage history as first-class data so "days in stage" and future conversion metrics need no reconstruction.
- A board read model computed in one query, and a list that reuses the account scope predicate.
- Kanban drag and drop that is accessible (keyboard, screen reader announcements) without a second UI library.

**Non-Goals:**
- Quotes, dashboards, notifications, automatic consumables opportunities, order/Sage sync, discounts or taxes on lines (see proposal).

## Decisions

### D1. One `opportunities` table with `status` + `stage_id`, closing stages stay real stages

`status open | won | lost` is derived at write time from the target stage's flags and stored: open stages keep `open`, the `is_won` stage sets `won`, the `is_lost` stage sets `lost`. Lists and the board filter by `status` cheaply; the stage is still the source of truth for the column. Won and lost rows keep their closing stage so the board can show "Ganadas este mes" without a second table.
- *Discarded*: `status` only, no stage on closed rows — the consumables pipeline has two "won-like" stages (Recurrente, En riesgo) that must remain distinguishable.
- *Discarded*: closed opportunities in a separate table — the account section and the timeline would union two tables for one concept.

### D2. Explicit lifecycle commands; `PATCH` never touches stage, status or owner

`POST /opportunities/{id}/stage {stage_id}` moves among open stages of the same pipeline (forward or backward), `POST /win {won_amount?, won_at?}`, `POST /lose {loss_reason_id, competitor_brand_id?, note?}`, `POST /reopen {stage_id}` (managers/admins; back to an open stage, clears the closing fields), `POST /at-risk {flag: bool}` (consumables pipeline only), `PUT /assignment {owner_id}` (managers/admins). `PATCH` edits name, estimated amount (rejected when lines exist), expected close date, description and the tender block. Each command validates its transition in the aggregate and records one audit event with a specific action.
- *Discarded*: `PATCH {stage_id}` — three different validations (open move, win, lose) behind one field, and a generic "updated" audit row where the timeline needs "Ganada por 12.500 €".
- *Discarded*: won/lost as a free stage change — the loss reason requirement (change 02) would have to be enforced by the client.

### D3. `win` records amount and date; the quote supplies them later

`won_amount` defaults to the current amount, `won_at` to now; both editable in the command. Change 07 will call the same command with the accepted quote total, so the contract does not change when quotes arrive.
- *Discarded*: requiring an accepted quote — blocks the pipeline until change 07 and does not match tenders won without a CRM quote.

### D4. Amount rule: lines win over the estimate

`amount` is a stored column recomputed by the service after any line command: `SUM(quantity × unit_price)` when lines exist, else `estimated_amount`. `estimated_amount` stays stored so removing the last line restores it. `PATCH estimated_amount` returns `opportunity_has_lines` (409) when lines exist. Lines: `product_id`, `quantity` (numeric(10,2) > 0), `unit_price` (numeric(12,2) ≥ 0, default list price at insertion), `sort_order`; retired products stay on existing lines but cannot be added.
- *Discarded*: computing the amount on read — the board sums hundreds of rows per column; a stored column indexed with `(pipeline_id, stage_id, status)` keeps it one aggregate query.
- *Discarded*: dropping the manual estimate once lines exist — a rep often knows "about 30 k" before knowing the configuration.

### D5. Tender block and defaults

`is_tender bool`, `tender_reference text null`, `tender_deadline date null`, `estimated_award_date date null`. `is_tender` defaults to `account_type.buys_via_tender` at creation; deadlines are only accepted when `is_tender` is true (`tender_fields_require_tender` 422). "Hoy" lists open tender opportunities whose `tender_deadline` is within the next 7 days or past.
- *Discarded*: a `tenders` child table — one tender per opportunity in Quermed's practice; a table would add a join to every list for three nullable columns.

### D6. "En riesgo": stored flag, scanned by an idempotent job

`is_at_risk bool`, `at_risk_since timestamptz null`, `at_risk_source enum (manual | automatic) null`. Rule (consumables pipeline, `status = won`, stage `is_won`): flagged automatically when `last_activity_at` (max of the linked activities' `scheduled_at`, done only) and `updated_at` are both older than `AT_RISK_AFTER_DAYS` (setting, default 60). The scan `python -m app.tooling.at_risk_scan` sets the flag and moves the row to the `is_at_risk` stage (recording history + audit with actor = system); it never clears automatic flags — the rep clears by `POST /at-risk {flag:false}` or by registering a done activity (the activity service clears an automatic flag and moves back to the won stage). The compose backend service runs the scan at start and every 6 h through a lightweight in-process scheduler (`asyncio` task started in the FastAPI lifespan when `AT_RISK_SCAN_INTERVAL_HOURS > 0`); the CLI form is for cron in production.
- *Discarded*: Celery/APScheduler — a new runtime dependency and a worker container for one query a day.
- *Discarded*: computing "at risk" on read — the flag must be a stage on the board (the seed already has the "En riesgo" stage) and must be manually overridable.
- *Discarded*: clearing automatic flags automatically when time passes — silent flapping; a human action is the only way out.

### D7. Data model

| Table | Columns | Constraints / indexes |
|---|---|---|
| `opportunities` | `id`, `account_id FK RESTRICT`, `pipeline_id FK RESTRICT`, `stage_id FK pipeline_stages RESTRICT`, `division_id FK RESTRICT`, `owner_id FK users RESTRICT`, `name text ≤ 200`, `description text null`, `status opportunities_status_enum`, `estimated_amount numeric(12,2) ≥ 0`, `amount numeric(12,2) ≥ 0`, `expected_close_date date`, `won_amount numeric(12,2) null`, `won_at timestamptz null`, `lost_at timestamptz null`, `loss_reason_id FK null`, `competitor_brand_id FK brands null`, `loss_note text null`, `is_tender bool`, `tender_reference text null`, `tender_deadline date null`, `estimated_award_date date null`, `is_at_risk bool`, `at_risk_since timestamptz null`, `at_risk_source enum null`, `stage_entered_at timestamptz`, `created_by FK users`, `version`, `created_at`, `updated_at` | checks: `status='won' → won_at NOT NULL`, `status='lost' → loss_reason_id NOT NULL AND lost_at NOT NULL`, `is_tender OR (tender_reference IS NULL AND tender_deadline IS NULL AND estimated_award_date IS NULL)`, `is_at_risk = (at_risk_since IS NOT NULL)`; indexes `(account_id, status)`, `(owner_id, status)`, `(pipeline_id, stage_id, status)` board, `(status, expected_close_date)`, `(is_tender, tender_deadline) WHERE status='open'`, `(is_at_risk) WHERE is_at_risk` |
| `opportunity_lines` | `id`, `opportunity_id FK CASCADE`, `product_id FK RESTRICT`, `quantity numeric(10,2) > 0`, `unit_price numeric(12,2) ≥ 0`, `sort_order int`, `created_at`, `updated_at` | unique `(opportunity_id, product_id)`; index `opportunity_id` |
| `opportunity_stage_history` | `id`, `opportunity_id FK CASCADE`, `from_stage_id FK null`, `to_stage_id FK`, `actor_id FK users null` (null = system scan), `occurred_at`, `seconds_in_previous_stage int null` | index `(opportunity_id, occurred_at DESC)` |
| `activities` (+) | `opportunity_id FK opportunities SET NULL null` | index `opportunity_id`; service check `activity.account_id == opportunity.account_id` |

Migration `0006_opportunities`. `stage_entered_at` gives "days in stage" without touching history on every read. `ProductRepository.is_referenced` (change 05) becomes a real query on `opportunity_lines`.
- *Discarded*: `division_id` derived from the pipeline — the equipment pipeline serves five divisions; the opportunity's own division feeds the scope and the forecast by division.

### D8. Visibility and permissions

Reads: `scoped_accounts` predicate applied through a join on `accounts` (`GET /opportunities`, `/board`, `/accounts/{id}/opportunities`, detail). Writes: `ensure_opportunity_writer` — `admin`/`sales_manager` always; `sales_rep` when `opportunity.owner_id == user.id`; `back_office` never (`forbidden`). Creation by a rep on a visible account: owner = rep when the rep can write the account, else the account owner (managers may pick any active rep). Reassignment and reopen: managers/admins only (`assignment_forbidden`, `reopen_forbidden`).
- *Discarded*: opportunity-level territory — an opportunity is always inside a centre; a second scope would let the two disagree.

### D9. Read models

- `GET /opportunities` → `Page[OpportunitySummaryRead]` (default `status=open`, sort `expected_close_date`; also `amount`, `stage_entered_at`, `updated_at`) with `account_name`, `stage_name`, `owner_name`, `days_in_stage`, badges.
- `GET /opportunities/board?pipeline_id=&division_id=&owner_id=` → `BoardRead { pipeline, columns: [{ stage, count, total_amount, items: OpportunitySummaryRead[] (open ones, capped at 50 by `stage_entered_at` asc), has_more }], closed_this_month: { won_count, won_amount, lost_count } }`. Two statements: one aggregate grouped by stage, one window-limited select (`row_number() over (partition by stage_id)`).
- `GET /opportunities/{id}` → `OpportunityRead` with lines, stage history and the loss/tender blocks.
- Timeline: `TimelineEntry.kind = "opportunity_stage"` with payload `stage_change { opportunity_id, opportunity_name, from_stage, to_stage, actor_name, amount }` built from `opportunity_stage_history` in the same union query as activities; `kind = "opportunity_closed"` reuses the same payload for won/lost.
- `/me/today` gains `tenders_due: OpportunitySummaryRead[]` (deadline ≤ today + 7 d) and `at_risk: OpportunitySummaryRead[]` for the user's (or selected rep's) opportunities.
- *Discarded*: board as N per-stage requests — a rep with six columns would fire six requests per refresh; the window function keeps one round trip.

### D10. Domain and application layout

`app/domain/opportunities/{entities.py (Opportunity, OpportunityLine, OpportunityStatus, AtRiskSource, StageChange), errors.py (stage_not_in_pipeline 422, invalid_opportunity_transition 409, opportunity_closed 409, loss_reason_requires_brand 422, loss_reason_requires_note 422, opportunity_has_lines 409, tender_fields_require_tender 422, at_risk_not_supported 422, line_product_inactive 422, line_duplicated 409, reopen_forbidden 403), repository.py}`; `app/application/opportunities/{commands.py, service.py (OpportunityService: create, update, move_stage, win, lose, reopen, set_at_risk, assign, add/update/remove_line), queries.py (OpportunityQueries: list_page, board, for_account, detail), at_risk.py (scan)}`; `app/api/v1/opportunities.py`; `app/tooling/at_risk_scan.py`; activity service extended (`opportunity_id` check + automatic at-risk clearing); `TimelineQueries` unions history rows.

### D11. Frontend

Routes: `/oportunidades` (list on mobile, board on desktop; the same page decides by `useIsDesktop`), `/oportunidades/nueva` (asks the centre first, like `/hoy/nueva`), `/oportunidades/:id` (sheet), `/oportunidades/:id/editar`, `/oportunidades/:id/ganar`, `/oportunidades/:id/perder`, `/oportunidades/:id/lineas`, `/centros/:id/oportunidades/nueva` (pre-filled centre). Navigation: "Pipeline" (icon `KanbanSquare`) as the third entry.

Feature `features/opportunities/{api,queries,schemas,hooks (useCanWriteOpportunity),components/{OpportunityCard, StageBadge, AmountText, OpportunityForm, WinForm, LoseForm, LinesEditor, TenderFields, StageHistory, Board (dnd-kit: DndContext, one sortable column per stage, PointerSensor + KeyboardSensor, `announcements` in Spanish), StagePicker (native select fallback on mobile)},pages/{PipelinePage, OpportunityPage, OpportunityRoutes}}`; `features/accounts` gains `OpportunitiesSection`; `features/activities` form gains an opportunity field (pre-filled, hidden when absent) and "Hoy" two blocks; the timeline renders `opportunity_stage` / `opportunity_closed` entries with a stage icon.

Mobile creation (three fields):

```
┌──────────────────────────┐
│ Nueva oportunidad     ✕  │
├──────────────────────────┤
│ Centro: Clínica Tambre   │ ← pre-filled from the 360º; search from the list
│ División [Vascular ▾]    │ ← account divisions first; pipeline shown as hint
│ Importe estimado [ 30.000 ]│
│ ─ Más datos ▸            │ ← nombre (autogenerado), fecha cierre (+90/+30 d),
│                          │    licitación (marcada si el centro compra por concurso)
├──────────────────────────┤
│        [ Guardar ]       │
└──────────────────────────┘
```

Desktop board:

```
Pipeline · Equipos [▾]   División [Todas ▾]   Comercial [Todos ▾]        [+ Nueva]
┌ Contacto 4 · 62 k ┐┌ Demo 3 · 90 k ┐┌ Presupuesto 5 · 210 k ┐┌ Negociación 2 · 80 k ┐
│ Tambre · Doppler   ││ …             ││ ⚑ H. La Paz · Ecógrafo ││ …                   │
│ 12,5 k · 6 d       ││               ││ 60 k · 12 d · 30/09   ││                     │
└────────────────────┘└───────────────┘└───────────────────────┘└─────────────────────┘
Ganadas este mes: 3 · 95 k   Perdidas: 1
```

Dropping a card on an open column calls `/stage` optimistically (rollback + toast on error); dropping on Ganada/Perdida opens the win/lose form instead of moving. Keyboard: focus a card, Space to lift, arrows to change column, Space to drop — provided by dnd-kit's `KeyboardSensor` with `sortableKeyboardCoordinates`.
- *Discarded*: `react-beautiful-dnd` — unmaintained, no keyboard sensor abstraction; `@dnd-kit` is the maintained, accessible option.
- *Discarded*: kanban on mobile — columns of 300 px cards on a 412 px screen hide everything but one stage; the list with a stage filter and a stage picker in the sheet covers the mobile job.

### D12. Testing

- Backend unit: aggregate transitions (open moves, win/lose requirements, reopen, at-risk only on consumables, closed rows immutable), amount rule with lines, tender validation, name generation, at-risk scan rule with a fixed clock, permissions matrix.
- Backend integration: migration round trip; list scope through accounts (rep in/out of scope), board totals and per-column cap, timeline union, `/me/today` blocks, activity ↔ opportunity account check and automatic at-risk clearing, audit actions, `If-Match` on every command, scan idempotence.
- Frontend: creation defaults (division → pipeline hint, tender flag from the account type, close date), list badges and filters, board columns/totals and keyboard move announcement, win/lose forms (brand/note requirements), lines editor amount recomputation, account section, Hoy blocks.
- E2E (desktop + mobile, axe): rep creates an opportunity from the 360º page → moves it (drag on desktop, picker on mobile) → adds a line → loses it with a competitor brand → timeline shows the stage entries; manager sees the board totals.

## Risks / Trade-offs

- **[Board size]** → per-column cap (50) with `has_more` and a link to the filtered list; aggregate totals are unaffected by the cap.
- **[Optimistic drag then 409]** → card snaps back, conflict dialog, board refetch; `If-Match` carried per card.
- **[Automatic at-risk on stale data]** → the scan only flags won consumables rows and never clears; the setting can be set to 0 to disable in a tenant that does not want it.
- **[In-process scheduler duplicates across replicas]** → the scan is idempotent (flags rows not already flagged); production runs it via cron with the interval setting at 0.
- **[Activities without opportunity link in legacy data]** → link optional; nothing changes for existing rows.

## Migration Plan

1. Migration `0006_opportunities` (three tables, two enums, nullable FK on `activities`, indexes); no backfill.
2. Deploy backend and frontend together (additive API; `TodayRead` and `TimelineEntryRead` gain optional members; the navigation gains an entry).
3. Rollback: `alembic downgrade 0005_product_catalogue` drops the column, tables and enums.

## Open Questions

- None blocking. Whether the at-risk threshold should differ per division can be decided when real usage exists (the setting is global in the MVP).

### Implementation notes (recorded during /opsx:apply)

- The board read model uses three statements, not two: the per-stage aggregate, a `row_number`-capped id query and a hydration select through the shared base join — mapping subquery columns positionally proved fragile, and the third statement is an indexed `IN` on ≤ 50 ids per column.
- `/me/today` composes the tender/at-risk blocks in the router (`TodayQueries` + `OpportunityQueries`) instead of extending `TodayQueries`: the opportunities query module already imports the activities module for the Madrid timezone, and the reverse import would be circular.
- The activity form fetches the centre's opportunity options through the activities feature's own API helper (`listAccountOpportunityOptions`) rather than importing the opportunities feature, keeping the cross-feature dependency one-directional (opportunities → activities).
- Server-side timeline titles ("Ganada · 24.000,00 €") are formatted by a small Spanish euro helper in the queries module; screens still format amounts client-side with `Intl`.
- Kanban keyboard support ships through dnd-kit's `KeyboardSensor` with Spanish announcements; jsdom cannot measure droppable rects, so the unit tests cover rendering/totals/close zones and the stage move is exercised through the `StagePicker` (unit) and pointer drag was left to manual verification — the E2E flow moves stages through the picker, which works on both layouts.
- The at-risk CLI (`app.tooling.at_risk_scan`) is unit-tested through `scan_at_risk` with the fake unit of work and repository-tested through `list_at_risk_candidate_ids`; the CLI wrapper itself is exercised by the lifespan scheduler at container start.
- `Board` renders the won/lost stages as drop-only dashed zones (the board API returns only open columns); dropping there routes to the win/lose forms.
- E2E toasts render in two DOM nodes (toaster + live region) and the 360º page keeps both layout trees mounted, so assertions use `.first()` / `visible=true` as in earlier specs.
