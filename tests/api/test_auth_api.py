"""API tests for authentication: the whole stack, over HTTP, on an in-memory DB."""

from app.api.deps import get_current_user
from app.domain.models import User


def test_register_returns_user_without_password(client):
    response = client.post("/auth/register", json={"username": "alice", "password": "password-123"})

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert body["role"] == "user"
    assert "password" not in body and "password_hash" not in body


def test_register_duplicate_username_is_409(client):
    payload = {"username": "alice", "password": "password-123"}
    client.post("/auth/register", json=payload)

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 409


def test_register_validates_input(client):
    response = client.post("/auth/register", json={"username": "a", "password": "short"})

    assert response.status_code == 422  # Pydantic rejected it before our code ran
    fields = {err["loc"][-1] for err in response.json()["detail"]}
    assert fields == {"username", "password"}


def test_login_with_bad_password_is_401(client):
    client.post("/auth/register", json={"username": "alice", "password": "password-123"})

    response = client.post("/auth/token", data={"username": "alice", "password": "nope-nope"})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_me_returns_the_logged_in_user(client, alice):
    response = client.get("/auth/me", headers=alice)

    assert response.status_code == 200
    assert response.json()["username"] == "alice"


def test_me_without_token_is_401(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_garbage_token_is_401(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_dependency_override_example(client):
    """`dependency_overrides` swaps any dependency for the duration of a test.

    Here we skip real authentication entirely and pretend a user is logged in.
    Handy when a test is about something else and auth is just noise.
    """
    fake_user = User(id=123, username="pretend", password_hash="x")
    client.app.dependency_overrides[get_current_user] = lambda: fake_user
    try:
        response = client.get("/auth/me")
    finally:
        client.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["username"] == "pretend"
