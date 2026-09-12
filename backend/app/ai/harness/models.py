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


class ContractMap(StrictModel):
    document_type: str | None = None
    purpose: str | None = None
    observations: list[Observation] = Field(default_factory=list)
    missing_material: list[str] = Field(default_factory=list)


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
