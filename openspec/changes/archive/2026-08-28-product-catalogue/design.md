## Context

Change 02 delivered brands (`brands`, own/competitor, `brand_divisions`), divisions and one default pipeline per division; change 03/04 established the domain layout (aggregate + repository Protocol + in-memory fake + service with audit), `Page[T]` pagination, `If-Match` locking, trigram search and the admin master-data screens (`features/admin/{brands,loss-reasons,pipelines,job-titles}`). Quermed's article master lives in Sage; its article code is the only stable identifier shared by the ERP, invoices and the reps' vocabulary.

Confirmed product inputs: brand → family → product structure; `kind` = equipment | consumable | service; one list price plus an optional cost; manual creation now, CSV import in change 08 with the Sage code as the unique reference.

Constraints: quote lines (change 07) must resolve a product in one query; the catalogue list must answer under 500 ms for a few thousand articles; cost is management-only information; every mutation audited; no delete.

## Goals / Non-Goals

**Goals:**
- Two small aggregates (`ProductFamily`, `Product`) whose invariants make the future import idempotent.
- A catalogue read model fast enough to be the product picker of the quote form on a phone.
- Role-based field visibility (`cost_price`) enforced in one place on the backend.
- Reuse the reference/admin patterns so families cost one screen and products one form.

**Non-Goals:**
- Sage synchronisation, stock, multiple price lists, VAT per product, variants/kits, serial numbers, images, import UI (see proposal).

## Decisions

### D1. Family is the hinge between product and division; brand stays orthogonal

`product_families.division_id` is mandatory; a product has exactly one family, so `product.division` is derived (`family.division_id`) and never stored twice. Brand is a separate mandatory FK: the same brand (e.g. a competitor) can sell in several divisions, which `brand_divisions` already models. The service validates on create/update that the brand is linked to the family's division **only as a warning-free rule** — no error: the brand/division links are a filter hint, not a business invariant (a brand's first product in a new division would otherwise require an admin round trip).
- *Discarded*: `division_id` on `products` — two sources of truth that the import would have to reconcile row by row.
- *Discarded*: family as a plain text tag — no division inheritance, no admin control, typos multiply across an import.
- *Discarded*: product enforcing `brand ∈ family.division` — rejected because `brand_divisions` is incomplete today ("empty until the catalogue change"); instead, creating a product **adds the link** `brand_divisions(brand, family.division)` if missing, so the brand filter stays consistent for free.

### D2. `sku` is the Sage code: normalised, unique, immutable once referenced

`Product.normalise_sku` = trim, uppercase, collapse internal whitespace; stored as `text` with a unique index on the normalised value (`uq_products_sku`). The SKU can be edited while no quote line references the product (a typo at manual entry); once referenced (checked by the service through a `ProductRepository.is_referenced(id)` hook that returns `False` until change 07 implements it) the PATCH returns `product_sku_locked` (409). Duplicate on create → `product_sku_exists` (409) with `extensions.existing_product_id`, the same shape the accounts duplicate uses.
- *Discarded*: SKU as the primary key — quotes and audits would be tied to an ERP code that Sage can renumber; UUIDv7 stays the identity.
- *Discarded*: case-sensitive SKU — Sage exports mix cases; two "HAD-1000"/"had-1000" rows would be a certain import bug.

### D3. `kind` enum with three values, semantic hooks only where needed now

`products_kind_enum` (`equipment`, `consumable`, `service`). In this change `kind` drives only the list icon, the filter and the import validation. Later changes attach behaviour: change 06 uses the **family's division** to pick the default pipeline (pipelines are per division, per change 02 — not per kind), and the post-MVP equipment feature uses `kind = equipment` for serial numbers and demo/loan. Recorded here so the proposal's "kind picks the pipeline" is read correctly: kind narrows the pipeline *type* (tender vs. direct is decided by the account type, division by the family), it does not own a pipeline.
- *Discarded*: `kind` on the family — a family like "Ecógrafos" also holds consumables (gel, fundas) and services (mantenimiento).
- *Discarded*: boolean flags (`is_equipment`, `is_service`) — mutually exclusive states as flags invite impossible combinations.

