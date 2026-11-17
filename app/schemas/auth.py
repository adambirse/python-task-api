"""Request/response schemas (DTOs) for auth and users.

Pydantic validates incoming JSON before any of our code runs, and response
models control exactly which fields go back out (password_hash never leaves).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import Role


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    # from_attributes lets Pydantic read fields off our domain dataclasses.
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Role
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Lifetime in seconds")
