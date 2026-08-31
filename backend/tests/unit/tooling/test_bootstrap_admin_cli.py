"""CLI contract of the production first-admin bootstrap."""

import pytest

from app.tooling import bootstrap_admin


def test_requires_email(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "a-long-enough-passphrase")

    assert bootstrap_admin.main() == 2
    assert "BOOTSTRAP_ADMIN_EMAIL" in capsys.readouterr().err


def test_requires_password(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "direccion@quermed.com")
    monkeypatch.delenv("BOOTSTRAP_ADMIN_PASSWORD", raising=False)

    assert bootstrap_admin.main() == 2
    assert "BOOTSTRAP_ADMIN_PASSWORD" in capsys.readouterr().err


def test_runs_with_both_variables(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: dict[str, str] = {}

    async def fake_run(email: str, password: str) -> str:
        seen["email"] = email
        seen["password"] = password
        return "created"

    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "direccion@quermed.com")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "a-long-enough-passphrase")
    monkeypatch.setattr(bootstrap_admin, "run", fake_run)

    assert bootstrap_admin.main() == 0
    assert seen == {"email": "direccion@quermed.com", "password": "a-long-enough-passphrase"}
    assert "created" in capsys.readouterr().out
