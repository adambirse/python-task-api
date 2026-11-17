"""Engine and session factory.

One engine per process (it owns the connection pool). One session per request
(it is the unit of work: everything in a request commits or rolls back together).
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        kwargs: dict[str, object] = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in database_url:
            # An in-memory SQLite DB lives only as long as its connection,
            # so share one connection across threads (used by tests).
            kwargs["poolclass"] = StaticPool
        return create_engine(database_url, **kwargs)
    return create_engine(database_url, pool_pre_ping=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: objects stay readable after commit, so the
    # repository can map them to domain entities afterwards.
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session, commit on success, roll back on any error.

    Used as a FastAPI dependency, so the transaction boundary is the request.
    Repositories only `flush()`; they never commit. That way a service that
    touches two repositories still gets one atomic transaction.
    """
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# The same scope as a `with` block, for code outside a request (startup, scripts).
unit_of_work = contextmanager(session_scope)
