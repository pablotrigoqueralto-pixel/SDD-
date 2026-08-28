## ADDED Requirements

### Requirement: Catalogue audit events
The following events SHALL be recorded in the same transaction as the mutation: `product.created` (field snapshot, `cost_price` included), `product.updated` (field diffs), `product.activated`, `product.deactivated`, `product_family.created`, `product_family.updated`. Import upserts SHALL reuse `product.created` / `product.updated` and SHALL record nothing for `unchanged` rows.

#### Scenario: Price change audited
- **WHEN** back office changes `list_price` from 100.00 to 120.00
- **THEN** one `product.updated` row exists with `changes.list_price = { before: "100.00", after: "120.00" }`

#### Scenario: Cost visible in the audit log
- **WHEN** an admin reads the audit row of a product created with a cost
- **THEN** the snapshot includes `cost_price`
