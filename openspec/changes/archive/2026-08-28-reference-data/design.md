## Context

Change 01 delivered the foundation: layered FastAPI backend with unit of work + audit, optimistic locking, admin conventions (list + sheet/dialog form, `If-Match`), divisions seeded with stable ids, and the frontend shell with `DataList`, `ResponsiveFormContainer`, `CheckboxList`, `NativeSelect` and the admin hub. This change adds the remaining reference data every business entity needs, following exactly those conventions so it stays a small, mechanical change.

Inputs confirmed by the product owner: six account types, six activity types, thirteen own brands (admin-editable), six loss reasons ("Competidor" requires a brand, "Otro" a note), two pipelines with fixed stages.

## Goals / Non-Goals

**Goals:**
- One migration and one idempotent seed delivering all masters with stable ids, so every environment (dev, CI, prod) shares the same identifiers.
- Read endpoints usable by every role plus a single bundle endpoint the frontend caches.
- Admin CRUD (no delete) for brands, loss reasons and pipeline stages with audit and locking, reusing the users/territories patterns.
- Frontend `features/reference` hooks that later changes (accounts, activities, pipeline) consume without new requests.

**Non-Goals:**
- Business entities that reference the masters.
- Structural pipeline editing (adding/removing pipelines or stages, changing won/lost semantics).
- UI editing of account types and activity types (seed only in the MVP).
- Deleting master values (deactivation only).

## Decisions

### D1. One table per master, no generic "lookup" table

Separate tables `account_types`, `activity_types`, `brands`, `loss_reasons`, `pipelines`, `pipeline_stages` with typed columns and foreign keys from later entities.
- *Discarded*: a single `lookups(kind, code, name)` table — loses foreign-key integrity per kind, forces every query to filter by kind, and cannot hold master-specific columns (`probability`, `is_won`, `requires_brand`).

### D2. Stable identifiers: `code` + deterministic UUIDv5

Every master row has `id` (UUID) and a unique, immutable `code` (snake_case, English). Seeded ids are `uuid5(REFERENCE_NAMESPACE, "<table>:<code>")`, the same mechanism already used for divisions. Admin-created brands and loss reasons get UUIDv7 ids and an admin-supplied or derived code.
- *Discarded*: integer ids — inconsistent with the rest of the schema; random UUIDs for seeds — ids would differ per environment and break fixtures/E2E.

### D3. Seed-only masters vs admin-editable masters

| Master | Seeded | Admin edit | Why |
|---|---|---|---|
| account_types | 6 | no | Drives defaults (tender flag); the set is stable; "simplicity wins" |
| activity_types | 6 | no | Icons and "counts as contact" are code-level semantics |
| brands | 13 own | create / rename / activate / divisions / competitor flag | New manufacturers and competitors appear over time |
| loss_reasons | 6 | create / rename / activate (flags fixed on seeded rows) | Management refines the list |
| pipelines | 2 | rename only | Structure is product design |
| pipeline_stages | 5 + 5 | rename, probability, reorder (within pipeline), activate | Probabilities tuned from experience |

Seed-only masters still have `is_active` so a future change can retire a value without a migration.
- *Discarded*: making everything editable with a generic admin — more screens, more ways to break code paths that depend on codes (`is_won`, `requires_brand`).

### D4. Data model

Common columns as in change 01 (`id`, `created_at`, `updated_at`; `version` on editable aggregates).

| Table | Columns | Constraints / indexes |
|---|---|---|
| `account_types` | `code text unique`, `name_es text`, `sort_order int`, `buys_via_tender bool`, `is_active bool` | — |
| `activity_types` | `code text unique`, `name_es text`, `sort_order int`, `icon text`, `counts_as_contact bool`, `is_active bool` | — |
| `brands` | `code text unique`, `name citext unique`, `is_own bool`, `is_active bool`, `version` | index `is_own`, `is_active` |
| `brand_divisions` | `brand_id FK brands CASCADE`, `division_id FK divisions RESTRICT` | PK `(brand_id, division_id)` |
| `loss_reasons` | `code text unique`, `name_es citext unique`, `sort_order int`, `requires_brand bool`, `requires_note bool`, `is_active bool`, `version` | — |
| `pipelines` | `code text unique` (`equipment`, `consumables`), `name_es citext unique`, `sort_order int`, `version` | — |
| `pipeline_divisions` | `pipeline_id FK CASCADE`, `division_id FK RESTRICT` | PK `(pipeline_id, division_id)`, **unique `division_id`** (one default pipeline per division) |
| `pipeline_stages` | `pipeline_id FK RESTRICT`, `code text`, `name_es text`, `sort_order int`, `probability smallint 0–100`, `is_won bool`, `is_lost bool`, `is_at_risk bool`, `is_active bool`, `version` | unique `(pipeline_id, code)`, unique `(pipeline_id, sort_order)` deferrable (reorder swaps), check `probability between 0 and 100`, check `not (is_won and is_lost)` |

