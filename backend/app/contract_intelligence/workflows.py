"""Workflow orchestration boundary.

MedFlux keeps workflows transport-neutral. An outbox event is persisted first;
Temporal/Camunda/NATS/Redis adapters can consume it later without changing
contract semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WorkflowCommand:
    event_type: str
    contract_id: str | None
    payload: dict[str, Any]


def commands_for_event(event_type: str, contract_id: str | None, payload: dict | None = None) -> list[WorkflowCommand]:
    payload = dict(payload or {})
    if event_type in {"contract.accepted", "contract.reanalyzed", "contract.amendment_added"}:
        return [
            WorkflowCommand("policy.evaluate", contract_id, payload),
            WorkflowCommand("obligations.refresh", contract_id, payload),
            WorkflowCommand("work_queue.refresh", contract_id, payload),
        ]
    if event_type == "invoice.received":
        return [WorkflowCommand("invoice.reconcile", contract_id, payload)]
    if event_type in {"obligation.due", "obligation.breached"}:
        return [WorkflowCommand("work_queue.refresh", contract_id, payload)]
    return []
