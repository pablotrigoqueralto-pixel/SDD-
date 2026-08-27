"""ASGI entry point for uvicorn/gunicorn: `app.asgi:app`."""

from app.infrastructure.settings import get_settings
from app.main import create_app

app = create_app(get_settings())
