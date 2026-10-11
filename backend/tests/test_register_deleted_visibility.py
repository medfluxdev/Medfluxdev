"""Vertragsliste: als gelöscht markierte Verträge nur für Administration und Vertragsmanagement."""

from __future__ import annotations

import json

from tests.test_register_grid import _as, _grid, _populate, _seed

DELETED_FILTER = {"filters": [{"column": "business_status", "op": "in", "value": ["geloescht"]}]}


def _values(client, slug, column, spec=None):
    response = client.get("/api/register/grid/values", params={"organization_slug": slug, "column": column, "spec": json.dumps(spec or {})})
    assert response.status_code == 200, response.text
    return response.json()["values"]


def test_reader_roles_never_see_deleted_contracts(monkeypatch):
    slug, ids = _seed()
    admin = _as(monkeypatch, ids, "admin", "admin")
    a, b, deleted = _populate(admin, slug, ids)

    for role in ("viewer", "reviewer"):
        client = _as(monkeypatch, ids, "viewer", role)
        query = {"organization_slug": slug}
        assert {item["contract_id"] for item in _grid(client, slug)["items"]} == {a, b}
        # Option, Statusfilter und beides zusammen – der Server blendet sie trotzdem aus.
        assert deleted not in {item["contract_id"] for item in _grid(client, slug, {"include_deleted": True})["items"]}
        assert _grid(client, slug, DELETED_FILTER)["total"] == 0
        assert _grid(client, slug, {**DELETED_FILTER, "include_deleted": True})["total"] == 0
        assert _grid(client, slug, {"filters": [{"column": "business_status", "op": "in", "value": ["geloescht", "in_arbeit"]}]})["total"] == 2
        assert _grid(client, slug, {"include_deleted": True})["spec"]["include_deleted"] is False
        # Baum, Werte und Spaltenoptionen verraten sie ebenfalls nicht.
        tree = _grid(client, slug, {"include_deleted": True}, include_tree="true")["tree"]
        assert sum(hospital["count"] for hospital in tree) == 2
        assert "geloescht" not in {item["value"] for item in _values(client, slug, "business_status", {"include_deleted": True})}
        columns = client.get("/api/register/columns", params=query).json()["columns"]
        status = next(item for item in columns if item["key"] == "business_status")
        assert "geloescht" not in {option["value"] for option in status["options"]}
        # Die Standardansicht „Gelöschte Verträge“ wird nicht angeboten.
        views = client.get("/api/register/views", params=query).json()["items"]
        assert "deleted" not in {item.get("system_key") for item in views}
        # Ein Export ist für diese Rollen ohnehin gesperrt.
        assert client.get("/api/register/grid/export.xlsx", params={**query, "spec": json.dumps(DELETED_FILTER)}).status_code == 403


def test_editors_still_see_deleted_contracts(monkeypatch):
    slug, ids = _seed()
    admin = _as(monkeypatch, ids, "admin", "admin")
    _, _, deleted = _populate(admin, slug, ids)

    for key, role in (("admin", "admin"), ("manager", "contract_manager")):
        client = _as(monkeypatch, ids, key, role)
        query = {"organization_slug": slug}
        assert _grid(client, slug, {"include_deleted": True})["total"] == 3
        assert _grid(client, slug, DELETED_FILTER)["items"][0]["contract_id"] == deleted
        views = client.get("/api/register/views", params=query).json()["items"]
        assert "deleted" in {item.get("system_key") for item in views}
        status = next(item for item in client.get("/api/register/columns", params=query).json()["columns"] if item["key"] == "business_status")
        assert "geloescht" in {option["value"] for option in status["options"]}
        export = client.get("/api/register/grid/export.xlsx", params={**query, "spec": json.dumps(DELETED_FILTER)})
        assert export.status_code == 200
