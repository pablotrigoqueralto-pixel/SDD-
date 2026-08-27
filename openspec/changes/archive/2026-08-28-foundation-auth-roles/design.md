## Context

Greenfield repository containing only the SDD governance layer, standards (`backend-standards.mdc`, `frontend-standards.mdc`), the constitution, Dockerfiles, `docker-compose.yml` and pre-commit config. No application code exists. This change creates the technical foundation every later change builds on: scaffolding, CI, authentication, users/roles, territory scope, audit log, API conventions and the frontend shell.

Stack was confirmed by the product owner during `/ai-specs:init-greenfield`; this design records the justification with discarded alternatives as required by the constitution.

## Goals / Non-Goals

**Goals:**
- Running local stack and green CI from a clean clone.
- Secure, simple authentication that a small team can operate, ready for Microsoft Entra ID later.
- Role + territory + division scope model that later changes apply to business records without redesign.
- Immutable audit mechanism that requires zero effort per use case (recorded by the unit of work).
- API conventions (errors, pagination, locking, OpenAPI) fixed once.
- Mobile-first shell with Spanish copy and the accessibility baseline.

**Non-Goals:**
- Any business entity beyond users, territories and divisions.
- OIDC login implementation, password reset by email, self-registration.
- Production infrastructure and backups (change 10).

## Decisions

### D1. Stack (recorded for the whole project)

| Choice | Discarded alternative | Reason (criteria: maturity → maintainability by a small team → mobile performance → hosting cost) |
|---|---|---|
| Python 3.12 + FastAPI | Node + NestJS | FastAPI generates OpenAPI natively, has far less ceremony (no modules/decorators/DI containers) and Pydantic gives validation and typing in one place. NestJS would unify the language with the frontend but doubles boilerplate for a team of this size. |
| Python 3.12 + FastAPI | Django + DRF | Django's admin and ORM are mature, but DRF is weaker at typing and OpenAPI, and Django's sync-first ORM complicates the async story. We do not need Django admin since the CRM has its own admin screens. |
| PostgreSQL 16 | MySQL 8 | Better full-text search (`tsvector` with Spanish config) for global search, `citext`, transactional DDL for safe migrations, richer JSON for audit diffs. |
| SQLAlchemy 2 async + Alembic | Django ORM / Tortoise | SQLAlchemy 2 has typed `Mapped[]` models, explicit query control for the < 500 ms budget, and Alembic is the de-facto migration tool. Tortoise is niche. |
| React 18 + Vite + TypeScript | Vue 3 + Vite | Larger ecosystem for kanban (dnd-kit), virtualised lists, headless accessible primitives (Radix) and PDF tooling. |
| Tailwind + shadcn/ui | MUI | shadcn/ui components are project code (no upgrade lock-in), lighter bundles on mobile, Radix accessibility built in. MUI is heavier and harder to fit to a custom design system. |
| TanStack Query + Zustand | Redux Toolkit | Server state is 95 % of the app state; TanStack Query handles caching, retries and optimistic updates natively. Redux would duplicate server state and add boilerplate. |
| pytest / Vitest / Playwright | Cypress for E2E | Playwright runs multiple browsers and mobile emulation in one config, is faster in CI, and has first-class axe integration. |
| GitHub Actions | GitLab CI | Repository lives on GitHub; no extra service. |
| Docker Compose (dev), single container images (prod) | Serverless | Long-lived connections to PostgreSQL, predictable cost for a SME, simpler mental model. |

### D2. Backend layout and dependency injection

- Layers exactly as `backend-standards.mdc`: `api → application → domain ← infrastructure`.
- FastAPI `Depends` wires: `get_session` → `SqlAlchemyUnitOfWork` → repositories → services. Services are constructed per request (cheap objects); no global container.
  - *Discarded*: `dependency-injector` library — extra concept for little gain at this size.
- Unit of work (`app/application/shared/unit_of_work.py`) exposes `users`, `territories`, `refresh_tokens` repositories, an `audit` collector, `commit()` and `rollback()`. `commit()` flushes collected `AuditEvent`s to `audit_log` before committing so audit and data share a transaction.

### D3. Authentication

- Access token: JWT `HS256`, 15 min, claims `sub`, `role`, `iat`, `exp`, `jti`. Secret from `JWT_SECRET` (≥ 32 bytes; startup fails otherwise).
  - *Discarded*: `RS256` now — key management overhead without a second verifier. Switch when SSO or a second service needs to verify tokens.