Seed content (codes → Spanish names):
- account_types: `ivf_clinic` Clínica FIV / laboratorio, `public_hospital` Hospital público (`buys_via_tender`), `private_hospital` Hospital privado, `private_practice` Clínica o consulta privada, `podiatry_center` Centro de podología / pie diabético, `distributor` Distribuidor.
- activity_types: `visit` Visita, `call` Llamada, `email` Email, `demo` Demo, `training` Formación, `note` Nota (`counts_as_contact=false`); icons `map-pin`, `phone`, `mail`, `presentation`, `graduation-cap`, `sticky-note` (lucide names).
- brands (own): fertipro, hadeco, viasonix, siemens, comen, minitube, three_gen ("3Gen"), atys, uscom, northern_meditec, rimos, prodimed, huckerts. Division links are **not** seeded (the catalogue change will populate them from products; admins can set them meanwhile).
- loss_reasons: `price` Precio, `competitor` Competidor (`requires_brand`), `no_budget` Sin presupuesto, `project_cancelled` Proyecto cancelado, `timing` Plazos, `other` Otro (`requires_note`).
- pipelines: `equipment` Equipos (divisions: gynaecology, vascular, neurology, equipment, carts_and_arms), `consumables` Consumibles (divisions: assisted_reproduction, consumables).
- stages Equipos: `contact` Contacto 10, `demo` Demo 30, `quote` Presupuesto 50, `negotiation` Negociación/Licitación 70, `won` Ganada 100 (`is_won`), `lost` Perdida 0 (`is_lost`).
- stages Consumibles: `trial` Prueba 20, `first_order` Pedido inicial 60, `recurring` Recurrente 100 (`is_won`), `at_risk` En riesgo 100 (`is_at_risk`, open), `lost` Perdida 0 (`is_lost`).

Migration `0002_reference_data` creates the tables; the seed (`seed.py`) upserts rows by `code` (names/flags refreshed, admin-editable fields — `name`, `probability`, `sort_order`, `is_active` — preserved when the row already exists, see D6).

### D5. API contract

All under `/api/v1`; reads for every authenticated role; writes `admin` only; list endpoints for masters are **not paginated** (bounded lists, sorted by `sort_order`/`name`).

| Method & path | Roles | Notes |
|---|---|---|
| `GET /reference-data` | auth | `ReferenceDataRead{account_types[], activity_types[], divisions[], brands[], loss_reasons[], pipelines[{…, stages[]}]}`, active and inactive rows with `is_active` so historic records still resolve; `ETag` = hash of max `updated_at` |
| `GET /account-types`, `GET /activity-types` | auth | plain arrays |
| `GET /brands?is_own=&is_active=&q=` | auth | `BrandRead[]` (`division_ids[]`, `version`) |
| `POST /brands` | admin | `BrandCreate{name, is_own, division_ids[]}` → 201; `code` derived from name (slug) |
| `PATCH /brands/{id}` + `If-Match` | admin | `BrandUpdate{name?, is_own?, is_active?, division_ids?}` |
| `GET /loss-reasons` | auth | `LossReasonRead[]` |
| `POST /loss-reasons` | admin | `LossReasonCreate{name}` → 201 (`requires_*` false) |
| `PATCH /loss-reasons/{id}` + `If-Match` | admin | `LossReasonUpdate{name?, is_active?}` |
| `GET /pipelines` | auth | `PipelineRead[]` with ordered `stages[]` |
| `PATCH /pipelines/{id}` + `If-Match` | admin | `PipelineUpdate{name?}` |
| `PATCH /pipelines/{id}/stages/{stage_id}` + `If-Match` (stage version) | admin | `StageUpdate{name?, probability?, is_active?}` |
| `PUT /pipelines/{id}/stages/order` + `If-Match` (pipeline version) | admin | `StageOrder{stage_ids[]}` — must contain every stage of the pipeline exactly once; bumps pipeline version |

Error codes introduced: `brand_name_already_exists` (409), `loss_reason_name_already_exists` (409), `pipeline_name_already_exists` (409), `stage_order_invalid` (422, missing/extra/duplicated ids), `stage_probability_invalid` (422), `stage_flag_immutable` (400, attempt to change `is_won/is_lost/is_at_risk`), `last_active_stage` (400, deactivating would leave a pipeline without an open stage), `unknown_reference` (422, division ids — reused).

Audit events: `brand.created`, `brand.updated`, `brand.activated`, `brand.deactivated`, `loss_reason.created`, `loss_reason.updated`, `pipeline.updated`, `pipeline_stage.updated`, `pipeline_stages.reordered`.

### D6. Seed strategy for editable masters

`seed.py` upserts by `code` but only fills admin-editable columns on **insert** (`ON CONFLICT DO UPDATE` limited to non-editable semantic flags). Running the seed in production therefore never overwrites a renamed brand or a tuned probability.
- *Discarded*: full overwrite on every run — would undo admin changes on each deploy; skip-if-exists — could not fix a wrong semantic flag centrally.

