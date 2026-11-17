"""Authentication use cases: register, log in, and resolve a token to a user.

Notice there is no `Request`, `HTTPException` or `Session` anywhere in here.
The service only talks to an injected repository and raises domain errors.
"""

from datetime import timedelta

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.domain.models import Role, User
from app.repositories.interfaces import UserRepository
from app.schemas.auth import Token, UserCreate


class AuthService:
    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self._users = users
        self._settings = settings

    def register(self, data: UserCreate, *, role: Role = Role.USER) -> User:
        if self._users.get_by_username(data.username) is not None:
            raise ConflictError(f"Username '{data.username}' is already taken")
        user = User(
            username=data.username,
            password_hash=hash_password(data.password),
            role=role,
        )
        return self._users.add(user)

    def login(self, username: str, password: str) -> Token:
        user = self._users.get_by_username(username)
        # Same error for "no such user" and "wrong password", so an attacker
        # can't use the login endpoint to discover which usernames exist.
        if user is None or not verify_password(password, user.password_hash):
            raise AuthenticationError("Incorrect username or password")

        expires_in = timedelta(minutes=self._settings.access_token_expire_minutes)
        token = create_access_token(
            user_id=user.id,  # type: ignore[arg-type]
            role=user.role.value,
            secret_key=self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm,
            expires_in=expires_in,
        )
        return Token(access_token=token, expires_in=int(expires_in.total_seconds()))

    def get_user_from_token(self, token: str) -> User:
        payload = decode_access_token(
            token,
            secret_key=self._settings.jwt_secret_key,
            algorithm=self._settings.jwt_algorithm,
        )
        # Re-load the user rather than trusting the token alone: a deleted user's
        # token should stop working, and the role comes from the database.
        user = self._users.get_by_id(payload.user_id)
        if user is None:
            raise AuthenticationError("User no longer exists")
        return user

    def ensure_admin_exists(self, username: str, password: str) -> None:
        """Idempotent seed for local demos."""
        if self._users.get_by_username(username) is None:
            self.register(UserCreate(username=username, password=password), role=Role.ADMIN)
