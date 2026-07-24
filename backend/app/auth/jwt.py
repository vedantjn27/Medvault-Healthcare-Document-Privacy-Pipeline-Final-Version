"""Argon2 password hashing, JWT issuance, authentication, and ownership guards."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from beanie import PydanticObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.config import Settings, get_settings
from app.db.models import User


password_hasher = PasswordHash.recommended()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Hash a password with pwdlib's recommended Argon2 configuration."""

    return password_hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password without exposing hash-library failures to callers."""

    try:
        return password_hasher.verify(password, hashed_password)
    except (TypeError, ValueError):
        return False


def create_access_token(
    subject: str,
    settings: Settings,
    *,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed access token containing only identity and timing claims."""

    issued_at = datetime.now(UTC)
    expires_at = issued_at + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    payload = {
        "sub": subject,
        "iat": issued_at,
        "nbf": issued_at,
        "exp": expires_at,
        "type": "access",
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str, settings: Settings) -> str:
    """Validate a JWT and return its user identifier."""

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "iat", "nbf", "exp", "type"]},
        )
        if payload.get("type") != "access":
            raise InvalidTokenError("Unexpected token type")
        subject = payload.get("sub")
        if not isinstance(subject, str) or not PydanticObjectId.is_valid(subject):
            raise InvalidTokenError("Invalid token subject")
        return subject
    except InvalidTokenError as exc:
        raise authentication_error() from exc


def authentication_error(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    """Resolve an active database user from a bearer token."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise authentication_error()
    user_id = decode_access_token(credentials.credentials, settings)
    user = await User.get(PydanticObjectId(user_id))
    if user is None or not user.is_active:
        raise authentication_error()
    return user


def require_owner(owner_id: PydanticObjectId, current_user: User) -> None:
    """Enforce ownership while avoiding cross-user resource enumeration."""

    if current_user.id is None or owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")


CurrentUser = Annotated[User, Depends(get_current_user)]
