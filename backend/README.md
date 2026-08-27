# Quermed CRM — Backend

FastAPI service exposing the CRM REST API under `/api/v1`. Conventions live in
`../ai-specs/specs/backend-standards.mdc`; setup steps in `../ai-specs/specs/development_guide.md`.

```bash
make install   # uv sync --all-extras
make migrate   # alembic upgrade head
make seed      # reference data
make dev       # http://localhost:8000/docs
make test
```