### D4. Prices: `numeric(12,2)` EUR ex VAT, cost optional and stripped by role in the API layer

`list_price numeric(12,2) NOT NULL CHECK ≥ 0`, `cost_price numeric(12,2) NULL CHECK ≥ 0`, `currency` fixed `EUR` (no column — documented; a column arrives with multi-currency if ever). Prices travel as JSON strings with two decimals in the API (`Decimal` in Pydantic, `"1250.00"`) so JavaScript never rounds them. `ProductRead` is the full model; `ProductPublicRead` omits `cost_price`; the router picks the schema via `can_view_cost(user)` (`sales_manager`, `admin`). Writes of `cost_price` by `back_office` are accepted (they type what Sage says) but never echoed back to them.
- *Discarded*: `cost_price` as `null` for non-viewers — a rep cannot distinguish "no cost recorded" from "hidden"; omitting the field is the honest contract and the OpenAPI types stay exact.
- *Discarded*: float columns / numbers in JSON — `0.1 + 0.2` in a quote total is not something the finance team forgives.
- *Discarded*: margin computed here — belongs to the quote line (discounts) in change 07.

### D5. Data model

| Table | Columns | Constraints / indexes |
|---|---|---|
| `product_families` | `id`, `code text` (slug, unique, immutable, generated from name on manual create), `name citext`, `division_id FK divisions RESTRICT`, `sort_order int`, `is_active bool`, `version`, `created_at`, `updated_at` | `uq_product_families_name_division (name, division_id)`; index `division_id` |
| `products` | `id`, `sku text` (normalised), `name text`, `brand_id FK brands RESTRICT`, `family_id FK product_families RESTRICT`, `kind products_kind_enum`, `list_price numeric(12,2)`, `cost_price numeric(12,2) null`, `unit text` (default `ud`, ≤ 20), `description text null` (≤ 2000), `is_active bool`, `created_by FK users`, `version`, `created_at`, `updated_at` | `uq_products_sku (sku)`; `ix_products_name_trgm gin (name gin_trgm_ops)`, `ix_products_sku_trgm gin (sku gin_trgm_ops)`; `ix_products_family_id`, `ix_products_brand_id`, `ix_products_kind`, `ix_products_is_active`; checks `list_price >= 0`, `cost_price IS NULL OR cost_price >= 0`, `length(name) BETWEEN 1 AND 200` |

Migration `0005_product_catalogue`; seed `PRODUCT_FAMILIES` with deterministic ids via `reference_id("product_families", code)` per division (Fertilidad: `medios-cultivo`, `micromanipulacion`, `incubadoras`, `consumibles-fiv`; Cardiología: `ecografos`, `dopplers`, `electrodos`, `holter`; Hospitalario: `carros`, `mobiliario`, `monitorizacion`, `servicios`). The seed is idempotent (`ON CONFLICT (id) DO NOTHING`, as job titles). No products are seeded (real data arrives via import; the E2E seed creates its own).
- *Discarded*: `families` as rows of a generic `reference_items` table — every master so far has its own table with typed columns; consistency wins.
- *Discarded*: a `brand_id` on families — Quermed families cut across brands (two ultrasound brands in "Ecógrafos").

### D6. Catalogue read model

`GET /products?q=&division_id=&family_id=&brand_id=&kind=&own=&is_active=&sort=&page=&page_size=` → `Page[ProductSummaryRead | ProductSummaryPublicRead]` with `id, sku, name, brand{id,name,is_own}, family{id,name,division_id}, kind, list_price, (cost_price), unit, is_active, version`. `q` matches `sku ILIKE q%` **or** trigram on `name`/`sku` (prefix match on SKU first so typing "HAD-10" lists the Hadeco range instantly); default sort `name`, also `sku`, `list_price`, `updated_at`. `is_active` defaults to `true` for reps and back office (the picker never offers retired products); managers/admins may pass `is_active=false` or `all`. Page size cap 100. Detail `GET /products/{id}` returns the same shape plus `description`, `created_at`, `updated_at`.
- *Discarded*: nested family/brand *ids only* — the list would need the reference bundle for names and the picker in change 07 would render ids before hydration.
- *Discarded*: including products in `GET /reference-data` — thousands of rows in the bundle every session; families (≈ 15 rows) do go in.

