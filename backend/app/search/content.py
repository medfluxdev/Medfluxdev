"""Inhaltssuche ueber alle Vertragsdokumente (§4A) – vollstaendig lokal.

Volltext (deutscher Wortstamm) plus Teilwortsuche (Komposita wie
„Störungshotline“) und eine kleine, feste Synonymliste. Jeder Treffer nennt
Dokument und Seite. Optional ordnet ein lokales Embedding-Modell (Ollama)
inhaltlich aehnliche Seiten zu; ohne Modell bleibt es bei der Textsuche.
"""

from __future__ import annotations

import json
import logging
import math
import re
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import and_, func, literal, or_, select
from sqlalchemy.orm import Session

from app.contracts.detail.recovery import fix_text, load_canonical_pages
from app.core.config import settings
from app.database.models import Contract
from app.database.models.content_search import ContractTextPage
from app.database.models.contract import ContractDocument
from app.database.models.document import DocumentFile, DocumentVersion

logger = logging.getLogger(__name__)

SYNONYMS: tuple[tuple[str, ...], ...] = (
    ("hotline", "störungsannahme", "helpdesk", "service-hotline", "telefonischer support", "supporthotline"),
    ("24/7", "rund um die uhr", "24 stunden", "7 tage die woche", "24x7", "365 tage"),
    ("reaktionszeit", "reaktionsfrist", "interventionszeit", "wiederherstellungszeit"),
    ("wartung", "instandhaltung", "inspektion"),
    ("fernwartung", "remote-service", "remote service", "fernzugriff", "fernzugang"),
    ("ersatzteile", "ersatzteil", "verschleißteile"),
    ("preisanpassung", "preiserhöhung", "preisgleitklausel", "indexierung", "wertsicherung"),
    ("kündigung", "kündigungsfrist", "kündigen"),
    ("datenschutz", "auftragsverarbeitung", "dsgvo", "avv"),
    ("vertragsstrafe", "pönale"),
    ("softwarepflege", "software-update", "updates", "softwareaktualisierung"),
    ("verfügbarkeit", "betriebsbereitschaft", "uptime"),
    ("notdienst", "bereitschaftsdienst", "rufbereitschaft"),
    ("haftung", "haftungsbeschränkung", "haftungsbegrenzung"),
    ("schulung", "einweisung", "training"),
)

MAX_CONTRACTS = 50
HITS_PER_CONTRACT = 3
INDEX_BATCH = 50
SEMANTIC_THRESHOLD = 0.55
_SEPARATORS = re.compile(r"[/–-]+")


@dataclass
class QueryUnit:
    text: str
    alternatives: list[str] = field(default_factory=list)


def _normalize(text: str) -> str:
    return _SEPARATORS.sub(" ", text).strip()


def parse_query(raw: str) -> list[QueryUnit]:
    """Zerlegt die Suche in Einheiten (Phrase in Anfuehrungszeichen, bekannte
    Mehrwort-Begriffe, sonst Woerter); jede Einheit mit ihren Synonymen."""
    text = (raw or "").strip().casefold()
    if not text:
        return []
    units: list[QueryUnit] = []
    for quoted in re.findall(r'"([^"]+)"', text):
        units.append(QueryUnit(quoted.strip()))
    text = re.sub(r'"[^"]+"', " ", text)
    phrases = sorted({term for group in SYNONYMS for term in group if " " in term}, key=len, reverse=True)
    for phrase in phrases:
        if phrase in text:
            units.append(QueryUnit(phrase))
            text = text.replace(phrase, " ")
    for word in re.split(r"\s+", text):
        word = word.strip(".,;:!?()[]")
        if len(word) >= 2:
            units.append(QueryUnit(word))
    for unit in units:
        group = next((group for group in SYNONYMS if unit.text in group), None)
        unit.alternatives = list(dict.fromkeys([unit.text, *(group or ())]))
    return units


# --------------------------------------------------------------------------- index

