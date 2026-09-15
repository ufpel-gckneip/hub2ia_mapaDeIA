"""JWT auth: short-lived access token + refresh token (TODO #6).

Replaces fastapi-users' built-in login route so that `/auth/jwt/login` returns
both an access token (short TTL, used as the Bearer token) and a refresh token
(longer TTL). `/auth/jwt/refresh` exchanges a valid refresh token for a new
access token. The two token types use different JWT audiences and cannot be
substituted for one another.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.users import get_jwt_strategy, get_refresh_strategy, get_user_manager

router = APIRouter(prefix="/auth/jwt", tags=["auth"])


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenPair)
async def login(
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager=Depends(get_user_manager),
):
    """Verify credentials (OAuth2 password form) and issue an access+refresh pair."""
    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="LOGIN_BAD_CREDENTIALS")
    access = await get_jwt_strategy().write_token(user)
    refresh = await get_refresh_strategy().write_token(user)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=AccessToken)
async def refresh(body: RefreshRequest, user_manager=Depends(get_user_manager)):
    """Exchange a valid, active-user refresh token for a fresh access token."""
    user = await get_refresh_strategy().read_token(body.refresh_token, user_manager)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="INVALID_REFRESH_TOKEN")
    access = await get_jwt_strategy().write_token(user)
    return AccessToken(access_token=access)
