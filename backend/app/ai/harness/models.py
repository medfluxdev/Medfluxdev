from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Observation(StrictModel):
    topic: str
    summary: str
    block_refs: list[str]
    related_refs: list[str] = Field(default_factory=list)
    ambiguity: str | None = None


class VisualRegionReference(StrictModel):
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    block_id: str


class OptionItem(StrictModel):
    # Perception-level evidence only. "label" and "price_text" are observed
    # surface strings; whether an option is actually selected/applicable is
    # decided by Qwen, never by this perception schema.
    label: str
    price_text: str | None = None
    block_id: str
    region: VisualRegionReference | None = None
    control_region: VisualRegionReference | None = None
    nearby_text: list[str] = Field(default_factory=list)
    selection_hint: bool | None = None


class OptionCluster(StrictModel):
    cluster_label: str = ""
    options: list[OptionItem] = Field(default_factory=list)


class SelectionRelation(StrictModel):
    cluster: str
    option: str
    selected: bool
    applicability: Literal["applicable", "alternative", "superseded", "unknown"] = "unknown"
    block_ids: list[str] = Field(default_factory=list)
    reason: str = Field(default="", max_length=400)


class NumberRole(StrictModel):
    value: str
    role: Literal["contract_number", "order_number", "reference", "customer_number", "other"]
    block_ids: list[str] = Field(default_factory=list)
    reason: str = Field(default="", max_length=400)


class PrecedenceRule(StrictModel):
    document_type: str
    rank: int = Field(ge=1)
    block_ids: list[str] = Field(default_factory=list)
    reason: str = Field(default="", max_length=400)


class ContractMap(StrictModel):
    document_type: str | None = None
    purpose: str | None = None
    observations: list[Observation] = Field(default_factory=list)
    missing_material: list[str] = Field(default_factory=list)
    # V3 semantic surface. These fields are established by Qwen reasoning only;
    # deterministic code may *apply* them but never *decide* them.
    selections: list[SelectionRelation] = Field(default_factory=list)
    number_roles: list[NumberRole] = Field(default_factory=list)
    precedence: list[PrecedenceRule] = Field(default_factory=list)
    unresolved_references: list[str] = Field(default_factory=list)


class EvidenceRef(StrictModel):
    block_id: str
    quote: str = Field(min_length=1)


class FactCandidate(StrictModel):
    field: str
    value: JsonValue = None
    normalized_value: JsonValue = None
    status: Literal["supported", "ambiguous", "conflicting", "missing", "unsupported"]
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    reasoning_summary: str = Field(default="", max_length=600)
    ambiguity: str | None = None
    conflicts: list[str] = Field(default_factory=list)
    missing_dependencies: list[str] = Field(default_factory=list)
    # V3: Qwen classifies applicability during fact resolution. Deterministic
    # code EXCLUDES "alternative"/"superseded" facts from the Contract model and
    # downstream calculations; it never decides this label itself.
    applicability: Literal["applicable", "alternative", "superseded", "unknown"] = "unknown"
    authority_note: str = Field(default="", max_length=400)


class CandidateBatch(StrictModel):
    candidates: list[FactCandidate] = Field(default_factory=list)


class GroundingDecision(StrictModel):
    candidate_index: int = Field(ge=0)
    supported: bool
    explanation: str = Field(max_length=400)


class GroundingBatch(StrictModel):
    decisions: list[GroundingDecision]


class VisionObservation(StrictModel):
    # Visual output is deliberately kept separate from textual evidence.  The
    # structured fields make it harder for a VLM to blur visible text with inference.
    description: str
    visible_text: list[str] = Field(default_factory=list)
    contract_signals: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class SectionUnderstanding(StrictModel):
    """Provisional per-page-batch reading used for VISUAL COMPUTE only.

    Never establishes contract-global semantic meaning; the Global stage does.
    """
    section_index: int
    pages: list[int] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)
    option_clusters: list[OptionCluster] = Field(default_factory=list)
    numbers: list[NumberRole] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    block_ids: list[str] = Field(default_factory=list)


class GlobalContractUnderstanding(StrictModel):
    """The single authoritative contract-global reasoning stage output."""
    document_type: str | None = None
    purpose: str | None = None
    parties_roles: list[str] = Field(default_factory=list)
    authority_order: list[str] = Field(default_factory=list)
    selections_summary: list[str] = Field(default_factory=list)
    key_clauses: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class ApplicabilityDecision(StrictModel):
    scope: Literal["option", "price", "number", "document", "table_column", "clause"]
    decision: Literal[
        "selected", "not_selected", "applicable", "alternative", "superseded",
        "authoritative", "secondary", "contract_number", "order_number",
        "reference", "customer_number", "other",
    ]
    target: str
    reason: str = Field(default="", max_length=400)
    block_ids: list[str] = Field(default_factory=list)


class ApplicabilityBatch(StrictModel):
    """Cross-clause reconciliation of selections, alternatives, number roles and
    document/attachment authority. Qwen decides; deterministic code applies."""
    decisions: list[ApplicabilityDecision] = Field(default_factory=list)