def _is_local(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def embed(texts: list[str]) -> Optional[list[list[float]]]:
    """Lokale Embeddings ueber Ollama; None wenn nicht konfiguriert oder nicht lokal."""
    model = settings.search_embedding_model.strip()
    if not model or not texts:
        return None
    if not _is_local(settings.ollama_base_url):
        logger.warning("Semantische Suche deaktiviert: Ollama-Adresse ist nicht lokal.")
        return None
    body = json.dumps({"model": model, "input": [text[:4000] for text in texts]}).encode("utf-8")
    request = urllib.request.Request(
        settings.ollama_base_url.rstrip("/") + "/api/embed", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - nur lokale Adresse (geprueft)
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - Suche faellt auf Volltext zurueck
        logger.warning("Embedding-Anfrage an das lokale Modell fehlgeschlagen.")
        return None
    vectors = payload.get("embeddings")
    return vectors if isinstance(vectors, list) and len(vectors) == len(texts) else None


def ensure_index(session: Session, organization_id: uuid.UUID, limit: int = INDEX_BATCH) -> int:
    """Liest fehlende Seitentexte aus den gespeicherten kanonischen Artefakten."""
    missing = session.execute(
        select(ContractDocument.contract_id, ContractDocument.document_version_id)
        .join(Contract, Contract.id == ContractDocument.contract_id)
        .outerjoin(ContractTextPage, and_(
            ContractTextPage.contract_id == ContractDocument.contract_id,
            ContractTextPage.document_version_id == ContractDocument.document_version_id,
        ))
        .where(Contract.organization_id == organization_id, ContractTextPage.id.is_(None))
        .limit(limit)
    ).all()
    for contract_id, document_version_id in missing:
        pages = load_canonical_pages(session, organization_id=organization_id, document_version_id=document_version_id)
        texts = [(page["page"], fix_text(page["text"]).strip()) for page in pages if page["text"].strip()]
        if not texts:
            session.add(ContractTextPage(
                organization_id=organization_id, contract_id=contract_id, document_version_id=document_version_id,
                page_number=0, text="",
            ))
            continue
        for number, text in texts:
            session.add(ContractTextPage(
                organization_id=organization_id, contract_id=contract_id, document_version_id=document_version_id,
                page_number=number, text=text,
            ))
    session.flush()
    _ensure_embeddings(session, organization_id, limit)
    return len(missing)


def _ensure_embeddings(session: Session, organization_id: uuid.UUID, limit: int) -> None:
    model = settings.search_embedding_model.strip()
    if not model:
        return
    rows = session.scalars(
        select(ContractTextPage).where(
            ContractTextPage.organization_id == organization_id,
            ContractTextPage.page_number > 0,
            or_(ContractTextPage.embedding.is_(None), ContractTextPage.embedding_model != model),
        ).limit(limit)
    ).all()
    vectors = embed([row.text for row in rows]) if rows else None
    if vectors is None:
        return
    for row, vector in zip(rows, vectors):
        row.embedding = vector
        row.embedding_model = model
    session.flush()


# --------------------------------------------------------------------------- search

def _unit_condition(unit: QueryUnit):
    parts = []
    for alternative in unit.alternatives:
        parts.append(ContractTextPage.search_vector.op("@@")(func.phraseto_tsquery("german", _normalize(alternative))))
        if len(alternative) >= 4:
            escaped = alternative.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            parts.append(ContractTextPage.text.ilike(f"%{escaped}%"))
    return or_(*parts)


def _rank_query(units: list[QueryUnit]):
    query = None
    for unit in units:
        for alternative in unit.alternatives:
            part = func.phraseto_tsquery("german", _normalize(alternative))
            query = part if query is None else query.op("||")(part)
    return query


def _snippet(text: str, units: list[QueryUnit], width: int = 220) -> str:
    lower = text.casefold()
    positions = [
        (lower.find(alternative), alternative)
        for unit in units for alternative in unit.alternatives
        if lower.find(alternative) >= 0
    ]
    if not positions:
        stems = [alternative[: max(4, len(alternative) - 2)] for unit in units for alternative in unit.alternatives]
        positions = [(lower.find(stem), stem) for stem in stems if len(stem) >= 4 and lower.find(stem) >= 0]
    start = min(positions)[0] if positions else 0
    begin = max(0, start - width // 2)
    snippet = text[begin:begin + width].replace("\n", " ")
    return ("…" if begin > 0 else "") + snippet.strip() + ("…" if begin + width < len(text) else "")


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norm = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norm if norm else 0.0


def search_contents(
    session: Session, organization_id: uuid.UUID, raw_query: str, visible: Optional[set[uuid.UUID]]
) -> dict:
    units = parse_query(raw_query)
    if not units:
        return {"query": raw_query, "terms": [], "semantic": False, "items": []}

    base = (
        select(
            ContractTextPage.id, ContractTextPage.contract_id, ContractTextPage.document_version_id,
            ContractTextPage.page_number, ContractTextPage.text,
            Contract.register_number, Contract.short_description, Contract.supplier,
            func.coalesce(ContractDocument.title, DocumentFile.original_filename).label("document"),
            ContractDocument.is_valid,
        )
        .join(Contract, Contract.id == ContractTextPage.contract_id)
        .join(ContractDocument, and_(
            ContractDocument.contract_id == ContractTextPage.contract_id,
            ContractDocument.document_version_id == ContractTextPage.document_version_id,
        ))
        .join(DocumentVersion, DocumentVersion.id == ContractTextPage.document_version_id)
        .join(DocumentFile, DocumentFile.id == DocumentVersion.document_file_id)
        .where(
            ContractTextPage.organization_id == organization_id,
            ContractTextPage.page_number > 0,
            Contract.lifecycle_state == "active",
        )
    )
    if visible is not None:
        base = base.where(Contract.id.in_(visible))

    rank = func.ts_rank_cd(ContractTextPage.search_vector, _rank_query(units))
    rows = session.execute(
        base.add_columns(rank.label("rank")).where(and_(*[_unit_condition(unit) for unit in units]))
        .order_by(rank.desc()).limit(500)
    ).all()
    hits: dict[uuid.UUID, dict] = {}

    def add(row, score: float, match: str) -> None:
        entry = hits.setdefault(row.contract_id, {
            "contract_id": str(row.contract_id),
            "register_number": row.register_number,
            "short_description": row.short_description or row.supplier,
            "score": 0.0,
            "hits": [],
        })
        entry["score"] = max(entry["score"], score)
        if len(entry["hits"]) < HITS_PER_CONTRACT and not any(
            hit["document_version_id"] == str(row.document_version_id) and hit["page"] == row.page_number for hit in entry["hits"]
        ):
            entry["hits"].append({
                "document_version_id": str(row.document_version_id),
                "document": row.document,
                "document_valid": bool(row.is_valid),
                "page": row.page_number,
                "snippet": _snippet(row.text, units),
                "match": match,
            })

    for row in rows:
        add(row, float(row.rank or 0) + 1.0, "text")

    semantic = False
    model = settings.search_embedding_model.strip()
    if model:
        vector = embed([raw_query])
        if vector:
            semantic = True
            candidates = session.execute(
                base.add_columns(ContractTextPage.embedding.label("embedding"), literal(0).label("rank"))
                .where(ContractTextPage.embedding_model == model)
            ).all()
            scored = sorted(
                ((_cosine(vector[0], row.embedding), row) for row in candidates if row.embedding),
                key=lambda item: item[0], reverse=True,
            )[:30]
            for score, row in scored:
                if score >= SEMANTIC_THRESHOLD:
                    add(row, score, "semantic")

    items = sorted(hits.values(), key=lambda item: item["score"], reverse=True)[:MAX_CONTRACTS]
    for item in items:
        item.pop("score")
    return {
        "query": raw_query,
        "terms": [{"term": unit.text, "alternatives": unit.alternatives[1:]} for unit in units],
        "semantic": semantic,
        "items": items,
    }


def index_status(session: Session, organization_id: uuid.UUID) -> dict:
    documents = session.scalar(
        select(func.count()).select_from(ContractDocument).join(Contract, Contract.id == ContractDocument.contract_id)
        .where(Contract.organization_id == organization_id)
    ) or 0
    indexed = session.scalar(
        select(func.count(func.distinct(func.concat(ContractTextPage.contract_id, ContractTextPage.document_version_id))))
        .where(ContractTextPage.organization_id == organization_id)
    ) or 0
    without_text = session.scalar(
        select(func.count()).where(ContractTextPage.organization_id == organization_id, ContractTextPage.page_number == 0)
    ) or 0
    return {
        "documents": documents,
        "indexed": indexed,
        "without_text": without_text,
        "semantic_model": settings.search_embedding_model.strip() or None,
    }
