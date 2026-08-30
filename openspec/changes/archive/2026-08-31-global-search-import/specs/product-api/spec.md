## ADDED Requirements

### Requirement: Product import endpoint
The documented-only import contract SHALL become live: `POST /api/v1/products/import` implements the dry-run/confirm flow of `import-api` over `ProductImportRow` and `ProductService.upsert_by_sku`, keeping the change-05 semantics — rows match existing products by normalised SKU, never change the code, and report `created` / `updated` / `unchanged` per row.

#### Scenario: Contract behaviour preserved
- **WHEN** a file row carries an existing SKU with a changed list price
- **THEN** the product is updated through the same validation and audit path as a manual `PATCH`, and the report marks the row `updated`
