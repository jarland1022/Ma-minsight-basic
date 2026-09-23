"""Auth service tests."""

from uuid import uuid4

import jwt
import pytest

from app.core.config import settings
from app.services.auth import (
    JWT_ALGORITHM,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_create_and_decode() -> None:
    user_id = uuid4()
    token = create_access_token(user_id=user_id, username="admin", is_admin=True)
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["username"] == "admin"
    assert payload["is_admin"] is True


def test_jwt_invalid_secret() -> None:
    token = create_access_token(user_id=uuid4(), username="u", is_admin=False)
    with pytest.raises(jwt.PyJWTError):
        jwt.decode(token, "wrong-secret", algorithms=[JWT_ALGORITHM])
