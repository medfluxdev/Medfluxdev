"""Gemeinsamer Test-Harness für die STEP-8B-Semantik-Gruppen-Pipeline.

Der `StructuredContractExtractor.extract` macht pro Chunk EINEN KI-Aufruf je
Feldgruppe (identity_equipment, dates_termination, costs_payment, services_sla)
plus ggf. einen Verifier-Aufruf. Dieser Helper baut daraus einen httpx-Handler,
der anhand des System-Prompts (Gruppen-Marker) bzw. des Verifier-Prompts die
passende Antwort liefert – ohne externe KI.
"""

from __future__ import annotations

import json
from typing import Callable, Optional

from app.ai.groups.verifier import SENSITIVE_FIELDS, VERIFIER_SYSTEM_PROMPT

GROUP_MARKERS = {
    "Identität & Geräte": "identity_equipment",
    "Laufzeit & Kündigung": "dates_termination",
    "Kosten & Zahlung": "costs_payment",
    "Leistungen & Service-Level": "services_sla",
}


def chat_reply(req, content: str):
    return __import__("httpx").Response(
        200, json={"message": {"role": "assistant", "content": content}}
    )


def extract_groups(contract: dict) -> dict:
    """Zerlegt ein vollständiges Contract-JSON in die Feldgruppen-Antworten."""
    return {
        "identity_equipment": {
            "identity": contract.get("identity", {}),
            "equipment": contract.get("equipment", []),
        },
        "dates_termination": {
            "dates": contract.get("dates", {}),
            "termination": contract.get("termination", {}),
        },
        "costs_payment": {
            "costs": contract.get("costs", {}),
            "payment": contract.get("payment", {}),
        },
        "services_sla": {
            "services": contract.get("services", {}),
            "sla": contract.get("sla", {}),
        },
    }


def verifier_reply(decisions: Optional[list[dict]] = None, fields=None) -> dict:
    """Baut eine Verifier-Antwort. Standard: alle sensiblen Felder supported."""
    if decisions is None:
        fields = fields or SENSITIVE_FIELDS
        decisions = [{"field": f, "supported": True, "reason": "belegt"} for f in fields]
    return {"decisions": decisions}


def build_handler(
    contract: dict,
    *,
    verifier_decisions: Optional[list[dict]] = None,
    verifier_fields: Optional[list[str]] = None,
    none_groups: Optional[set] = None,
):
    """Baut einen httpx-Handler für die Gruppen- + Verifier-Aufrufe.

    `contract`: vollständiges Contract-JSON, das in Gruppen zerlegt wird.
    `none_groups`: Gruppen, die einen leeren/fehlgeschlagenen Chunk simulieren.
    """
    groups = extract_groups(contract)
    call_count = 0

    def handler(req):
        nonlocal call_count
        call_count += 1
        payload = json.loads(req.content)
        system = payload["messages"][0]["content"]

        if VERIFIER_SYSTEM_PROMPT.strip()[:60] in system:
            return chat_reply(req, json.dumps(
                verifier_reply(verifier_decisions, verifier_fields), ensure_ascii=False))

        for marker, group in GROUP_MARKERS.items():
            if marker in system:
                if none_groups and group in none_groups:
                    return chat_reply(req, json.dumps(
                        {k: ([] if isinstance(groups[group][k], list) else {})
                         for k in groups[group]}, ensure_ascii=False))
                return chat_reply(req, json.dumps(groups[group], ensure_ascii=False))
        return chat_reply(req, "{}")

    handler.call_count = call_count  # noqa: B009 - pragmatisch gesetzt
    return handler


def make_failed_handler(error) -> Callable:
    def handler(req):
        raise error
    return handler
