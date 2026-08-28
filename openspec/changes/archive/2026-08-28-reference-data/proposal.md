## Why

Accounts, activities, opportunities and the catalogue (changes 03–06) all classify records against the same small vocabularies: account types, activity types, brands, loss reasons and the two sales pipelines with their stages. Defining them once, seeded with Quermed's real values and maintainable by an administrator, avoids re-touching three later changes and keeps every dropdown short and meaningful ("zero useless fields", "business vocabulary").

Constitution principles served: zero useless fields (fixed, short lists with a real use in a flow or report), smart defaults (default pipeline per division, default stage per pipeline), business vocabulary (Centro, Visita, Demo, Licitación), one screen one purpose (one plain admin list per master), audit (every master change is audited).

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- **Account types** (reference data, seeded): Clínica FIV / laboratorio, Hospital público, Hospital privado, Clínica o consulta privada, Centro de podología / pie diabético, Distribuidor. A flag marks types that buy through public tenders (Hospital público) so later changes can default the pipeline stage "Negociación/Licitación".
- **Activity types** (seeded): Visita, Llamada, Email, Demo, Formación, Nota. Each carries an icon key and whether it counts as a customer contact (Nota does not) for future activity reports.
- **Brands**: the 13 represented manufacturers seeded as own brands (Fertipro, Hadeco, Viasonix, Siemens, Comen, Minitube, 3Gen, Atys, Uscom, Northern Meditec, Rimos, Prodimed, Huckerts). Each brand has an own/competitor flag and the divisions it belongs to. Administrators can create, rename, deactivate and re-link brands; competitor brands are created by administrators when needed (used by loss reasons and by "brands already in use at the account").
- **Loss reasons** (seeded, admin-editable): Precio, Competidor, Sin presupuesto, Proyecto cancelado, Plazos, Otro. "Competidor" is flagged as requiring a brand; "Otro" as requiring a free-text note.
- **Pipelines and stages** (seeded, admin-editable order/probability/names, structure fixed):
  - Equipos: Contacto (10 %) → Demo (30 %) → Presupuesto (50 %) → Negociación/Licitación (70 %) → Ganada (100 %, won) / Perdida (0 %, lost).
  - Consumibles: Prueba (20 %) → Pedido inicial (60 %) → Recurrente (100 %, won) → En riesgo (open, flagged "at risk") / Perdida (0 %, lost).
  - Each pipeline declares which divisions use it by default (Equipos for equipment divisions, Consumibles for Reproducción asistida and Fungibles); stages carry `sort_order`, `probability`, `is_won`, `is_lost`, `is_at_risk`.
- **Read API for every role**: one lightweight endpoint per master plus a combined `GET /api/v1/reference-data` bundle the frontend loads once per session and caches (staleTime 5 min), so later screens never wait for six requests.
- **Admin API and screens** for brands, loss reasons and pipeline stages (rename, reorder, probability, activate/deactivate) following the users/territories conventions: `version` + `If-Match`, audit events, problem+json codes. Account types and activity types are read-only in the MVP (seed only) because their set is stable and drives code paths.
- **Admin hub** gains three entries: "Marcas", "Motivos de pérdida", "Pipelines".

## Non-goals

- Accounts, contacts, activities, opportunities, products, quotes (changes 03–07) — they only reference these masters.
- Free-form "custom fields" or per-user lists (constitution: no configurable custom fields).
- Adding or removing pipelines and stages structurally (won/lost semantics, at-risk flag) from the UI; the MVP ships exactly the two pipelines, admins can rename, reorder and tune probabilities.
- Editing account types and activity types from the UI (seed-only in this change).
- Deleting any master value: deactivation only, because historical records reference them.
- Importing masters from Excel (the import change handles accounts/contacts; masters are seeded).

## Roles and territory visibility

| Role | Access in this change |
|---|---|
| `admin` | Read everything; create/edit/deactivate brands, loss reasons, pipeline stages. |
| `sales_manager`, `back_office`, `sales_rep` | Read everything (masters are global, not territory-scoped). |

Reference data is not subject to territory scope: every authenticated user reads the same lists. Territory visibility keeps applying to the business records (accounts, opportunities) that reference them in later changes.

## Capabilities

### New Capabilities
- `reference-data-model`: tables, invariants and idempotent seed for account types, activity types, brands, loss reasons, pipelines and stages.
- `reference-data-api`: read endpoints for every role (per master and combined bundle) and admin write endpoints for brands, loss reasons and stages with optimistic locking and audit.
- `reference-data-admin-screens`: admin lists and forms for brands, loss reasons and pipeline stages, plus the frontend reference-data cache used by later screens.

### Modified Capabilities
- `admin-screens`: the admin hub shows three additional entries (Marcas, Motivos de pérdida, Pipelines).
- `audit-log`: new audited actions `brand.*`, `loss_reason.*`, `pipeline_stage.*`.

## Impact

- New tables: `account_types`, `activity_types`, `brands`, `brand_divisions`, `loss_reasons`, `pipelines`, `pipeline_divisions`, `pipeline_stages`. Migration `0002_reference_data`; seed extended (idempotent, stable ids).
- New API surface: `GET /api/v1/reference-data`, `GET /api/v1/account-types`, `GET /api/v1/activity-types`, `GET /api/v1/brands` (+ `POST`, `PATCH /{id}`), `GET /api/v1/loss-reasons` (+ `POST`, `PATCH /{id}`), `GET /api/v1/pipelines` (with stages) (+ `PATCH /pipelines/{id}/stages/{stage_id}`, `PUT /pipelines/{id}/stages/order`).
- Frontend: `features/admin/brands`, `features/admin/loss-reasons`, `features/admin/pipelines`, `features/reference` (cached bundle hooks), admin hub and i18n `admin`/`reference` namespaces.
- Documentation: `api-spec.yml`, `data-model.md`, `development_guide.md` (seed contents).
- No new dependencies.
