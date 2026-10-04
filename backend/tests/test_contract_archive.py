"""PR-5 Vertrags-Archiv (nicht-destruktiv, reversibel) – Transaktion-pro-Test.

Archivierte Verträge erscheinen nicht im aktiven Portfolio (Default/archived=false),
sondern nur mit `archived=true`. `archived_at`/`is_archived` werden im List-Item
geliefert. Bei nicht erreichbarer DB SKIPPED (Unit-Suite bleibt grün) – Muster
wie test_contract_search.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.contracts.search import SearchParams, build_contract_search
from app.database.models import Contract, Organization
from app.database.services import create_organization
from tests.test_contract_search import AS_OF, _mk_contract


def _pg_available(engine) -> bool:
    try:
        with engine.connect() as c:
            c.execute(text("select 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(settings.database_url, pool_pre_ping=True)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _require_pg(engine):
    if not _pg_available(engine):
        pytest.skip("PostgreSQL nicht erreichbar – Archiv-Tests übersprungen")
    yield


@pytest.fixture
def db(engine):
    session = Session(engine, expire_on_commit=False)
    session.begin()
    yield session
    session.rollback()
    session.close()


def _org(db) -> Organization:
    return create_organization(db, name="Klinik", slug=f"klinik-{uuid.uuid4().hex[:12]}")


def _archive(db, contract_id, *, archived=True):
    c = db.get(Contract, contract_id)
    c.is_archived = archived
    c.archived_at = datetime.now(timezone.utc) if archived else None
    db.flush()
    return c


def _search(db, org, **params):
    params.setdefault("organization_id", org.id)
    return build_contract_search(
        db, SearchParams(**params), organization_id=org.id, request_as_of=AS_OF
    )


def _numbers(resp) -> list[str]:
    return [i["contract_number"] for i in resp["items"]]


def test_archived_hidden_by_default(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", title="Aktiv")
    c2, _, _ = _mk_contract(db, org, contract_number="CN-B", title="Archiv")
    _archive(db, c2.id)
    resp = _search(db, org)
    assert _numbers(resp) == ["CN-A"]


def test_archive_filter_true_only_archived(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", title="Aktiv")
    c2, _, _ = _mk_contract(db, org, contract_number="CN-B", title="Archiv")
    _archive(db, c2.id)
    resp = _search(db, org, archived=True)
    assert _numbers(resp) == ["CN-B"]
    item = resp["items"][0]
    assert item["is_archived"] is True
    assert item["archived_at"] is not None


def test_archive_filter_false_excludes_archived(db):
    org = _org(db)
    _mk_contract(db, org, contract_number="CN-A", title="Aktiv")
    c2, _, _ = _mk_contract(db, org, contract_number="CN-B", title="Archiv")
    _archive(db, c2.id)
    resp = _search(db, org, archived=False)
    assert _numbers(resp) == ["CN-A"]


def test_unarchive_restores_contract(db):
    org = _org(db)
    c, _, _ = _mk_contract(db, org, contract_number="CN-B", title="Wiedergeholt")
    _archive(db, c.id, archived=True)
    assert _search(db, org, archived=True)["total_count"] == 1
    _archive(db, c.id, archived=False)
    resp = _search(db, org)
    assert _numbers(resp) == ["CN-B"]
    item = resp["items"][0]
    assert item["is_archived"] is False
    assert item["archived_at"] is None


def test_archived_org_isolation(db):
    org1 = _org(db)
    org2 = _org(db)
    c1, _, _ = _mk_contract(db, org1, contract_number="CN-1", title="Eine")
    _mk_contract(db, org2, contract_number="CN-2", title="Zwei")
    _archive(db, c1.id)
    resp = _search(db, org2, archived=True)
    assert _numbers(resp) == []


def test_archive_route_unknown_org_404(db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    cid = uuid.uuid4()
    resp = client.post(f"/api/contracts/{cid}/archive", params={"organization_slug": "does-not-exist"})
    assert resp.status_code == 404


def test_unarchive_route_unknown_org_404(db):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    cid = uuid.uuid4()
    resp = client.post(f"/api/contracts/{cid}/unarchive", params={"organization_slug": "does-not-exist"})
    assert resp.status_code == 404