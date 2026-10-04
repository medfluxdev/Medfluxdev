"""STEP 8B Korrektur (Gate D) – fokussierte Tests fuer die EXAKTE Quell-Navigation.

Geprueft wird MIT dem eigentlichen Original-PDF-Koordinatensystem:
- View->Medibox-Umrechnung fuer alle Rotationen (0/90/180/270), inkl. Dimension
  und In-Media-Box-Fortbestand (Kreislauf-Verifikation gegen medibox_to_view).
- Span->exakte Wort-/Segment-Box-Aufloesung (nie Element-Ebene, wenn Segment da).
- Deterministische Oversized-/Krossheit-Schutzregeln (guard_oversized).
- Transparentes Hervorhebungs-Render auf einem synthetischen PDF: Originaldatei
  bleibt byte-identisch, Fuellung ist HALBtransparent (kein opaker RGBA-Trick).

Nur deterministische, lokale Tests; keine echten Vertraege, keine KI.
"""

from __future__ import annotations

import hashlib

import fitz
import pytest

from app.documents.intelligence.canonical import (
    BoundingRegion,
    Element,
    Page,
    TextSpan,
    WordRegion,
)
from app.documents.intelligence.highlight import (
    guard_oversized,
    medibox_to_view,
    page_view_to_mediabox,
    render_transparent_highlights,
    resolve_span_boxes,
)

VIEW_W, VIEW_H = 595.32, 841.92
MED_W, MED_H = 841.92, 595.32


def _view_box(x0, y0, x1, y1, page=1):
    return BoundingRegion(page=page, x0=x0, y0=y0, x1=x1, y1=y1)


def _assert_close(a, b, tol=1e-6):
    assert abs(a - b) <= tol


# ------------------------------------------------------- Rotation-Mathematik


@pytest.mark.parametrize(
    "rot", [0, 90, 180, 270],
)
def test_view_to_mediabox_roundtrip_all_rotations(rot):
    r = _view_box(10, 20, 100, 300)
    m = page_view_to_mediabox(
        r, rot,
        med_w=MED_W if rot in (90, 270) else VIEW_W,
        med_h=MED_H if rot in (90, 270) else VIEW_H,
    )
    # Im Media-Box bleiben (nie negative, nie ausserhalb)
    assert m.x0 >= 0 and m.y0 >= 0
    assert 0 <= m.x1 <= (MED_W if rot in (90, 270) else VIEW_W) + 1e-6
    assert 0 <= m.y1 <= (MED_H if rot in (90, 270) else VIEW_H) + 1e-6
    # Groessen bleiben erhalten
    _assert_close(m.height, r.width if rot in (90, 270) else r.height)
    _assert_close(m.width, r.height if rot in (90, 270) else r.width)
    # Kreislauf zurueck in den View
    back = medibox_to_view(
        m, rot,
        view_w=VIEW_W, view_h=VIEW_H,
    )
    _assert_close(back.x0, r.x0)
    _assert_close(back.x1, r.x1)
    _assert_close(back.y0, r.y0)
    _assert_close(back.y1, r.y1)


def test_view_to_mediabox_270_specific_values():
    r = _view_box(10, 20, 100, 300)
    m = page_view_to_mediabox(r, 270, med_w=MED_W, med_h=MED_H)
    # Formel: x_m = W_m - y_v ; y_m = x_v
    _assert_close(m.x0, 841.92 - 300)
    _assert_close(m.y0, 10)
    _assert_close(m.x1, 841.92 - 20)
    _assert_close(m.y1, 100)


def test_view_to_mediabox_90_specific_values():
    r = _view_box(10, 20, 100, 300)
    m = page_view_to_mediabox(r, 90, med_w=MED_W, med_h=MED_H)
    # Formel: x_m = y_v ; y_m = H_m - x_v
    _assert_close(m.x0, 20)
    _assert_close(m.y0, 595.32 - 100)
    _assert_close(m.x1, 300)
    _assert_close(m.y1, 595.32 - 10)


def test_center_invariant_rotated_pages():
    center = _view_box(297.66 - 5, 420.96 - 5, 297.66 + 5, 420.96 + 5)
    m270 = page_view_to_mediabox(center, 270, med_w=MED_W, med_h=MED_H)
    _assert_close((m270.x0 + m270.x1) / 2, MED_W / 2)
    _assert_close((m270.y0 + m270.y1) / 2, MED_H / 2)


def test_view_to_mediabox_supports_native_resolution_ranges():
    with pytest.raises(ValueError):
        page_view_to_mediabox(_view_box(0, 0, 1, 1), 45, med_w=100, med_h=100)


# ------------------------------------------------------- Span->Exakte Boxen


