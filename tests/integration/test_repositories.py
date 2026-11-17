"""Repository contract tests.

The same tests run against BOTH implementations: the SQLAlchemy one and the
in-memory fake used by the unit tests. If they pass for both, we can trust that
unit tests using the fake reflect real behaviour.

The SQLAlchemy repository runs on in-memory SQLite by default. Set
TEST_DATABASE_URL to a PostgreSQL URL (CI does) to also run it on Postgres.
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import build_engine, build_session_factory
from app.domain.models import Role, Task, TaskStatus, User
from app.repositories.memory import InMemoryTaskRepository, InMemoryUserRepository
from app.repositories.sqlalchemy import SqlAlchemyTaskRepository, SqlAlchemyUserRepository

DATABASE_URLS = {"sqlite": "sqlite:///:memory:"}
if postgres_url := os.environ.get("TEST_DATABASE_URL"):
    DATABASE_URLS["postgres"] = postgres_url


@contextmanager
def open_session(url: str) -> Iterator[Session]:
    engine = build_engine(url)
    Base.metadata.create_all(engine)
    session = build_session_factory(engine)()
    try:
        yield session
    finally:
        session.rollback()  # nothing is committed, so the database is left clean
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(params=["memory", *DATABASE_URLS])
def repos(request):
    if request.param == "memory":
        yield InMemoryUserRepository(), InMemoryTaskRepository()
        return
    with open_session(DATABASE_URLS[request.param]) as session:
        yield SqlAlchemyUserRepository(session), SqlAlchemyTaskRepository(session)


@pytest.fixture
def owner(repos) -> User:
    users, _ = repos
    return users.add(User(username="alice", password_hash="hash"))


def test_user_add_assigns_id_and_can_be_found(repos):
    users, _ = repos

    saved = users.add(User(username="bob", password_hash="hash", role=Role.ADMIN))

    assert saved.id is not None
    assert users.get_by_id(saved.id) == saved
    assert users.get_by_username("bob") == saved
    assert users.get_by_username("nobody") is None


def test_task_crud(repos, owner):
    _, tasks = repos

    created = tasks.add(Task(title="One", owner_id=owner.id))
    assert tasks.get_by_id(created.id).title == "One"

    created.title = "Renamed"
    created.status = TaskStatus.DONE
    tasks.update(created)
    reloaded = tasks.get_by_id(created.id)
    assert (reloaded.title, reloaded.status) == ("Renamed", TaskStatus.DONE)

    tasks.delete(created.id)
    assert tasks.get_by_id(created.id) is None


def test_task_list_filters_and_paginates(repos, owner):
    users, tasks = repos
    other = users.add(User(username="carol", password_hash="hash"))
    for i in range(5):
        tasks.add(Task(title=f"alice-{i}", owner_id=owner.id))
    tasks.add(Task(title="carol-0", owner_id=other.id, status=TaskStatus.DONE))

    assert len(tasks.list()) == 6
    assert len(tasks.list(owner_id=owner.id)) == 5
    assert [t.title for t in tasks.list(status=TaskStatus.DONE)] == ["carol-0"]
    page = tasks.list(owner_id=owner.id, limit=2, offset=2)
    assert [t.title for t in page] == ["alice-2", "alice-3"]
