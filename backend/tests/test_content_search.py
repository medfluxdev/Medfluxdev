"""§4A Inhaltssuche: Volltext + Teilwort + Synonyme mit Seitenangabe, Sichtbarkeit, optionale Embeddings."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import contract_register, register_grid
from app.core.scope_context import ScopeContext
from app.database import scope_queries
from app.database.models import Account, AccountMembership, Contract
from app.database.models.content_search import ContractTextPage
from app.database.models.contract import ContractDocument
from app.database.models.document import DocumentFile, DocumentVersion
from app.database.models.organization import Organization
from app.database.session import create_session
from app.search import content
from app.search.content import parse_query


def test_query_parsing_with_phrases_and_synonyms():
    units = parse_query('24/7 Hotline "Reaktionszeit 4 Stunden"')
    texts = [unit.text for unit in units]
    assert texts == ["reaktionszeit 4 stunden", "24/7", "hotline"]
    assert "rund um die uhr" in units[1].alternatives
    assert "störungsannahme" in units[2].alternatives
    assert [unit.text for unit in parse_query("rund um die Uhr Notdienst")] == ["rund um die uhr", "notdienst"]
    assert parse_query("   ") == []


def _seed():
    ids = {key: uuid4() for key in ("org", "admin", "other")}
    slug = f"search-{uuid4().hex[:12]}"
    session = create_session()
    try:
        session.add(Organization(id=ids["org"], name="Suche Test", slug=slug))
        for key in ("admin", "other"):
            session.add(Account(id=ids[key], login_name=f"{key}-{slug}@x.invalid", display_name=key.title(), credential_digest="t"))
        session.flush()
        session.add(AccountMembership(organization_id=ids["org"], account_id=ids["admin"], role="admin"))
        session.add(AccountMembership(organization_id=ids["org"], account_id=ids["other"], role="contract_manager"))
        session.commit()
    finally:
        session.close()
    return slug, ids


def _document(session, org, contract_id, name, pages, main=True):
    file_id, version_id = uuid4(), uuid4()
    digest = uuid4().hex * 2
    session.add(DocumentFile(
        id=file_id, organization_id=org, original_filename=name, stored_filename="x.pdf", file_extension="pdf",
        file_size_bytes=1, sha256=digest, storage_key=f"{file_id.hex}/original.pdf", import_status="imported",
    ))
    session.flush()
    session.add(DocumentVersion(id=version_id, organization_id=org, document_file_id=file_id, version_no=1, sha256=digest, storage_key=f"{file_id.hex}/original.pdf"))
    session.flush()
    session.add(ContractDocument(organization_id=org, contract_id=contract_id, document_version_id=version_id, is_main=main))
    for number, text in enumerate(pages, start=1):
        session.add(ContractTextPage(organization_id=org, contract_id=contract_id, document_version_id=version_id, page_number=number, text=text))
    return version_id


def _client(monkeypatch, ids, key, role):
    actor = SimpleNamespace(organization_id=ids["org"], account_id=ids[key], role=role, is_developer=False, display_name=key.title())
    for module in (contract_register, register_grid):
        monkeypatch.setattr(module, "current_actor", lambda request, organization_slug: actor)
        monkeypatch.setattr(module, "current_scope_context", lambda: ScopeContext())
    monkeypatch.setattr(scope_queries, "current_identity", lambda: actor)
    app = FastAPI()
    app.include_router(contract_register.router)
    app.include_router(register_grid.router)
    return TestClient(app)


def test_search_finds_pages_with_sources_and_respects_visibility(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    admin = _client(monkeypatch, ids, "admin", "admin")
    ct = admin.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung CT"}}).json()["contract_id"]
    mrt = admin.post("/api/contracts", params=query, json={"values": {"short_description": "Wartung MRT"}}).json()["contract_id"]
    secret = admin.post("/api/contracts", params=query, json={"values": {"short_description": "Geheim"}}).json()["contract_id"]
    session = create_session()
    try:
        _document(session, ids["org"], UUID(ct), "Wartungsvertrag CT.pdf", [
            "§ 1 Vertragsgegenstand Wartung des Computertomographen.",
            "§ 5 Service: Die 24/7-Hotline des Auftragnehmers ist rund um die Uhr erreichbar. Reaktionszeit 4 Stunden.",
        ])
        _document(session, ids["org"], UUID(mrt), "MRT.pdf", [
            "Die Störungshotline ist werktags von 8 bis 17 Uhr besetzt.",
        ])
        _document(session, ids["org"], UUID(secret), "Geheim.pdf", ["Hotline für die Geschäftsführung."])
        session.commit()
    finally:
        session.close()
    admin.put(f"/api/contracts/{secret}/confidentiality", params=query, json={"is_confidential": True})

    result = admin.get("/api/register/content-search", params={**query, "q": "24/7 Hotline"}).json()
    assert [item["contract_id"] for item in result["items"]] == [ct]
    hit = result["items"][0]["hits"][0]
    assert hit["page"] == 2 and hit["document"] == "Wartungsvertrag CT.pdf"
    assert "24/7-Hotline" in hit["snippet"] and hit["match"] == "text"

    hotline = admin.get("/api/register/content-search", params={**query, "q": "Hotline"}).json()
    assert {item["contract_id"] for item in hotline["items"]} == {ct, mrt, secret}
    assert {term["term"] for term in hotline["terms"]} == {"hotline"}

    other = _client(monkeypatch, ids, "other", "contract_manager")
    hidden = other.get("/api/register/content-search", params={**query, "q": "Hotline"}).json()
    assert secret not in {item["contract_id"] for item in hidden["items"]}
    assert other.get("/api/register/content-search", params={**query, "q": "x" * 201}).status_code == 422
    assert other.get("/api/register/content-search/status", params=query).json()["indexed"] == 3


def test_semantic_matches_use_local_embeddings_only(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    admin = _client(monkeypatch, ids, "admin", "admin")
    cid = admin.post("/api/contracts", params=query, json={"values": {"short_description": "Notfall"}}).json()["contract_id"]
    session = create_session()
    try:
        _document(session, ids["org"], UUID(cid), "Notfall.pdf", ["Techniker sind jederzeit telefonisch erreichbar."])
        session.commit()
    finally:
        session.close()

    monkeypatch.setattr(content.settings, "search_embedding_model", "test-embed")
    calls = []

    def fake_embed(texts):
        calls.append(texts)
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(content, "embed", fake_embed)
    result = admin.get("/api/register/content-search", params={**query, "q": "Störungsdienst"}).json()
    assert result["semantic"] is True
    assert result["items"][0]["contract_id"] == cid and result["items"][0]["hits"][0]["match"] == "semantic"

    monkeypatch.setattr(content.settings, "ollama_base_url", "http://10.0.0.5:11434")
    monkeypatch.setattr(content, "embed", content.__dict__["embed"])
    assert content._is_local("http://10.0.0.5:11434") is False


def test_index_reads_canonical_pages_and_marks_documents_without_text(monkeypatch):
    slug, ids = _seed()
    query = {"organization_slug": slug}
    admin = _client(monkeypatch, ids, "admin", "admin")
    cid = admin.post("/api/contracts", params=query, json={"values": {"short_description": "Scan"}}).json()["contract_id"]
    session = create_session()
    try:
        with_text = _document(session, ids["org"], UUID(cid), "a.pdf", [])
        empty = _document(session, ids["org"], UUID(cid), "b.pdf", [], main=False)
        session.commit()
    finally:
        session.close()

    def fake_pages(session, *, organization_id, document_version_id):
        return [{"page": 1, "text": "Fernwartung über VPN"}] if document_version_id == with_text else []

    monkeypatch.setattr(content, "load_canonical_pages", fake_pages)
    session = create_session()
    try:
        assert content.ensure_index(session, ids["org"]) == 2
        session.commit()
        assert content.ensure_index(session, ids["org"]) == 0
        status = content.index_status(session, ids["org"])
        assert status == {"documents": 2, "indexed": 2, "without_text": 1, "semantic_model": None}
    finally:
        session.close()
    found = admin.get("/api/register/content-search", params={**query, "q": "Remote-Service"}).json()
    assert found["items"][0]["hits"][0]["snippet"].startswith("Fernwartung")