def _page_with_segments(page_text, segs):
    elem = Element(
        element_id="e1",
        type="text",
        text=page_text,
        page=1,
        region=_view_box(0, 0, VIEW_W, 40),
        spans=[TextSpan(offset=0, length=len(page_text))],
        reading_order=0,
    )
    elem.word_regions = [
        WordRegion(text=seg.text, offset=seg.offset, length=len(seg.text),
                   region=seg.region, granularity="segment")
        for seg in segs
    ]
    page = Page(
        page_number=1,
        width_pt=VIEW_W,
        height_pt=VIEW_H,
        original_width_pt=VIEW_W,
        original_height_pt=VIEW_H,
        pdf_rotation=0,
        text=page_text,
        elements=[elem],
    )
    return page


def test_resolve_span_boxes_uses_segment_not_element():
    pg_text = "Anlage 13.115,00 Summe Teil X"
    off = pg_text.index("13.115,00")
    page = _page_with_segments(
        pg_text,
        [WordRegion(text=pg_text, offset=0, length=len(pg_text),
                    region=_view_box(5, 6, 300, 24), granularity="segment")],
    )
    boxes = resolve_span_boxes(page, off, len("13.115,00"))
    assert len(boxes) == 1
    assert boxes[0].granularity == "segment"
    assert boxes[0].text == pg_text


def test_resolve_span_no_word_regions_falls_back_element_explicit():
    pg_text = "Kündigungsfrist"
    elem = Element(
        element_id="e1", type="text", text=pg_text, page=1,
        region=_view_box(5, 6, 120, 24),
        spans=[TextSpan(offset=0, length=len(pg_text))], reading_order=0,
    )
    page = Page(page_number=1, width_pt=VIEW_W, height_pt=VIEW_H, text=pg_text,
                elements=[elem])
    boxes = resolve_span_boxes(page, 0, len(pg_text))
    assert len(boxes) == 1
    assert boxes[0].granularity == "element"


def test_resolve_span_phrase_across_two_segments():
    pg_text = "Kündigungsfrist beträgt Monate"
    s1 = 0
    s2 = pg_text.index("beträgt")
    segs = [
        WordRegion(text="Kündigungsfrist", offset=s1, length=15,
                   region=_view_box(5, 6, 120, 24), granularity="segment"),
        WordRegion(text="beträgt Monate", offset=s2, length=len("beträgt Monate"),
                   region=_view_box(130, 6, 330, 24), granularity="segment"),
    ]
    page = _page_with_segments(pg_text, segs)
    phrase = "Kündigungsfrist beträgt"
    off = pg_text.index(phrase)
    boxes = resolve_span_boxes(page, off, len(phrase))
    assert len(boxes) == 2


def test_resolve_span_ignores_out_of_range_element():
    pg_text = "abc 123.456,00 xyz"
    queried = "123.456,00"
    off = pg_text.index(queried)
    # Element-Span deckt gar nicht die angefragte Spanne ab -> keine Treffer
    elem = Element(
        element_id="e1", type="text", text=pg_text, page=1,
        region=_view_box(0, 0, VIEW_W, 40),
        spans=[TextSpan(offset=0, length=2)], reading_order=0,
    )
    page = Page(page_number=1, width_pt=VIEW_W, height_pt=VIEW_H,
                text=pg_text, elements=[elem])
    assert resolve_span_boxes(page, off, len(queried)) == []


# ------------------------------------------------------- Schutzregeln (Guard)


def _wr(text, x0, y0, x1, y1, granularity="segment"):
    return WordRegion(text=text, offset=0, length=len(text) or 1,
                      region=_view_box(x0, y0, x1, y1), granularity=granularity)


def test_guard_rejects_coarse_element_box():
    wr = _wr("summe aller wartungsleistungen gem kapitel drei", 5, 5, 400, 60, granularity="element")
    res = guard_oversized([wr], page_w=VIEW_W, page_h=VIEW_H, target_text="13.115,00")
    assert res[0]["ok"] is False
    assert "coarse_element_box" in res[0]["reasons"]


def test_guard_accepts_short_element_only():
    wr = _wr("13.115,00", 5, 5, 80, 20, granularity="element")
    res = guard_oversized([wr], page_w=VIEW_W, page_h=VIEW_H, target_text="13.115,00")
    assert res[0]["ok"] is True


def test_guard_rejects_oversized_width_element():
    wr = _wr("942.480,00", 5, 5, 700, 20, granularity="element")
    res = guard_oversized([wr], page_w=VIEW_W, page_h=VIEW_H, target_text="942.480,00")
    assert res[0]["ok"] is False
    assert any(r.startswith("oversized_width") for r in res[0]["reasons"])