- Refresh token: 32 random bytes, base64url, delivered as `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth` cookie; stored as SHA-256 hash in `refresh_tokens` with `user_id`, `expires_at`, `used_at`, `revoked_at`, `replaced_by_id`. Rotation on every refresh; reuse detection revokes the whole family.
  - *Discarded*: refresh token in localStorage — XSS exposure. *Discarded*: server-side sessions (Redis) — extra service to operate.
- Password hashing: argon2id via `pwdlib` (parameters: default `argon2-cffi` recommended). *Discarded*: bcrypt — 72-byte limit and weaker against GPU attacks.
- Lockout: `failed_login_attempts` and `locked_until` columns on `users`; incremented in the same transaction as the `auth.login_failed` audit event.
- Rate limiting: `slowapi` with in-memory storage (single instance in MVP). Documented limitation: multi-instance deployments need a shared backend (Redis) — decision deferred to change 10.
- `AuthProvider` protocol: `authenticate(credentials) -> AuthenticatedUser | None`. `PasswordAuthProvider` implemented now; login router depends on the protocol. `User.identity_provider` (`password | entra_id`, enum) + `external_id` prepared.

### D4. Authorization model

- `Role` enum on `users.role`; checked by a `require_roles(*roles)` dependency at router level for coarse gates (admin endpoints).
- Fine-grained rules in `app/domain/shared/policies.py`:
  - `Scope(territory_ids, province_codes, division_ids)`, produced by `resolve_scope(user)`.
  - `VisibilityPolicy.can_read(user, scope, record: Scoped)` / `can_write(...)` where `Scoped` is a protocol with `owner_id`, `territory_id`, `division_id | None`.
  - Rule: `admin | sales_manager | back_office` → all; `sales_rep` → `record.owner_id == user.id or (record.territory_id in scope.territory_ids and (record.division_id is None or record.division_id in scope.division_ids))`.
  - Later changes implement `scoped_to(user)` SQL filters from the same `Scope` object so lists never post-filter in Python.
  - *Discarded*: a generic permissions table / ACLs — over-engineering for four roles; violates "simplicity wins". *Discarded*: territory as pure list of users without provinces — loses the smart default (province → territory) for account creation.

### D5. Data model

Tables (all with `id UUID PK` (UUIDv7 generated in application), `created_at timestamptz`, `updated_at timestamptz`; mutable aggregates with `version integer not null default 1`):

| Table | Columns (besides common) | Indexes / constraints |
|---|---|---|
| `users` | `email citext unique`, `full_name text`, `password_hash text`, `role users_role_enum`, `is_active bool default true`, `identity_provider users_identity_provider_enum default 'password'`, `external_id text null`, `failed_login_attempts int default 0`, `locked_until timestamptz null` | unique `(identity_provider, external_id)` where `external_id is not null`; index `role`, `is_active` |
| `refresh_tokens` | `user_id FK users RESTRICT`, `token_hash text unique`, `expires_at`, `used_at null`, `revoked_at null`, `replaced_by_id FK self null`, `user_agent text null`, `ip inet null` | index `user_id`, `expires_at` |
| `territories` | `name citext unique`, `is_active bool` | — |
| `territory_provinces` | `territory_id FK CASCADE`, `province_code char(2)` | PK `(territory_id, province_code)`, **unique `province_code`** (one territory per province), check `province_code ~ '^(0[1-9]|[1-4][0-9]|5[0-2])$'` |
| `divisions` | `code text unique`, `name_es text`, `sort_order int` | — |
| `user_territories` | `user_id FK CASCADE`, `territory_id FK RESTRICT` | PK `(user_id, territory_id)` |
| `user_divisions` | `user_id FK CASCADE`, `division_id FK RESTRICT` | PK `(user_id, division_id)` |
| `audit_log` | `occurred_at timestamptz`, `actor_id UUID null`, `entity_type text`, `entity_id UUID null`, `action text`, `changes jsonb`, `trace_id text` | index `(entity_type, entity_id, occurred_at desc)`, `(actor_id, occurred_at desc)`, `occurred_at desc` |

- Migration `0001_foundation` creates the extension `citext`, enums, all tables, and a `crm_app` role grant statement `GRANT INSERT, SELECT ON audit_log TO crm_app` (guarded: only executed when the role exists, so local dev with the superuser still works). Compose creates the DB with the `crm` superuser for dev; the least-privilege `crm_app` role is created by the seed for integration tests and by ops in change 10.
  - *Discarded*: database trigger blocking updates — grants are simpler and auditable; a trigger would also be needed for superuser in dev, which we do not want to protect against.
