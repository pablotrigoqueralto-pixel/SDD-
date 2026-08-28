## ADDED Requirements

### Requirement: Product family master
The system SHALL persist product families in `product_families` with `id`, `code` (unique slug, immutable), `name` (case-insensitive, unique within its division), `division_id` (mandatory FK to `divisions`, `ON DELETE RESTRICT`), `sort_order`, `is_active`, `version`, `created_at`, `updated_at`. A family SHALL belong to exactly one division; a product's division SHALL be derived from its family and never stored on the product. Families SHALL never be deleted; retirement is `is_active = false`.

#### Scenario: Family name unique within a division
- **WHEN** an admin creates a family "Ecógrafos" in Cardiología while "ecógrafos" already exists in that division
- **THEN** creation is rejected with `product_family_exists` (409)

#### Scenario: Same name in two divisions
- **WHEN** an admin creates "Consumibles" in Fertilidad and "Consumibles" in Hospitalario
- **THEN** both rows exist with different codes

#### Scenario: Division cannot be deleted while families exist
- **WHEN** a division row referenced by a family is deleted at the database level
- **THEN** the database rejects the delete

### Requirement: Starter families seed
The seed SHALL insert an initial family list per division with deterministic ids (`reference_id("product_families", code)`) and SHALL be idempotent (`ON CONFLICT (id) DO NOTHING`), so admin edits made after the first run are preserved.

#### Scenario: Seed twice
- **WHEN** the seed runs on a database where an admin renamed "Dopplers" to "Doppler vascular"
- **THEN** the rename is preserved and no duplicate rows are created

### Requirement: Product entity
The system SHALL persist products in `products` with `id` (UUIDv7), `sku` (Sage article code: text, normalised, unique), `name` (1–200 chars), `brand_id` (FK `brands` RESTRICT), `family_id` (FK `product_families` RESTRICT), `kind` (`equipment` | `consumable` | `service`), `list_price` (`numeric(12,2)`, ≥ 0, EUR ex VAT), `cost_price` (`numeric(12,2)`, nullable, ≥ 0), `unit` (text ≤ 20, default `ud`), `description` (nullable, ≤ 2000), `is_active`, `created_by`, `version`, `created_at`, `updated_at`. Products SHALL never be deleted. Competitor brands SHALL be accepted as `brand_id`.

#### Scenario: Negative price rejected
- **WHEN** a product is created with `list_price = -1`
- **THEN** the domain rejects it with `price_invalid` (422)

#### Scenario: Cost optional
- **WHEN** a product is created without `cost_price`
- **THEN** the row is stored with `cost_price = NULL`

#### Scenario: Competitor product
- **WHEN** a product is created with a brand whose `is_own = false`
- **THEN** it is stored and listed like any other product

### Requirement: SKU normalisation and uniqueness
`sku` SHALL be normalised before persistence: trimmed, upper-cased, internal whitespace collapsed to a single space. Two products SHALL NOT share a normalised SKU (`uq_products_sku`). The SKU SHALL be editable only while no other record references the product; the repository SHALL expose `is_referenced(product_id)` (returns `false` until quotes exist) and the aggregate SHALL reject a SKU change on a referenced product with `product_sku_locked` (409).

#### Scenario: Case-insensitive duplicate
- **WHEN** "HAD-1000" exists and a product is created with sku " had-1000 "
- **THEN** creation is rejected with `product_sku_exists` (409) and `extensions.existing_product_id`

#### Scenario: Typo corrected before use
- **WHEN** an unreferenced product's SKU is changed from "HAD-100O" to "HAD-1000"
- **THEN** the change is stored normalised

#### Scenario: SKU locked once referenced
- **WHEN** `is_referenced` returns `true` for a product and its SKU is changed
- **THEN** the change is rejected with `product_sku_locked` (409)

### Requirement: Brand-division link kept consistent
When a product is created or moved to a family, the service SHALL ensure `brand_divisions` contains `(brand_id, family.division_id)`, inserting the link when missing, so the brand appears under that division's filters.

#### Scenario: First product of a brand in a division
- **WHEN** a Vinno product is created in the family "Ecógrafos" (Cardiología) and Vinno has no division links
- **THEN** after the create, `brand_divisions` contains (Vinno, Cardiología)

### Requirement: Product indexes
The `products` table SHALL have a unique b-tree index on `sku`, trigram GIN indexes on `name` and `sku`, and b-tree indexes on `family_id`, `brand_id`, `kind` and `is_active`; `product_families` SHALL have an index on `division_id`.

#### Scenario: Name search uses the trigram index
- **WHEN** `EXPLAIN` runs the catalogue name search on a table with more than 1 000 rows and sequential scans disabled
- **THEN** the plan uses `ix_products_name_trgm`

### Requirement: Import contract
The domain SHALL expose `ProductService.upsert_by_sku(row, actor)` accepting a `ProductImportRow` (`sku`, `name`, `brand_code` or `brand_name`, `family_code`, `kind`, `list_price`, optional `cost_price`, `unit`, `description`, `is_active`) and returning `created`, `updated` or `unchanged`. An existing SKU SHALL update every mutable field except the SKU; unknown brand or family SHALL fail the row with `brand_not_found` / `family_not_found` without creating masters.

#### Scenario: Row unchanged
- **WHEN** a row identical to the stored product is upserted
- **THEN** the result is `unchanged`, `version` does not increase and no audit event is recorded

#### Scenario: Row updates price
- **WHEN** a row with the same SKU and a new `list_price` is upserted
- **THEN** the result is `updated`, the price is stored and `product.updated` is audited

#### Scenario: Unknown family
- **WHEN** a row references `family_code = "laser"` which does not exist
- **THEN** the row fails with `family_not_found` and nothing is written
