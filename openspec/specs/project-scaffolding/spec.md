# project-scaffolding

## Purpose
Monorepo layout, tooling, local Docker stack, CI pipelines and quality gates for backend and frontend.

## Requirements

### Requirement: Monorepo layout
The repository SHALL contain a `backend/` package and a `frontend/` package following the folder structures defined in `backend-standards.mdc` and `frontend-standards.mdc`, and both SHALL build and run through the root `docker-compose.yml`.

#### Scenario: Local stack starts from a clean clone
- **WHEN** a developer runs `docker compose up --build` on a clean clone with a copied `.env.example`
- **THEN** the `db`, `migrate`, `backend` and `frontend` services start, `migrate` exits with code 0, `http://localhost:8000/health/ready` returns 200 and `http://localhost:8080` serves the login page

#### Scenario: Backend runs without Docker
- **WHEN** a developer runs `make install`, `make migrate`, `make seed` and `make dev` in `backend/` with a reachable PostgreSQL
- **THEN** the API listens on port 8000 and `/docs` renders the OpenAPI UI

#### Scenario: Frontend runs without Docker
- **WHEN** a developer runs `npm ci` and `npm run dev` in `frontend/` with `VITE_API_URL` pointing to the backend
- **THEN** the app is served on port 5173 and can log in against the backend

### Requirement: Quality gates
The project SHALL provide lint, format, type-check and test commands for both packages, and the pre-commit configuration SHALL run them on staged files.

#### Scenario: Backend quality commands
- **WHEN** `make lint`, `make typecheck` and `make test` are run in `backend/`
- **THEN** each exits 0 on the scaffolded codebase and exits non-zero when a violation is introduced

#### Scenario: Frontend quality commands
- **WHEN** `npm run lint`, `npm run typecheck`, `npm run test:unit` and `npm run build` are run in `frontend/`
- **THEN** each exits 0 on the scaffolded codebase and exits non-zero when a violation is introduced

#### Scenario: Pre-commit blocks a violation
- **WHEN** a developer commits a Python file with an unused import or a TSX file with a hard-coded Spanish literal
- **THEN** the corresponding hook fails and the commit is rejected

### Requirement: Continuous integration blocks merges
GitHub Actions workflows SHALL run on every pull request and push to `main`, and a failing job SHALL block the merge.

#### Scenario: Backend workflow
- **WHEN** a pull request touches `backend/**`
- **THEN** the `backend` workflow runs ruff, mypy, unit tests, integration tests against a PostgreSQL 16 service, an Alembic upgrade → downgrade → upgrade round-trip, `alembic check`, and fails if the exported `ai-specs/specs/api-spec.yml` differs from the app's generated schema

#### Scenario: Frontend workflow
- **WHEN** a pull request touches `frontend/**`
- **THEN** the `frontend` workflow runs eslint, tsc, Vitest with coverage, the production build, a check that `src/api/schema.d.ts` is current with `api-spec.yml`, and Playwright E2E against the compose stack on desktop and mobile projects

#### Scenario: Coverage threshold enforced
- **WHEN** backend line coverage falls below 80 % (or below 90 % in `app/domain` / `app/application`) or frontend coverage on `src/features` and `src/lib` falls below 80 %
- **THEN** the corresponding workflow fails

### Requirement: Developer documentation
The repository SHALL contain `ai-specs/specs/development_guide.md` (from the template structure) and a root `README.md` startup section describing prerequisites, environment variables, local run, tests and migrations.

#### Scenario: New developer onboarding
- **WHEN** a developer follows `development_guide.md` on a machine with Docker, Python 3.12 and Node 20
- **THEN** they reach a running local stack and a passing test suite without asking for undocumented steps
