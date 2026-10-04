"""Lokale Passwort- und Session-Sicherheit fuer MedFlux (STEP 16)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any

PBKDF2_ITERATIONS = 310_000
PASSWORD_SCHEME = "pbkdf2_sha256"
TOKEN_VERSION = 1


class AuthSecurityError(ValueError):
    pass


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    if len(password) < 10:
        raise AuthSecurityError("Passwort muss mindestens 10 Zeichen lang sein.")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{PASSWORD_SCHEME}${PBKDF2_ITERATIONS}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_b64, expected_b64 = encoded.split("$", 3)
        if scheme != PASSWORD_SCHEME:
            return False
        rounds = int(iterations)
        if rounds < 100_000 or rounds > 2_000_000:
            return False
        salt = _b64d(salt_b64)
        expected = _b64d(expected_b64)
    except (TypeError, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return hmac.compare_digest(actual, expected)


def _sign(payload_b64: str, secret: str) -> str:
    return _b64e(hmac.new(secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).digest())


def create_session_token(*, user_id: str, organization_id: str, role: str, secret: str, ttl_seconds: int) -> str:
    if not secret or secret == "change-me":
        raise AuthSecurityError("Unsicheres APP_SECRET_KEY.")
    now = int(time.time())
    payload = {
        "v": TOKEN_VERSION,
        "sub": user_id,
        "org": organization_id,
        "role": role,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    encoded = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{encoded}.{_sign(encoded, secret)}"


def decode_session_token(token: str, *, secret: str, now: int | None = None) -> dict[str, Any]:
    try:
        encoded, signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthSecurityError("Ungueltige Sitzung.") from exc
    if not hmac.compare_digest(signature, _sign(encoded, secret)):
        raise AuthSecurityError("Ungueltige Sitzung.")
    try:
        payload = json.loads(_b64d(encoded).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AuthSecurityError("Ungueltige Sitzung.") from exc
    current = int(time.time()) if now is None else now
    if payload.get("v") != TOKEN_VERSION or not isinstance(payload.get("exp"), int):
        raise AuthSecurityError("Ungueltige Sitzung.")
    if payload["exp"] <= current:
        raise AuthSecurityError("Sitzung abgelaufen.")
    for key in ("sub", "org", "role"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise AuthSecurityError("Ungueltige Sitzung.")
    return payload
