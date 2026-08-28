## Why

Quermed's sales follow-up today lives in each rep's head and in loose spreadsheets: nobody can answer "what is open in Cardiología this quarter, at which stage, for how much" without a phone call. Changes 02–05 delivered the masters the pipeline needs — two pipelines with stages and probabilities, loss reasons, account types that buy via tender, accounts with owner and territory, activities and the catalogue. This change adds the record that ties them together: the **opportunity** (Oportunidad), moved through its pipeline from the phone in seconds and read by management as a kanban and a forecast.

Constitution principles served: 30-second capture (centre + division + amount), smart defaults (pipeline from the division, stage = first, owner = account owner, expected close date by pipeline), one screen one purpose (list / kanban / opportunity sheet), business vocabulary (Oportunidad, Etapa, Ganada, Perdida, Licitación, En riesgo), visibility inherited from the centre, immutable audit and stage history, optimistic locking, i18n-ready, accessible kanban with keyboard fallback.

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- **Opportunity aggregate**: `opportunities` with account, pipeline and current stage, division, owner, auto-generated name (editable), estimated amount (EUR ex VAT), expected close date, status (`open` | `won` | `lost`), won amount/date, loss reason (+ competitor brand and note when the reason requires them), `is_at_risk` and `at_risk_since`, tender block (`is_tender`, `tender_reference`, `tender_deadline`, `estimated_award_date`), `version`. Every stage change is recorded in `opportunity_stage_history` (from, to, actor, timestamp, days in the previous stage).
- **Optional product lines**: `opportunity_lines` (product, quantity, unit price defaulting to the list price) — when lines exist the amount is the sum of the lines; otherwise the manual estimate stands.
- **Lifecycle commands**: `POST /opportunities/{id}/stage` (any open stage, forward or backward), `/win` (final amount + date), `/lose` (reason, brand/note when required), `/reopen` (managers), `/at-risk` (toggle, consumables pipeline only); `PATCH` edits descriptive fields and the tender block; reassignment of owner only for managers/admins.
- **Automatic "En riesgo"**: a consumables opportunity in a won-recurring stage with no activity and no line change for N days (`AT_RISK_AFTER_DAYS`, default 60) is flagged by a scheduled job run by the backend container (and idempotently by the seed/CLI); the rep clears it by registering activity or manually.
- **Activities link**: activities gain an optional `opportunity_id` (activity form pre-filled from the opportunity sheet); the account timeline shows stage changes and closes as `opportunity_stage` entries next to activities.
- **Read models**: scoped, paginated `GET /opportunities` (filters stage, pipeline, division, owner, status, at risk, tender, close date range; sort by amount, close date, days in stage, updated), `GET /opportunities/board?pipeline_id=` (columns per stage with count and total, capped per column), `GET /accounts/{id}/opportunities`; "Hoy" gains tender deadlines within 7 days and at-risk centres.
- **Screens**: `/oportunidades` — list on mobile (filters, amount, days in stage, badges Licitación / En riesgo) and kanban on desktop (columns per stage, drag and drop with keyboard alternative, column totals); opportunity sheet with header (amount, stage picker, Ganar / Perder / En riesgo actions), tender block, product lines, activities and stage history; three-field creation from the account 360º page and from the list; "Oportunidades" section in the account page; navigation entry "Pipeline" in the bottom bar.
- **Reference bundle**: unchanged; `AT_RISK_AFTER_DAYS` is a setting, not a master.

## Non-goals

- Formal quotes, PDF, email and quote acceptance (change 07); the win action accepts an amount typed by the rep until a quote can supply it.
- Forecast and conversion dashboards beyond the column totals (change 09).
- Automatic creation of a consumables opportunity when equipment is won; installed base / serial numbers; order or Sage synchronisation.
- Multi-currency, taxes and discounts on opportunity lines (discounts belong to the quote).
- Notifications by email or push (the "Hoy" page is the only alerting surface in the MVP).

## Roles and territory visibility

| Role | Opportunities |
|---|---|
| `sales_rep` | Sees the opportunities of the accounts they can see; creates on those accounts (owner = self or the account owner); edits, moves and closes the ones they own. |
| `sales_manager` | Sees, edits, moves and closes everything; reassigns owners; reopens closed opportunities. |
| `back_office` | Read-only on everything (lists, board, sheet); never writes. |
| `admin` | Everything, plus the `AT_RISK_AFTER_DAYS` setting and pipelines master (already in change 02). |

Visibility is the account's visibility (`ScopeFilter` on the account); an opportunity never widens or narrows what the rep already sees.

## Capabilities

### New Capabilities
- `opportunity-model`: opportunity aggregate, lines, stage history, tender block, at-risk rule, name generation, amount rule, migration and indexes.
- `opportunity-api`: scoped list, board and account endpoints; create/update; stage, win, lose, reopen, at-risk and reassignment commands; activity link; at-risk job; "Hoy" additions.
- `opportunity-screens`: mobile list and desktop kanban, opportunity sheet with actions and lines, creation from the account page, account section, navigation entry.

### Modified Capabilities
- `activity-model`: activities gain an optional `opportunity_id` (must belong to the same account).
- `activity-api`: `/me/today` returns tender deadlines and at-risk opportunities; activity payloads carry `opportunity_id`; the account timeline emits `opportunity_stage` entries.
- `activity-screens`: activity form pre-filled with the opportunity; "Hoy" shows the two new blocks; timeline renders stage entries.
- `account-screens`: "Oportunidades" section in the 360º page with a create shortcut.
- `app-shell`: bottom bar / sidebar gains "Pipeline" (five entries: Hoy · Centros · Pipeline · Más · Administración).
- `audit-log`: events `opportunity.*` (created, updated, stage_changed, won, lost, reopened, at_risk_set, at_risk_cleared, reassigned, line_added/updated/removed).

## Impact

- New tables: `opportunities`, `opportunity_lines`, `opportunity_stage_history`; column `activities.opportunity_id`; migration `0006_opportunities`.
- New API: `/api/v1/opportunities` (+ `/board`, `/{id}`, `/{id}/stage|win|lose|reopen|at-risk|assignment`, `/{id}/lines`), `/accounts/{id}/opportunities`; extended `/me/today`, `/activities`, `/accounts/{id}/timeline`.
- Backend job: `app.tooling.at_risk_scan` (idempotent) scheduled inside the backend container; new setting `AT_RISK_AFTER_DAYS`.
- Frontend: `features/opportunities` (list, board, sheet, forms, lines), `@dnd-kit/core` + `@dnd-kit/sortable` as the only new dependency (accessible drag and drop with keyboard sensors), i18n namespace `opportunities`, navigation change.
- Documentation: `api-spec.yml`, `data-model.md`, `development_guide.md` (at-risk job, setting, pipeline rules).
