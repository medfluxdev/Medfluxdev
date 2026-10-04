"""Typed enterprise CLM primitives for MedFlux.

The models separate extracted facts from operational intelligence. They are
vendor-neutral and evidence-first so they can be populated by Qwen, reviewed by
humans and projected deterministically into persistence/workflows.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.evidence import SourceEvidence


RelationType = Literal[
    "amends", "supersedes", "references", "renews", "governs",
    "covers", "ordered_by", "corroborates", "conflicts_with",
]
AuthorityLevel = Literal["primary", "secondary", "unknown"]
ObligationStatus = Literal["proposed", "active", "satisfied", "breached", "waived", "unknown"]
PolicyOutcome = Literal["pass", "warn", "fail", "unknown"]
ActionKind = Literal[
    "review", "assign", "notify", "request_document", "verify_invoice",
    "create_work_item", "link_equipment",
]


class ContractRelation(BaseModel):
    relation_type: RelationType
    source_contract_id: Optional[UUID] = None
    target_contract_id: Optional[UUID] = None
    source_document_version_id: Optional[UUID] = None
    target_document_version_id: Optional[UUID] = None
    authority: AuthorityLevel = "unknown"
    rationale: Optional[str] = None
    evidence: list[SourceEvidence] = Field(default_factory=list)


class ContractGraph(BaseModel):
    contract_id: Optional[UUID] = None
    relations: list[ContractRelation] = Field(default_factory=list)


class ObligationCondition(BaseModel):
    kind: Literal["date", "event", "threshold", "state", "manual"]
    expression: str
    evidence: list[SourceEvidence] = Field(default_factory=list)


class Obligation(BaseModel):
    key: str
    title: str
    description: Optional[str] = None
    owner_role: Optional[str] = None
    status: ObligationStatus = "proposed"
    due_date: Optional[date] = None
    recurrence: Optional[str] = None
    conditions: list[ObligationCondition] = Field(default_factory=list)
    source_field_refs: list[str] = Field(default_factory=list)
    evidence: list[SourceEvidence] = Field(default_factory=list)
    requires_review: bool = True


class ObligationInstance(BaseModel):
    obligation_key: str
    occurrence_key: str
    due_date: Optional[date] = None
    status: ObligationStatus = "active"
    completed_at: Optional[datetime] = None
    evidence: list[SourceEvidence] = Field(default_factory=list)


class PolicyCheck(BaseModel):
    key: str
    description: str
    expected: Any = None
    source_field_refs: list[str] = Field(default_factory=list)


class PolicyDecision(BaseModel):
    policy_key: str
    outcome: PolicyOutcome
    explanation: str
    evidence: list[SourceEvidence] = Field(default_factory=list)
    requires_review: bool = False


class PortfolioQuestion(BaseModel):
    query: str
    contract_ids: list[UUID] = Field(default_factory=list)
    supplier: Optional[str] = None
    equipment_id: Optional[UUID] = None
    as_of_date: Optional[date] = None


class PortfolioResult(BaseModel):
    answer: str
    contract_ids: list[UUID] = Field(default_factory=list)
    evidence: list[SourceEvidence] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class ActionProposal(BaseModel):
    kind: ActionKind
    reason: str
    contract_id: Optional[UUID] = None
    work_item_type: Optional[str] = None
    assignee_role: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence: list[SourceEvidence] = Field(default_factory=list)
    requires_human_approval: bool = True
