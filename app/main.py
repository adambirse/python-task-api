"""Application factory.

`create_app(settings)` builds a fresh app. Production calls it with settings
from the environment; tests call it with an in-memory database.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api.routes import admin, auth, health, tasks
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    ForbiddenError,
    NotFoundError,
)
from app.db.session import build_engine, build_session_factory, unit_of_work
from app.repositories.sqlalchemy import SqlAlchemyUserRepository
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

# One table that maps domain errors to HTTP. Adding a new error type is one line.
_STATUS_FOR_ERROR: dict[type[DomainError], int] = {
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    ForbiddenError: status.HTTP_403_FORBIDDEN,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
}


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    code = next(
        (c for err, c in _STATUS_FOR_ERROR.items() if isinstance(exc, err)),
        status.HTTP_400_BAD_REQUEST,
    )
    headers = {"WWW-Authenticate": "Bearer"} if code == status.HTTP_401_UNAUTHORIZED else None
    return JSONResponse(status_code=code, content={"detail": exc.message}, headers=headers)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Startup. Schema changes are applied by Alembic (`alembic upgrade head`),
        # not here: the app should never silently alter a production database.
        if settings.seed_admin_username and settings.seed_admin_password:
            with unit_of_work(session_factory) as session:
                AuthService(SqlAlchemyUserRepository(session), settings).ensure_admin_exists(
                    settings.seed_admin_username, settings.seed_admin_password
                )
            logger.info("Seeded admin user %s", settings.seed_admin_username)
        yield
        # Shutdown: release pooled connections.
        engine.dispose()

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory

    app.add_exception_handler(DomainError, domain_error_handler)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(tasks.router)
    app.include_router(admin.router)
    return app


app = create_app()
