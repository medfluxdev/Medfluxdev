"""Dashboard-Paket (STEP 12) – Uebersichts-Read-Model.

- `models.py`: getrennte, explizit getypte Response-DTOs.
- `service.py`: READ-ONLY, deterministischer, org-gebundener Lese-Dienst auf
  Basis akzeptierter Lauefe + aktiver STEP-11-Warnungen (keine KI, keine
  Neuberechnung von Warnungen im Dashboard).
"""

from app.dashboard.models import (
    ActionItem,
    DashboardOverview,
    DataFreshness,
    DataQualityItem,
    DeadlineBucket,
    FinancialSummary,
    KpiCard,
    MoneyTotal,
)
from app.dashboard.service import DashboardError, build_dashboard_overview

__all__ = [
    "ActionItem",
    "DashboardError",
    "DashboardOverview",
    "DataFreshness",
    "DataQualityItem",
    "DeadlineBucket",
    "FinancialSummary",
    "KpiCard",
    "MoneyTotal",
    "build_dashboard_overview",
]
