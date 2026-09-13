"""Registriert alle ORM-Modelle (fuer Beziehungs-Aufloesung + Alembic-Autogenerate)."""

from app.database.models.organization import Organization
from app.database.models.organization_structure import Hospital, Department, CostCenter, ContractDepartment
from app.database.models.account import Account, AccountMembership
from app.database.models.login_session import LoginSession
from app.database.models.activity_log import ActivityLog
from app.database.models.application_setting import ApplicationSetting
from app.database.models.auth import AuditEvent, User
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
from app.database.models.work_item_collaboration import WorkItemCollaboration, WorkItemComment
from app.database.models.review import ReviewAction
from app.database.models.override import ContractOverride
from app.database.models.fact_review import ContractReview, FactReview
from app.database.models.demo import DemoWorkspace, DemoWorkspaceEntry
from app.database.models.warning import ContractWarning, WarningEvaluationRun
from app.database.models.intelligence import (
    ContractRelationRecord,
    ContractObligationRecord,
    PolicyDecisionRecord,
    IntelligenceEvent,
    ActionProposalRecord,
)

__all__ = [
    "Organization",
    "Hospital",
    "Department",
    "CostCenter",
    "ContractDepartment",
    "Account",
    "AccountMembership",
    "LoginSession",
    "ActivityLog",
    "ApplicationSetting",
    "User",
    "AuditEvent",
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
    "WorkItemCollaboration",
    "WorkItemComment",
    "ReviewAction",
    "ContractOverride",
    "FactReview",
    "ContractReview",
    "DemoWorkspace",
    "DemoWorkspaceEntry",
    "WarningEvaluationRun",
    "ContractWarning",
    "ContractRelationRecord",
    "ContractObligationRecord",
    "PolicyDecisionRecord",
    "IntelligenceEvent",
    "ActionProposalRecord",
]
