"""Database-Paket (STEP 10): SQLAlchemy-ORM, Session-Handling, Persistenz-Services.

WICHTIG: Der Import dieses Pakets darf KEINE DB-Verbindung oeffnen (Lazy via
`get_engine()`/`create_session()`), damit bestehende unit-Tests und Routen ohne
laufende Datenbank unveraendert funktionieren.
"""

from app.database.base import Base, NAMING_CONVENTION
from app.database.session import (
    create_session,
    get_engine,
    get_session_factory,
    reset_engine_for_tests,
    session_scope,
)
from app.database.models import (
    Organization,
    DocumentFile,
    DocumentVersion,
    DocumentArtifact,
    ProcessingRun,
    ProcessingSummary,
    ContractExtraction,
    ExtractionEvidence,
    CalculationRun,
    CalculationResult,
    CalculationReviewFlag,
    Contract,
    ContractDocument,
    ContractEquipment,
    ReviewAction,
)

__all__ = [
    "Base",
    "NAMING_CONVENTION",
    "create_session",
    "get_engine",
    "get_session_factory",
    "reset_engine_for_tests",
    "session_scope",
    "Organization",
    "DocumentFile",
    "DocumentVersion",
    "DocumentArtifact",
    "ProcessingRun",
    "ProcessingSummary",
    "ContractExtraction",
    "ExtractionEvidence",
    "CalculationRun",
    "CalculationResult",
    "CalculationReviewFlag",
    "Contract",
    "ContractDocument",
    "ContractEquipment",
    "ReviewAction",
]
