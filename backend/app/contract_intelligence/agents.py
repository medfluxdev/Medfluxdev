"""Agent contracts for specialized, evidence-first reasoning.

These are orchestration boundaries, not autonomous database writers. Every
agent returns typed proposals/facts; deterministic code validates and persists.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

TIn = TypeVar("TIn")
TOut = TypeVar("TOut")


class ContractAgent(Protocol[TIn, TOut]):
    name: str

    async def run(self, payload: TIn) -> TOut:
        ...
