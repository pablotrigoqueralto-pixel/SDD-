## 1. Backend domain

- [x] 1.1 [BE] Write failing unit tests for `ProductFamily` in `domain/reference/entities.py` (`create` with slug `code` from name, `rename`, `set_sort_order`, `deactivate`/`reactivate`, `division_id` immutable) and error `product_family_exists`; implement
- [x] 1.2 [BE] Write failing unit tests for `normalise_sku` (trim, upper-case, collapse whitespace) and the `Product` aggregate in `domain/catalogue/entities.py` (`create` with `unit = "ud"` default, `ProductKind`, `price_invalid` for negative list/cost price, `name` 1–200, `unit` ≤ 20, `description` ≤ 2000, `update`, `change_sku(referenced)` → `product_sku_locked`, `activate`/`deactivate` idempotent); implement `domain/catalogue/{entities,errors}.py`
- [x] 1.3 [BE] Define `ProductRepository` Protocol (`get`, `get_by_sku`, `add`, `save` with version, `is_referenced` returning `False`) and `ReferenceRepository` methods for families (`list_product_families`, `get_product_family`, `get_product_family_by_name`, `add_product_family`, `save_product_family`, `ensure_brand_division(brand_id, division_id)`); extend `UnitOfWork` and the in-memory fakes

## 2. Backend data model and migration

- [x] 2.1 [BE] ORM models `ProductFamilyModel` and `ProductModel` per design D5 (enum `products_kind_enum`, `numeric(12,2)` prices, checks, unique `sku`, trigram GIN indexes on `name`/`sku`, b-tree indexes)
- [x] 2.2 [BE] Write migration `0005_product_catalogue` (hand-reviewed, `crm_app` grants); integration test round-trip `upgrade → downgrade 0004_activities → upgrade` and `alembic check`
- [x] 2.3 [BE] Add `PRODUCT_FAMILIES` seed (12 starter families across Fertilidad / Cardiología / Hospitalario with `reference_id("product_families", code)`) and `seed_product_families` (`ON CONFLICT DO NOTHING`); integration test: seed twice preserves an admin rename

## 3. Backend repositories and queries

- [x] 3.1 [TEST]+[BE] Integration tests and implementation for `SqlAlchemyProductRepository` (add/get/get_by_sku normalised/save with conflict, `is_referenced` stub) and family methods on the SQL reference repository incl. `ensure_brand_division`
- [x] 3.2 [TEST]+[BE] `ProductQueries.list_page(filters, params, can_view_cost)` with `q` (SKU prefix `ILIKE` first, trigram on `name`/`sku` when `len(q) ≥ 3`, prefix matches ranked first), filters `division_id` (through family), `family_id`, `brand_id`, `kind`, `own`, `is_active`, sorts (`cost_price` only for cost viewers), embedded `brand`/`family`; plan test proving `ix_products_name_trgm` is used with `enable_seqscan = off`
- [x] 3.3 [TEST]+[BE] Reference bundle: `product_families[]` ordered by division then `sort_order`, ETag includes families' `updated_at`; `GET /product-families` ordering

## 4. Backend services and API

