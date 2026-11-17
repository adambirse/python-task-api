"""Unit tests for AuthService.

Two styles of test double are shown side by side:

* A **fake** (InMemoryUserRepository) is a real, working implementation. You
  check the *resulting state*: "after registering, the user can be found".
* A **mock** (unittest.mock) records calls. You check the *interaction*:
  "add() was never called". Useful when the thing you care about is a side
  effect that didn't (or did) happen.

Prefer fakes for most tests, since they break less when internals change.
Reach for mocks when the interaction itself is the behaviour under test.
"""

from unittest.mock import create_autospec

import pytest

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import hash_password
from app.domain.models import Role, User
from app.repositories.interfaces import UserRepository
from app.repositories.memory import InMemoryUserRepository
from app.schemas.auth import UserCreate
from app.services.auth_service import AuthService


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret_key="unit-test-secret-key-long-enough")


@pytest.fixture
def users() -> InMemoryUserRepository:
    return InMemoryUserRepository()


@pytest.fixture
def service(users: InMemoryUserRepository, settings: Settings) -> AuthService:
    return AuthService(users, settings)


# ---- fakes: assert on state ------------------------------------------------


def test_register_stores_user_with_hashed_password(service, users):
    user = service.register(UserCreate(username="alice", password="password-123"))

    stored = users.get_by_username("alice")
    assert stored is not None
    assert stored.id == user.id
    assert stored.role == Role.USER
    assert stored.password_hash != "password-123"


def test_register_rejects_duplicate_username(service):
    service.register(UserCreate(username="alice", password="password-123"))

    with pytest.raises(ConflictError):
        service.register(UserCreate(username="alice", password="another-password"))


def test_login_returns_token_that_resolves_back_to_the_user(service):
    user = service.register(UserCreate(username="alice", password="password-123"))

    token = service.login("alice", "password-123")

    assert service.get_user_from_token(token.access_token).id == user.id


@pytest.mark.parametrize(
    ("username", "password"),
    [("alice", "wrong-password"), ("nobody", "password-123")],
    ids=["wrong password", "unknown user"],
)
def test_login_failures_give_the_same_error(service, username, password):
    service.register(UserCreate(username="alice", password="password-123"))

    with pytest.raises(AuthenticationError, match="Incorrect username or password"):
        service.login(username, password)


def test_token_for_deleted_user_is_rejected(settings):
    # Issue a token with one repository, then resolve it against an empty one,
    # which is what the service would see after the user was deleted.
    issuer = AuthService(InMemoryUserRepository(), settings)
    issuer.register(UserCreate(username="alice", password="password-123"))
    token = issuer.login("alice", "password-123").access_token

    with pytest.raises(AuthenticationError, match="no longer exists"):
        AuthService(InMemoryUserRepository(), settings).get_user_from_token(token)


def test_ensure_admin_exists_is_idempotent(service, users):
    service.ensure_admin_exists("admin", "admin-password-123")
    service.ensure_admin_exists("admin", "admin-password-123")

    admin = users.get_by_username("admin")
    assert admin is not None and admin.role == Role.ADMIN


# ---- mocks: assert on interactions ------------------------------------------


def test_duplicate_registration_never_writes(settings):
    # create_autospec builds a mock that has exactly the interface's methods,
    # so a typo like `repo.ad(...)` fails instead of silently passing.
    repo = create_autospec(UserRepository, instance=True)
    repo.get_by_username.return_value = User(username="alice", password_hash="x", id=1)

    with pytest.raises(ConflictError):
        AuthService(repo, settings).register(UserCreate(username="alice", password="password-123"))

    repo.get_by_username.assert_called_once_with("alice")
    repo.add.assert_not_called()


def test_login_looks_up_user_by_username(settings):
    repo = create_autospec(UserRepository, instance=True)
    repo.get_by_username.return_value = User(
        username="alice", password_hash=hash_password("password-123"), id=7
    )

    token = AuthService(repo, settings).login("alice", "password-123")

    assert token.token_type == "bearer"
    repo.get_by_username.assert_called_once_with("alice")
