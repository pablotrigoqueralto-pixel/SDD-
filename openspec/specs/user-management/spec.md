# user-management

## Purpose
Users, roles, activation, admin CRUD and self profile.

## Requirements

### Requirement: User entity
The system SHALL store users with `id`, `email` (unique, case-insensitive), `full_name`, `role` (`sales_rep | sales_manager | back_office | admin`), `is_active`, `version`, `created_at`, `updated_at`, and the optional SSO columns `identity_provider`, `external_id`.

Required fields and justification: `email` (login and notification identity), `full_name` (shown as "Comercial" on records and reports), `role` (drives authorization).

#### Scenario: Email uniqueness is case-insensitive
- **WHEN** an admin creates a user with `Ana@Quermed.com` and another with `ana@quermed.com`
- **THEN** the second request returns 409 with code `email_already_exists`

### Requirement: Admin creates users
`POST /api/v1/users` SHALL allow an `admin` to create a user with an initial password, role, territories and divisions.

#### Scenario: Successful creation
- **WHEN** an admin posts a valid `UserCreate` (`email`, `full_name`, `role`, `password`, `territory_ids[]`, `division_ids[]`)
- **THEN** the response is 201 with `UserRead` (never including password data) and an audit event `user.created` is recorded

#### Scenario: Non-admin creates a user
- **WHEN** a `sales_manager`, `back_office` or `sales_rep` posts to `/api/v1/users`
- **THEN** the response is 403 with code `forbidden`

#### Scenario: Unknown territory or division
- **WHEN** `territory_ids` or `division_ids` contains an id that does not exist
- **THEN** the response is 422 with a field error and code `unknown_reference`

### Requirement: Admin updates users
`PATCH /api/v1/users/{user_id}` SHALL allow an `admin` to change `full_name`, `role`, `is_active`, `territory_ids`, `division_ids`, and to set a new password (`password`), using optimistic locking.

#### Scenario: Update with matching version
- **WHEN** an admin patches a user with `If-Match: "<current version>"`
- **THEN** the response is 200 with the updated `UserRead`, `version` incremented, and an audit event `user.updated` listing changed fields (password change recorded as `user.password_reset` without values)

#### Scenario: Stale version
- **WHEN** the `If-Match` value differs from the stored version
- **THEN** the response is 409 with code `conflict`

#### Scenario: Admin deactivates themselves
- **WHEN** an admin sets `is_active: false` on their own user, or changes their own role away from `admin`
- **THEN** the response is 400 with code `cannot_demote_self`

#### Scenario: Deactivation ends sessions
- **WHEN** a user is deactivated
- **THEN** all their refresh tokens are revoked and their existing access tokens are rejected at the next request

### Requirement: List and read users
`GET /api/v1/users` SHALL return a paginated list; `GET /api/v1/users/{user_id}` SHALL return one user.

Visibility per role: `admin`, `sales_manager`, `back_office` read all users; `sales_rep` receives 403 on both endpoints.
Pagination: `page` (default 1), `page_size` (default 50, max 200). Sorting: `sort` over `full_name`, `email`, `role`, `created_at` (default `full_name`). Filters: `role`, `is_active`, `territory_id`, `q` (prefix match on `full_name` or `email`).

#### Scenario: Manager lists users
- **WHEN** a `sales_manager` calls `GET /api/v1/users?role=sales_rep&is_active=true`
- **THEN** the response is 200 with `{ items, total, page, page_size }` containing only active sales reps, each with their territories and divisions

#### Scenario: Sales rep lists users
- **WHEN** a `sales_rep` calls `GET /api/v1/users`
- **THEN** the response is 403 with code `forbidden`

### Requirement: Self profile
`GET /api/v1/me` SHALL return the authenticated user with their resolved scope (territories with provinces, divisions). `PATCH /api/v1/me` SHALL allow changing only `full_name`.

#### Scenario: Read own profile
- **WHEN** any authenticated user calls `GET /api/v1/me`
- **THEN** the response is 200 with `MeRead` including `role`, `territories[]`, `divisions[]`

#### Scenario: Attempt to change own role
- **WHEN** a user patches `/api/v1/me` with `role`
- **THEN** the response is 422 because `role` is not an accepted field
