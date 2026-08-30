# Development Guide

This guide provides step-by-step instructions for setting up the development environment, running the Quermed CRM locally and executing the test suites.

## 🚀 Setup Instructions

### Prerequisites

Ensure you have the following installed:
- **Docker** and **Docker Compose** (v2)
- **Python 3.12** and **uv** (`pip install uv`)
- **Node.js 20+** and **npm 10+**
- **Git**
- (Optional) **GNU make** — every `make` target below is also listed as a plain command

### 1. Clone the Repository

```bash
git clone <repository-url>
cd SDD-
```

### 2. Environment Configuration

Root (Docker Compose) — copy and adjust:

```bash
cp .env.example .env
```

| Variable | Purpose | Default |
|---|---|---|
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Database created by the `db` service | `quermed_crm` / `crm` / `crm` |
| `JWT_SECRET` | Signs access tokens; **at least 32 characters**. Rotating it logs every user out. | (set one) |
| `CORS_ORIGINS` | Allowed browser origins, comma-separated; keep `localhost` and the `*.local` pattern for LAN/mobile testing | `http://localhost:5173,http://localhost:8080,http://*.local:5173,http://*.local:8080` |
| `ENVIRONMENT` | `dev`, `test`, `staging`, `prod` — the refresh cookie is `Secure` only in `staging`/`prod` | `dev` |
| `LOG_LEVEL` | `debug`, `info`, `warning`, `error` | `info` |
| `VITE_API_URL` | Backend base URL baked into the frontend build (**no `/api/v1` suffix**) | `http://localhost:8000` |
| `AUTH_RATE_LIMIT` | Per-IP limit on `/auth/*` (slowapi syntax) | `10/minute` |

Backend outside Docker (`backend/.env`, see `backend/.env.example`): `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGINS`, `ENVIRONMENT`, `LOG_LEVEL`.

Frontend outside Docker (`frontend/.env.local`, see `frontend/.env.example`): `VITE_API_URL`.

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 3. Run Everything with Docker Compose

```bash
docker compose up --build
```

Services:
- `db` — PostgreSQL 16 on `localhost:5432` (named volume `db_data`)
- `migrate` — one-shot: `alembic upgrade head` + reference data seed, then exits
- `backend` — FastAPI on http://localhost:8000 (OpenAPI UI at `/docs`, health at `/health` and `/health/ready`)
- `frontend` — nginx serving the built SPA on http://localhost:8080

Create the first administrator (idempotent; also used by the E2E suite):

```bash
docker compose exec -e E2E_ADMIN_PASSWORD='choose-a-long-passphrase' backend python -m app.tooling.e2e_seed
```

Log in at http://localhost:8080 with `admin@quermed.com` and that password (override the email with `E2E_ADMIN_EMAIL`).

### 4. Backend Setup (without Docker)

```bash
cd backend
uv sync --all-extras                 # make install
cp .env.example .env                 # then set JWT_SECRET
uv run alembic upgrade head          # make migrate
uv run python -m app.infrastructure.db.seed   # make seed (divisions + crm_app role)
uv run uvicorn app.asgi:app --reload --port 8000   # make dev
```

A PostgreSQL must be reachable at `DATABASE_URL` (the compose `db` service works: `docker compose up -d db`).

### 5. Frontend Setup (without Docker)

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run dev                          # http://localhost:5173
```

Regenerate the typed API client whenever `ai-specs/specs/api-spec.yml` changes:

```bash
npm run api:types
```

### 6. Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

Hooks: whitespace/EOF/YAML/large-file/private-key checks, `ruff` + `mypy` for `backend/`, `prettier` + `eslint` for `frontend/`.

## 🧪 Testing

### Backend Testing

```bash
cd backend
uv run pytest tests/unit                       # make test-unit  (no database)
uv run pytest --cov=app --cov-report=term-missing   # make test (unit + integration)
uv run ruff check . && uv run ruff format --check .  # make lint
uv run mypy app tests                          # make typecheck
```

Integration tests need PostgreSQL at `TEST_DATABASE_URL` (default `postgresql+asyncpg://crm:crm@localhost:5432/quermed_crm_test`). Create it once:

```bash
docker compose up -d db
docker compose exec db psql -U crm -d postgres -c "CREATE DATABASE quermed_crm_test;"
```