### D7. Domain layout

`app/domain/reference/` with entities `Brand`, `LossReason`, `Pipeline` (aggregate root owning `PipelineStage`s: reorder, rename stage, set probability, deactivate stage with the "at least one open stage" invariant), value-free read models for account/activity types. Repositories: `BrandRepository`, `LossReasonRepository`, `PipelineRepository` (loads stages), plus `ReferenceQueries` for the bundle. Services: `BrandService`, `LossReasonService`, `PipelineService`. Unit of work gains the three repositories.
- *Discarded*: treating stages as their own aggregate — reorder and the "one open stage" rule are pipeline-level invariants.

### D8. Frontend

- `features/reference`: `useReferenceData()` (single query, `staleTime` 5 min, `gcTime` 30 min) and derived selectors `useAccountTypes()`, `useActivityTypes()`, `useBrands()`, `useLossReasons()`, `usePipelines()`, `useDivisions()` reading from the bundle; helpers `labelOf(list, id)`. Admin mutations invalidate `referenceKeys.all` so every consumer refreshes.
  - *Discarded*: one query per master everywhere — six requests on each screen that needs a dropdown; the bundle is a few KB.
- `features/admin/brands`, `features/admin/loss-reasons`, `features/admin/pipelines` following the users/territories structure (`api.ts`, `queries.ts`, `pages/*ListPage.tsx`, `pages/*FormRoute.tsx`, `components/*Form.tsx`).
- Admin hub cards: Usuarios, Territorios, Marcas, Motivos de pérdida, Pipelines (2-column grid on ≥ `sm`).
- Pipeline screen: one page listing both pipelines; each pipeline is a card with its stages in order. Reorder uses "subir/bajar" buttons (touch-friendly, keyboard accessible) rather than drag and drop; editing a stage opens the shared sheet/dialog form (nombre, probabilidad, activo). Won/lost/at-risk flags are shown as badges, not editable.
  - *Discarded*: dnd-kit here — it arrives with the opportunity kanban (change 06); buttons are simpler and accessible.

Mobile layout (first):

```
┌──────────────────────────┐
│ ◀  Pipelines             │
├──────────────────────────┤
│ Equipos                  │
│ ┌──────────────────────┐ │
│ │ 1 Contacto      10 % │ │  ← stage row: order, name, probability,
│ │   [▲] [▼]  [Editar]  │ │     badge (Ganada/Perdida/En riesgo/Inactiva)
│ ├──────────────────────┤ │
│ │ 2 Demo          30 % │ │
│ │ …                    │ │
│ └──────────────────────┘ │
│ Consumibles              │
│ …                        │
├──────────────────────────┤
│  Hoy   Más   Admin       │
└──────────────────────────┘
```

Desktop: the two pipeline cards side by side (`lg:grid-cols-2`), same rows, buttons inline. Brands and loss reasons reuse `DataList` (name, own/competitor badge, divisions, Inactivo) with the search box for brands.

### D9. Testing

- Backend unit: `Pipeline` invariants (reorder validation, last open stage, immutable flags, probability range), slug derivation for brand codes, seed upsert policy (fake repo).
- Backend integration: migration round-trip (existing test), seed idempotency for the new tables including "admin rename survives re-seed", every endpoint × status codes, authorization (admin vs others) added to the matrix test, bundle ETag.
- Frontend: reference hooks with MSW (single request shared by selectors, invalidation after mutation), each admin list/form, pipeline reorder buttons and disabled states.
- E2E (desktop + mobile): admin renames a brand, creates a competitor brand, reorders two stages and edits a probability; sales rep cannot open the admin pages; axe on each page.

## Risks / Trade-offs

- **Bundle staleness (5 min)**: a rep may see a renamed brand up to 5 minutes late; acceptable for reference data, and the admin's own session invalidates immediately.
- **`pipeline_divisions` unique per division** forces exactly one default pipeline per division; later changes still let a user pick the other pipeline for an opportunity.
- **Codes derived from brand names** (`slugify`) can collide (e.g. "3Gen" vs "3-Gen"); the unique constraint reports `brand_name_already_exists` and the admin adjusts the name — no separate code field in the UI (zero useless fields).
- **Deferrable unique on stage order** requires PostgreSQL-specific DDL; consistent with the rest of the schema (citext, enums).
- Brand ↔ division links stay empty until the catalogue change; screens must render brands without divisions gracefully.

### Implementation notes (recorded during /opsx:apply)

- The `GET /pipelines/{id}` read endpoint was added (not in D5) because the admin screen and the reorder flow need a single pipeline with its fresh version after a mutation.
- Loading placeholders (`DataList`, pipelines page) carry `role="status"`: axe flagged `aria-label` on a generic `div` (`aria-prohibited-attr`) during the E2E run.
- On desktop `DataList` renders table rows, not buttons; E2E specs select rows by text so they work for both layouts.
- "Pipeline" is treated as product vocabulary (it appears in the briefing and the navigation), so the i18n jargon test no longer rejects it.
