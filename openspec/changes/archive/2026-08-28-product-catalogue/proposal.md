## Why

Opportunities and quotes (changes 06 and 07) are lines of products with prices: without a catalogue every quote starts from a blank line typed by hand, prices drift between reps and nothing can be aggregated by division or brand. Quermed already keeps its articles in Sage; the CRM needs the same articles, identified by the Sage code, with the few attributes selling needs — brand, family, kind, list price — so a rep can build a quote in seconds on the phone and management can read the pipeline by product line.

Constitution principles served: zero useless fields (name, SKU, brand, family, kind, price — nothing else mandatory), smart defaults (family fixes the division, kind picks the pipeline), one screen one purpose (a searchable catalogue and a product form), business vocabulary (Producto, Familia, Marca, Equipo, Consumible, Servicio — never "item" or "SKU" in the UI: "Código Sage"), i18n-ready, audit of every change.

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- **Product families**: admin-editable master `product_families` (`name`, `division`, `sort_order`, `is_active`), seeded with a starter list per division (e.g. Ecógrafos, Dopplers, Medios de cultivo, Micromanipulación, Electrodos, Carros); a family belongs to exactly one division so every product inherits its division.
- **Products**: `sku` (Sage article code, mandatory, unique, immutable once used), `name`, `brand` (own or competitor, from change 02), `family`, `kind` (`equipment` | `consumable` | `service`), `list_price` (EUR, ex VAT, ≥ 0), optional `cost_price` (visible to `sales_manager`/`admin` only), `unit` (ud, caja, kit…), `description`, `is_active`, `version`. Competitor products are allowed (brand `is_own = false`) so lost deals and installed base can name them.
- **Catalogue API**: paginated, searchable list (`q` on name/SKU, filters by division, family, brand, kind, own/competitor, active), detail, create/update for `admin` and `back_office`, activate/deactivate (never delete), families CRUD for `admin`. Cost price stripped from responses for reps and back office.
- **Catalogue screens**: "Catálogo" reachable from "Más" for every role (read) with search, division/brand/kind filters and product cards (name, brand badge, family, kind icon, price); product form (admin/back office) with SKU, name, brand, family, kind, price, unit, description, cost (managers/admins); "Familias" admin screen reusing the loss-reasons pattern; the account's "Marcas en uso" picker now also shows the products of the brand as a hint (no data change).
- **Reference bundle**: families join `GET /reference-data` (small, stable list); products do **not** (they are paginated and searched on demand).
- **Import readiness**: SKU uniqueness, upsert-by-SKU semantics and a `ProductImportRow` schema are defined now so change 08 imports the Sage export without touching the model.

## Non-goals

- Live synchronisation with Sage, stock, warehouses or supplier data.
- Multiple price lists, currency conversion, VAT rates per product (quotes apply VAT in change 07).
- Product variants, bundles/kits, serial-number tracking (equipment on loan arrives with the "Equipos" feature after the MVP).
- Images or attachments.
- CSV import UI (change 08) — only the import contract is fixed here.

## Roles and territory visibility

| Role | Catalogue |
|---|---|
| `sales_rep` | Read active products and families; never sees `cost_price`. |
| `sales_manager` | Read everything incl. `cost_price` and inactive products; no writes. |
| `back_office` | Create and edit products (incl. prices), activate/deactivate; sees `cost_price`? **No** — cost is management information. |
| `admin` | Everything, plus families master. |

The catalogue is global: no territory or division scoping applies (a rep may quote any product; division filters are convenience, not security).

## Capabilities

### New Capabilities
- `product-model`: families and products tables, invariants (SKU normalisation and uniqueness, price rules, kind), seed of starter families, migration and indexes.
- `product-api`: catalogue list/detail/create/update/activate endpoints with role-based field visibility, families endpoints, import row contract.
- `product-screens`: catalogue list with search and filters, product form, families admin screen, navigation entry under "Más".

### Modified Capabilities
- `reference-data-api`: the bundle gains `product_families[]`.
- `reference-data-admin-screens`: the cache exposes `useProductFamilies()`; the admin hub gains "Familias".
- `audit-log`: events `product.*` and `product_family.*`.

## Impact

- New tables: `product_families`, `products`. Migration `0005_product_catalogue`; seed extended with families.
- New API: `/api/v1/products` (list, create), `/products/{id}` (read, patch), `/product-families` (list, create, patch); `reference-data` bundle extended.
- Frontend: `features/catalogue` (list, form, families admin), navigation in "Más", i18n namespace `catalogue`.
- Documentation: `api-spec.yml`, `data-model.md`, `development_guide.md` (families seed, price visibility).
- No new dependencies.
