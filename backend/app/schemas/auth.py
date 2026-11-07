"""Authentication request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    display_name: str = Field(min_length=2, max_length=80)

    @field_validator("display_name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        name = value.strip()
        if len(name) < 2:
            raise ValueError("display_name must contain at least 2 visible characters")
        return name


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class UserOut(ORMModel):
    id: str
    email: str
    display_name: str
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserOut
    csrf_token: str
    expires_at: datetime


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class DeleteAccountRequest(BaseModel):
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)
    confirm: str = Field(description="Type DELETE to confirm")

    @field_validator("confirm")
    @classmethod
    def _confirm(cls, value: str) -> str:
        if value != "DELETE":
            raise ValueError('confirmation must be the exact text "DELETE"')
        return value


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class ApiTokenOut(ORMModel):
    id: str
    name: str
    prefix: str
    scope: str
    created_at: datetime
    last_used_at: datetime | None


class ApiTokenCreated(BaseModel):
    token: str
    record: ApiTokenOut
    warning: str = "This token is shown once. Store it securely; it cannot be retrieved again."
