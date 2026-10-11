"""Angabe aus einer markierten Dokumentstelle (erneute Erfassung, Phase 4).

Zusagen: der Wert wird per Code gelesen (kein Modell), die Stelle muss auf der Seite
stehen, Mehrdeutiges wird abgelehnt, die Fundstelle wird gespeichert und verschwindet,
sobald der Wert auf anderem Weg geaendert wird.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from app.database.models import ActivityLog, Contract
from app.database.models.contract import ContractDocument
from app.database.models.register import ContractFieldProvenance
from app.database.session import create_session
from app.register import from_document
from app.register.from_document import CaptureError, normalize, parse_date, parse_duration, parse_percent, values_from_quote
from app.register.service import capture_from_document, update_register
from tests.test_reextraction import TEXT, _actor, _client, _imported, _seed

# --- Lesen ohne Modell ------------------------------------------------------------------------


def test_dates_are_read_from_numeric_word_and_iso_forms():
    assert parse_date("gilt ab 01.04.2025") == date(2025, 4, 1)
    assert parse_date("tritt am 1. Januar 2025 in Kraft") == date(2025, 1, 1)
    assert parse_date("Beginn: 3. Okt. 2024") == date(2024, 10, 3)
    assert parse_date("2026-02-28") == date(2026, 2, 28)
    with pytest.raises(CaptureError, match="mehrere Daten"):
        parse_date("vom 01.01.2025 bis 31.12.2027")
    with pytest.raises(CaptureError, match="kein Datum"):
        parse_date("31.02.2025")  # gibt es nicht


def test_durations_numbers_words_and_brackets():
    assert parse_duration("für zwei Jahre") == (2, "years")
    assert parse_duration("zwölf (12) Monate") == (12, "months")
    assert parse_duration("mit einer Frist von 3 Monaten zum Quartalsende") == (3, "months")
    assert parse_duration("sechs Wochen") == (6, "weeks")
    with pytest.raises(CaptureError, match="mehrere Fristen"):
        parse_duration("3 Monate, frühestens nach 24 Monaten")
    with pytest.raises(CaptureError, match="keine Dauer"):
        parse_duration("zum Quartalsende")


def test_field_specific_reading():
    assert values_from_quote("notice_period", "sechs Monate zum Jahresende") == {"notice_period_value": 6, "notice_period_unit": "months"}
    assert values_from_quote("notice_to", "zum Ende eines Kalendervierteljahres") == {"notice_to": "quarter_end"}
    assert values_from_quote("maintenance_interval_months", "jährliche Wartung, alle 12 Monate") == {"maintenance_interval_months": 12}
    assert values_from_quote("maintenance_interval_months", "einmal pro Jahr: alle 1 Jahr") == {"maintenance_interval_months": 12}
    assert values_from_quote("price_adjustment_percent", "Erhöhung um 3,5 % jährlich") == {"price_adjustment_percent": Decimal("3.5")}
    assert values_from_quote("short_description", "  Wartung   CT\nSiemens ") == {"short_description": "Wartung CT Siemens"}
    assert parse_percent("2 Prozent") == Decimal("2")
    with pytest.raises(CaptureError, match="nicht aus dem Dokument"):
        values_from_quote("partner_id", "Siemens")  # Verweis auf Stammdaten: nicht aus Text
    with pytest.raises(CaptureError, match="nicht aus dem Dokument"):
        values_from_quote("reminder_todo", "anrufen")  # interne Angabe, steht nicht im Vertrag
    with pytest.raises(CaptureError):
        values_from_quote("term_model", "befristet")
    assert normalize("Kündigung zum  Jahres­ende – „x“") == 'Kündigung zum Jahresende - "x"'


# --- Speichern mit Fundstelle ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _storage(tmp_path, monkeypatch):
    # Die Seitentexte kommen aus dem gespeicherten kanonischen Artefakt (gleicher Ablageort wie der Test).
    from app.core.config import settings

    monkeypatch.setattr(settings, "contracts_dir", tmp_path)


def _version(contract_id: str) -> UUID:
    session = create_session()
    try:
        return session.scalars(select(ContractDocument.document_version_id).where(ContractDocument.contract_id == UUID(contract_id))).first()
    finally:
        session.close()


def _capture(contract_id, ids, key, quote, page=1):
    session = create_session()
    try:
        contract = session.get(Contract, UUID(contract_id), with_for_update=True)
        capture = from_document.prepare_capture(session, contract=contract, field_key=key, document_version_id=_version(contract_id), page=page, quote=quote)
        capture_from_document(session, contract=contract, actor=_actor(ids), capture=capture)
        session.commit()
    finally:
        session.close()


def _row(contract_id, key):
    session = create_session()
    try:
        return session.scalars(select(ContractFieldProvenance).where(
            ContractFieldProvenance.contract_id == UUID(contract_id), ContractFieldProvenance.field_key == key,
        )).one()
    finally:
        session.close()


def test_capture_saves_value_with_source_and_any_other_change_drops_it(tmp_path):
    slug, ids = _seed()
    contract_id = _imported(tmp_path, slug)
    _capture(contract_id, ids, "term_start_date", "Beginn 01.01.2025")
    session = create_session()
    try:
        contract = session.get(Contract, UUID(contract_id))
        assert contract.term_start_date == date(2025, 1, 1)
        events = [row for row in session.scalars(select(ActivityLog).where(ActivityLog.object_id == UUID(contract_id))) if row.event_name == "contract.value_from_document"]
        assert events and events[0].context_data["page"] == 1
    finally:
        session.close()
    row = _row(contract_id, "term_start_date")
    assert (row.origin, row.source_page, row.source_quote) == ("manual", 1, "Beginn 01.01.2025")

    # Zeitraum: Wert und Einheit, beide mit derselben Fundstelle.
    _capture(contract_id, ids, "notice_period", "Kündigungsfrist sechs Monate")
    assert _row(contract_id, "notice_period_value").source_quote == "Kündigungsfrist sechs Monate"

    # Von Hand geaendert: die Fundstelle gilt nicht mehr.
    session = create_session()
    try:
        contract = session.get(Contract, UUID(contract_id), with_for_update=True)
        update_register(session, contract=contract, actor=_actor(ids), changes={"term_start_date": "2025-02-01"}, confirm=[])
        session.commit()
    finally:
        session.close()
    assert _row(contract_id, "term_start_date").source_quote is None


def test_capture_rejects_text_that_is_not_on_the_page(tmp_path):
    slug, ids = _seed()
    contract_id = _imported(tmp_path, slug)
    with pytest.raises(CaptureError, match="nicht gefunden"):
        _capture(contract_id, ids, "term_start_date", "Beginn 01.01.2030")
    with pytest.raises(CaptureError, match="kein gelesener Text"):
        _capture(contract_id, ids, "term_start_date", "Beginn 01.01.2025", page=9)


def test_api_page_text_capture_permissions_and_scope(tmp_path, monkeypatch):
    slug, ids = _seed()
    contract_id = _imported(tmp_path, slug)
    version = _version(contract_id)
    query = {"organization_slug": slug}

    from app.api.routes import contract_register
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    def client(org_ids, key, role):
        _client(monkeypatch, org_ids, key, role)  # setzt Akteur und Scope
        app = FastAPI()
        app.include_router(contract_register.router)
        return TestClient(app)

    viewer = client(ids, "viewer", "viewer")
    text = viewer.get(f"/api/contracts/{contract_id}/documents/{version}/pages/1/text", params=query)
    assert text.status_code == 200 and "Beginn 01.01.2025" in text.json()["text"] and text.json()["pages"] == [1]
    body = {"field_key": "term_start_date", "document_version_id": str(version), "page": 1, "quote": "Beginn 01.01.2025"}
    assert viewer.post(f"/api/contracts/{contract_id}/register/from-document", params=query, json=body).status_code == 403

    other_slug, other_ids = _seed()
    stranger = client(other_ids, "admin", "admin")
    assert stranger.get(f"/api/contracts/{contract_id}/documents/{version}/pages/1/text", params={"organization_slug": other_slug}).status_code == 404

    manager = client(ids, "manager", "contract_manager")
    wrong = manager.post(f"/api/contracts/{contract_id}/register/from-document", params=query, json={**body, "quote": "steht nicht da"})
    assert wrong.status_code == 422 and "nicht gefunden" in wrong.json()["detail"]
    check = manager.post(f"/api/contracts/{contract_id}/register/from-document", params=query, json={**body, "dry_run": True})
    assert check.json() == {"preview": "01.01.2025", "page": 1, "quote": "Beginn 01.01.2025"}
    period = manager.post(f"/api/contracts/{contract_id}/register/from-document", params=query, json={**body, "field_key": "notice_period", "quote": "Kündigungsfrist sechs Monate", "dry_run": True})
    assert period.json()["preview"] == "6 Monate"
    assert "term_start_date" in {item["key"] for item in text.json()["fields"]}
    saved = manager.post(f"/api/contracts/{contract_id}/register/from-document", params=query, json=body)
    assert saved.status_code == 200, saved.text
    field = saved.json()["fields"]["term_start_date"]
    assert field["value"] == "2025-01-01"
    assert field["document_source"] == {"document_version_id": str(version), "page": 1, "quote": "Beginn 01.01.2025"}
    assert TEXT  # Testtext enthaelt die markierte Stelle
