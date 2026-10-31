from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.app.core.security import UserRole


class DemoLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()


class AuthenticatedProfile(BaseModel):
    id: str
    email: str
    role: UserRole
    display_name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: AuthenticatedProfile
