# territory-scope

## Purpose
Territories (provinces), divisions seed, user scope assignment and the visibility rule applied to business records.

## Requirements

### Requirement: Territories
The system SHALL store territories with `id`, `name` (unique), a set of Spanish province codes (INE two-digit codes, each province in at most one territory), `is_active`, `version`, timestamps.

Required fields and justification: `name` (label on account cards and reports), `provinces` (resolve an account's province → territory automatically, the smart default for account assignment).

#### Scenario: Province belongs to one territory
- **WHEN** an admin creates or updates a territory including province `28` while another territory already contains `28`
- **THEN** the response is 409 with code `province_already_assigned` naming the conflicting territory

#### Scenario: Invalid province code
- **WHEN** a province code is not one of the 52 INE codes (`01`–`52`)
- **THEN** the response is 422 with a field error and code `invalid_province`

### Requirement: Territory administration
`POST /api/v1/territories`, `PATCH /api/v1/territories/{id}` (optimistic locking) SHALL be allowed for `admin` only. `GET /api/v1/territories` and `GET /api/v1/territories/{id}` SHALL be readable by `admin`, `sales_manager`, `back_office`; `sales_rep` receives 403 (they see their own via `/me`).

List: pagination as the API foundation; sort by `name` (default); filters `is_active`, `q` (prefix on name).

#### Scenario: Admin creates territory
- **WHEN** an admin posts `{ "name": "Centro", "provinces": ["28", "45", "19"] }`
- **THEN** the response is 201 with `TerritoryRead` and an audit event `territory.created`

#### Scenario: Deactivate territory with assigned users
- **WHEN** an admin sets `is_active: false` on a territory that still has active users assigned
- **THEN** the response is 400 with code `territory_in_use` listing the user count

### Requirement: Divisions seed
The system SHALL seed the seven product divisions as reference data: `assisted_reproduction`, `consumables`, `gynaecology`, `vascular`, `neurology`, `equipment`, `carts_and_arms`, each with a Spanish display name, and expose them at `GET /api/v1/divisions` (readable by every authenticated role, not paginated, sorted by `sort_order`).

#### Scenario: Idempotent seed
- **WHEN** `make seed` runs twice
- **THEN** exactly seven divisions exist with unchanged ids

#### Scenario: Divisions listed
- **WHEN** any authenticated user calls `GET /api/v1/divisions`
- **THEN** the response is 200 with the seven divisions in `sort_order`

### Requirement: User scope assignment
A user SHALL have zero or more territories and zero or more divisions. Assignments SHALL be set through `POST/PATCH /api/v1/users` (`territory_ids`, `division_ids`) and SHALL be audited.

#### Scenario: Assignment change is audited
- **WHEN** an admin changes a user's territories from `[A]` to `[A, B]`
- **THEN** an audit event `user.scope_changed` records `territory_ids` before and after

#### Scenario: Sales rep without scope
- **WHEN** a `sales_rep` has no territories or no divisions
- **THEN** `GET /api/v1/me` returns empty lists and the frontend shows a warning "Sin territorio o división asignados; contacta con administración"

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
