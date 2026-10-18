"""Vertragstitel: eigenes Feld (KI-Titel mit Nachweis), eigene Spalte, Pflicht fuer „Gueltig“ (Titel oder Kurzbeschreibung)."""

from __future__ import annotations

import json
from datetime import date

from app.register.fields import FIELDS, coerce_value, missing_required
from app.reextract.facts import REGISTER_KEYS
from tests.test_register_grid import _as, _grid, _seed


def test_field_is_separate_from_the_short_description():
    assert FIELDS["contract_title"].label_de == "Vertragstitel"
    assert FIELDS["short_description"].label_de == "Kurzbeschreibung"
    assert coerce_value("contract_title", "  Full-Service-Vertrag  ") == "Full-Service-Vertrag"
    # Der Nachweis „Vertragstitel“ fuehrt zum Vertragstitel, nicht zur Kurzbeschreibung.
    assert REGISTER_KEYS["identity.contract_title"] == ("contract_title",)


def test_valid_needs_a_title_or_a_short_description():
    base = {"term_model": "perpetual", "term_start_date": date(2026, 1, 1)}
    assert missing_required({**base, "contract_title": "Wartung"}) == []
    assert missing_required({**base, "short_description": "Wartung"}) == []
    assert missing_required(base) == ["contract_title"]


def test_grid_column_filter_sort_and_display_title(monkeypatch):
    slug, ids = _seed()
    admin = _as(monkeypatch, ids, "admin", "admin")
    query = {"organization_slug": slug}
    created = {}
    for name, values in (
        ("titled", {"contract_title": "Beta-Vertrag", "short_description": "intern"}),
        ("only_title", {"contract_title": "Alpha-Vertrag"}),
        ("only_description", {"short_description": "Charlie"}),
    ):
        response = admin.post("/api/contracts", params=query, json={"values": values})
        assert response.status_code == 200, response.text
        created[name] = response.json()["contract_id"]

    columns = admin.get("/api/register/columns", params=query).json()["columns"]
    column = next(item for item in columns if item["key"] == "contract_title")
    assert column["label"] == "Vertragstitel" and column["default"] is False

    spec = {"columns": ["register_number", "contract_title"], "sort": {"column": "contract_title", "dir": "asc"}}
    grid = _grid(admin, slug, spec)
    titles = {item["contract_id"]: item["values"] for item in grid["items"]}
    assert titles[created["titled"]]["contract_title"] == "Beta-Vertrag"
    assert titles[created["only_description"]]["contract_title"] in (None, "–")
    # Fehlt der Titel, nennt die Liste den Vertrag nach der Kurzbeschreibung; der Titel steht sonst vorn.
    assert titles[created["titled"]]["display_title"] == "Beta-Vertrag"
    assert titles[created["only_description"]]["display_title"] == "Charlie"
    assert [item["contract_id"] for item in grid["items"]][:2] == [created["only_title"], created["titled"]]

    # Filtern und Suchen finden den Titel.
    assert _grid(admin, slug, {"q": "alpha"})["total"] == 1
    hit = _grid(admin, slug, {"filters": [{"column": "contract_title", "op": "contains", "value": "Beta"}]})
    assert [item["contract_id"] for item in hit["items"]] == [created["titled"]]

    # Sortieren nach der Bezeichnung in der Spalte „Vertrag“.
    by_display = _grid(admin, slug, {"sort": {"column": "display_title", "dir": "asc"}})
    assert [item["values"]["display_title"] for item in by_display["items"]] == ["Alpha-Vertrag", "Beta-Vertrag", "Charlie"]
    assert json.dumps(by_display)
