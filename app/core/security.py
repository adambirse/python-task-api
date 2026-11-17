"""Password hashing and JWT handling.

These are pure functions with no knowledge of HTTP or the database, which makes
them trivial to unit test.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.exceptions import AuthenticationError

# Work factor: each +1 doubles the time to hash. Slow is the point, it makes
# brute-forcing stolen hashes expensive. The test suite lowers this for speed.
BCRYPT_ROUNDS = 12


def hash_password(plain_password: str) -> str:
    """Hash with bcrypt. The salt is generated per password and stored in the hash."""
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt(BCRYPT_ROUNDS)).decode()


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Constant-time comparison, handled by bcrypt."""
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    role: str


def create_access_token(
    *,
    user_id: int,
    role: str,
    secret_key: str,
    algorithm: str,
    expires_in: timedelta,
    now: datetime | None = None,
) -> str:
    """Create a signed JWT.

    `sub` (subject) is the standard claim for "who this token is about". JWT
    requires it to be a string. `now` is injectable so tests can control time.
    """
    issued_at = now or datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "role": role,
        "iat": issued_at,
        "exp": issued_at + expires_in,
    }
    return jwt.encode(claims, secret_key, algorithm=algorithm)


def decode_access_token(token: str, *, secret_key: str, algorithm: str) -> TokenPayload:
    """Verify the signature and expiry, then return the claims we care about.

    Always pass `algorithms` explicitly: never let the token choose its own
    algorithm (the classic "alg: none" attack).
    """
    try:
        claims = jwt.decode(token, secret_key, algorithms=[algorithm])
        return TokenPayload(user_id=int(claims["sub"]), role=str(claims["role"]))
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Token has expired") from exc
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid token") from exc
