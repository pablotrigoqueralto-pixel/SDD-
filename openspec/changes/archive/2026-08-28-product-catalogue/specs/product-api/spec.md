## ADDED Requirements

### Requirement: Catalogue list
`GET /api/v1/products` SHALL return a paginated `Page[ProductSummaryRead]` (page size default 25, max 100) for any authenticated role, with filters `q`, `division_id`, `family_id`, `brand_id`, `kind`, `own` (true = own brands, false = competitors), `is_active` and `sort` (`name` default, `sku`, `list_price`, `updated_at`, `cost_price` only for cost viewers). `q` SHALL match a SKU prefix case-insensitively, and, when `q` has three or more characters, additionally match `name` and `sku` by trigram similarity, SKU prefix matches ranked first. Each item SHALL embed `brand { id, name, is_own }` and `family { id, name, division_id }`. The catalogue SHALL be global: no territory or division scoping applies.

#### Scenario: Prefix search
- **WHEN** a rep calls `GET /products?q=had-10`
- **THEN** products whose SKU starts with "HAD-10" are listed first, followed by trigram matches on name

#### Scenario: Filter by division
- **WHEN** `division_id` = Cardiología
- **THEN** only products whose family belongs to Cardiología are returned

#### Scenario: Sort by cost as a rep
- **WHEN** a `sales_rep` requests `sort=cost_price`
- **THEN** the response is 422 `validation_error`

#### Scenario: Under 500 ms
- **WHEN** the list is requested with a name search on 5 000 products
- **THEN** the response time is under 500 ms

### Requirement: Inactive products hidden by default
`is_active` SHALL default to `true` for `sales_rep` and `back_office`; `sales_manager` and `admin` MAY pass `is_active=false` or `is_active=all`. A `sales_rep` or `back_office` passing `is_active=false|all` SHALL receive 403 `forbidden`.

#### Scenario: Rep default
- **WHEN** a rep lists products without `is_active`
- **THEN** retired products are absent

#### Scenario: Manager sees retired
- **WHEN** a manager lists with `is_active=all`
- **THEN** active and retired products are returned with their `is_active` flag

### Requirement: Product detail
`GET /api/v1/products/{id}` SHALL return `ProductRead` (summary fields plus `description`, `created_at`, `updated_at`) for any authenticated role; unknown ids SHALL return 404 `not_found`. Retired products SHALL still be readable by id by every role (quotes and history resolve them).

#### Scenario: Retired product by id
- **WHEN** a rep opens a retired product by id
- **THEN** the response is 200 with `is_active = false`

### Requirement: Cost price visibility
`cost_price` SHALL appear in list and detail responses only for `sales_manager` and `admin`; for other roles the field SHALL be omitted (not `null`). `admin` and `back_office` MAY send `cost_price` on create and update; for `back_office` the write is stored and the response omits the field. The OpenAPI document SHALL describe both response variants (`ProductRead` and `ProductPublicRead`).

#### Scenario: Rep never sees cost
- **WHEN** a rep reads a product that has `cost_price = 800.00`
- **THEN** the JSON body has no `cost_price` key

#### Scenario: Back office writes cost
- **WHEN** back office creates a product with `cost_price = 800.00`
- **THEN** the row stores 800.00 and the 201 response has no `cost_price` key; a manager reading it sees `"800.00"`

### Requirement: Product create and update
`POST /api/v1/products` (201) and `PATCH /api/v1/products/{id}` (200, requires `If-Match`) SHALL be allowed for `admin` and `back_office` only; other roles receive 403 `forbidden`. Prices SHALL be JSON strings with two decimals in requests and responses. `PATCH` SHALL accept any subset of `sku`, `name`, `brand_id`, `family_id`, `kind`, `list_price`, `cost_price`, `unit`, `description`. Duplicate SKU SHALL return 409 `product_sku_exists` with `extensions.existing_product_id`; a stale `If-Match` SHALL return 409 `conflict`; a missing `If-Match` SHALL return 428.

#### Scenario: Create with minimum fields
- **WHEN** back office posts `{ sku, name, brand_id, family_id, kind, list_price }`
- **THEN** the response is 201 with `unit = "ud"`, `is_active = true`, `version = 1`

#### Scenario: Rep cannot create
- **WHEN** a rep posts a product
- **THEN** the response is 403 `forbidden`

#### Scenario: Stale version
- **WHEN** a PATCH carries `If-Match: "1"` and the product is at version 2
- **THEN** the response is 409 `conflict`

### Requirement: Activate and deactivate
`POST /api/v1/products/{id}/deactivate` and `POST /api/v1/products/{id}/activate` (require `If-Match`) SHALL toggle `is_active` for `admin` and `back_office`; deactivating an already inactive product SHALL be idempotent (200, version unchanged). There SHALL be no `DELETE` endpoint.

#### Scenario: Retire a product
- **WHEN** back office deactivates an active product
- **THEN** the response is 200 with `is_active = false` and the product disappears from the rep's default list

### Requirement: Product family endpoints
`GET /api/v1/product-families` (any role, ordered by division then `sort_order`), `POST /api/v1/product-families` and `PATCH /api/v1/product-families/{id}` (admin only, `If-Match`) SHALL exist. `PATCH` SHALL accept `name`, `sort_order`, `is_active`; `division_id` and `code` SHALL be immutable. Deactivating a family SHALL NOT deactivate its products.

#### Scenario: Admin creates a family
- **WHEN** an admin posts `{ name: "Láser", division_id }`
- **THEN** the response is 201 with a generated `code = "laser"` and the family appears in the bundle

#### Scenario: Back office cannot edit families
- **WHEN** back office patches a family
- **THEN** the response is 403 `forbidden`

#### Scenario: Division immutable
- **WHEN** an admin patches `division_id`
- **THEN** the response is 422 `validation_error`

### Requirement: Catalogue OpenAPI and errors
All endpoints SHALL be documented in `ai-specs/specs/api-spec.yml` with RFC 7807 problem responses and the error codes `product_sku_exists`, `product_sku_locked`, `product_family_exists`, `price_invalid`, `brand_not_found`, `family_not_found`.

#### Scenario: Schema types regenerated
- **WHEN** `npm run api:types` runs against the backend OpenAPI
- **THEN** `ProductRead`, `ProductPublicRead`, `ProductCreate`, `ProductUpdate`, `ProductFamilyRead` and `ProductImportRow` are generated
