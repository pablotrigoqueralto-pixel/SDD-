## 1. Backend domain

- [x] 1.1 [BE] Write failing unit tests for `slugify_code` (accents, spaces, "3Gen" → `three_gen` special-cased via leading digit words, collisions produce identical slugs); implement `domain/reference/codes.py`
- [x] 1.2 [BE] Write failing unit tests for `Brand` (create own/competitor, rename, set divisions, activate/deactivate) and `LossReason` (create appended last, rename, activate); implement `domain/reference/entities.py` and errors (`BrandNameAlreadyExistsError`, `LossReasonNameAlreadyExistsError`, `PipelineNameAlreadyExistsError`, `StageOrderInvalidError`, `StageProbabilityInvalidError`, `StageFlagImmutableError`, `LastActiveStageError`)
- [x] 1.3 [BE] Write failing unit tests for the `Pipeline` aggregate: `rename`, `update_stage(name, probability, is_active)` with probability range and last-open-stage guard, `reorder(stage_ids)` validation (missing/extra/duplicate/foreign) and contiguous `sort_order` reassignment; implement
- [x] 1.4 [BE] Define repository protocols `BrandRepository`, `LossReasonRepository`, `PipelineRepository` (get with stages, list_all, add, save with version) and `ReferenceReadRepository` (account types, activity types); extend `UnitOfWork` protocol and `FakeUnitOfWork` with in-memory fakes (name uniqueness, stage versions)

## 2. Backend data model, migration and seed

- [x] 2.1 [BE] ORM models `account_types`, `activity_types`, `brands`, `brand_divisions`, `loss_reasons`, `pipelines`, `pipeline_divisions` (unique `division_id`), `pipeline_stages` (unique `(pipeline_id, code)`, deferrable unique `(pipeline_id, sort_order)`, checks on probability and won/lost) per design D4
- [x] 2.2 [BE] Generate and hand-review migration `0002_reference_data` (deferrable constraint DDL, checks, indexes, reversible downgrade); run the round-trip locally and `alembic check`
- [x] 2.3 [BE] Write failing integration tests for the seed: six account types (only Hospital público tenders), six activity types (Nota not a contact), thirteen own brands (`three_gen`), six loss reasons (flags), two pipelines with stages/probabilities/flags and one default pipeline per division, deterministic ids, idempotency; implement `seed.py` extension with insert-only editable columns
- [x] 2.4 [TEST] Integration test: after an admin rename (brand) and a probability change (stage), re-running the seed preserves both; semantic flags are refreshed when they differ

## 3. Backend repositories and unit of work

- [x] 3.1 [TEST] Integration tests for `SqlAlchemyBrandRepository` (add, get, list filters `is_own/is_active/q`, save with version → conflict, division links sync, name uniqueness → `brand_name_already_exists`)
- [x] 3.2 [BE] Implement `SqlAlchemyBrandRepository`, `SqlAlchemyLossReasonRepository` (append `sort_order`), `SqlAlchemyPipelineRepository` (loads stages ordered; saves stage edits and reorders within one transaction using the deferrable constraint), `SqlAlchemyReferenceReadRepository`; register them in `SqlAlchemyUnitOfWork`

## 4. Backend services and API