- [x] 4.1 [BE] Write failing unit tests for `ProductService.create/update` (`ensure_catalogue_writer`: admin and back office only → `forbidden`; duplicate SKU → `product_sku_exists` with `existing_product_id`; `brand_not_found` / `family_not_found`; `ensure_brand_division` called with the family's division; `cost_price` accepted from back office; audit `product.created` snapshot incl. cost and `product.updated` diffs); implement `application/catalogue/{commands,service}.py`
- [x] 4.2 [BE] Write failing unit tests for `ProductService.activate/deactivate` (idempotent, audit `product.activated`/`product.deactivated`) and `upsert_by_sku(ProductImportRow)` (`created` / `updated` / `unchanged` with no audit and no version bump; brand by `brand_code` or case-insensitive `brand_name`; family by `family_code`; SKU never changed); implement with `schemas/catalogue.py::ProductImportRow`
- [x] 4.3 [BE] Write failing unit tests for `ReferenceService` family commands (`create_product_family` with slug and `product_family_exists`, `update_product_family` name/sort_order/is_active only, audit `product_family.created/updated`); implement
- [x] 4.4 [BE] Write failing API tests for `GET /products` (all roles; filters, search ranking, sort, pagination cap 100; `is_active` default and 403 for rep/back office passing `false|all`; 422 for `sort=cost_price` as rep) and `GET /products/{id}` (404, retired readable); implement `schemas/catalogue.py` (`ProductSummaryRead`, `ProductRead`, `ProductPublicRead` variants with `Decimal` prices serialised as two-decimal strings) and router `api/v1/products.py` picking the schema with `can_view_cost(user)`
- [x] 4.5 [BE] Write failing API tests for `POST /products`, `PATCH /products/{id}` (403 rep/manager, 201 defaults, 409 `product_sku_exists` + extension, 409 `product_sku_locked`, 428/409 locking, `cost_price` stored but omitted for back office and present for manager), `POST /products/{id}/activate|deactivate`; implement
- [x] 4.6 [BE] Write failing API tests for `GET/POST/PATCH /product-families` (admin only writes, 403 back office, 422 on `division_id` patch, 409 duplicate name in division, bundle gains the family with a new ETag); implement in `api/v1/reference.py`; register error codes in the problem-details catalogue

## 5. Frontend foundation

- [x] 5.1 [FE] Regenerate `src/api/schema.d.ts` (`npm run api:types`); add `productKeys` to `query-keys.ts`; add `catalogue` i18n namespace (`Catálogo`, `Producto`, `Código Sage`, `Marca`, `Familia`, `Tipo`, `Equipo`/`Consumible`/`Servicio`, `Precio de lista`, `Coste`, `Unidad`, `Descripción`, `Activo`, validation keys) and error codes `product_sku_exists`, `product_sku_locked`, `product_family_exists`, `price_invalid`
- [x] 5.2 [FE]+[TEST] `features/reference`: `useProductFamilies()` selector from the bundle and bundle invalidation on family mutations; MSW reference fixtures gain `product_families`; test "families from the bundle without extra request"
- [x] 5.3 [FE]+[TEST] `features/catalogue/{api,queries,schemas,hooks}`: list/detail/create/update/activate/deactivate calls with `ifMatch`, `useProducts(filters)` with `placeholderData`, mutations (`meta.silent`, invalidate lists and detail), `useCanEditCatalogue` (admin, back office), `useCanViewCost` (manager, admin); zod schema with `parsePrice("1.250,50") → "1250.50"` and `formatPrice`; unit tests for the price helpers and the schema; MSW handlers `catalogue.ts` + `catalogue-fixtures.ts`

## 6. Frontend catalogue screens

- [x] 6.1 [FE]+[TEST] `CatalogueListPage` at `/catalogo`: `PageHeader` with "Nuevo producto" (writers only), search box (debounced 300 ms), division chips, `ProductFilters` (brand own-first, kind, state for managers/admins) persisted in the URL query string, `ProductCard` (`KindIcon`, name, brand, family, SKU, `PriceText`), `DataList` pagination, `EmptyState`; tests: search request, filter persistence, no create action for rep
- [x] 6.2 [FE]+[TEST] `ProductForm` + `ProductFormRoute` at `/catalogo/nuevo` and `/catalogo/:id` in `ResponsiveFormContainer`: six fields above the fold (Código Sage, Nombre, Marca, Familia grouped by division, Tipo radio group, Precio de lista `inputMode="decimal"`), collapsed "Más datos" (Unidad default `ud`, Descripción, Coste only for cost viewers, Activo on edit); `If-Match` + `ConflictDialog` on 409 `conflict`; inline SKU duplicate message with link to the existing product; read-only mode for roles without write rights; tests: minimal create payload, duplicate inline link, cost hidden for back office, manager read-only, 409 conflict opens dialog
- [x] 6.3 [FE] Register routes in `app/routes.ts` / `router.tsx` (lazy), add "Catálogo" to the "Más" screen for every role, export `features/catalogue/index.ts`
- [x] 6.4 [FE]+[TEST] `features/admin/product-families` following `loss-reasons` (list grouped by division, create/edit form with division locked on edit, sort order, active); route `/admin/familias` and admin hub entry; tests: create shows under its division and invalidates the bundle

## 7. Documentation

- [x] 7.1 Update `ai-specs/specs/api-spec.yml` (`/products`, `/products/{id}`, `/products/{id}/activate`, `/products/{id}/deactivate`, `/product-families`, `/product-families/{id}`, `ProductRead`/`ProductPublicRead`/`ProductSummaryRead`/`ProductCreate`/`ProductUpdate`/`ProductFamilyRead`/`ProductImportRow`, bundle `product_families`, new error codes)
- [x] 7.2 Update `ai-specs/specs/data-model.md` (`product_families`, `products`, ER diagram, indexes, price and SKU principles) and `development_guide.md` (families seed, cost visibility rule, import contract, catalogue routes)

## 8. Quality gates and E2E

- [x] 8.1 [TEST] Backend gates: `ruff`, `mypy --strict`, full pytest (unit + integration) green, coverage not below the current threshold
- [x] 8.2 [TEST] Frontend gates: `eslint`, `prettier --check`, `tsc -p tsconfig.app.json`, vitest green
- [x] 8.3 [E2E] Extend `e2e/fixtures/app.ts` (`createProductFamily`, `createProduct`) and write `e2e/catalogue.spec.ts` (desktop + mobile, axe on list and form): admin creates a family → back office creates a product with a cost → rep searches by SKU prefix, opens it and sees no cost and no create action → manager opens it and sees the cost; deactivated product disappears from the rep's list
- [x] 8.4 [E2E] Run the compose smoke procedure (`AUTH_RATE_LIMIT=1000/minute`, `up -d --build`, e2e seed, `npx playwright test`, `down`) and record implementation deviations in `design.md` "Implementation notes"
