"""Berechnungs-Modelle & Statusen (STEP 9).

Trennt KLAR die berechneten Resultate von den extrahierten Daten. Jedes
berechnete Feld ist eigenständig repräsentierbar als Wert + Status +
Erklärung + verwendete Eingaben, damit ein einzelner Fehlschlag nicht alle
anderen Berechnungen invalidieren kann und jedes Ergebnis nachvollziehbar ist.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from app.models.enums import ContractStatus


class CalculationStatus(str, Enum):
    """Outcome einer einzelnen Berechnung bzw. eines Feldes.

    Passt zum bestehenden Enum-Stil (str-Enum, snake_case-Werte).
    """

    CALCULATED = "calculated"          # deterministisch aus Eingaben berechnet
    EXPLICIT = "explicit"              # direkt aus dem Vertrag übernommen
    NOT_CALCULABLE = "not_calculable"  # Eingaben fehlen/ereignisbasiert
    REVIEW_REQUIRED = "review_required"  # mehrdeutig, aber prüfbar
    CONFLICT = "conflict"              # widersprüchliche Eingaben


class TaxBasis(str, Enum):
    """Steuer-Basis eines Betrags (future-safe Darstellung).

    Wird NUR gesetzt, wenn der Vertrag das explizit hergibt; sonst UNKNOWN.
    Es wird NIEMALS Netto/Brutto erfunden oder eine 19 %-Mehrwertsteuer
    angenommen.
    """

    UNKNOWN = "unknown"
    NET = "net"
    GROSS = "gross"


class DateCalculationKind(str, Enum):
    """Wie ein berechnetes Datumsfeld zustande kam (Erklärbarkeit)."""

    EXPLICIT = "explicit"                     # direkt extrahiert
    DERIVED_START_PLUS_DURATION = "derived_start_plus_duration"
    RENEWAL_SHIFT = "renewal_shift"           # automatische Verlängerung
    CALENDAR_SUBTRACTION = "calendar_subtraction"


class DateTimeResult(BaseModel):
    """Ein berechnetes Datum mit Status, Erklärung und Eingabe-Provenienz."""

    value: Optional[date] = None
    status: CalculationStatus = CalculationStatus.NOT_CALCULABLE
    kind: Optional[DateCalculationKind] = None
    explanation: str = ""
    inputs: dict[str, str] = Field(default_factory=dict)   # stabile Feldreferenzen
    review_required: bool = False


class DifferenceResult(BaseModel):
    """Differenz (Tage) zu einem expliziten `as_of_date`.

    Negative Werte gelten als gültig (bereits vergangen) und werden NICHT auf
    Null geklemmt – das würde Information verlieren.
    """

    value: Optional[int] = None  # Tage (negativ möglich), None wenn nicht berechenbar
    status: CalculationStatus = CalculationStatus.NOT_CALCULABLE
    target_date: Optional[date] = None
    as_of_date: Optional[date] = None
    explanation: str = ""
    inputs: dict[str, str] = Field(default_factory=dict)
    review_required: bool = False


class CalcDuration(BaseModel):
    """Kanonische kalenderbewusste Dauer (für interne Arithmetik)."""

    days: int = Field(default=0, ge=0)
    weeks: int = Field(default=0, ge=0)
    months: int = Field(default=0, ge=0)
    years: int = Field(default=0, ge=0)


class RenewalBoundary(BaseModel):
    """Eine berechnete Vertrags-/Verlängerungsgrenze."""

    period_index: int = Field(ge=0)  # 0 = initiale Laufzeit, 1 = erste Verlängerung ...
    start_date: date
    end_date: date
    kind: DateCalculationKind = DateCalculationKind.DERIVED_START_PLUS_DURATION
    explanation: str = ""
    review_required: bool = False


class CalculatedDateField(BaseModel):
    """Gesamtheit der berechneten Datumsfelder für EINEN Vertrag."""

    calculated_end_date: DateTimeResult = Field(default_factory=DateTimeResult)
    latest_cancellation_date: DateTimeResult = Field(default_factory=DateTimeResult)
    next_renewal_date: DateTimeResult = Field(default_factory=DateTimeResult)
    days_until_end: DifferenceResult = Field(default_factory=DifferenceResult)
    days_until_latest_cancellation: DifferenceResult = Field(
        default_factory=DifferenceResult
    )
    current_contract_status: ContractStatusDerivation = Field(
        default_factory=lambda: ContractStatusDerivation()
    )
    renewal_boundaries: list[RenewalBoundary] = Field(default_factory=list)


class ContractStatusDerivation(BaseModel):
    """Objektiver, code-berechneter Vertragsstatus.

    Nur objektiv ableitbare Zustände STEP 9: ACTIVE / EXPIRED / UNKNOWN.
    TERMINATED wird NUR gemeldet, wenn explizit extrahiert (contract.status
    == TERMINATED o. ä. / manuelles Kündigungs-Evidence vorliegt). Keine
    Risiko-Warnung (EXPIRING_SOON gehört zu STEP 11).
    """

    status: ContractStatus = ContractStatus.UNKNOWN
    explanation: str = ""
    used_as_of_date: Optional[date] = None
    inputs: dict[str, str] = Field(default_factory=dict)


class MoneyFieldResult(BaseModel):
    """Ein berechneter Geldwert (Decimal-exakt) mit Status/Erklärung."""

    value: Optional[Decimal] = Field(
        default=None, description="Exaktes Decimal; None = unbekannt/nicht berechenbar"
    )
    currency: Optional[str] = None
    status: CalculationStatus = CalculationStatus.NOT_CALCULABLE
    explanation: str = ""
    inputs: dict[str, str] = Field(default_factory=dict)
    review_required: bool = False


class RecurringCostNormalized(BaseModel):
    """Normalisierter wiederkehrender Kostenwert (SELF_A: pro Standardperiode)."""

    annual: MoneyFieldResult = Field(default_factory=MoneyFieldResult)
    monthly: MoneyFieldResult = Field(default_factory=MoneyFieldResult)
    # Umbuchungs-/Korrelations-Diagnose
    source_period: str = "unknown"
    corroboration: Optional[str] = None


class CostCategory(BaseModel):
    """Eine Kostenkategorie; aggregiert NUR vergleichbare Einheiten derselben Währung.

    `not_aggregatable`-Anteile (z. B. stündlich je Stunde, Reise-/Material-
    kosten, bedingte Zusatzkosten) werden separat, nie blind addiert.
    """

    key: str
    label: str
    currency: Optional[str] = None
    amount: Optional[Decimal] = None  # exakt aggregierter Wert (gleiche Währung)
    status: CalculationStatus = CalculationStatus.NOT_CALCULABLE
    explanation: str = ""
    inputs: list[str] = Field(default_factory=list)
    components: list[MoneyFieldResult] = Field(default_factory=list)


class CostTaxBreakdown(BaseModel):
    """Netto/Brutto-Aufteilung der wiederkehrenden Kosten (UAT Defect Batch A).

    Wird ausschliesslich deterministisch abgeleitet, wenn eine verlaessliche
    Steuer-Basis **UND** ein Steuersatz bekannt sind. `computed` ist False, sobald
    Basis oder Satz fehlen – es wird NIEMALS eine 19%-Mehrwertsteuer angenommen
    oder ein Brutto erfunden (`expanded_euros`/`netto` bleiben dann None).

    `base_tax_basis` sagt, in welcher Basis das kanonische recurring-Ergebnis
    vorliegt (net -> netto = Basis; gross -> brutto = Basis). Die Gegen-Basis
    wird exakt (Decimal) ueber den Satz abgeleitet.
    """

    computed: bool = False
    base_tax_basis: TaxBasis = TaxBasis.UNKNOWN
    rate_percent: Optional[float] = None
    currency: Optional[str] = None
    monthly_net: Optional[Decimal] = None
    monthly_gross: Optional[Decimal] = None
    annual_net: Optional[Decimal] = None
    annual_gross: Optional[Decimal] = None
    # Umsatzsteuerbeträge (gross - net), nur bei computed=True gesetzt.
    monthly_tax: Optional[Decimal] = None
    annual_tax: Optional[Decimal] = None
    explanation: str = ""


class PriceDevelopmentItem(BaseModel):
    """Preisentwicklung/Preisfixierung eines Vertrags (evidence-getragen).

    Ein Fakten-String (z. B. „Festpreis über 8 Jahre") plus Provenienz zum
    extrahierten Feld. Wird NIE neu interpretiert – nur extrahierte Angaben
    werden angezeigt.
    """

    key: str
    label: str
    text: Optional[str] = None
    evidence_field_ref: Optional[str] = None
    status: CalculationStatus = CalculationStatus.NOT_CALCULABLE
    # Deterministisch aus dem Fakten-Text geparste Fixpreis-Dauer (Jahre),
    # z. B. „Festpreis über 8 Jahre" -> 8. Nur gesetzt, wenn belegbar.
    period_years: Optional[int] = None


class CalculateContractCosts(BaseModel):
    """Gesamtheit der berechneten Kostenfelder für EINEN Vertrag."""

    normalized_recurring: RecurringCostNormalized = Field(
        default_factory=RecurringCostNormalized
    )
    # Repräsentierbarer Gesamtvertragswert. `total_contract_value_status` bleibt
    # aus Rückwärtskompatibilität erhalten und spiegelt dessen Status.
    total_contract_value: MoneyFieldResult = Field(default_factory=MoneyFieldResult)
    total_contract_value_status: CalculationStatus = CalculationStatus.NOT_CALCULABLE
    currency_conflict: bool = False
    tax_basis: TaxBasis = TaxBasis.UNKNOWN
    tax_rate_percent: Optional[float] = None
    category_totals: list[CostCategory] = Field(default_factory=list)
    # UAT Defect Batch A: Netto/Brutto-Aufteilung + Preisfixierung/-entwicklung.
    tax_breakdown: CostTaxBreakdown = Field(default_factory=CostTaxBreakdown)
    price_development: list[PriceDevelopmentItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def recurring_cost_conflict(self) -> bool:
        """True, wenn sich normalisierte wiederkehrende Kosten widersprechen."""
        return (
            self.normalized_recurring.annual.status == CalculationStatus.CONFLICT
        )


class ContractCalculationResult(BaseModel):
    """Ergebnis der Date & Cost Engine für einen Vertrag (STEP 9).

    Vollständig vom Extraktionsmodell getrennt; enthält nur berechnete Werte.
    """

    contract_id: Optional[str] = None
    as_of_date: date
    calculation_version: str = "step9-1.1"
    dates: CalculatedDateField = Field(default_factory=CalculatedDateField)
    costs: CalculateContractCosts = Field(default_factory=CalculateContractCosts)
    overall_review_required: bool = False
    review_reasons: list[str] = Field(default_factory=list)
