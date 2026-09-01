# product-api (delta)

Creating a product family reuses an existing one of the same division instead of answering 409.

## MODIFIED Requirements

### Requirement: Product family endpoints
`GET /api/v1/product-families` (any role, ordered by division then `sort_order`), `POST /api/v1/product-families` and `PATCH /api/v1/product-families/{id}` (admin only, `If-Match`) SHALL exist. `PATCH` SHALL accept `name`, `sort_order`, `is_active`; `division_id` and `code` SHALL be immutable. Deactivating a family SHALL NOT deactivate its products. A `POST` matching an existing family **of the same division** (by `code` or by unaccented name) SHALL reuse that family — reactivating it when inactive — and answer 201 with an `outcome` of `created`, `reused` or `reactivated`. Family `code` is unique across the whole catalogue, so the same name under a **different** division SHALL keep answering 409 `product_family_exists`: handing back another division's family would silently file products under the wrong division.

#### Scenario: Admin creates a family
- **WHEN** an admin posts `{ name: "Láser", division_id }`
- **THEN** the response is 201 with a generated `code = "laser"`, `outcome = "created"` and the family appears in the bundle

#### Scenario: Same family name in the same division
- **WHEN** the name resolves to the code of a family that already exists in that division
- **THEN** the response is 201 with that family and `outcome = "reused"`, and no duplicate is created

#### Scenario: Same family name in another division
- **WHEN** the name matches a family that exists in a different division
- **THEN** the response is 409 `product_family_exists`, because a family code is unique catalogue-wide and reusing the other division's family would misfile every product added to it

#### Scenario: Back office cannot edit families
- **WHEN** back office patches a family
- **THEN** the response is 403 `forbidden`

#### Scenario: Division immutable
- **WHEN** an admin patches `division_id`
- **THEN** the response is 422 `validation_error`