### D7. Families through the reference module, products through a new catalogue module

Families are master data: `app/domain/reference/entities.py` gains `ProductFamily` (like `LossReason`: `rename`, `deactivate`, `reactivate`, `set_sort_order`), `ReferenceRepository` gains its methods, `GET/POST/PATCH /product-families` follow `/loss-reasons` (admin writes, everyone reads), the bundle gains `product_families[]` and the frontend cache exposes `useProductFamilies()`. Products are a business aggregate: `app/domain/catalogue/{entities.py (Product, ProductKind, normalise_sku), errors.py, repository.py}`, `app/application/catalogue/{commands.py, service.py (ProductService: create, update, activate, deactivate; audit product.created/updated/activated/deactivated), queries.py (ProductQueries)}`, `app/api/v1/products.py`. `ensure_catalogue_writer(user)` allows `admin` and `back_office`.
- *Discarded*: both in `reference` — products have search, pagination, prices and role-based fields; the reference module is a small-list cache by design.
- *Discarded*: both in `catalogue` — families would need their own bundle plumbing and admin screen pattern instead of reusing the four that exist.

### D8. Import contract fixed now, executed in change 08

`app/schemas/catalogue.py` defines `ProductImportRow { sku, name, brand_code | brand_name, family_code, kind, list_price, cost_price?, unit?, description?, is_active? }` and `ProductService.upsert_by_sku(row, actor)`: SKU present → update the mutable fields (never the SKU), absent → create; returns `created | updated | unchanged`. Unit-tested here with the in-memory repository so change 08 only adds CSV parsing, validation report and the screen. `brand_name` resolution is case-insensitive on `brands.name` (citext).
- *Discarded*: designing the import when it is built — the SKU normalisation, the "unchanged" detection and the audit shape are exactly the things that break when retrofitted.

### D9. Frontend

Routes: `/catalogo` (list), `/catalogo/nuevo` and `/catalogo/:id` (form in `ResponsiveFormContainer`; read-only view for roles without write), `/admin/familias`.

Feature `features/catalogue/{api,queries,schemas,hooks (useCanEditCatalogue, useCanViewCost),components/{ProductCard,ProductFilters,ProductForm,KindIcon,PriceText},pages/{CatalogueListPage,ProductFormRoute},routes.tsx,index.ts}`; `features/admin/product-families/*` copies the `loss-reasons` structure (list, form with division select). Query keys `productKeys` (`list(filters)`, `detail(id)`); mutations invalidate `productKeys.lists()` and the detail. Navigation: "Catálogo" in "Más" for every role; "Familias" in the admin hub. i18n namespace `catalogue` (`Catálogo`, `Producto`, `Código Sage`, `Marca`, `Familia`, `Tipo`, `Equipo`, `Consumible`, `Servicio`, `Precio de lista`, `Coste`, `Unidad`, `Activo`).

Catalogue (mobile):

```
┌──────────────────────────┐
│ Catálogo             [+] │  ← [+] only admin / back office
│ 🔍 Nombre o código Sage  │
│ [Fertilidad][Cardio][Hosp]│ ← division chips; Marca / Tipo in "Filtros"
├──────────────────────────┤
│ 🖥 Ecógrafo Vinno E10    │
│   Vinno · Ecógrafos      │
│   HAD-1000     12.500,00 €│
│ 🧴 Gel ultrasonidos 5 l  │
│   Genérico · Consumibles │
│   GEL-5L          18,50 €│
│ …                        │
├──────────────────────────┤
│  Hoy  Centros  Más       │
└──────────────────────────┘
```

Product form (one column, six fields above the fold): Código Sage · Nombre · Marca (select, own first) · Familia (select grouped by division) · Tipo (segmented Equipo/Consumible/Servicio) · Precio de lista; collapsed "Más datos": Unidad, Descripción, Coste (only when `useCanViewCost`), Activo. Prices are entered with the browser's numeric keypad (`inputMode="decimal"`) and displayed with `Intl.NumberFormat('es-ES', {currency: 'EUR'})`.
- *Discarded*: a data grid with inline editing on desktop — the catalogue is read far more than written; one form keeps the audit trail explicit.
- *Discarded*: product detail as a full page — nothing to show beyond the form fields; the sheet keeps the list scroll position.

