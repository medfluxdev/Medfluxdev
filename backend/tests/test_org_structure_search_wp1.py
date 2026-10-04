"""WP1.3 — search over the organisation structure (pure, DB-free)."""
from types import SimpleNamespace
from uuid import uuid4

from app.organization_structure.search import department_path, search_structure


def _hospital(name):
    return SimpleNamespace(id=uuid4(), name=name)


def _dept(hospital, name, code, parent=None, unit_type=None, active=True):
    return SimpleNamespace(id=uuid4(), hospital_id=hospital.id, parent_id=parent.id if parent else None,
                           name=name, code=code, unit_type=unit_type, is_active=active)


def _cc(hospital, code, name, dept=None, active=True):
    return SimpleNamespace(id=uuid4(), hospital_id=hospital.id, department_id=dept.id if dept else None,
                           code=code, name=name, is_active=active)


def _heidelberg():
    hd = _hospital("Krankenhaus Heidelberg")
    klinik = _dept(hd, "Medizinische Klinik", "MK", unit_type="klinik")
    kardio = _dept(hd, "Kardiologie", "KARD", parent=klinik, unit_type="abteilung")
    hkl = _dept(hd, "Herzkatheter", "HKL", parent=kardio, unit_type="funktionsbereich")
    radio = _dept(hd, "Radiologie", "RAD", unit_type="abteilung")
    ct = _dept(hd, "CT", "CT", parent=radio)
    it = _dept(hd, "IT", "IT", active=False)
    centers = [
        _cc(hd, "471100", "Radiologie", radio),
        _cc(hd, "471110", "Röntgen", radio),
        _cc(hd, "471120", "CT", ct),
        _cc(hd, "471130", "MRT", radio),
        _cc(hd, "472110", "Herzkatheter", hkl),
    ]
    return hd, [klinik, kardio, hkl, radio, ct, it], centers


def test_cost_center_number_search_shows_department_and_hospital():
    hd, depts, centers = _heidelberg()
    hits = search_structure("471120", hospitals=[hd], departments=depts, cost_centers=centers)
    assert [h.kind for h in hits] == ["cost_center"]
    hit = hits[0].as_dict()
    assert hit["code"] == "471120" and hit["name"] == "CT"
    assert hit["hospital_name"] == "Krankenhaus Heidelberg"
    assert hit["path_label"] == "Radiologie › CT"


def test_department_hit_carries_full_path_root_first():
    hd, depts, centers = _heidelberg()
    hits = search_structure("herzk", hospitals=[hd], departments=depts, cost_centers=centers)
    kinds = {(h.kind, h.code) for h in hits}
    assert ("department", "HKL") in kinds and ("cost_center", "472110") in kinds
    dept_hit = next(h for h in hits if h.kind == "department")
    assert dept_hit.path == ("Medizinische Klinik", "Kardiologie", "Herzkatheter")
    assert dept_hit.unit_type == "funktionsbereich"


def test_prefix_on_code_ranks_above_substring_and_inactive_sorts_last():
    hd, depts, centers = _heidelberg()
    hits = search_structure("4711", hospitals=[hd], departments=depts, cost_centers=centers)
    assert [h.code for h in hits] == ["471100", "471110", "471120", "471130"]
    it_hits = search_structure("it", hospitals=[hd], departments=depts, cost_centers=centers)
    assert it_hits and it_hits[-1].code == "IT" and it_hits[-1].is_active is False


def test_short_or_empty_query_returns_nothing():
    hd, depts, centers = _heidelberg()
    assert search_structure("", hospitals=[hd], departments=depts, cost_centers=centers) == []
    assert search_structure("4", hospitals=[hd], departments=depts, cost_centers=centers) == []


def test_department_path_is_cycle_safe():
    hd = _hospital("X")
    a = _dept(hd, "A", "A")
    b = _dept(hd, "B", "B", parent=a)
    a.parent_id = b.id  # corrupt data: A -> B -> A
    by_id = {a.id: a, b.id: b}
    assert department_path(b, by_id) == ("A", "B")
