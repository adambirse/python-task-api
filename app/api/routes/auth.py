"""Auth controller. Thin on purpose: parse input, call one service method, return."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import AuthServiceDep, CurrentUser
from app.schemas.auth import Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(data: UserCreate, auth: AuthServiceDep) -> UserRead:
    return UserRead.model_validate(auth.register(data))


@router.post("/token", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], auth: AuthServiceDep) -> Token:
    """OAuth2 password flow: form fields `username` and `password`.

    Using the standard form means the Swagger UI "Authorize" button just works.
    """
    return auth.login(form.username, form.password)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