### D10. Testing

- Backend unit: SKU normalisation and uniqueness, price checks, family/division derivation, brand-division link creation, `upsert_by_sku` outcomes, cost visibility predicate, family lifecycle.
- Backend integration: migration round trip and seed idempotence; `/products` filters, search (prefix vs trigram), sort, pagination and the `is_active` default per role; `cost_price` present/absent by role (incl. back office write-but-not-read); 409 duplicate and `sku_locked`; families endpoints and the bundle; audit events; `If-Match` on both.
- Frontend: list renders cards and filters, search debounce and empty state, form defaults (`unit = ud`, no default `kind`: the segmented control requires one deliberate tap) and payload, cost field hidden for reps/back office, price formatting, families admin CRUD.
- E2E (desktop + mobile, axe): admin creates a family, back office creates a product, rep searches it by SKU prefix and sees no cost; manager sees the cost.

## Risks / Trade-offs

- **[Cost leaks through list sorting]** → `sort=cost_price` is only accepted for cost viewers; otherwise 422.
- **[SKU edited after quotes exist]** → `is_referenced` hook + `product_sku_locked`; change 07 implements the hook the day quote lines exist.
- **[Import rows with unknown brand/family]** → the contract returns row-level errors (`brand_not_found`, `family_not_found`) rather than auto-creating masters; auto-creation of families is an explicit option of change 08.
- **[Trigram index on `sku` with short codes]** → prefix `ILIKE` runs first on the unique b-tree; trigram only for `len(q) ≥ 3`.
- **[Seeded family list wrong for Quermed]** → families are editable and deactivatable; the seed is a starting point, not a constraint.

## Migration Plan

1. Migration `0005_product_catalogue` (two tables, enum, indexes) + seed families; no backfill.
2. Deploy backend and frontend together (additive: new endpoints, bundle gains `product_families`).
3. Rollback: `alembic downgrade 0004_activities` drops tables and enum; the bundle field disappears with the backend.

## Open Questions

- None blocking. The starter family list per division is a guess to be corrected by the admin after import; confirmed unit codes (`ud`, `caja`, `kit`, `h`) can be extended freely since `unit` is free text.

### Implementation notes (recorded during /opsx:apply)

- Starter families follow the real seeded divisions (Reproducción asistida, Fungibles, Ginecología, Vascular, Neurología, Equipos, Carros y brazos soporte): sixteen families with underscore codes (`medios_cultivo`, `dopplers`…), the same slug convention as every other master, instead of the hyphenated examples in D5.
- Families live in the reference module as `ProductFamilyRepository` / `ProductFamilyService` (own repository, like loss reasons) rather than extra methods on a single reference repository; `ensure_division` sits on `BrandRepository`.
- `ProductQueries` builds the catalogue read model with joined brand/family rows in one statement; the list response is `Page[ProductSummaryRead] | Page[ProductSummaryPublicRead]` chosen by `can_view_cost(user)` so the OpenAPI document carries both variants. `ProductImportRow` is not consumed by any endpoint yet, so the OpenAPI exporter adds it explicitly as a documented-only schema.
- `is_active` on `GET /products` is a `true | false | all` query value (not a bare boolean) so the 403 for reps and back office is explicit; the catalogue uses its own page dependency (default 25, cap 100).
- Frontend price parsing accepts Spanish input ("12.500,50", "13.000") and API strings alike; `KindIcon` only adds its screen-reader label outside the form's segmented control, where the visible text already names the kind (a duplicated label broke the E2E label click).
- The E2E spec searches by the full Sage code: the desktop and mobile projects share the time-based prefix of `uniqueSuffix()`, so a prefix search leaked the other project's still-active product. Seed tests that edit rows outside the test transaction now restore them (`test_product_families_seed`, `test_job_titles_seed`) so a persistent local database stays valid across runs.
