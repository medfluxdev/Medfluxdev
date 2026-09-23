"""Versionierte Warn-Policy (STEP 11).

Zentrale, versionierte Konfiguration der Fristen-Buckets (180/90/60/30/14/7)
und der Schweregrad-Zuordnung. Ein Krankenhaus kann spaeter eigene Vorlaufzeiten
konfigurieren, ohne die Engine umzuschreiben. Die Policy-Version wird bei jeder
Evaluation aufgezeichnet, damit historische Warnungen reproduzierbar bleiben.

KEINE Fristen/Konstanten im Engine-Code verstreut.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.contracts.warnings.models import WarningSeverity

# Kalendertage; Werte streng absteigend. 0 = heute fällig, <0 = verstrichen.
DEFAULT_MEDFLUX_THRESHOLDS: tuple[int, ...] = (180, 90, 60, 30, 14, 7)
DEFAULT_POLICY_VERSION = "step11-default-1"


@dataclass(frozen=True)
class WarningPolicy:
    """Unveränderliche, versionierte Warn-Policy.

    `thresholds` sind Vorlauf-Buckets in Kalendertagen (absteigend).
    Kalender-Tage; vertragliche Fristen werden NICHT still zu Arbeitstagen.
    """

    version: str = DEFAULT_POLICY_VERSION
    # Nur Buckets INTERN der positiven Frist; 0 (heute) und <0 (verstrichen)
    # werden von der Engine als eigene Zustände behandelt.
    thresholds: tuple[int, ...] = DEFAULT_MEDFLUX_THRESHOLDS

    @classmethod
    def default(cls) -> "WarningPolicy":
        return cls()

    def match_threshold(self, days: int) -> Optional[int]:
        """Liefert den zutreffenden Vorlauf-Bucket (Kalendertage) -> None.

        - days > 180        -> None (noch ausserhalb jeder Warnschwelle)
        - 91..180           -> 180
        - 61..90            -> 90
        - 31..60            -> 60
        - 15..30            -> 30
        - 8..14             -> 14
        - 1..7              -> 7
        - 0                 -> 0 (heute fällig)
        - <0                -> None (verstrichen; eigener Typ)
        """
        if days == 0:
            return 0
        if days < 0:
            return None
        # Kleinster Bucket, der die Restzeit noch abdeckt (= dringlichster,
        # genau passender Vorlauf). Dadurch: 91..180->180, 61..90->90, ... 1..7->7.
        matched = [t for t in self.thresholds if days <= t]
        return min(matched) if matched else None


def severity_for_days(days: int) -> Optional[WarningSeverity]:
    """Schweregrad aus Tagen (Kalendertage) – positive Annäherungs-Warnungen.

    91..180 -> LOW; 61..90 -> MEDIUM; 31..60 -> MEDIUM; 15..30 -> HIGH;
    8..14 -> HIGH; 1..7 -> CRITICAL; 0 -> CRITICAL; <0 -> CRITICAL;
    >180 -> None (keine Warnung).
    """
    if days <= 0:
        return WarningSeverity.CRITICAL
    if days <= 7:
        return WarningSeverity.CRITICAL
    if days <= 14:
        return WarningSeverity.HIGH
    if days <= 30:
        return WarningSeverity.HIGH
    if days <= 60:
        return WarningSeverity.MEDIUM
    if days <= 90:
        return WarningSeverity.MEDIUM
    if days <= 180:
        return WarningSeverity.LOW
    return None


def severity_to_risk(severity: Optional[WarningSeverity]) -> str:
    """Deterministische Projektion Warn-Schweregrad -> bestehendes RiskLevel-Enum.

    RiskLevel unterstuetzt nur low/medium/high/unknown (Kein neues Risiko-System).
    """
    if severity in (None, WarningSeverity.INFO):
        return "unknown" if severity is None else "low"
    if severity == WarningSeverity.LOW:
        return "low"
    if severity == WarningSeverity.MEDIUM:
        return "medium"
    # HIGH und CRITICAL fallen auf das bestehende Top-Level "high"
    return "high"


def field(refs: list[str]) -> str:
    return refs[0] if refs else ""
