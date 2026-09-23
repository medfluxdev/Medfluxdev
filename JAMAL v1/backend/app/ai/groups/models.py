"""Feldgruppen-Modelle für die spezialisierte Extraktion (STEP 8B-Semantik).

Statt die KI jedes Mal das GESAMTE `Contract`-Schema extrahieren zu lassen,
werden bewusst KLEINE, semantische Feldgruppen abgefragt. Jede Gruppe ist eine
dünne Hülle um die bestehenden Medflux-Modelle (ContractIdentity, Equipment,
ContractDates, Termination, Costs, Payment, Services, SLA) – es wird KEIN
paralleles Fachmodell eingeführt.

Die Gruppen (je ein kleiner JSON-Schema für Ollama `format`):
  - identity_equipment   -> identity + equipment
  - dates_termination    -> dates + termination
  - costs_payment        -> costs + payment
  - services_sla         -> services + sla

Die Felder werden deterministisch in das `Contract`-Modell übernommen.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.models.contract import (
    ContractDates,
    ContractIdentity,
    Costs,
    Equipment,
    Payment,
    SLA,
    Services,
    Termination,
)


class IdentityEquipmentGroup(BaseModel):
    """Vertragsidentität + abgedeckte Geräte."""

    identity: ContractIdentity = Field(default_factory=ContractIdentity)
    equipment: list[Equipment] = Field(default_factory=list)


class DatesTerminationGroup(BaseModel):
    """Laufzeit-/Terminangaben + Kündigungsbedingungen."""

    dates: ContractDates = Field(default_factory=ContractDates)
    termination: Termination = Field(default_factory=Termination)


class CostsPaymentGroup(BaseModel):
    """Kosten- und Zahlungsbedingungen."""

    costs: Costs = Field(default_factory=Costs)
    payment: Payment = Field(default_factory=Payment)


class ServicesSlaGroup(BaseModel):
    """Leistungsumfang + Service-Level."""

    services: Services = Field(default_factory=Services)
    sla: SLA = Field(default_factory=SLA)
