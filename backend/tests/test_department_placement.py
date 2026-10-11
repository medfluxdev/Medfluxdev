"""Regeln der Abteilungsstruktur: Klinik oben, Abteilung unter Klinik oder oben, Station/Funktionsbereich darunter."""

from __future__ import annotations

from uuid import UUID

from app.database.models.organization_structure import Department
from app.database.session import create_session
from app.organization_structure.placement import child_issues, placement_issue, rules_payload
from tests.test_cost_center_patch_and_search_api_wp1 import _client, _seed


def test_rules_are_pure_and_never_guess():
    assert placement_issue("klinik", False, None) is None
    assert placement_issue("klinik", True, "klinik") == "Eine Klinik steht direkt unter dem Krankenhaus."
    assert placement_issue("abteilung", False, None) is None  # z. B. IT direkt unter dem Krankenhaus
    assert placement_issue("abteilung", True, "klinik") is None
    assert placement_issue("abteilung", True, "station") is not None
    assert placement_issue("station", False, None) == "Eine Station steht unter einer Klinik oder Abteilung."
    assert placement_issue("station", True, "abteilung") is None
    assert placement_issue("funktionsbereich", True, "klinik") is None
    # Ohne Typ (Kind oder übergeordnet) und für Bereich/Einheit gibt es keine Regel.
    assert placement_issue(None, True, "station") is None
    assert placement_issue("station", True, None) is None
    assert placement_issue("bereich", False, None) is None
    assert child_issues("abteilung", [("Kardiologie", "abteilung"), ("Station 3", "station"), ("Klinik X", "klinik")]) == ["Kardiologie", "Klinik X"]
    assert rules_payload()["abteilung"]["parents"] == [None, "klinik"]


def test_api_rejects_new_violations_and_flags_existing(monkeypatch):
    slug, actor, ids = _seed()
    client = _client(actor, monkeypatch)
    query = {"organization_slug": slug}
    base = {"hospital_id": str(ids["hospital_a"])}
    path = "/api/organization-structure/departments"

    klinik = client.post(path, params=query, json={**base, "name": "Medizinische Klinik", "code": "MK", "unit_type": "klinik"})
    assert klinik.status_code == 200, klinik.text
    kid = klinik.json()["id"]
    abteilung = client.post(path, params=query, json={**base, "name": "Kardiologie", "code": "KAR", "unit_type": "abteilung", "parent_id": kid})
    assert abteilung.status_code == 200, abteilung.text
    aid = abteilung.json()["id"]
    assert client.post(path, params=query, json={**base, "name": "IT", "code": "IT", "unit_type": "abteilung"}).status_code == 200
    station = client.post(path, params=query, json={**base, "name": "Station 3", "code": "ST3", "unit_type": "station", "parent_id": aid})
    assert station.status_code == 200, station.text

    # Neue Verstöße werden abgelehnt (mit Regeltext).
    nested = client.post(path, params=query, json={**base, "name": "Klinik unter Klinik", "code": "KUK", "unit_type": "klinik", "parent_id": kid})
    assert nested.status_code == 422 and "direkt unter dem Krankenhaus" in nested.json()["detail"]
    top_station = client.post(path, params=query, json={**base, "name": "Station oben", "code": "STO", "unit_type": "station"})
    assert top_station.status_code == 422 and "unter einer Klinik oder Abteilung" in top_station.json()["detail"]
    # Typwechsel, der Untereinheiten unpassend machte, wird abgelehnt.
    retype = client.patch(f"{path}/{aid}", params=query, json={"unit_type": "station"})
    assert retype.status_code == 422 and "Station 3" in retype.json()["detail"]
    # Umhängen an eine unpassende Stelle ebenso.
    move = client.patch(f"{path}/{kid}", params=query, json={"parent_id": aid})
    assert move.status_code == 422

    # Bestehende Abweichung (direkt in der DB, wie aus früheren Daten) bleibt und wird markiert.
    session = create_session()
    try:
        session.get(Department, UUID(station.json()["id"])).parent_id = None
        session.commit()
    finally:
        session.close()
    structure = client.get("/api/organization-structure", params=query).json()
    by_name = {row["name"]: row for row in structure["departments"]}
    assert by_name["Station 3"]["placement_issue"] == "Eine Station steht unter einer Klinik oder Abteilung."
    assert by_name["Kardiologie"]["placement_issue"] is None
    assert structure["placement_rules"]["klinik"]["parents"] == [None]
    # Umbenennen der abweichenden Einheit bleibt möglich (nur geänderte Einordnungen werden geprüft).
    assert client.patch(f"{path}/{station.json()['id']}", params=query, json={"name": "Station 3a"}).status_code == 200
