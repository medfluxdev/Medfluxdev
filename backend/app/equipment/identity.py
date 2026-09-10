"""Deterministische Geräte-Identitäts-Bewertung (PR-4).

Reine Funktionen – keine DB, keine KI. Die KI extrahiert nur Fakt-Felder
(Name, Hersteller, Modell, Serien-/Inventarnummer …); die BEWERTUNG
(identified_exact/partial/generic/ambiguous + review) wird hier in Code
abgeleitet. Es werden NIE Kennungen erfunden.
"""

from __future__ import annotations

from typing import Optional

from app.models.enums import IdentificationQuality, RelationshipQuality


def _has_any(*values: Optional[str]) -> bool:
    return any(v is not None and str(v).strip() != "" for v in values)


def identification_quality(
    *,
    serial_number: Optional[str] = None,
    inventory_number: Optional[str] = None,
    device_name: Optional[str] = None,
    model: Optional[str] = None,
    manufacturer: Optional[str] = None,
    equipment_category: Optional[str] = None,
) -> IdentificationQuality:
    """Sicherheit der Geräte-Identität (aus belegten Kennungen).

    - EXACT   : eindeutige Kennung (Serien- ODER Inventarnummer) belegt.
    - PARTIAL : benannte Identität (Name/Modell/Hersteller), KEINE eindeutige
                Kennung -> nicht eindeutig identifizierbar (Manual Review).
    - GENERIC : nur generische Kategorie (z. B. "Kühlgeräte") -> Review.
    - UNKNOWN : keine nutzbare Identität.
    """
    if _has_any(serial_number, inventory_number):
        return IdentificationQuality.EXACT
    if _has_any(device_name, model, manufacturer):
        return IdentificationQuality.PARTIAL
    if _has_any(equipment_category):
        return IdentificationQuality.GENERIC
    return IdentificationQuality.UNKNOWN


def relationship_quality(
    identification: IdentificationQuality,
    *,
    has_evidence: bool = False,
) -> RelationshipQuality:
    """Beziehungswahrscheinlichkeit Gerät<->Vertrag.

    Eindeutige Kennung MIT Beleg -> exact (vertrauenswürdige Zuordnung).
    Eindeutige Kennung OHNE Beleg -> partial (Identität eindeutig, aber
    Vertrags-Zuordnung nicht belegt). Partielle/Generische/Unbekannte
    Identität -> partial/generic/ambiguous.
    """
    if identification == IdentificationQuality.EXACT:
        return RelationshipQuality.EXACT if has_evidence else RelationshipQuality.PARTIAL
    if identification == IdentificationQuality.PARTIAL:
        return RelationshipQuality.PARTIAL
    if identification == IdentificationQuality.GENERIC:
        return RelationshipQuality.GENERIC
    return RelationshipQuality.AMBIGUOUS


def requires_manual_review(rel: RelationshipQuality) -> bool:
    """Nur exact/belegt darf autoritativ ohne Review stehen.

    Partielle, generische oder mehrdeutige Beziehung -> manueller Review
    (niemals in eine autoritative Zuordnung umwandeln).
    """
    return rel in (
        RelationshipQuality.PARTIAL,
        RelationshipQuality.GENERIC,
        RelationshipQuality.AMBIGUOUS,
    )


def review_reason_de(rel: RelationshipQuality) -> Optional[str]:
    mapping = {
        RelationshipQuality.PARTIAL: (
            "Gerät nur teilweise identifiziert (keine eindeutige Serien-/"
            "Inventarnummer vorhanden)."
        ),
        RelationshipQuality.GENERIC: (
            "Nur generische Geräte-/Wartungsbeschreibung – nicht eindeutig."
        ),
        RelationshipQuality.AMBIGUOUS: (
            "Geräte-Zuordnung mehrdeutig bzw. ohne nutzbare Identität – "
            "Beleg reicht für eine autoritative Zuordnung nicht aus."
        ),
    }
    return mapping.get(rel)


def identity_fingerprint(
    *,
    serial_number: Optional[str] = None,
    inventory_number: Optional[str] = None,
    model: Optional[str] = None,
    manufacturer: Optional[str] = None,
    device_name: Optional[str] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Stabile Schlüssel-Helfer für die canonical equipment-Master-Zuordnung.

    Liefert (serial, inventory) als die bevorzugten Org-scoped Identifier.
    Für nicht-eindeutige Geräte wird NICHT auf einen trügerischen
    Kennungs-String gemergt (kein Raten).
    """
    return (
        serial_number.strip() if serial_number and serial_number.strip() else None,
        inventory_number.strip() if inventory_number and inventory_number.strip() else None,
    )
