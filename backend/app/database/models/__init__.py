"""Registriert alle ORM-Modelle (fuer Beziehungs-Aufloesung + Alembic-Autogenerate)."""

from app.database.models.organization import Organization
from app.database.models.application_setting import ApplicationSetting
from app.database.models.document import DocumentFile, DocumentVersion
from app.database.models.artifact import DocumentArtifact
from app.database.models.processing import ProcessingRun, ProcessingSummary
from app.database.models.extraction import ContractExtraction, ExtractionEvidence
from app.database.models.calculation import (
    CalculationRun,
    CalculationResult,
    CalculationReviewFlag,
)
from app.database.models.contract import Contract, ContractDocument, ContractEquipment
from app.database.models.equipment import Equipment
from app.database.models.work_item import WorkItem
from app.database.models.review import ReviewAction
from app.database.models.override import ContractOverride
from app.database.models.fact_review import ContractReview, FactReview
from app.database.models.demo import DemoWorkspace, DemoWorkspaceEntry
from app.database.models.warning import ContractWarning, WarningEvaluationRun

__all__ = [
    "Organization",
    "ApplicationSetting",
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
    "Equipment",
    "WorkItem",
    "ReviewAction",
    "ContractOverride",
    "FactReview",
    "ContractReview",
    "DemoWorkspace",
    "DemoWorkspaceEntry",
    "WarningEvaluationRun",
    "ContractWarning",
]
