"""Shared fixtures.

pytest injects fixtures by parameter name, which is the testing equivalent of
dependency injection: each test declares what it needs and gets a fresh copy.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core import security
from app.core.config import Settings
from app.db.base import Base
from app.main import create_app

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin-password-123"


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """bcrypt is slow on purpose. 4 rounds (the minimum) keeps the suite fast."""
    monkeypatch.setattr(security, "BCRYPT_ROUNDS", 4)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        jwt_secret_key="test-secret-key-that-is-long-enough",
        access_token_expire_minutes=5,
        seed_admin_username=ADMIN_USERNAME,
        seed_admin_password=ADMIN_PASSWORD,
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    """A full app over a brand new in-memory database for every test."""
    app = create_app(settings)
    # Tests create the schema directly. Real deployments use `alembic upgrade head`.
    Base.metadata.create_all(app.state.engine)
    with TestClient(app) as test_client:  # `with` runs the startup/shutdown lifespan
        yield test_client
    # Leaving the `with` ran shutdown, which disposed the engine and so threw
    # away the in-memory database. Nothing to clean up.


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/auth/token", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def register_and_login(
    client: TestClient, username: str, password: str = "password-123"
) -> dict[str, str]:
    response = client.post("/auth/register", json={"username": username, "password": password})
    assert response.status_code == 201, response.text
    return login(client, username, password)


@pytest.fixture
def alice(client: TestClient) -> dict[str, str]:
    """Auth headers for an ordinary user."""
    return register_and_login(client, "alice")


@pytest.fixture
def bob(client: TestClient) -> dict[str, str]:
    return register_and_login(client, "bob")


@pytest.fixture
def admin(client: TestClient) -> dict[str, str]:
    return login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