They are skipped with a clear message when the database is unreachable. Coverage threshold: 80 % (CI fails below).

Migrations are verified by `tests/integration/test_migrations.py` (upgrade → downgrade → upgrade → `alembic check`).

### Frontend Testing

```bash
cd frontend
npm run lint
npm run typecheck
npm run test:unit        # Vitest + Testing Library + MSW, with coverage (80 % on features/ and lib/)
npm run build
```

### End-to-End Testing (Playwright)

Runs against the Docker Compose stack on desktop Chromium and a Pixel 7 emulation, with axe accessibility checks on every page:

The suite performs dozens of logins from one IP, so raise the auth rate limit for the run:

```bash
AUTH_RATE_LIMIT=1000/minute docker compose up -d --build
docker compose exec -e E2E_ADMIN_PASSWORD='e2e-admin-passphrase' backend python -m app.tooling.e2e_seed
cd frontend
npx playwright install chromium      # first time
E2E_ADMIN_PASSWORD='e2e-admin-passphrase' npm run test:e2e
```

Environment overrides: `E2E_BASE_URL` (default `http://localhost:8080`), `E2E_API_URL` (default `http://localhost:8000`), `E2E_ADMIN_EMAIL`.

## 🌱 Reference Data (seed)

`python -m app.infrastructure.db.seed` (`make seed`, also run by the compose `migrate` service) is idempotent and safe in production:

| Master | Seeded values | Editable by administrators |
|---|---|---|
| Divisions | 7 product divisions | no |
| Account types | Clínica FIV / laboratorio, Hospital público (tenders), Hospital privado, Clínica o consulta privada, Centro de podología / pie diabético, Distribuidor | no (seed only) |
| Activity types | Visita, Llamada, Email, Demo, Formación, Nota (not a contact) | no (seed only) |
| Brands | 13 represented manufacturers as own brands | yes (name, own/competitor, divisions, active; new brands) |
| Loss reasons | Precio, Competidor (requires brand), Sin presupuesto, Proyecto cancelado, Plazos, Otro (requires note) | yes (name, active; new reasons) |
| Pipelines | Equipos (5 divisions) and Consumibles (2 divisions) with their stages and probabilities | yes (names, probabilities, order, active) |
| Job titles (cargos) | Ginecólogo/a, Embriólogo/a, Director/a de laboratorio FIV, Cirujano/a vascular, Neurólogo/a, Jefe/a de servicio, Supervisor/a de enfermería, Compras / suministros, Gerencia, Electromedicina / ingeniería clínica, Otro | yes (name, active; new titles) |
| Product families (familias) | 16 starter families, two to four per division (e.g. Medios de cultivo, Dopplers, Electrodos, Carros) | yes (name, order, active; new families — the division is fixed at creation) |

Rows are matched by `code` with deterministic ids; re-running the seed never overwrites an administrator's edits, only semantic flags (`buys_via_tender`, `counts_as_contact`, `requires_*`, `is_won/is_lost/is_at_risk`).

## 🗃️ Database Migrations

```bash
cd backend
uv run alembic revision --autogenerate -m "describe_change"   # make migration m="describe_change"
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic check
```

Review every generated file by hand (enum changes, data migrations, index concurrency). Never edit a migration merged to `main`.

Business days for `GET /api/v1/me/today` (today, overdue, week) are computed server-side in `Europe/Madrid` (`tzdata` is a runtime dependency so Windows and slim containers resolve the zone). Activities closed more than 7 days ago are editable only by sales managers and admins (`activity_locked`).

Opportunities (`/api/v1/opportunities`): visibility is the account's; `PATCH` edits descriptive fields only, while stage moves, win/lose (loss reason rules from change 02), reopen (managers), at-risk and reassignment are explicit commands with `If-Match`. `amount` is the sum of the product lines when they exist, else the manual estimate. The board (`GET /opportunities/board`) returns one column per open stage capped at 50 cards. The automatic "En riesgo" flag for silent recurring consumables accounts is driven by `AT_RISK_AFTER_DAYS` (default 60) and runs inside the backend container every `AT_RISK_SCAN_INTERVAL_HOURS` (default 6; 0 disables it — use `python -m app.tooling.at_risk_scan` from cron in production). The scan never clears flags: the rep clears them manually or by registering a done activity linked to the opportunity. Frontend routes: `/oportunidades` (list on mobile, kanban on desktop), `/oportunidades/:id`, creation from the account 360º page.

