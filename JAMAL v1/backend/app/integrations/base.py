"""Provider-neutral connector contract for MedFlux integrations.

Concrete DMS/ERP/CMMS connectors must implement this interface and keep secrets
outside source control. The core product only depends on this stable boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ConnectorHealth:
    name: str
    configured: bool
    reachable: bool
    detail: str | None = None


@dataclass(frozen=True)
class ExternalDocument:
    external_id: str
    filename: str
    media_type: str | None
    content: bytes
    metadata: dict


class Connector(Protocol):
    name: str

    def health(self) -> ConnectorHealth: ...

    def pull_documents(self, *, cursor: str | None = None, limit: int = 100) -> tuple[list[ExternalDocument], str | None]: ...

    def push_event(self, event_type: str, payload: dict) -> None: ...


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, Connector] = {}

    def register(self, connector: Connector) -> None:
        if connector.name in self._connectors:
            raise ValueError(f"Connector already registered: {connector.name}")
        self._connectors[connector.name] = connector

    def get(self, name: str) -> Connector:
        try:
            return self._connectors[name]
        except KeyError as exc:
            raise KeyError(f"Unknown connector: {name}") from exc

    def health(self) -> list[ConnectorHealth]:
        return [connector.health() for connector in self._connectors.values()]


registry = ConnectorRegistry()
