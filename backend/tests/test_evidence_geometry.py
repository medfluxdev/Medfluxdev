"""Lage der Nachweise: nur „genau“, wenn der Wortlaut in der Box steht; Alt-Artefakte gedreht."""

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace as NS

from app.contracts.detail.evidence_geometry import (
    flip_stored_box,
    locate,
    match_key,
    same_text,
    verify_evidence_locations,
)
from app.contracts.detail.recovery import _flip_regions, legacy_bottom_up
from app.documents.intelligence.docling_provider import _coord_boxes


def _seg(text, x0, y0, x1, y1):
    return {"text": text, "region": {"page": 1, "x0": x0, "y0": y0, "x1": x1, "y1": y1}}


PAGE = {
    "page": 1,
    "height_pt": 842.0,
    "elements": [
        {"text": "ABIOMED Europe GmbH Neuenhofer Weg 3", "word_regions": [_seg("ABIOMED Europe GmbH Neuenhofer Weg 3", 220, 316, 380, 380)]},
        {"text": "Und", "word_regions": [_seg("Und", 290, 420, 310, 432)]},
        {"text": "Krankenhaus Nordwest GmbH Frankfurt Steinbacher Hohl 2-26 D-60488 Frankfurtam Main", "word_regions": [
            _seg("Krankenhaus Nordwest GmbH Frankfurt", 176, 468, 428, 486),
            _seg("Steinbacher Hohl 2-26 D-60488 Frankfurtam Main", 200, 488, 400, 524),
        ]},
        {"text": "Langer Absatz " * 40, "word_regions": [_seg("Langer Absatz " * 40, 40, 600, 560, 800)]},
    ],
}


def _ref(snippet, *, page=1, bbox=None, version="v1", **extra):
    return {"evidence_id": "e", "field_ref": "x", "document_version_id": version, "page": page, "snippet": snippet, "bbox": bbox, **extra}


def test_match_key_ignores_spaces_and_signs():
    assert match_key("Frankfurt am Main") == match_key("Frankfurtam  Main")
    assert match_key("Impella® AIC") == match_key("Impella®AIC")
    assert same_text("01.04.2025", "01. 04. 2025")
    assert not same_text("", "")


def test_locate_finds_the_text_across_segments_and_is_exact():
    box, exact = locate(PAGE, "Krankenhaus Nordwest GmbH Frankfurt Steinbacher Hohl 2-26 D-60488 Frankfurt am Main")
    assert exact
    assert box == {"x0": 176.0, "y0": 468.0, "x1": 428.0, "y1": 524.0}


def test_locate_is_only_approximate_when_the_box_is_much_larger_than_the_quote():
    box, exact = locate(PAGE, "Langer Absatz")
    assert not exact and box["y0"] == 600.0


def test_locate_returns_none_when_the_quote_is_not_on_the_page():
    assert locate(PAGE, "Krankenhaus Südwest") is None
    assert locate(PAGE, "a") is None


def test_verify_marks_exact_only_for_found_text_and_keeps_the_rest_honest():
    refs = [
        # Gespeicherte Box auf der falschen Stelle: der Text entscheidet, nicht die Box.
        _ref("Krankenhaus Nordwest GmbH Frankfurt", bbox={"x0": 220, "y0": 316, "x1": 380, "y1": 380}),
        _ref("Nicht auf der Seite", bbox={"x0": 1, "y0": 2, "x1": 3, "y1": 4}),
        _ref("Nicht auf der Seite"),
        _ref("Kein Seitenbezug", page=None),
        _ref("Krankenhaus Nordwest GmbH Frankfurt", version="anderes-dokument", bbox={"x0": 1, "y0": 2, "x1": 3, "y1": 4}),
    ]
    out = verify_evidence_locations(refs, [PAGE], "v1")
    assert [(r["location"], r["text_verified"]) for r in out] == [
        ("exact", True), ("approx", False), ("page", False), ("none", False), ("approx", False),
    ]
    assert out[0]["bbox"] == {"x0": 176.0, "y0": 468.0, "x1": 428.0, "y1": 486.0}
    assert out[0]["supports_exact_navigation"] is True


def test_legacy_docling_artifacts_are_flipped_once():
    assert legacy_bottom_up({"provenance": {"provider": "docling", "canonical_schema_version": "1.3.0"}})
    assert not legacy_bottom_up({"provenance": {"provider": "docling", "canonical_schema_version": "1.4.0"}})
    assert not legacy_bottom_up({"provenance": {"provider": "pymupdf", "canonical_schema_version": "1.3.0"}})

    elements = [{"region": {"page": 1, "x0": 10, "y0": 742, "x1": 50, "y1": 772}, "word_regions": [_seg("x", 10, 742, 50, 772)]}]
    _flip_regions(elements, 842.0)
    assert (elements[0]["region"]["y0"], elements[0]["region"]["y1"]) == (70.0, 100.0)
    assert (elements[0]["word_regions"][0]["region"]["y0"], elements[0]["word_regions"][0]["region"]["y1"]) == (70.0, 100.0)

    page = {"page": 1, "height_pt": 842.0, "legacy_bottom_up": True}
    ref = flip_stored_box(_ref("x", bbox={"x0": 10, "y0": 742, "x1": 50, "y1": 772}), [page])
    assert (ref["bbox"]["y0"], ref["bbox"]["y1"]) == (70.0, 100.0)
    untouched = flip_stored_box(_ref("x", bbox={"x0": 10, "y0": 742, "x1": 50, "y1": 772}), [{**page, "legacy_bottom_up": False}])
    assert untouched["bbox"]["y0"] == 742


class _CoordOrigin(str, Enum):
    BOTTOMLEFT = "BOTTOMLEFT"
    TOPLEFT = "TOPLEFT"


def test_docling_enum_origin_is_flipped():
    # Docling liefert ein Enum; str() ergibt „_CoordOrigin.BOTTOMLEFT“ – frueher wurde darum nie gedreht.
    prov = NS(bbox=NS(l=10, t=772, r=50, b=742, coord_origin=_CoordOrigin.BOTTOMLEFT))
    assert _coord_boxes(prov, 842.0) == (10.0, 70.0, 50.0, 100.0)
    top = NS(bbox=NS(l=10, t=70, r=50, b=100, coord_origin=_CoordOrigin.TOPLEFT))
    assert _coord_boxes(top, 842.0) == (10.0, 70.0, 50.0, 100.0)
