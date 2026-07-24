"""Email/password registration, login, and current-user API routes."""

from __future__ import annotations

import re
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pymongo.errors import DuplicateKeyError

from app.auth.jwt import CurrentUser, create_access_token, hash_password, verify_password
from app.config import Settings, get_settings
from app.db.models import PushSubscription, User


router = APIRouter(prefix="/auth", tags=["authentication"])
_DUMMY_PASSWORD_HASH = hash_password("MedVault-Dummy-Password-9!")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        requirements = (
            re.search(r"[a-z]", value),
            re.search(r"[A-Z]", value),
            re.search(r"\d", value),
            re.search(r"[^A-Za-z0-9]", value),
        )
        if not all(requirements):
            raise ValueError(
                "Password must include lowercase, uppercase, number, and special characters"
            )
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: PydanticObjectId
    email: EmailStr
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


def normalize_email(email: EmailStr | str) -> str:
    return str(email).strip().lower()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> User:
    email = normalize_email(payload.email)
    if await User.find_one(User.email == email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(email=email, hashed_password=hash_password(payload.password))
    try:
        await user.insert()
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        ) from exc
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = await User.find_one(User.email == normalize_email(payload.email))
    password_matches = verify_password(
        payload.password,
        user.hashed_password if user is not None else _DUMMY_PASSWORD_HASH,
    )
    if user is None or not password_matches or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(str(user.id), settings)
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def read_current_user(current_user: CurrentUser) -> User:
    return current_user


class PushSubscriptionRequest(PushSubscription):
    pass


@router.post("/push/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def subscribe_push(payload: PushSubscriptionRequest, current_user: CurrentUser) -> None:
    if not payload.endpoint.startswith("https://"):
        raise HTTPException(status_code=422, detail="Push endpoint must use HTTPS")
    current_user.push_subscription = PushSubscription.model_validate(payload)
    await current_user.save()


@router.delete("/push/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe_push(current_user: CurrentUser) -> None:
    """Remove the current browser subscription when the user disables notifications."""

    current_user.push_subscription = None
    await current_user.save()
