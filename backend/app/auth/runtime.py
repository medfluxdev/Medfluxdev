"""Request-lokaler Auth-Kontext fuer Provenienz ohne globale Benutzerzustände."""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_current_identity: ContextVar[Any | None] = ContextVar("medflux_auth_identity", default=None)


def current_identity():
    return _current_identity.get()


def bind_identity(identity) -> Token:
    return _current_identity.set(identity)


def reset_identity(token: Token) -> None:
    _current_identity.reset(token)
