"""Append-only audit graph primitives."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AuditNode(BaseModel):
    kind: str
    entity_id: Optional[UUID] = None
    label: str
    at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditEdge(BaseModel):
    source: str
    target: str
    relation: str


class AuditGraph(BaseModel):
    nodes: list[AuditNode] = Field(default_factory=list)
    edges: list[AuditEdge] = Field(default_factory=list)
