"""Search over the organisation structure (WP1.3).

Pure functions over already-loaded rows so the ranking is unit-testable
without a database. Scope filtering happens in the route before calling in.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence
from uuid import UUID

MAX_RESULTS = 25


@dataclass(frozen=True)
class SearchHit:
    kind: str                     # "department" | "cost_center"
    id: str
    code: str
    name: str
    hospital_id: str
    hospital_name: str
    path: tuple[str, ...]         # root ... leaf (department names)
    unit_type: Optional[str]
    department_id: Optional[str]  # for cost centers
    is_active: bool
    score: int

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "id": self.id,
            "code": self.code,
            "name": self.name,
            "hospital_id": self.hospital_id,
            "hospital_name": self.hospital_name,
            "path": list(self.path),
            "path_label": " › ".join(self.path),
            "unit_type": self.unit_type,
            "department_id": self.department_id,
            "is_active": self.is_active,
        }


def department_path(department, by_id: dict) -> tuple[str, ...]:
    """Root-first name chain; cycle-safe (a corrupt parent chain never loops)."""
    names: list[str] = []
    seen: set = set()
    cursor = department
    while cursor is not None and cursor.id not in seen:
        seen.add(cursor.id)
        names.append(cursor.name)
        cursor = by_id.get(cursor.parent_id) if cursor.parent_id else None
    return tuple(reversed(names))


def _score(query: str, code: str, name: str) -> int:
    q = query.casefold()
    c, n = (code or "").casefold(), (name or "").casefold()
    if q == c:
        return 100
    if c.startswith(q):
        return 80
    if n.startswith(q):
        return 60
    if q in c:
        return 40
    if q in n:
        return 30
    return 0


def search_structure(query: str, *, hospitals: Iterable, departments: Iterable, cost_centers: Iterable,
                     limit: int = MAX_RESULTS) -> list[SearchHit]:
    query = (query or "").strip()
    if len(query) < 2:
        return []
    hospital_names = {h.id: h.name for h in hospitals}
    departments = list(departments)
    dept_by_id = {d.id: d for d in departments}
    hits: list[SearchHit] = []

    for d in departments:
        score = _score(query, d.code, d.name)
        if score:
            hits.append(SearchHit(
                kind="department", id=str(d.id), code=d.code, name=d.name,
                hospital_id=str(d.hospital_id), hospital_name=hospital_names.get(d.hospital_id, ""),
                path=department_path(d, dept_by_id), unit_type=getattr(d, "unit_type", None),
                department_id=None, is_active=bool(d.is_active), score=score,
            ))

    for c in cost_centers:
        score = _score(query, c.code, c.name)
        if score:
            dept = dept_by_id.get(c.department_id) if c.department_id else None
            path = department_path(dept, dept_by_id) if dept is not None else ()
            hits.append(SearchHit(
                kind="cost_center", id=str(c.id), code=c.code, name=c.name,
                hospital_id=str(c.hospital_id), hospital_name=hospital_names.get(c.hospital_id, ""),
                path=path, unit_type=None,
                department_id=str(c.department_id) if c.department_id else None,
                is_active=bool(c.is_active), score=score,
            ))

    hits.sort(key=lambda h: (-h.score, not h.is_active, h.code.casefold(), h.name.casefold()))
    return hits[:limit]
