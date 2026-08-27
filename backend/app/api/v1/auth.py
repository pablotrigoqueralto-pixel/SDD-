"""Authentication endpoints: login, refresh, logout, password change."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from app.api.deps import CurrentUser, SettingsDep, get_auth_service
from app.api.rate_limit import auth_rate_limit, limiter
from app.application.auth.service import AuthService, ClientInfo, Session
from app.domain.users.value_objects import Email
from app.infrastructure.settings import Settings
from app.schemas.auth import LoginRequest, PasswordChangeRequest, TokenResponse
from app.schemas.users import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def client_info(request: Request) -> ClientInfo:
    return ClientInfo(
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )


def set_refresh_cookie(response: Response, raw_token: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_token,
        max_age=settings.refresh_token_ttl_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.environment in {"staging", "prod"},
        samesite="strict",
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


def token_response(session: Session) -> TokenResponse:
    return TokenResponse(
        access_token=session.access_token,
        expires_in=session.expires_in,
        user=UserRead.from_entity(session.user),
    )


@router.post("/login", response_model=TokenResponse, summary="Log in with email and password")
@limiter.limit(auth_rate_limit)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> TokenResponse:
    session = await service.login(Email(payload.email), payload.password, client_info(request))
    set_refresh_cookie(response, session.refresh_token, settings)
    return token_response(session)


@router.post("/refresh", response_model=TokenResponse, summary="Rotate the refresh token")
@limiter.limit(auth_rate_limit)
async def refresh(
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    refresh_token: RefreshCookie = None,
) -> TokenResponse:
    if refresh_token is None:
        from app.domain.shared.errors import UnauthenticatedError

        raise UnauthenticatedError("Missing refresh token")
    session = await service.refresh(refresh_token, client_info(request))
    set_refresh_cookie(response, session.refresh_token, settings)
    return token_response(session)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Log out")
async def logout(
    response: Response,
    user: CurrentUser,
    service: AuthServiceDep,
    refresh_token: RefreshCookie = None,
) -> None:
    await service.logout(refresh_token, actor_id=user.id)
    clear_refresh_cookie(response)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT, summary="Change the own password")
async def change_password(
    payload: PasswordChangeRequest,
    user: CurrentUser,
    service: AuthServiceDep,
    refresh_token: RefreshCookie = None,
) -> None:
    await service.change_password(
        user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        keep_refresh_token=refresh_token,
    )