Product catalogue (`/api/v1/products`, `/api/v1/product-families`): products are global (no territory scope) and identified by the Sage article code (`sku`, normalised to upper case and unique). `sales_rep` and `back_office` never receive `cost_price` (the field is omitted, not null); back office may still write it. Retired products (`is_active = false`) are hidden from the default list for reps and back office (`is_active=false|all` needs `sales_manager`/`admin`) but stay readable by id. `ProductService.upsert_by_sku` and the `ProductImportRow` schema are the import contract used by the CSV import (change 08): rows match existing products by code, never change the code, and report `created` / `updated` / `unchanged`. Frontend routes: `/catalogo`, `/catalogo/nuevo`, `/catalogo/:id`, `/admin/familias`.

Quotes (`/api/v1/quotes`): a quote (Presupuesto) is always created from an open opportunity and copies its lines; visibility is the account's, inherited through the opportunity. Numbering is a yearly company-wide sequence (`P-2026-0001`) allocated atomically from `quote_counters` in the creating transaction (Europe/Madrid year) — gapless, never reused. Drafts are edited freely (`PATCH` with `If-Match` replaces the whole `lines` array; per-line discount % and VAT 21/10/4/0, `ROUND_HALF_UP` at two decimals per line — the frontend mirrors the exact arithmetic in `computeQuoteTotals`, verified against the shared vector fixture `backend/tests/fixtures/quote_totals_vectors.json`). `POST /quotes/{id}/send` freezes the version, renders the PDF with ReportLab (fixed template, stored in `quote_pdfs` and re-downloadable forever; drafts get an on-the-fly preview) and emails it via Microsoft Graph from the acting rep's mailbox. Editing after sending means `POST /quotes/{id}/revise` (a new `-v2` draft under the same number). `POST /quotes/{id}/accept` wins the opportunity with the quote total and auto-rejects sibling open quotes in the same transaction; expiry (`valid_until`, default send + `validez_dias`) is visual only. Back office creates and edits drafts on any opportunity but never sends, accepts, rejects or revises (`quote_action_forbidden`); cost and margin are only serialized for managers/admins. Admin defaults (conditions and the email template with `{numero}`/`{centro}`/`{comercial}` placeholders) live in `app_settings` behind `GET/PUT /api/v1/quote-settings` (read open to authenticated users; write admin-only). Frontend routes: `/presupuestos`, `/presupuestos/:id`, sections on the opportunity sheet and the account 360º page, the "Presupuestos por caducar" block on Hoy and `/admin/presupuestos`.