- Provinces are not a table: the 52 INE codes and names, grouped by autonomous community, live in `app/domain/territories/provinces.py` (backend validation) and `frontend/src/lib/provinces.ts` (picker). They never change. *Discarded*: `provinces` table — would only add a join.

### D6. API contract

Base `/api/v1`. All responses JSON; errors `application/problem+json` (see api-foundation spec).

| Method & path | Roles | Notes |
|---|---|---|
| `POST /auth/login` | anon | body `LoginRequest{email,password}` → `TokenResponse{access_token,token_type,expires_in,user}` + cookie |
| `POST /auth/refresh` | cookie | → `TokenResponse` + rotated cookie |
| `POST /auth/logout` | auth | 204, clears cookie |
| `POST /auth/password` | auth | `PasswordChange{current_password,new_password}` → 204 |
| `GET /me` | auth | `MeRead{…UserRead, territories[TerritoryRead], divisions[DivisionRead]}` |
| `PATCH /me` | auth | `MeUpdate{full_name}` + `If-Match` |
| `GET /users` | admin, sales_manager, back_office | paginated, filters `role,is_active,territory_id,q`, sort `full_name,email,role,created_at` |
| `POST /users` | admin | `UserCreate` → 201 `UserRead` |
| `GET /users/{id}` | admin, sales_manager, back_office | `UserRead` |
| `PATCH /users/{id}` | admin | `UserUpdate` + `If-Match` |
| `GET /territories` | admin, sales_manager, back_office | paginated, filters `is_active,q`, sort `name` |
| `POST /territories` | admin | `TerritoryCreate{name,provinces[]}` |
| `GET /territories/{id}` | admin, sales_manager, back_office | `TerritoryRead{…, provinces[], user_count}` |
| `PATCH /territories/{id}` | admin | `TerritoryUpdate` + `If-Match` |
| `GET /divisions` | auth | `DivisionRead[]` |
| `GET /audit-log` | admin | paginated, filters `entity_type,entity_id,actor_id,action,from,to`, sort `-occurred_at` only |
| `GET /health`, `GET /health/ready` | anon | outside `/api/v1` |

`UserRead{id,email,full_name,role,is_active,identity_provider,territory_ids[],division_ids[],version,created_at,updated_at}` — never `password_hash`, `failed_login_attempts`, `locked_until`.

Error codes introduced: `invalid_credentials`, `account_locked`, `rate_limited`, `unauthenticated`, `forbidden`, `not_found`, `conflict`, `precondition_required`, `validation_error`, `invalid_sort_field`, `email_already_exists`, `unknown_reference`, `cannot_demote_self`, `invalid_current_password`, `password_too_short`, `province_already_assigned`, `invalid_province`, `territory_in_use`, `internal_error`.

### D7. Audit mechanism

- `AuditEvent` dataclass in `domain/shared/audit.py`; services call `uow.audit.record(event)`. Diffs are computed by the service from the entity before/after (`diff_fields(before, after, redact={"password_hash"})`), not by ORM introspection, so what is audited is explicit and typed.
  - *Discarded*: SQLAlchemy `before_flush` listener auto-diffing every model — implicit, hard to redact, couples audit to ORM internals.
- `actor_id` and `trace_id` come from a request-scoped `RequestContext` (contextvar) set by middleware.

### D8. Frontend architecture

- Vite + React Router `createBrowserRouter`; route objects in `app/router.tsx`; pages lazy per feature.
- Session: `features/auth/session.store.ts` (Zustand) holds `accessToken` (memory only) and `user`. Axios interceptor: attach token; on 401 → single in-flight refresh promise → retry; on refresh failure → clear store, navigate to `/login?next=`.
  - *Discarded*: storing the access token in localStorage — XSS exposure; sessionStorage also rejected because the refresh cookie already survives reloads.
- Bootstrapping: `main.tsx` calls refresh once before rendering routes (shows splash skeleton ≤ 1 s) so a reload does not flash the login page.
- i18n: `i18next` with namespaces `common`, `auth`, `admin`, `errors`. Error `code` → `errors:<code>`.
- Design tokens in `styles/globals.css` (`--color-primary` Quermed blue, neutral scale, `--radius`), Tailwind maps them; dark mode not in scope.
- Shared components introduced here: `AppShell`, `BottomNav`, `Sidebar`, `PageHeader`, `DataList` (cards < `lg`, table ≥ `lg`), `EmptyState`, `ErrorState`, `ConflictDialog`, `OfflineBanner`, `RoleGate`.