- [x] 4.1 [BE] Write failing unit tests for `BrandService.create/update` (audit `brand.created/updated/activated/deactivated`, unknown division → `unknown_reference`, duplicate name); implement
- [x] 4.2 [BE] Write failing unit tests for `LossReasonService.create/update` (audit `loss_reason.*`, duplicate name); implement
- [x] 4.3 [BE] Write failing unit tests for `PipelineService.rename/update_stage/reorder` (audits `pipeline.updated`, `pipeline_stage.updated`, `pipeline_stages.reordered` with before/after order; flag change → `stage_flag_immutable`); implement
- [x] 4.4 [BE] Write failing unit tests for `ReferenceQueries.bundle()` (includes inactive rows, stages ordered, ETag from max `updated_at`); implement `application/reference/queries.py`
- [x] 4.5 [BE] Write failing API tests for `GET /reference-data` (200 for every role, `ETag` + 304 on `If-None-Match`, 401 anonymous) and the five per-master read endpoints including brand filters; implement schemas and routers `api/v1/reference.py`
- [x] 4.6 [BE] Write failing API tests for brand administration (201, 409 duplicate, 422 unknown division, PATCH 200/428/409, 403 for non-admins); implement
- [x] 4.7 [BE] Write failing API tests for loss reason administration (201 appended last, 409 duplicate, PATCH, 403); implement
- [x] 4.8 [BE] Write failing API tests for pipeline administration: rename, stage patch (200, 422 probability, 400 immutable flag, 400 last active stage, 409 stale stage version), reorder (200 with new order and audit, 422 invalid order, 409 stale pipeline version); implement
- [x] 4.9 [TEST] Extend the authorization matrix with every new endpoint (reads for all roles, writes admin only)
- [x] 4.10 [BE] Export OpenAPI (`api-spec.yml`) and commit it

## 5. Frontend reference cache

- [x] 5.1 [FE] Regenerate `src/api/schema.d.ts`; add MSW fixtures/handlers for `/reference-data`, brands, loss reasons and pipelines reflecting the contract
- [x] 5.2 [FE] Write failing tests for `features/reference` (single request shared by `useAccountTypes/useActivityTypes/useDivisions/useBrands/useLossReasons/usePipelines`, `labelOf` helper, invalidation via `referenceKeys.all`); implement hooks and `query-keys` entry
- [x] 5.3 [FE] Switch the existing `useDivisions` consumer (user form) to the bundle selector and remove the standalone divisions query; keep tests green

## 6. Frontend admin screens

- [x] 6.1 [FE] Add i18n keys (`admin` namespace: marcas, motivos, pipelines; `reference` namespace for badges) and the five new error codes to `errors.json` + `ERROR_CODES`; update the translations test
- [x] 6.2 [FE] Write failing tests for `features/admin/brands` queries (list filters, create, update with `If-Match`, bundle invalidation); implement `api.ts`, `queries.ts`
- [x] 6.3 [FE] Write failing component tests for `BrandListPage` (badges Propia/Competencia, divisions, Inactivo, search + filter, empty state) and `BrandForm` (create competitor, duplicate name under field, edit with version, conflict dialog); implement pages, form and routes `/admin/marcas`, `/admin/marcas/nueva`, `/admin/marcas/:id`
- [x] 6.4 [FE] Write failing tests for `features/admin/loss-reasons` (list with requirement badges, create appended, edit name/active, duplicate); implement
- [x] 6.5 [FE] Write failing component tests for `PipelinesPage`: two cards, stage rows with badges, Subir/Bajar disabled at ends and accessible names including the stage name, reorder calls `PUT …/order` with `If-Match`, edit form (name, probability 0–100, active) calling the stage PATCH, inline messages for `last_active_stage` and `stage_probability_invalid`; implement page, `StageForm`, api and queries
- [x] 6.6 [FE] Update `AdminHubPage` to five cards (two columns from `sm`) and `features/admin/routes.tsx`; update hub test

## 7. End-to-end, docs and validation

- [x] 7.1 [E2E] Playwright spec `reference-data.spec.ts` (desktop + mobile, axe on each page): admin renames a brand, creates a competitor brand, adds a loss reason, moves a stage down and edits a probability; a sales rep gets "Sin permiso" on `/admin/marcas`
- [x] 7.2 [TEST] Run the full quality gates: backend lint/mypy/tests with coverage, frontend lint/prettier/tsc/unit/build, pre-commit hooks
- [x] 7.3 Update `ai-specs/specs/data-model.md` (eight tables, constraints, ER diagram) and `development_guide.md` (seed contents, editable vs seed-only masters)
- [x] 7.4 Verify `api-spec.yml` and `schema.d.ts` are current; run the compose stack smoke test and the E2E suite against it
