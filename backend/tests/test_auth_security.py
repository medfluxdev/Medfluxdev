from __future__ import annotations

import pytest

from app.auth.security import (
    AuthSecurityError,
    create_session_token,
    decode_session_token,
    hash_password,
    verify_password,
)

SECRET = "unit-test-secret-that-is-not-a-production-secret"


def test_password_hash_is_salted_and_verifies():
    first = hash_password("Klinik-Passwort-123!")
    second = hash_password("Klinik-Passwort-123!")

    assert first != second
    assert verify_password("Klinik-Passwort-123!", first) is True
    assert verify_password("falsch", first) is False


def test_password_rejects_too_short_value():
    with pytest.raises(AuthSecurityError):
        hash_password("kurz")


def test_session_token_round_trip_and_expiry(monkeypatch):
    monkeypatch.setattr("app.auth.security.time.time", lambda: 1_000)
    token = create_session_token(
        user_id="11111111-1111-1111-1111-111111111111",
        organization_id="22222222-2222-2222-2222-222222222222",
        role="reviewer",
        secret=SECRET,
        ttl_seconds=600,
    )

    payload = decode_session_token(token, secret=SECRET, now=1_001)
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"
    assert payload["org"] == "22222222-2222-2222-2222-222222222222"
    assert payload["role"] == "reviewer"

    with pytest.raises(AuthSecurityError, match="abgelaufen"):
        decode_session_token(token, secret=SECRET, now=1_600)


def test_session_token_rejects_tampering():
    token = create_session_token(
        user_id="11111111-1111-1111-1111-111111111111",
        organization_id="22222222-2222-2222-2222-222222222222",
        role="viewer",
        secret=SECRET,
        ttl_seconds=600,
    )
    payload, signature = token.split(".", 1)
    replacement = "A" if payload[-1] != "A" else "B"
    tampered = payload[:-1] + replacement + "." + signature

    with pytest.raises(AuthSecurityError):
        decode_session_token(tampered, secret=SECRET)


def test_session_token_rejects_default_secret():
    with pytest.raises(AuthSecurityError, match="APP_SECRET_KEY"):
        create_session_token(
            user_id="u",
            organization_id="o",
            role="viewer",
            secret="change-me",
            ttl_seconds=600,
        )
