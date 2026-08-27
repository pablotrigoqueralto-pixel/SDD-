## 1. Backend scaffolding

- [x] 1.1 [BE] Create `backend/pyproject.toml` (FastAPI, SQLAlchemy[asyncio], asyncpg, Alembic, pydantic-settings, pwdlib[argon2], PyJWT, slowapi, structlog, uvicorn, gunicorn; dev: pytest, pytest-asyncio, httpx, testcontainers[postgres], factory_boy, ruff, mypy) with ruff/mypy/pytest/coverage config, `uv.lock`, `Makefile`, `.env.example`
- [x] 1.2 [BE] Create package skeleton `app/{api,application,domain,infrastructure,schemas}` per backend-standards and `app/infrastructure/settings.py` (pydantic-settings, fail-fast on missing `DATABASE_URL`, `JWT_SECRET` ≥ 32 bytes, `CORS_ORIGINS`); test: settings raise on missing/short secret
- [x] 1.3 [BE] Write failing test for `GET /health` and `GET /health/ready` (200 / 503 when DB down), then implement `app/main.py` app factory with health router, CORS from settings, security headers middleware
- [x] 1.4 [BE] Write failing tests for `RequestContext` middleware (trace id from `X-Request-ID`, generated otherwise, echoed in response) and structured request log without personal data; implement `infrastructure/logging.py` + middleware
- [x] 1.5 [BE] Write failing tests for problem+json mapping (DomainError subclasses → status/code, RequestValidationError → 422 with `errors[]`, unhandled → 500 with trace id and no stack); implement `domain/shared/errors.py` and exception handlers
- [x] 1.6 [BE] Write failing tests for `PageParams`/`Page[T]` parsing (defaults, `page_size` > 200 → 422, `sort` validation → `invalid_sort_field`); implement `application/shared/pagination.py`
- [x] 1.7 [BE] Create async engine/session (`infrastructure/db/session.py`), `Base` with common columns mixin (`id` UUIDv7, `created_at`, `updated_at`, `version`), Alembic `env.py` (async), `alembic.ini` with timestamped `file_template`

## 2. Backend data model and migration

- [x] 2.1 [BE] Define ORM models `users`, `refresh_tokens`, `territories`, `territory_provinces`, `divisions`, `user_territories`, `user_divisions`, `audit_log` with enums, indexes and constraints from design D5
- [x] 2.2 [BE] Generate and hand-review migration `0001_foundation` (citext extension, enums, tables, unique province constraint, province check, guarded `GRANT INSERT, SELECT ON audit_log TO crm_app`), implement `downgrade`
- [x] 2.3 [TEST] Integration test: `alembic upgrade head` → `downgrade base` → `upgrade head` on empty DB, then `alembic check` is clean
- [x] 2.4 [BE] Write failing test for idempotent seed (seven divisions, stable ids, `crm_app` role created when absent); implement `infrastructure/db/seed.py` and `make seed`
- [x] 2.5 [BE] Add `domain/territories/provinces.py` with the 52 INE province codes/names grouped by autonomous community; unit test count and code format

## 3. Backend domain: users, territories, scope, audit

- [x] 3.1 [BE] Write failing unit tests for value objects `Email` (case-insensitive equality) and `Password` policy (≥ 12 chars → `password_too_short`); implement in `domain/users/value_objects.py`
- [x] 3.2 [BE] Write failing unit tests for `User` entity (`deactivate`, `change_role` with `cannot_demote_self` guard, `record_failed_login` → lock at 10, `reset_failed_logins`, `is_locked(now)`); implement `domain/users/entities.py`
- [x] 3.3 [BE] Write failing unit tests for `Territory` entity (province code validation → `invalid_province`, `deactivate` guard `territory_in_use`); implement `domain/territories/entities.py`
- [x] 3.4 [BE] Write failing unit tests for `resolve_scope` and `VisibilityPolicy.can_read/can_write` covering the four scenarios in territory-scope spec plus back_office; implement `domain/shared/policies.py` with `Scoped` protocol
- [x] 3.5 [BE] Write failing unit tests for `AuditEvent` + `diff_fields(before, after, redact)` (redaction of `password_hash`, unchanged fields omitted); implement `domain/shared/audit.py`
- [x] 3.6 [BE] Define repository protocols `UserRepository`, `TerritoryRepository`, `RefreshTokenRepository`, `AuditLogWriter` and `UnitOfWork` protocol; implement in-memory fakes under `tests/unit/fakes/`

## 4. Backend infrastructure: repositories and unit of work

