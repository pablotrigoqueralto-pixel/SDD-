## Why

Nothing exists yet: no backend, no frontend, no CI, no way to log in. Every MVP capability (accounts, activities, pipeline, quotes) depends on knowing *who* the user is, *what role* they have and *which territories and divisions* they cover, and on every mutation being auditable. This change lays that foundation once so that the following changes only add business capabilities.

Constitution principles served: security (robust auth, RBAC + ownership, secrets outside code, rate limiting), audit (immutable change log), operations (containers, versioned migrations, CI blocking merges), mobile-first (app shell designed for the phone first), business vocabulary and Spanish UI.

scope:
  backend: true
  frontend: true
design-linked: false

## What Changes

- **Repository scaffolding** for the monorepo: `backend/` (FastAPI, SQLAlchemy 2 async, Alembic, pytest, ruff, mypy) and `frontend/` (React 18, TypeScript, Vite, Tailwind, shadcn/ui, TanStack Query, Zustand, React Router, i18next, Vitest, Playwright), wired to the existing `docker-compose.yml`, Dockerfiles and pre-commit config.
- **Continuous integration** with GitHub Actions: lint, type-check, unit and integration tests, migration round-trip and OpenAPI drift check for backend; lint, type-check, unit tests, build and E2E for frontend. Failures block merge.
- **Authentication**: email + password login, short-lived access JWT, rotating refresh token in an HttpOnly cookie, logout, password change, account lockout after repeated failures, rate limiting on auth endpoints. Auth sits behind a provider abstraction so Microsoft Entra ID (OIDC) can be added later without API changes.
- **Users and roles**: `sales_rep`, `sales_manager`, `back_office`, `admin`. Admin can create, deactivate and edit users, assign role, territories and divisions.
- **Territories and divisions as access scope**: territories are geographic groups of Spanish provinces; divisions are the seven product divisions. A user's *scope* = assigned territories × assigned divisions. This change stores and exposes the scope; later changes use it to filter accounts and opportunities. Division reference data (the seven divisions) is seeded here because scope needs it; all other reference data comes in the next change.
- **Audit log** foundation: append-only `audit_log` table, unit-of-work hook that records every mutation with actor, entity, action and field diff; first audited entities are users, territories and user assignments.
- **API foundation**: `/api/v1` prefix, RFC 7807 error format, pagination envelope, `version` + `If-Match` optimistic locking, `/health` and `/health/ready`, OpenAPI export to `ai-specs/specs/api-spec.yml`.
- **Frontend app shell**: login screen, authenticated layout with mobile bottom navigation and desktop sidebar, session handling with silent refresh, role-aware routing, Spanish `es-ES` translation bundle, design tokens, offline banner, conflict dialog for `409`.
- **Admin screens**: user list and user form (role, territories, divisions, active flag); territory list and form.

## Non-goals

- Accounts, contacts, activities, pipelines, catalogue, quotes, dashboards (later changes).
- SSO / OIDC login itself (only the abstraction that allows it).
- Password reset by email (requires the email infrastructure of the quotes change; admins reset passwords manually in the MVP).
- Self-registration: users are created by an admin only.
- Reference data other than divisions (account types, activity types, brands, pipelines, stages → change 02).
- Row-level filtering of business entities by scope (defined here, applied when those entities exist).
- Production infrastructure (staging/prod, backups, alerting → change 10).

## Roles and territory visibility

| Role | Access in this change |
|---|---|
| `admin` | Manage users, territories, assignments; see the audit log. |
| `sales_manager` | Read users and territories (needed for team views later); no write. |
| `sales_rep` | Read own profile and own scope (territories + divisions); nothing else. |
| `back_office` | Read own profile; read users and territories. |

Territory visibility rule established for all later changes: a `sales_rep` sees a business record when they own it **or** the record's territory is in their territories **and** the record's division (when it has one) is in their divisions. `sales_manager`, `back_office` and `admin` see all records; `back_office` cannot move opportunities (enforced in the pipeline change).

## Capabilities

### New Capabilities
- `project-scaffolding`: monorepo layout, tooling, local Docker stack, CI pipelines and quality gates for backend and frontend.
- `authentication`: login, token refresh, logout, password change, lockout and rate limiting, provider abstraction for future SSO.
- `user-management`: users, roles, activation, admin CRUD, self profile.
- `territory-scope`: territories (provinces), divisions seed, user ↔ territory/division assignment and scope resolution.
- `audit-log`: append-only audit trail recorded from the unit of work, with admin read access.
- `api-foundation`: versioned API conventions — error format, pagination, optimistic locking, health endpoints, OpenAPI export.
- `app-shell`: frontend shell — login page, authenticated layout (mobile bottom nav / desktop sidebar), session store and silent refresh, role-aware routing, i18n bundle, offline banner, conflict dialog.
- `admin-screens`: user and territory management screens for admins.

### Modified Capabilities
(none — greenfield)

## Impact

- New directories: `backend/`, `frontend/`, `.github/workflows/`.
- New tables: `users`, `refresh_tokens`, `territories`, `territory_provinces`, `divisions`, `user_territories`, `user_divisions`, `audit_log`.
- New API surface: `/api/v1/auth/*`, `/api/v1/users/*`, `/api/v1/me`, `/api/v1/territories/*`, `/api/v1/divisions`, `/api/v1/audit-log`, `/health`, `/health/ready`.
- Documentation to create/update: `ai-specs/specs/api-spec.yml`, `ai-specs/specs/data-model.md`, `ai-specs/specs/development_guide.md`, root `README.md` startup section.
- Dependencies introduced: FastAPI, SQLAlchemy, asyncpg, Alembic, Pydantic v2, pwdlib[argon2], PyJWT, slowapi, structlog, pytest stack; React 18, Vite, Tailwind, shadcn/ui, TanStack Query, Zustand, React Router, react-hook-form, zod, i18next, Axios, Vitest, MSW, Playwright.
