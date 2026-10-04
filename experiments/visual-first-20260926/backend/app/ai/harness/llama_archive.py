"""LlamaIndex-backed, rebuildable lexical archive for the isolated MedFlux prototype.

Explicitly no embeddings or LLM. The index holds verified text nodes only.
Search requires tenant and a document allowlist supplied by the MedFlux ACL layer.
This module cannot grant permissions or change the production database.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from llama_index.core.schema import TextNode
from llama_index.core.storage.docstore.simple_docstore import SimpleDocumentStore


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


class LlamaArchive:
    def __init__(self):
        self._stores: dict[str, SimpleDocumentStore] = {}

    @staticmethod
    def _validate(tenant: str, records: list[VerifiedRecord]) -> None:
        if not tenant:
            raise ValueError("tenant required")
        for record in records:
            if (record.tenant != tenant or not record.verified or
                not record.document_id or not record.revision or
                record.page < 1 or not record.label or
                not record.source_quote or len(record.source_sha256) != 64 or
                not all(c in "0123456789abcdef" for c in record.source_sha256)):
                raise ValueError("unverified or cross-tenant evidence rejected")

    def rebuild(self, tenant: str, records: list[VerifiedRecord]) -> int:
        """Atomically replace one tenant's derived index; no production DB writes."""
        self._validate(tenant, records)
        store = SimpleDocumentStore()
        nodes = []
        seen = set()
        for record in records:
            key = (record.document_id, record.revision, record.page,
                   record.field, record.source_quote)
            if key in seen:
                continue
            seen.add(key)
            node_id = hashlib.sha256(repr((tenant, *key)).encode()).hexdigest()
            nodes.append(TextNode(
                id_=node_id,
                text="\n".join((record.field, record.label,
                                 record.value, record.source_quote)),
                metadata={
                    "tenant": tenant, "document_id": record.document_id,
                    "revision": record.revision, "page": record.page,
                    "field": record.field, "label": record.label,
                    "value": record.value, "source_quote": record.source_quote,
                    "source_sha256": record.source_sha256,
                },
            ))
        if nodes:
            store.add_documents(nodes)
        self._stores[tenant] = store
        return len(nodes)

    def search(self, tenant: str, allowed_documents: set[str], query: str,
               limit: int = 20) -> list[dict]:
        """All terms must occur in authorized node text, case-insensitively."""
        if not tenant or not allowed_documents or not query.strip():
            return []
        if limit < 1 or limit > 100:
            raise ValueError("invalid search limit")
        store = self._stores.get(tenant)
        if store is None:
            return []
        terms = query.casefold().split()
        results = []
        for doc_id, node in sorted(store.docs.items()):
            meta = node.metadata
            if (meta.get("tenant") != tenant or
                meta.get("document_id") not in allowed_documents):
                continue
            if all(term in node.text.casefold() for term in terms):
                # Only permitted, fixed metadata from verified source is returned.
                results.append({
                    "document_id": meta["document_id"],
                    "revision": meta["revision"],
                    "page": meta["page"],
                    "field": meta["field"],
                    "label": meta["label"],
                    "value": meta["value"],
                    "source_quote": meta["source_quote"],
                    "source_sha256": meta["source_sha256"],
                })
                if len(results) >= limit:
                    break
        return results
