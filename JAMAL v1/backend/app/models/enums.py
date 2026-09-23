"""Enumerations für das Medflux-Vertragsdatenmodell.

Diese Enums sind bewusst klein und werden nur dort eingesetzt,
wo eine begrenzte, bekannte Wertmenge den Datenbestand beschreibt.
"""

from enum import Enum


class ContractStatus(str, Enum):
    """Gesamtstatus eines Vertrags (aus Code berechnet, nicht von der KI)."""

    ACTIVE = "active"
    EXPIRING_SOON = "expiring_soon"
    EXPIRED = "expired"
    TERMINATED = "terminated"
    DRAFT = "draft"
    UNKNOWN = "unknown"


class ContractType(str, Enum):
    """Art des Vertrags – von der KI extrahiert."""

    MAINTENANCE = "maintenance"
    SERVICE = "service"
    LEASE = "lease"
    RENTAL = "rental"
    OTHER = "other"
    UNKNOWN = "unknown"


class ReviewStatus(str, Enum):
    """Prüfstatus eines extrahierten Wertes."""

    REVIEWED = "reviewed"
    NEEDS_REVIEW = "needs_review"
    AUTO_ACCEPTED = "auto_accepted"


class RiskLevel(str, Enum):
    """Risikoeinstufung (wird später durch Code berechnet)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class TimeUnit(str, Enum):
    """Zeiteinheit für Fristen und Dauerangaben."""

    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"
    YEARS = "years"
    HOURS = "hours"


class BillingInterval(str, Enum):
    """Abrechnungsintervall."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    ONCE = "once"
    OTHER = "other"


class ExtractionStatus(str, Enum):
    """Status der strukturellen Extraktion durch die lokale KI."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ValidationStatus(str, Enum):
    """Status der schemabasierten Validierung der Extraktion."""

    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class EquipmentCategory(str, Enum):
    """Kategorie einer Anlage/eines Geräts."""

    DEVICE = "device"
    SYSTEM = "system"
    SOFTWARE = "software"
    BUILDING = "building"
    OTHER = "other"


class ExtractionMethod(str, Enum):
    """Methode, mit der ein Wert extrahiert wurde."""

    AI = "ai"
    MANUAL = "manual"
    PROGRAMMATIC = "programmatic"


class CancellationRelation(str, Enum):
    """Beziehung der Kündigungsfrist zum Vertragsende."""

    TO_CONTRACT_END = "to_contract_end"
    TO_RENEWAL_DATE = "to_renewal_date"
    UNKNOWN = "unknown"


class ReviewFlag(str, Enum):
    """Grund für einen erforderlichen manuellen Review."""

    MISSING = "missing"
    CONFLICT = "conflict"
    VAGUE = "vague"
    EVENT_BASED = "event_based"
    LOW_CONFIDENCE = "low_confidence"
    OTHER = "other"


class IdentificationQuality(str, Enum):
    """Wie sicher ist ein Gerät/Einheit identifiziert (PR-4, deterministisch).

    Wird ausschliesslich in Code abgeleitet (keine KI): eine eindeutige
    Serien-/Inventarnummer ist die stärkste Identität; Modell ohne Kennung
    oder generische Wartungs-Beschreibung bleibt schwächer.
    """

    EXACT = "exact"          # eindeutige Kennung (Serie/Inventar) vorhanden
    PARTIAL = "partial"      # Name+Modell, aber keine eindeutige Kennung
    GENERIC = "generic"      # generische Geräte-/Wartungsbeschreibung
    UNKNOWN = "unknown"      # keine nutzbare Geräte-Identität


class RelationshipQuality(str, Enum):
    """Beziehung Gerät<->Vertrag (PR-4, deterministisch aus Belegen).

    `exact`  = belegte, eindeutige Identität (Serie/Inventar) → vertrauenswürdig.
    `partial`= belegtes Modell/Name ohne eindeutige Kennung → prüfen.
    `generic`= generische Abdeckung (z. B. "Kühlgeräte") → prüfen.
    `ambiguous`= Beleg reicht für eine autoritative Zuordnung nicht aus.
    """

    EXACT = "exact"
    PARTIAL = "partial"
    GENERIC = "generic"
    AMBIGUOUS = "ambiguous"


class WorkItemType(str, Enum):
    """Art eines Arbeits-/Handlungspunkts (PR-4).

    Deckt die autoritativen Vertrags-Warnungen (STEP 11) sowie
    gerätebezogene Punkte ab. Es werden NIE künstliche Punkte erzeugt.
    """

    CANCELLATION_DEADLINE = "cancellation_deadline"
    CONTRACT_EXPIRY = "contract_expiry"
    AUTOMATIC_RENEWAL = "automatic_renewal"
    CONTRACT_EXPIRED = "contract_expired"
    MANUAL_REVIEW = "manual_review"
    MISSING_COST = "missing_cost"
    EQUIPMENT_COVERAGE_REVIEW = "equipment_coverage_review"
    EQUIPMENT_RELATIONSHIP_AMBIGUOUS = "equipment_relationship_ambiguous"
    SLA_ISSUE = "sla_issue"


class WorkItemStatus(str, Enum):
    """Menschlicher Lebenszyklus eines Arbeitspunkts (minimal, PR-4)."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
