"""Vertrags-Portfolio-Suche (STEP 13) – PostgreSQL-authoritative, org-gebunden.

- `models.py`: minimale, getrennt getypte Response-DTOs (keine roh-Evidence).
- `service.py`: READ-ONLY, deterministischer Lese-Dienst. Postgres macht Filter,
  Ranking (exakt > praefix > FTS > fuzzy), Sortierung und Pagination.
  STEP-11-Warn-Semantik/STEP-9-Finanzen bleiben autoritativ; KEINE KI/Neuberechnung.
"""

from app.contracts.search.models import (
    ContractFacets,
    ContractFinance,
    ContractListItem,
    ContractListResponse,
    ContractWarningSummary,
    SearchFreshness,
)
from app.contracts.search.service import (
    FUZZY_MIN_LENGTH,
    MAX_QUERY_LENGTH,
    PAGE_SIZES,
    RISK_ALLOWLIST,
    SORT_ALLOWLIST,
    STATUS_ALLOWLIST,
    VALID_DIRECTIONS,
    WARNING_TYPE_ALLOWLIST,
    SearchError,
    SearchParams,
    build_contract_search,
    normalize_q,
)

__all__ = [
    "FUZZY_MIN_LENGTH",
    "MAX_QUERY_LENGTH",
    "PAGE_SIZES",
    "RISK_ALLOWLIST",
    "SORT_ALLOWLIST",
    "STATUS_ALLOWLIST",
    "VALID_DIRECTIONS",
    "WARNING_TYPE_ALLOWLIST",
    "ContractFacets",
    "ContractFinance",
    "ContractListItem",
    "ContractListResponse",
    "ContractWarningSummary",
    "SearchError",
    "SearchFreshness",
    "SearchParams",
    "build_contract_search",
    "normalize_q",
]
