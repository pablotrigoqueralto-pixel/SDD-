## MODIFIED Requirements

### Requirement: Account list
`GET /api/v1/accounts` SHALL return the paginated envelope of `AccountSummaryRead { id, name, account_type_id, city, province_code, territory_id, territory_name, owner_id, owner_name, is_active, territory_mismatch, primary_contact_name, last_contact_at, next_activity_at, updated_at }` with filters `q` (case-insensitive contains on `name`, `city`; exact normalised match on `tax_id`), `account_type_id`, `territory_id`, `owner_id`, `division_id`, `is_active` (default `true`), `unassigned` (owner null), sorting `sort=name|city|updated_at|last_contact_at` (`-` prefix for descending, default `name`; nulls last), `page` and `page_size` (max 100). Visibility: `admin`, `sales_manager`, `back_office` see all; a `sales_rep` sees accounts they own or whose `territory_id` is in their territories and whose divisions of interest are empty or intersect their divisions. `AccountRead` SHALL carry the same two timestamps. Response time SHALL stay under 500 ms with 50 000 accounts.

#### Scenario: Rep list is scoped
- **WHEN** a rep of territory `Centro` / division `vascular` lists accounts and the database has an account in `Centro` with divisions `{vascular}`, one in `Centro` with `{neurology}`, one in `Norte` owned by the rep and one in `Norte` owned by someone else
- **THEN** the list contains exactly the first and the third accounts

#### Scenario: Search by tax id
- **WHEN** `q = "b-12345678"` is sent and an account has `tax_id = "B12345678"`
- **THEN** that account is returned

#### Scenario: Unassigned filter for managers
- **WHEN** a manager lists with `unassigned=true`
- **THEN** only accounts with `owner_id = null` are returned

#### Scenario: Sort by last contact
- **WHEN** `sort=last_contact_at` is requested and one account was never contacted
- **THEN** contacted accounts come first (oldest contact first) and the never-contacted account last
