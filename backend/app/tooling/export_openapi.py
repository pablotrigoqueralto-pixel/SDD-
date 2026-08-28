"""Export the generated OpenAPI document to ai-specs/specs/api-spec.yml.

Usage: python -m app.tooling.export_openapi <output-path>
"""

import sys
from pathlib import Path

import yaml

from app.infrastructure.settings import Settings
from app.main import create_app
from app.schemas.catalogue import ProductImportRow

# Contracts documented for later changes although no endpoint consumes them yet.
DOCUMENTED_ONLY_SCHEMAS = (ProductImportRow,)

EXPORT_SETTINGS = Settings(
    _env_file=None,
    DATABASE_URL="postgresql+asyncpg://export:export@localhost:5432/export",
    JWT_SECRET="export-only-secret-export-only-secret-0123",  # noqa: S106 - never used to sign
    CORS_ORIGINS="http://localhost:5173",
    ENVIRONMENT="dev",
)


async def _never_ready() -> bool:
    return False


def render_openapi() -> str:
    app = create_app(EXPORT_SETTINGS, readiness_probe=_never_ready)
    document = app.openapi()
    schemas = document.setdefault("components", {}).setdefault("schemas", {})
    for model in DOCUMENTED_ONLY_SCHEMAS:
        schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
        for name, definition in schema.pop("$defs", {}).items():
            schemas.setdefault(name, definition)
        schemas[model.__name__] = schema
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write("usage: python -m app.tooling.export_openapi <output-path>\n")
        return 2
    output = Path(argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_openapi(), encoding="utf-8")
    sys.stdout.write(f"OpenAPI written to {output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