Microsoft Graph mail: configured with `GRAPH_SENDER_MODE` (`off` by default — dev, E2E and any environment without tenant consent), `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID` and `GRAPH_CLIENT_SECRET`. The integration is two plain `httpx` calls (client-credentials token + `POST /v1.0/users/{rep}/sendMail` with the PDF as base64 attachment, 10 s timeout). The Azure AD app registration needs the **application** permission `Mail.Send` with tenant-admin consent, and an [application access policy](https://learn.microsoft.com/graph/auth-limit-mailbox-access) scoping it to the sales mailboxes. Every send writes a `mail_outbox` row (`sent` / `failed` / `skipped`): a Graph failure never reverts the quote's sent status — the sheet shows the error and `POST /quotes/{id}/retry-email` re-sends the stored PDF. With mode `off` (or the "sin email" checkbox) the quote still freezes and the outbox records `skipped`; the rep downloads the PDF and sends it manually.

Global search (`GET /api/v1/search?q=`): one scoped request answering with grouped, capped results (5 per group, 10 contacts) across centros, contactos, oportunidades and presupuestos (current versions only) — products keep the catalogue search. Name matching is trigram over `f_unaccent(...)` expression indexes, so accented and unaccented spellings find each other; the term is also routed once by shape: `P-YYYY-NNNN` → quote numbers, `@` → emails, CIF/NIF shapes → `tax_id`, 7+ digits → phones (separators stripped). Results honour each role's account scope exactly like the lists. Frontend: the "Buscar" entry now occupies the fifth navigation slot for every role (Administración moved to the first card inside Más); recents (last 8 searches and visited records) live in the device's `localStorage` only.

Imports (`POST /api/v1/products/import`, `POST /api/v1/accounts/import`; `admin` and `back_office` only): multipart `.csv`/`.xlsx` upload with `dry_run=true` by default — the response is the full per-row report (`created` / `updated` / `unchanged` / `error` with the reason); confirming re-posts with `dry_run=false` and applies valid rows through the same services as manual API calls (row-by-row commits, idempotent matching makes re-runs safe). Caps: 2 000 data rows / 5 MB. Matching: products by normalised SKU (the change-05 `upsert_by_sku` contract; brand/family resolve by name, never created), accounts by normalised CIF with exact-normalised-name fallback (never fuzzy, never renamed, back-office updates limited to administrative fields), embedded contacts by email within the account. Header aliases are case- and accent-insensitive; the canonical Spanish columns are — catalogue: `Código` (SKU), `Nombre`, `Marca`, `Familia`, `Tipo` (equipo/consumible/servicio), `PVP`, `Coste`, `Unidad`, `Descripción`; accounts: `Nombre`, `CIF`, `Provincia` (código INE), `Ciudad`, `Dirección`, `Código postal`, `Teléfono`, `Email`, `Tipo`, plus optional `Contacto nombre`, `Contacto apellidos`, `Contacto email`, `Contacto teléfono`, `Cargo` (repeat the account columns to add several contacts). Prices accept Spanish decimal commas; CSV accepts `;` or `,` in UTF-8 or cp1252; `.xlsx` reads the first worksheet. Each confirmed run records `import.products_executed` / `import.accounts_executed` with the counts; dry runs record nothing. Frontend routes: `/buscar`, `/importar/catalogo`, `/importar/centros` (cards in Admin and Más).

Migration `0008_search_import` runs `CREATE EXTENSION IF NOT EXISTS unaccent` (same managed-PostgreSQL caveat as `pg_trgm` below: create it once as an administrator if the migration role lacks the privilege) and defines the IMMUTABLE `f_unaccent` wrapper behind the search expression indexes.

Migration `0003_accounts_contacts` runs `CREATE EXTENSION IF NOT EXISTS pg_trgm` (trigram indexes behind the account search). On managed PostgreSQL where the migration role is not a superuser, create the extension once as an administrator (`CREATE EXTENSION pg_trgm;`) before running `alembic upgrade head`; the statement is then a no-op.

## 📄 OpenAPI

The committed contract `ai-specs/specs/api-spec.yml` is generated, not hand-written:

```bash
cd backend
uv run python -m app.tooling.export_openapi ../ai-specs/specs/api-spec.yml   # make openapi
```

CI fails when the file is stale. After exporting, run `npm run api:types` in `frontend/` and commit both.

## 🔐 Security Notes

- Access tokens are 15-minute HS256 JWTs signed with `JWT_SECRET`; refresh tokens are 30-day rotating opaque tokens stored hashed, delivered as an `HttpOnly; SameSite=Strict` cookie scoped to `/api/v1/auth`. Frontend and API must share a site in production.
- Auth endpoints are rate limited to 10 requests/minute per IP (in-memory; single instance). Accounts lock for 15 minutes after 10 consecutive failures.
- The application database role `crm_app` (created by the seed) has `INSERT`/`SELECT` only on `audit_log` and `personal_data_access_log`; production deployments should connect the backend with that role instead of the superuser.
- GDPR: reading a contact's personal data by anyone other than the account owner, a sales manager or an admin appends a row to `personal_data_access_log` (user, contact, timestamp, trace id). Administrators query it at `GET /api/v1/audit-log/personal-data-access`. Contacts are never deleted: `POST /api/v1/contacts/{id}/anonymise` (managers/admins) clears the personal fields in place and the audit event stores only the field names.

## 🔄 CI

GitHub Actions (`.github/workflows/`):
- `backend.yml` — ruff, mypy, unit tests, migration round-trip, integration tests with coverage, OpenAPI drift.
- `frontend.yml` — eslint, prettier, tsc, Vitest coverage, build, generated types drift, Playwright E2E on the compose stack.
- `ci.yml` — pre-commit hooks. Configure `backend`, `frontend` and `ci` as required status checks on `main`.
