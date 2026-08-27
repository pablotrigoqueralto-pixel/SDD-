import pytest
from httpx import AsyncClient

from app.api.rate_limit import limiter
from app.domain.users.roles import Role
from tests.integration.api.conftest import PASSWORD, Users

pytestmark = pytest.mark.integration

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
PASSWORD_URL = "/api/v1/auth/password"


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = await client.post(LOGIN, json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_login_success_sets_refresh_cookie(client: AsyncClient, users: Users) -> None:
    user = await users.create(Role.SALES_REP, email="Ana@Quermed.com")

    response = await client.post(LOGIN, json={"email": "ana@quermed.com", "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["user"]["id"] == str(user.id)
    assert "password" not in body["user"]
    set_cookie = response.headers["set-cookie"]
    assert "refresh_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie


async def test_login_invalid_credentials(client: AsyncClient, users: Users) -> None:
    await users.create(Role.SALES_REP, email="ana@quermed.com")

    wrong = await client.post(LOGIN, json={"email": "ana@quermed.com", "password": "nope-nope"})
    unknown = await client.post(LOGIN, json={"email": "who@quermed.com", "password": PASSWORD})

    assert wrong.status_code == 401 and wrong.json()["code"] == "invalid_credentials"
    assert unknown.status_code == 401 and unknown.json()["code"] == "invalid_credentials"
    assert wrong.json()["detail"] == unknown.json()["detail"]


async def test_login_inactive_user_indistinguishable(client: AsyncClient, users: Users) -> None:
    await users.create(Role.SALES_REP, email="ana@quermed.com", is_active=False)

    response = await client.post(LOGIN, json={"email": "ana@quermed.com", "password": PASSWORD})

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


async def test_login_validation_error(client: AsyncClient) -> None:
    response = await client.post(LOGIN, json={"email": "x"})

    assert response.status_code == 422
    assert {e["field"] for e in response.json()["errors"]} == {"email", "password"}


async def test_tenth_failure_locks_account(client: AsyncClient, users: Users) -> None:
    await users.create(Role.SALES_REP, email="ana@quermed.com")
    for _ in range(10):
        response = await client.post(
            LOGIN, json={"email": "ana@quermed.com", "password": "bad-bad"}
        )
        assert response.status_code == 401
    limiter.reset()  # lockout, not the rate limit, is under test here

    locked = await client.post(LOGIN, json={"email": "ana@quermed.com", "password": PASSWORD})

    assert locked.status_code == 401
    assert locked.json()["code"] == "account_locked"


async def test_rate_limit_on_login(client: AsyncClient) -> None:
    for _ in range(10):
        response = await client.post(LOGIN, json={"email": "x@quermed.com", "password": "bad-bad"})
        assert response.status_code == 401

    limited = await client.post(LOGIN, json={"email": "x@quermed.com", "password": "bad-bad"})

    assert limited.status_code == 429
    assert limited.json()["code"] == "rate_limited"
    assert "retry-after" in limited.headers


async def test_refresh_rotates_and_detects_reuse(client: AsyncClient, users: Users) -> None:
    await users.create(Role.SALES_REP, email="ana@quermed.com")
    await login(client, "ana@quermed.com")
    first_cookie = client.cookies.get("refresh_token", path="/api/v1/auth")

    refreshed = await client.post(REFRESH)
    assert refreshed.status_code == 200
    second_cookie = client.cookies.get("refresh_token", path="/api/v1/auth")
    assert second_cookie and second_cookie != first_cookie

    client.cookies.set("refresh_token", first_cookie or "", path="/api/v1/auth")
    reused = await client.post(REFRESH)
    assert reused.status_code == 401
    assert reused.json()["code"] == "unauthenticated"

    client.cookies.set("refresh_token", second_cookie, path="/api/v1/auth")
    family_revoked = await client.post(REFRESH)
    assert family_revoked.status_code == 401


async def test_refresh_without_cookie(client: AsyncClient) -> None:
    response = await client.post(REFRESH)

    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"


async def test_logout_revokes_refresh_token(client: AsyncClient, users: Users) -> None:
    await users.create(Role.SALES_REP, email="ana@quermed.com")
    headers = await login(client, "ana@quermed.com")
    cookie = client.cookies.get("refresh_token", path="/api/v1/auth")

    response = await client.post(LOGOUT, headers=headers)

    assert response.status_code == 204
    assert 'refresh_token=""' in response.headers["set-cookie"]
    client.cookies.set("refresh_token", cookie or "", path="/api/v1/auth")
    assert (await client.post(REFRESH)).status_code == 401


async def test_change_password_flow(client: AsyncClient, users: Users) -> None:
    await users.create(Role.SALES_REP, email="ana@quermed.com")
    headers = await login(client, "ana@quermed.com")

    wrong = await client.post(
        PASSWORD_URL,
        json={"current_password": "nope", "new_password": "new-passphrase-2026"},
        headers=headers,
    )
    short = await client.post(
        PASSWORD_URL, json={"current_password": PASSWORD, "new_password": "short"}, headers=headers
    )
    ok = await client.post(
        PASSWORD_URL,
        json={"current_password": PASSWORD, "new_password": "new-passphrase-2026"},
        headers=headers,
    )

    assert wrong.status_code == 400 and wrong.json()["code"] == "invalid_current_password"
    assert short.status_code == 422
    assert short.json()["errors"][0] == {
        "field": "new_password",
        "message": "Password must have at least 12 characters",
        "code": "password_too_short",
    }
    assert ok.status_code == 204
    assert (await client.post(REFRESH)).status_code == 200  # current session kept
    await login(client, "ana@quermed.com", "new-passphrase-2026")


async def test_protected_endpoint_requires_valid_token(client: AsyncClient, users: Users) -> None:
    missing = await client.get("/api/v1/me")
    bad = await client.get("/api/v1/me", headers={"Authorization": "Bearer nope"})

    assert missing.status_code == 401 and missing.json()["code"] == "unauthenticated"
    assert bad.status_code == 401 and bad.json()["code"] == "unauthenticated"


async def test_token_of_deactivated_user_is_rejected(client: AsyncClient, users: Users) -> None:
    user = await users.create(Role.SALES_REP, is_active=False)

    response = await client.get("/api/v1/me", headers=users.headers(user))

    assert response.status_code == 401