Mobile layout (first):

```
┌──────────────────────────┐
│ ◀  Usuarios         [+]  │  ← PageHeader: back, title, primary action
├──────────────────────────┤
│ 🔍 Buscar por nombre…    │
│ [Rol ▾] [Activos ▾]      │
│ ┌──────────────────────┐ │
│ │ Ana García           │ │  ← card: name, role badge,
│ │ Comercial · Centro   │ │     territories, inactive badge
│ └──────────────────────┘ │
│ ┌──────────────────────┐ │
│ │ …                    │ │
├──────────────────────────┤
│  Hoy   Más   Admin       │  ← BottomNav (≥44 px targets)
└──────────────────────────┘
```

Desktop layout:

```
┌──────┬───────────────────────────────────────┐
│ Hoy  │ Usuarios                 [Nuevo usuario]│
│ Más  │ 🔍 Buscar   [Rol ▾] [Activos ▾]        │
│ Admin│ Nombre      Email       Rol   Territ.  │
│      │ Ana García  ana@…       Com.  Centro   │
│      │ …                                      │
└──────┴───────────────────────────────────────┘
```

Forms open in a `Sheet` (bottom, mobile) / `Dialog` (desktop) via one `ResponsiveFormContainer` so the form component is written once.

### D9. Testing strategy for this change

- Backend unit: policies (`VisibilityPolicy`), password/lockout logic, token rotation rules, diff/redaction, pagination parsing — with fake repositories.
- Backend integration: every endpoint × documented status codes; authorization matrix test parametrised over the four roles; migration round-trip; audit row written and rolled back with transaction; `crm_app` cannot update `audit_log`.
- Frontend unit/component: login form states, interceptor refresh-and-retry (MSW), `RoleGate`, `DataList` breakpoint rendering, problem → field error mapping, conflict dialog.
- E2E (desktop + mobile): login → admin creates territory → creates user → logs out → logs in as the new user → sees `/hoy` and no admin entry; axe on each page.

### D10. CI

- `.github/workflows/backend.yml` and `frontend.yml`, path-filtered, plus `ci.yml` that requires both as status checks. Postgres 16 service container for backend integration; compose stack built for frontend E2E; Playwright report uploaded as artifact.
- OpenAPI drift: job runs `make openapi` into a temp file and `diff`s against the committed one. Type drift: `npm run api:types` into temp and `diff`.

## Risks / Trade-offs

- **In-memory rate limiting** is per process; acceptable for a single instance MVP. Recorded as a follow-up for change 10.
- **HS256 shared secret**: rotating the secret logs everyone out; acceptable, documented in `development_guide.md`.
- **`SameSite=Strict` refresh cookie** means the SPA and API must share the site (same registrable domain) in production; compose uses `localhost` for both. Change 10 must serve the API under the same domain (path or subdomain).
- **Seven divisions hard-seeded**: adding a division is a seed change + deploy, not a UI action. Deliberate: divisions are stable and "zero configuration" wins.
- **Provinces as code, not table**: any future need for sub-province zones would require a schema change; judged unlikely for a team of this size.
- **Scope rule complexity** (territory ∧ division): mixed geography/speciality teams need it, but it must be explained in the user form (inline warning implemented) to avoid "why can't I see this centre" support calls.

### Implementation notes (recorded during /opsx:apply)

- **Login bookkeeping does not use optimistic locking.** `failed_login_attempts` / `locked_until` are persisted through `UserRepository.save_login_state`, an unconditional `UPDATE` that neither checks nor bumps `version`. Rationale: two concurrent logins of the same user (the E2E suite exposed it) must both succeed, and a login must never make an administrator's pending edit fail with `409`. Role, scope, name and password changes keep the versioned `save`.
- **Auth rate limit is configurable** (`AUTH_RATE_LIMIT`, default `10/minute`, slowapi syntax). The spec value stays the default; automated E2E runs, which perform dozens of logins from one IP, set `1000/minute` through the compose `.env`. The limit is still per process (in-memory storage), as stated in Risks.
- **Tests use the non-data router.** Vitest renders with `MemoryRouter` (`src/test/render.tsx`): React Router's data router builds `Request` objects on navigation, which jsdom + MSW cannot construct. The app itself uses `createBrowserRouter`.
- **shadcn/ui is vendored under `src/components/ui`** with a relaxed lint profile; the toast close button received an `aria-label` after axe flagged it in E2E.
