"""Dependency-free archive transfer record. No LlamaIndex import during normal app startup."""
from dataclasses import dataclass

@dataclass(frozen=True)
class VerifiedRecord:
    tenant: str
    document_id: str
    revision: str
    page: int
    field: str
    label: str
    value: str
    source_quote: str
    source_sha256: str
    verified: bool