- [x] 4.1 [TEST] Integration tests for `SqlAlchemyUserRepository` (get by id/email case-insensitive, add, save with `expected_version` → `ConcurrentModificationError`, load territories/divisions)
- [x] 4.2 [BE] Implement `SqlAlchemyUserRepository`, `SqlAlchemyTerritoryRepository` (province uniqueness → `province_already_assigned` from IntegrityError), `SqlAlchemyRefreshTokenRepository`
- [x] 4.3 [TEST] Integration test: unit of work commits audit rows with data in one transaction and writes nothing on rollback; `crm_app` role gets permission error on `UPDATE audit_log`
- [x] 4.4 [BE] Implement `SqlAlchemyUnitOfWork` with audit collector flushed on `commit()`, `RequestContext` contextvar for `actor_id`/`trace_id`

## 5. Backend application services and API

- [x] 5.1 [BE] Write failing unit tests for `AuthService.login` (success, invalid, inactive, lockout at 10, counter reset, audit events `auth.login_succeeded/failed/locked_out`) with fakes; implement `PasswordAuthProvider`, `AuthProvider` protocol and `AuthService`
- [x] 5.2 [BE] Write failing unit tests for JWT issue/verify (15 min expiry, claims, expired/invalid → `unauthenticated`) and refresh rotation (rotate, reuse → revoke family, expiry); implement `infrastructure/security/jwt.py` and `AuthService.refresh/logout/change_password`
- [x] 5.3 [BE] Write failing API tests for `POST /auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/password` per authentication spec (all status codes, cookie attributes, rate limit 429 with `Retry-After`); implement `api/v1/auth.py`, `api/deps.py` (`current_user`, `require_roles`), slowapi setup
- [x] 5.4 [BE] Write failing unit tests for `UserService` (create with unknown reference → `unknown_reference`, duplicate email → `email_already_exists`, update with version, self-demotion guard, deactivation revokes tokens, audit events `user.*`); implement service and `UserQueries.list` with filters/sort
- [x] 5.5 [BE] Write failing API tests for `/users` (list filters and sort, 403 for sales_rep, create 201, patch with/without `If-Match` → 200/428/409, `/me` read and patch); implement `api/v1/users.py`, `api/v1/me.py`, schemas `UserCreate/Update/Read/MeRead/MeUpdate`
- [x] 5.6 [BE] Write failing unit tests for `TerritoryService` (create, province conflict, update, deactivate in use, audit `territory.*`); implement service, queries, `api/v1/territories.py`, `api/v1/divisions.py` with API tests per spec
- [x] 5.7 [BE] Write failing API tests for `GET /audit-log` (admin only, filters, newest first, actor name); implement `AuditQueries` and `api/v1/audit_log.py`
- [x] 5.8 [TEST] Authorization matrix integration test parametrised over the four roles × every endpoint in design D6 asserting expected 2xx/403
- [x] 5.9 [BE] Implement `make openapi` export to `ai-specs/specs/api-spec.yml`, run it, commit the generated spec

## 6. Frontend scaffolding

- [x] 6.1 [FE] Create Vite + React 18 + TypeScript project in `frontend/` with `tsconfig` per frontend-standards (`strict`, `noUncheckedIndexedAccess`, `@/` alias), Tailwind, `globals.css` design tokens, ESLint flat config (typescript-eslint strict, react-hooks, jsx-a11y, tanstack/query, `react/jsx-no-literals` scoped), Prettier, `.env.example`
- [x] 6.2 [FE] Add shadcn/ui primitives (Button, Input, Label, Form, Select, Sheet, Dialog, Toast, Skeleton, Badge, Accordion, Command) and lucide icons; verify token contrast (4.5:1 text, 3:1 UI) in a unit test over the palette
- [x] 6.3 [FE] Configure Vitest + Testing Library + MSW (`src/test/setup.ts`, `renderWithProviders`), Playwright (`desktop-chromium`, `mobile-chromium` Pixel 7, axe fixture), `npm run api:types` generating `src/api/schema.d.ts` from `api-spec.yml`
- [x] 6.4 [FE] Write failing unit test for `lib/env.ts` (missing `VITE_API_URL` throws); implement zod-validated env
- [x] 6.5 [FE] Write failing unit tests for `lib/problem.ts` (problem+json → `Problem`, field errors extraction, unknown code fallback); implement
- [x] 6.6 [FE] Set up i18next with `es-ES` namespaces `common`, `auth`, `admin`, `errors` (role labels, error code messages); unit test that every error code from design D6 has a translation

## 7. Frontend session and shell

