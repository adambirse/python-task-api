"""Dependency injection wiring.

FastAPI's `Depends` builds a small object graph per request:

    Session -> Repository -> Service -> route

Each piece only asks for what it needs, and tests can replace any piece with
`app.dependency_overrides[...]`. This file is the "composition root": the one
place that knows which concrete classes are used.
"""

from collections.abc import Callable, Iterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import ForbiddenError
from app.db.session import session_scope
from app.domain.models import Role, User
from app.repositories.sqlalchemy import SqlAlchemyTaskRepository, SqlAlchemyUserRepository
from app.services.auth_service import AuthService
from app.services.task_service import TaskService

# Tells FastAPI (and the Swagger "Authorize" button) where tokens come from.
# It reads the "Authorization: Bearer <token>" header and returns 401 if missing.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_settings(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


def get_db_session(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.session_factory)


SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[Session, Depends(get_db_session)]


def get_auth_service(session: SessionDep, settings: SettingsDep) -> AuthService:
    return AuthService(SqlAlchemyUserRepository(session), settings)


def get_task_service(session: SessionDep) -> TaskService:
    return TaskService(SqlAlchemyTaskRepository(session))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], auth: AuthServiceDep) -> User:
    """Authentication: turn a bearer token into a User, or fail with 401."""
    return auth.get_user_from_token(token)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: Role) -> Callable[[User], User]:
    """Role-based authorisation, as a dependency factory.

    Usage: `admin: Annotated[User, Depends(require_role(Role.ADMIN))]`
    or on a whole router: `APIRouter(dependencies=[Depends(require_role(Role.ADMIN))])`.
    """

    def checker(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("You don't have permission to do this")
        return user

    return checker
