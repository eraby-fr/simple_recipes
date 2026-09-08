from datetime import timedelta, timezone, datetime

import pytest

from app.auth import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.config import settings


class TestPasswordHashing:
    def test_correct_password_verifies(self):
        hashed = hash_password("monmotdepasse")
        assert verify_password("monmotdepasse", hashed) is True

    def test_wrong_password_rejected(self):
        hashed = hash_password("motdepasse-correct")
        assert verify_password("mauvais-motdepasse", hashed) is False

    def test_hash_differs_from_plaintext(self):
        password = "monmotdepasse"
        assert hash_password(password) != password

    def test_same_password_produces_different_hashes(self):
        h1 = hash_password("same-password")
        h2 = hash_password("same-password")
        assert h1 != h2

    def test_hash_is_verifiable(self):
        for password in ["abc12345", "P@ssw0rd!", "très-long-mot-de-passe-sécurisé"]:
            assert verify_password(password, hash_password(password))


class TestJWT:
    def test_create_and_decode_valid_token(self):
        token = create_access_token({"sub": "1", "username": "alice"})
        data = decode_token(token)
        assert data is not None
        assert data.user_id == 1
        assert data.username == "alice"

    def test_invalid_token_returns_none(self):
        assert decode_token("invalid.token.value") is None

    def test_tampered_token_returns_none(self):
        token = create_access_token({"sub": "1", "username": "alice"})
        tampered = token + "x"
        assert decode_token(tampered) is None

    def test_expired_token_returns_none(self):
        token = create_access_token(
            {"sub": "1", "username": "alice"},
            expires_delta=timedelta(seconds=-1),
        )
        assert decode_token(token) is None

    def test_missing_sub_returns_none(self):
        token = create_access_token({"username": "alice"})
        assert decode_token(token) is None

    def test_missing_username_returns_none(self):
        token = create_access_token({"sub": "1"})
        assert decode_token(token) is None

    def test_empty_string_returns_none(self):
        assert decode_token("") is None

    def test_default_expiry_is_three_months(self):
        before = datetime.now(timezone.utc).replace(microsecond=0)
        token = create_access_token({"sub": "1", "username": "alice"})
        after = datetime.now(timezone.utc)
        import jwt as pyjwt
        payload = pyjwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected_delta = timedelta(minutes=settings.access_token_expire_minutes)
        assert before + expected_delta <= exp <= after + expected_delta + timedelta(seconds=5)
        assert settings.access_token_expire_minutes == 60 * 24 * 90  # 3 months