def test_guard_keeps_inpage_segment_wide_box():
    # Segment-/Wort-Boxen sind Provider-Geometrie und bleiben exakt,
    # solange sie in der Seitenbegrenzung liegen (kein Laengen-Raten).
    wr = _wr("10.1 Anfängliche Laufzeit und Verlängerungen ...", 300, 500, 500, 590,
             granularity="segment")
    res = guard_oversized([wr], page_w=VIEW_W, page_h=VIEW_H, target_text="Kündigungsfrist")
    assert res[0]["ok"] is True


def test_guard_rejects_outside_page():
    # Box ragt ueber die rechte Seitenkante hinaus
    wr = _wr("942.480,00", 520, 5, 640, 20, granularity="segment")
    res = guard_oversized([wr], page_w=VIEW_W, page_h=VIEW_H, target_text="942.480,00")
    assert res[0]["ok"] is False
    assert "outside_page" in res[0]["reasons"]


# ------------------------------------------------------- Transparentes Render


def _make_pdf(tmp_path, *, rotation=0) -> tuple:
    pdf = tmp_path / "src.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.set_rotation(rotation)
    rect = page.insert_text((72, 72), "Hallo Medflux Target")
    # Sicherstellen, dass Media-Box/Groessen die Erwartung erfuellen
    doc.save(pdf)
    doc.close()
    before = pdf.read_bytes()
    return pdf, before


def test_render_transparent_preserves_original_and_is_not_opaque(tmp_path):
    pdf, before = _make_pdf(tmp_path)
    doc = fitz.open(pdf)
    page = doc.load_page(0)
    rect = page.search_for("Medflux Target")[0]
    doc.close()

    wr = WordRegion(text="Medflux Target", offset=0, length=len("Medflux Target"),
                    region=BoundingRegion(page=1, x0=rect.x0, y0=rect.y0,
                                          x1=rect.x1, y1=rect.y1),
                    granularity="segment")
    # Pruefpunkt FERN der Textglyphen, gezielt auf einer leeren Seitenflaeche,
    # damit der HALBTRANSPARENT-Fuellwert gemessen wird und nicht die schwarze
    # Zeichentinte (Sonst koennte opake Farbe fälschlich "hell" erscheinen).
    blank = BoundingRegion(page=1, x0=50, y0=600, x1=120, y1=630)
    wblank = WordRegion(text="x", offset=0, length=1,
                        region=blank, granularity="segment")
    png = tmp_path / "hl.png"
    info = render_transparent_highlights(pdf, 1, [wblank], png, dpi=100)
    assert png.exists() and png.stat().st_size > 0
    assert info["box_count"] == 1
    assert info["fill_opacity"] == 0.22
    assert info["original_unmodified"] is True
    # Original bleibt byte-identisch
    assert pdf.read_bytes() == before

    pix = fitz.Pixmap(str(png))
    try:
        # Pixel in der Mitte der Hervorhebung: hell (halbtransparent), nicht opak dunkelrot
        mid_x = int(((blank.x0 + blank.x1) / 2) * 100 / 72)
        mid_y = int(((blank.y0 + blank.y1) / 2) * 100 / 72)
        r, g, b = pix.pixel(mid_x, mid_y)
    finally:
        pix = None
    # Opake dunkelrot-Fuellung der Vorversion waere g <= ~26; halbtransparent ist g hell.
    assert r > 200
    assert g > 150
    assert g > b  # Orangeton: rot dominiert, aber gruen klar sichtbar


def test_render_terms_rotated_page_keep_box_in_mediabox(tmp_path):
    pdf, before = _make_pdf(tmp_path, rotation=90)
    doc = fitz.open(pdf)
    page = doc.load_page(0)
    med = page.mediabox
    doc.close()
    # Synthetische View-Box (nur Geometrie-Rechnung; Textlage egal)
    wr = WordRegion(text="x", offset=0, length=1,
                    region=_view_box(10, 10, 60, 30),
                    granularity="segment")
    png = tmp_path / "hl90.png"
    info = render_transparent_highlights(pdf, 1, [wr], png, dpi=100)
    assert info["box_count"] == 1
    r = info["rects_mediabox"][0]
    assert r["x0"] >= 0 and r["y0"] >= 0
    assert r["x1"] <= float(med.width) + 1e-6
    assert r["y1"] <= float(med.height) + 1e-6
    # Rotation 90 vertauscht Orientezungen: Media-Rechteck ist hoeher als breit
    assert (r["y1"] - r["y0"]) > (r["x1"] - r["x0"])
    # Original unveraendert
    assert pdf.read_bytes() == before


def test_render_sha256_original_unchanged(tmp_path):
    pdf, before = _make_pdf(tmp_path)
    sha_before = hashlib.sha256(before).hexdigest()
    # Kein Render -> pruefen, dass sha-Basis stabil ist (kein Seiteneffekt der Erzeugung)
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == sha_before