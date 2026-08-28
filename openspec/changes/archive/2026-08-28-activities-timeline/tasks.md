## 1. Backend domain

- [x] 1.1 [BE] Write failing unit tests for the `Activity` aggregate: `record_done` (defaults now/done), `plan`, `note_cannot_be_planned`, `complete` (done_at default, outcome), `cancel` (`cancel_reason_required`), `reschedule` (planned only), terminal states → `invalid_activity_transition`; implement `domain/activities/{entities,errors}.py` with `ActivityStatus`, `ActivityOutcome`
- [x] 1.2 [BE] Write failing unit tests for `Activity.ensure_editable(actor, now)` (owner 7-day window on done, planned always, managers always, others never → `activity_locked`) and `update_details`; implement
- [x] 1.3 [BE] Write failing unit tests for `NextAction` validation (`next_action_in_past`, no notes) and `Activity.follow_up(next_action)` producing a planned activity with same account/contacts/owner; implement
- [x] 1.4 [BE] Define `ActivityRepository` (get, add, save with version, list_by_account_and_contacts check helper) and extend `AccountRepository` with `refresh_activity_summary(account_id)`; extend `UnitOfWork` and the unit-test fakes (`InMemoryActivityRepository`, summary recomputation in the fake account repo)

## 2. Backend data model and migration

- [x] 2.1 [BE] ORM models `activities`, `activity_contacts`, enums, checks and indexes per design D4; columns `last_contact_at`, `next_activity_at` and index `(territory_id, last_contact_at)` on `accounts`
- [x] 2.2 [BE] Write migration `0004_activities` (hand-reviewed, grants for `crm_app`); integration test round-trip `upgrade → downgrade 0003 → upgrade` and `alembic check`

## 3. Backend repositories and queries

- [x] 3.1 [TEST]+[BE] Integration tests and implementation for `SqlAlchemyActivityRepository` (add/get/save with conflict, contacts sync, `contact_not_in_account` check) and `refresh_activity_summary` (note excluded, cancelled excluded, nulls when empty)
- [x] 3.2 [TEST]+[BE] `TimelineQueries.list_page(account_id, filters, params)` returning `TimelineEntry` with `occurred_at` rule and `kind = activity`; scoped through `load_visible_account`
- [x] 3.3 [TEST]+[BE] `TodayQueries.for_user(user_id, now)` with `Europe/Madrid` day/week boundaries (tests at 23:30 / 00:30 and Sunday/Monday edges), buckets `today`, `overdue`, `week.done_by_type`, `week.planned_remaining`
- [x] 3.4 [TEST]+[BE] Account queries: `last_contact_at` / `next_activity_at` in `AccountSummary`/`AccountRead`, `sort=last_contact_at` with nulls last

## 4. Backend services and API

- [x] 4.1 [BE] Write failing unit tests for `ActivityService.create` (writer check via `ensure_account_writer`, back office 403, `owner_id` only for managers → `assignment_forbidden`, contacts of the account, next action, summary refresh, `activity.created`); implement `application/activities/{commands,service}.py`
- [x] 4.2 [BE] Write failing unit tests for `ActivityService.update/complete/cancel/reschedule` (edit window, transitions, audit events `activity.updated/completed/cancelled/rescheduled`, next action on complete, summary refresh after each); implement
- [x] 4.3 [BE] Write failing API tests for `POST/GET /activities`, `GET /activities/{id}` (404 out of scope), list filters and scoping; implement schemas `schemas/activities.py` and router `api/v1/activities.py`
- [x] 4.4 [BE] Write failing API tests for `PATCH /activities/{id}`, `/complete`, `/cancel`, `/reschedule` (428/409 locking, 409 transition/locked, 422 reason/past next action); implement
- [x] 4.5 [BE] Write failing API tests for `GET /accounts/{id}/timeline` (order, filters, pagination, 404 out of scope) and `GET /me/today` (rep payload, manager `user_id`, rep with `user_id` → 403, midnight cases); implement routes in `api/v1/accounts.py` and `api/v1/me.py`
- [x] 4.6 [TEST] Extend the authorization matrix with the new endpoints; add the new error codes to the shared list
- [x] 4.7 [BE] Export OpenAPI (`api-spec.yml`) and regenerate `frontend/src/api/schema.d.ts`

## 5. Frontend foundations

- [x] 5.1 [FE] MSW fixtures/handlers for activities, timeline and today; `activityKeys` in `query-keys.ts`; new error codes in `errors.json` + `ERROR_CODES`; i18n namespace `activities`; routes `/hoy/nueva`, `/centros/:id/actividades`, `/centros/:id/actividades/nueva`, `/centros/:id/actividades/:activityId`
- [x] 5.2 [FE] Write failing tests for `features/activities` queries (create/complete/cancel/reschedule with `If-Match`, invalidation of today, timeline, account detail and list); implement `api.ts`, `queries.ts`, `schemas.ts`

## 6. Frontend screens

- [x] 6.1 [FE] Write failing component tests for `ActivityTypePicker` (radio group, icons from the master, keyboard) and `ActivityForm` (three-tap visit payload, Hecha/Planificada toggle with tomorrow 09:00 default, Nota disables Planificada, contacts pre-check primary, next action, manager owner selector, inline backend errors); implement
- [x] 6.2 [FE] Write failing tests for `ActivityFormRoute` (from 360º with centre pre-filled, from Hoy with account search) and `ActivityDetailRoute` (edit / complete / cancel / reschedule sheets, read-only when locked); implement
- [x] 6.3 [FE] Write failing tests for the timeline section in `AccountPage` (five entries, count, "Ver todas", request `page_size=5`, actions on planned entries) and `TimelinePage` (filters, pagination); implement and reorder the 360º sections (Actividades first)
- [x] 6.4 [FE] Write failing tests for `TodayPage` (weekly summary, Atrasadas and Hoy lists, one-tap Hecha sheet → `/complete`, Reprogramar → `/reschedule`, empty states, manager rep selector → `?user_id=`, back office without actions, scope warning kept); implement replacing the placeholder
- [x] 6.5 [FE] Account list column "Último contacto" (relative / "Nunca") with `sort=last_contact_at`, header "Último contacto" / "Próxima actividad", "Nueva actividad" action; update list/page tests

## 7. End-to-end, docs and validation

- [x] 7.1 [E2E] Playwright `activities.spec.ts` (desktop + mobile, axe): rep records a visit from the 360º page with a next action → the follow-up appears in Hoy → marks it done → the timeline shows both and the account list shows "Último contacto"; manager views the rep's Hoy
- [x] 7.2 [TEST] Run all quality gates: backend ruff/mypy/pytest with coverage, frontend lint/prettier/tsc/vitest/build, pre-commit
- [x] 7.3 Update `ai-specs/specs/data-model.md` (activities, activity_contacts, account columns, ER diagram, indexes), `development_guide.md` (timezone rule, edit window) and `api-spec.yml`
- [x] 7.4 Compose stack smoke test and E2E suite against it; tear down and reset `AUTH_RATE_LIMIT`
