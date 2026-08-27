# Contributing

## Workflow

Every change follows the Spec-Driven Development lifecycle (`/opsx:new` → proposal → specs → design → tasks → `/opsx:apply` → `/opsx:verify` → `/opsx:archive`). Standards live in `ai-specs/specs/` and are mandatory:

- `ai-specs/specs/backend-standards.mdc`
- `ai-specs/specs/frontend-standards.mdc`
- `ai-specs/specs/documentation-standards.mdc`

## Pre-commit hooks

Linting and formatting run automatically on every `git commit` through the [pre-commit](https://pre-commit.com) framework.

Install once per clone:

```bash
pip install pre-commit
pre-commit install
```

Run on the whole repository (e.g. after pulling or before opening a PR):

```bash
pre-commit run --all-files
```

Hooks configured in `.pre-commit-config.yaml`:

| Scope | Hooks |
|---|---|
| All files | trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files, detect-private-key, check-merge-conflict |
| `backend/` | ruff (lint + autofix), ruff-format, mypy `--strict` |
| `frontend/` | prettier (with Tailwind class sorting), eslint (`--max-warnings=0`) |

If a hook modifies files, stage the changes and commit again. Hooks are not to be bypassed with `--no-verify`.

## Local stack

```bash
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend API: http://localhost:8000 (OpenAPI UI at `/docs`)
- PostgreSQL: `localhost:5432`

Copy `.env.example` to `.env` to override defaults (`CORS_ORIGINS`, `VITE_API_URL`, `JWT_SECRET`, database credentials).
