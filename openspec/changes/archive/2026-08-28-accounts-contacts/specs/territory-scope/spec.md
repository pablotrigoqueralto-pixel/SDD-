## MODIFIED Requirements

### Requirement: Scope resolution service
The backend SHALL expose a domain service `resolve_scope(user) -> Scope` returning the user's territory ids, province codes and division ids, and a `VisibilityPolicy.can_read(user, record)` / `can_write(user, record)` protocol applied to business records exposing `owner_id`, `territory_id` and `division_ids` (a set; empty means "no division restriction"): `admin`, `sales_manager` and `back_office` see all records; a `sales_rep` sees a record when they own it, or when the record's territory is in their territories and the record's `division_ids` is empty or intersects their divisions. The same rule SHALL be available as a SQL predicate (`ScopeFilter`) applied by repositories to list and detail queries, and a test SHALL assert the policy and the predicate agree on a fixture matrix. The account is the scoped record; contacts inherit their account's scope.

#### Scenario: Rep sees a record in territory and division
- **WHEN** a `sales_rep` with territory `Centro` and division `vascular` evaluates a record in territory `Centro` with divisions `{vascular, neurology}` owned by someone else
- **THEN** `can_read` is true

#### Scenario: Rep excluded by division
- **WHEN** the same rep evaluates a record in `Centro` with divisions `{neurology}`
- **THEN** `can_read` is false

#### Scenario: Record without divisions
- **WHEN** the same rep evaluates a record in `Centro` with no divisions of interest
- **THEN** `can_read` is true

#### Scenario: Rep sees owned record outside scope
- **WHEN** the same rep evaluates a record they own in territory `Norte`
- **THEN** `can_read` is true

#### Scenario: Manager sees everything
- **WHEN** a `sales_manager` evaluates any record
- **THEN** `can_read` and `can_write` are true

#### Scenario: Policy and SQL agree
- **WHEN** the fixture matrix of accounts (owned / in territory / other divisions / other territory / unassigned) is evaluated by `VisibilityPolicy` and by the repository list with `ScopeFilter`
- **THEN** both return the same set of visible ids for each user of the matrix
