"""Provider-neutrale Konflikt-/Disparitaets-Diagnostik fuer Quellwerte (STEP 8B).

Beobachtete Realitaet: Ein Quellwert kann an verschiedenen Stellen des
Dokuments unterschiedlich stehen (z. B. Seriennummer "21115" im Scan/Brief
gegenueber "24445" in der Geraetetabelle). Medflux darf hier NIE raten und
darf NUR einen Wert bevorzugen, weil er plausibler wirkt. Stattdessen werden
alle Kandidaten mit ihren Quellen erhalten und als konfliktbehaftet markiert.

Absichtlich KEIN generischer Konflikt-Aufloesungsmotor – das Modell repraesentiert
nur den Zustand "mehrere Kandidaten" (ConflictStatus) so, dass ein
Downstream-System entweder durch manuellen Review oder durch strikte Regel
(Toleranz, exakte Uebereinstimmung) entscheiden kann.

Wichtig:
- Alle Werte werden als STRINGS im Original-Wortlaut bewahrt
  (`values_by_source`).
- `normal_forms` darf NICHT heimlich normalisiert werden; nur deterministische,
  eindeutige Normalisierung (z. B. deutsche Betraege "13.115,00") wird genutzt,
  um Kandidaten zu gruppieren.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.documents.intelligence.token_safety import safe_normalize_money, token_normal_form


class SourceType(str, Enum):
    """Art der Quelle eines Kandidaten (Recognition-Ebene)."""

    NATIVE_TEXT = "native"
    OCR_TEXT = "ocr"
    TABLE_CELL = "table_cell"
    DOCX = "docx"


class ValueCandidate(BaseModel):
    """Ein einzelner gelesener Kandidat mit Herkunft."""

    value: str = Field(description="Original-Wortlaut (unveraendert)")
    source_type: SourceType
    page: Optional[int] = Field(default=None, ge=1)
    source_text: Optional[str] = None
    element_id: Optional[str] = None
    ocr_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @property
    def location(self) -> str:
        src = self.source_type.value
        return f"{self.page or '-'}:{src}" if self.page else src


class DisparityStatus(str, Enum):
    """Zustand einer Kandidatengruppe nach deterministischer Gruppierung."""

    CONSISTENT = "consistent"
    CONFLICT = "conflict"
    SINGLE = "single"
    UNDETERMINED = "undetermined"


class ValueDisparity(BaseModel):
    """Ergebnis der Kandidaten-Gruppierung (keine Aufloesung, nur Diagnose)."""

    family: str = Field(description="Diagnose-Gruppe, z. B. 'serial', 'money'")
    candidates: list[ValueCandidate] = Field(default_factory=list)
    status: DisparityStatus = DisparityStatus.UNDETERMINED
    reasons: list[str] = Field(default_factory=list)
    review_required: bool = False


def grouped_normal_forms(values: list[ValueCandidate]) -> list[str]:
    """Deterministische Normalformen fuer die Gruppierung (kein Raten).

    Nutzt nur eindeutige, regellose Normalisierungen (deutsche Geldbetraege,
    Kleinschreibung, entkernte Whitespaces). Nicht eindeutig normalisierbare
    Werte bleiben in ihrer Rohform (query `token_normal_form`).
    """
    forms: list[str] = []
    for c in values:
        raw = (c.value or "").strip()
        if not raw:
            continue
        money = safe_normalize_money(raw)
        if money.ok:
            forms.append(f"money:{money.amount}")
        else:
            forms.append(token_normal_form(raw))
    return forms


def classify_values(family: str, values: list[ValueCandidate]) -> ValueDisparity:
    """Gruppiert Kandidaten deterministisch und markiert Konflikte.

    Status-Interpretation:
    - CONSISTENT: >=2 Kandidaten, ALLE gleiche Normalform.
    - SINGLE: genau 1 Kandidat.
    - CONFLICT: >=2 Kandidaten mit verschiedenen Normalformen.
    - UNDETERMINED: 0 Kandidaten oder nicht gruppierbar.

    Es wird NIE ein "richtiger" Wert bestimmt.
    """
    disp = ValueDisparity(family=family, candidates=list(values))
    forms = grouped_normal_forms(values)
    if len(forms) == 0:
        disp.status = DisparityStatus.UNDETERMINED
        disp.reasons.append("keine_kandidaten")
        return disp
    if len(forms) == 1:
        disp.status = DisparityStatus.SINGLE
        disp.reasons.append("single_kandidat_kein_konflikt")
        return disp
    unique = set(forms)
    if len(unique) == 1:
        disp.status = DisparityStatus.CONSISTENT
        disp.reasons.append(f"alle_kandidaten_gleich ({forms[0]})")
    else:
        disp.status = DisparityStatus.CONFLICT
        disp.review_required = True
        disp.reasons.append("mehrere_normalformen: " + ", ".join(sorted(unique)))
    return disp