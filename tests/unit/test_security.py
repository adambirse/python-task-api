"""Unit tests for pure functions: no fixtures, no mocks, just input and output."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.exceptions import AuthenticationError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "unit-test-secret-key-long-enough"
ALG = "HS256"


def test_hash_password_does_not_store_plain_text():
    hashed = hash_password("s3cret-password")

    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_same_password_hashes_differently_each_time():
    # A random salt per hash means identical passwords don't look identical in the DB.
    assert hash_password("same-password") != hash_password("same-password")


def test_token_round_trip():
    token = create_access_token(
        user_id=42, role="admin", secret_key=SECRET, algorithm=ALG, expires_in=timedelta(minutes=5)
    )

    payload = decode_access_token(token, secret_key=SECRET, algorithm=ALG)

    assert payload.user_id == 42
    assert payload.role == "admin"


def test_expired_token_is_rejected():
    an_hour_ago = datetime.now(UTC) - timedelta(hours=1)
    token = create_access_token(
        user_id=1,
        role="user",
        secret_key=SECRET,
        algorithm=ALG,
        expires_in=timedelta(minutes=5),
        now=an_hour_ago,
    )

    with pytest.raises(AuthenticationError, match="expired"):
        decode_access_token(token, secret_key=SECRET, algorithm=ALG)


def test_token_signed_with_another_key_is_rejected():
    token = create_access_token(
        user_id=1,
        role="admin",
        secret_key="an-attackers-own-secret-key-also-long",
        algorithm=ALG,
        expires_in=timedelta(minutes=5),
    )

    with pytest.raises(AuthenticationError, match="Invalid"):
        decode_access_token(token, secret_key=SECRET, algorithm=ALG)


def test_unsigned_token_is_rejected():
    # The "alg: none" attack: a token with no signature at all.
    token = jwt.encode({"sub": "1", "role": "admin"}, key=None, algorithm="none")

    with pytest.raises(AuthenticationError):
        decode_access_token(token, secret_key=SECRET, algorithm=ALG)


@pytest.mark.parametrize("garbage", ["", "not-a-jwt", "a.b.c"])
def test_malformed_tokens_are_rejected(garbage):
    with pytest.raises(AuthenticationError):
        decode_access_token(garbage, secret_key=SECRET, algorithm=ALG)
