"""Kostenstelle direkt beim Anlegen/Bearbeiten einer Abteilung (optional)."""

from __future__ import annotations

from sqlalchemy import select

from app.database.models.organization_structure import CostCenter
from app.database.session import create_session
from tests.test_cost_center_patch_and_search_api_wp1 import _client, _seed


def _centers(code: str):
    session = create_session()
    try:
        return session.scalars(select(CostCenter).where(CostCenter.code == code)).all()
    finally:
        session.close()


def test_department_with_new_existing_or_foreign_cost_center(monkeypatch):
    slug, actor, ids = _seed()
    client = _client(actor, monkeypatch)
    query = {"organization_slug": slug}
    base = {"hospital_id": str(ids["hospital_a"]), "unit_type": None}

    # Ohne Kostenstelle: wie bisher.
    plain = client.post("/api/organization-structure/departments", params=query, json={**base, "name": "Labor", "code": "LAB"})
    assert plain.status_code == 200 and plain.json()["cost_center"] is None

    # Neue Nummer: Kostenstelle wird für die Abteilung angelegt (Name = Abteilung).
    created = client.post("/api/organization-structure/departments", params=query, json={**base, "name": "Haustechnik", "code": "HT", "cost_center_code": " 950100 "})
    assert created.status_code == 200, created.text
    assert created.json()["cost_center"]["created"] is True
    [center] = _centers("950100")
    assert str(center.department_id) == created.json()["id"] and center.name == "Haustechnik"

    # Nummer gehört schon einer anderen Abteilung: abgelehnt, nichts angelegt.
    taken = client.post("/api/organization-structure/departments", params=query, json={**base, "name": "Doppelt", "code": "DPL", "cost_center_code": "471100"})
    assert taken.status_code == 409 and "Radiologie" in taken.json()["detail"]

    # Bearbeiten: neue Nummer ersetzt die bisherige Verknüpfung; leer löst sie (Kostenstelle bleibt).
    dep_id = created.json()["id"]
    changed = client.patch(f"/api/organization-structure/departments/{dep_id}", params=query, json={"cost_center_code": "950200"})
    assert changed.status_code == 200, changed.text
    assert _centers("950100")[0].department_id is None
    assert str(_centers("950200")[0].department_id) == dep_id
    cleared = client.patch(f"/api/organization-structure/departments/{dep_id}", params=query, json={"cost_center_code": ""})
    assert cleared.status_code == 200 and _centers("950200")[0].department_id is None