- [x] 7.1 [FE] Write failing tests (MSW) for Axios client: attaches bearer token, single in-flight refresh on 401 then retry, redirect to `/login?next=` on refresh failure; implement `api/client.ts` and `features/auth/session.store.ts`
- [x] 7.2 [FE] Write failing component tests for `LoginPage` (valid submit navigates to `next` or `/hoy`, `invalid_credentials` and `account_locked` messages, email kept, keyboard order and Enter submit); implement page with react-hook-form + zod
- [x] 7.3 [FE] Write failing tests for bootstrap refresh on reload (splash then page, no login flash) and `logout` (store + query cache cleared, navigate `/login`); implement in `main.tsx`/`providers.tsx` and `features/auth`
- [x] 7.4 [FE] Write failing component tests for `AppShell`: `BottomNav` below 1024 px with ≥ 44 px targets and current route highlighted, `Sidebar` at ≥ 1024 px, admin entry only for `admin`; implement `AppShell`, `BottomNav`, `Sidebar`, `PageHeader`
- [x] 7.5 [FE] Write failing tests for `AuthGuard` (redirect with `next`) and `RoleGate` ("Sin permiso" page); implement router in `app/router.tsx` with lazy pages `/hoy` (placeholder), `/mas`, `/admin`
- [x] 7.6 [FE] Write failing tests for `OfflineBanner` (appears on offline event, hides on online) and `ConflictDialog` (opens on 409, "Recargar" invalidates query); implement both and wire to the query/mutation error handlers
- [x] 7.7 [FE] Write failing tests for `DataList` (cards below `lg`, table at `lg`, loading skeleton, `EmptyState`, `ErrorState` with retry); implement shared components

## 8. Frontend admin screens

- [x] 8.1 [FE] Write failing tests for `features/admin/users` queries (`useUsers` with filters, `useCreateUser`, `useUpdateUser` sending `If-Match`) against MSW handlers reflecting `api-spec.yml`; implement `api.ts`, `queries.ts`, `query-keys.ts`
- [x] 8.2 [FE] Write failing component tests for `UserListPage` (search, role/active filters, Spanish role labels, "Inactivo" badge, empty state with action); implement page at `/admin/usuarios`
- [x] 8.3 [FE] Write failing component tests for `UserForm` (create fields, edit fields with "Restablecer contraseña" and activo, `email_already_exists` under email, conflict dialog on 409, scope warning for Comercial without territory/division); implement form in `ResponsiveFormContainer` (Sheet mobile / Dialog desktop)
- [x] 8.4 [FE] Write failing tests for `features/admin/territories` queries and `TerritoryListPage` (provinces, user count); implement
- [x] 8.5 [FE] Write failing component tests for `TerritoryForm` (province picker grouped by community from `lib/provinces.ts`, taken provinces disabled with owner name, `province_already_assigned` highlight); implement
- [x] 8.6 [FE] Implement `/admin` hub page with two large cards ("Usuarios", "Territorios") and component test for navigation

## 9. End-to-end and CI

- [x] 9.1 [E2E] Playwright fixtures: seeded admin user via API, per-role storage state, `make e2e-seed`
- [x] 9.2 [E2E] Spec `auth.spec.ts`: login success, invalid credentials, lockout message, reload keeps session, logout — desktop and mobile, axe on each page
- [x] 9.3 [E2E] Spec `admin.spec.ts`: admin creates territory, creates sales rep with territory + division, logs out, logs in as rep, sees `/hoy` without admin entry, opens `/admin/usuarios` → "Sin permiso"
- [x] 9.4 [BE] `.github/workflows/backend.yml`: ruff, mypy, unit, integration with Postgres 16 service, migration round-trip + `alembic check`, OpenAPI drift diff, coverage thresholds
- [x] 9.5 [FE] `.github/workflows/frontend.yml`: eslint, tsc, Vitest coverage, build, `api:types` drift diff, Playwright against compose stack (both projects), report artifact; `ci.yml` requiring both
- [x] 9.6 [TEST] Run `pre-commit run --all-files`, `docker compose up --build` from clean clone, confirm `migrate` exits 0, `/health/ready` 200, login page served on 8080

## 10. Documentation

- [x] 10.1 Create `ai-specs/specs/data-model.md` from the template with the eight tables, constraints, indexes and ER diagram
- [x] 10.2 Create `ai-specs/specs/development_guide.md` from the template: prerequisites, env vars, Docker and non-Docker run, tests, migrations, seed, `JWT_SECRET` rotation note, `crm_app` role note
- [x] 10.3 Verify `ai-specs/specs/api-spec.yml` matches the final routers (task 5.9) and add the root `README.md` startup section linking to the guide
