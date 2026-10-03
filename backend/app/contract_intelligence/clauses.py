"""Clause library and explainable fingerprinting."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ClauseFingerprint:
    normalized_text: str
    fingerprint: str


def normalize_clause(text: str) -> str:
    value = " ".join(str(text or "").lower().split())
    value = re.sub(r"\b\d+(?:[.,]\d+)?\b", "<num>", value)
    return value


def fingerprint_clause(text: str) -> ClauseFingerprint:
    normalized = normalize_clause(text)
    return ClauseFingerprint(
        normalized_text=normalized,
        fingerprint=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    )
