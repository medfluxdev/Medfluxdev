"""Entscheidungen der Feldprüfung: prüfen, was eine Aktion bedeutet, bevor etwas gespeichert wird.

Reiner Code ohne DB. Die Route führt das Ergebnis aus (Faktprüfung über denselben Weg wie die Karten, dazu ein
Ereignis im Protokoll mit den verworfenen Alternativen).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.contracts.review.events import EXCLUSION_REASONS
from app.contracts.review.field_review import display, normalize
from app.contracts.review.service import ReviewConflict, ReviewError

DECISIONS = ("keep", "accept", "manual", "defer", "not_in_document")
EVIDENCE_ACTIONS = ("primary", "exclude", "restore")
FINDING_DECISIONS = ("link", "note", "dismiss", "restore")


@dataclass
class DecisionPlan:
    #: confirmed | corrected | None (nur Ereignis, z. B. Zurückstellen)
    fact_action: Optional[str]
    corrected_value: Optional[object]
    note: Optional[str]
    event_kind: str
    #: Wert vor und nach der Entscheidung (Anzeige) – leer, wenn sich nichts ändert
    changes_value: bool
    chosen: Optional[str]
    alternatives: list[dict]
    previous: Optional[str]


def check_version(field: dict, expected: Optional[str]) -> None:
    """Hat inzwischen jemand anders an diesem Feld etwas geändert? Dann nichts überschreiben.

    `None` heißt „das Feld war beim Laden noch unberührt“ – die Route ruft die Prüfung nur auf, wenn der Client den
    Stand überhaupt mitgeschickt hat.
    """
    if (expected or None) != (field.get("version") or None):
        raise ReviewConflict(
            "Das Feld wurde inzwischen geändert (Entscheidung, Nachweis oder Wert). Bitte neu laden und erneut entscheiden."
        )


def _alternatives(field: dict, chosen_key: Optional[str]) -> list[dict]:
    return [
        {
            "display": item["display"],
            "sources": [source["label"] for source in item["sources"]],
            "evidence_ids": item["evidence_ids"],
            "run_number": item.get("run_number"),
        }
        for item in field["candidates"] if item["key"] != chosen_key
    ]


def plan_decision(
    field: dict, decision: str, *, candidate_key: Optional[str] = None, value: Optional[str] = None,
    note: Optional[str] = None, confirm_change: bool = False,
) -> DecisionPlan:
    if decision not in DECISIONS:
        raise ReviewError("Unbekannte Entscheidung.")
    if field["kind"] == "calculated":
        raise ReviewError("Berechnete Werte werden nicht einzeln bestätigt – sie folgen den Angaben, aus denen sie entstehen.")
    previous = field["current"]

    if decision == "defer":
        if not field["decision_needed"]:
            raise ReviewError("Zu dieser Angabe ist nichts offen, das zurückgestellt werden könnte.")
        return DecisionPlan(None, None, note, "deferred", False, None, [], previous)

    if decision == "not_in_document":
        if field["present"]:
            raise ReviewError("Für diese Angabe liegt ein Wert vor. Bitte bestätigen oder korrigieren.")
        return DecisionPlan(None, None, note, "not_in_document", False, None, [], None)

    if decision == "manual":
        text = " ".join((value or "").split())
        if not text:
            raise ReviewError("Bitte einen Wert angeben.")
        changed = normalize(text) != normalize(previous)
        return DecisionPlan(
            "corrected", text, (note or "").strip() or "Von Hand eingetragen.", "decision", changed, text,
            _alternatives(field, normalize(text)), previous,
        )

    if decision == "keep":
        if not field["present"]:
            raise ReviewError("Es gibt keinen gespeicherten Wert, der beibehalten werden könnte.")
        return DecisionPlan(
            "confirmed", None, (note or "").strip() or None, "decision", False, previous,
            _alternatives(field, normalize(previous)), previous,
        )

    # accept: ein Kandidat wird gewählt
    candidate = next((item for item in field["candidates"] if item["key"] == candidate_key), None)
    if candidate is None:
        raise ReviewError("Der gewählte Wert steht nicht mehr zur Auswahl. Bitte neu laden.")
    if candidate["is_current"]:
        return DecisionPlan(
            "confirmed", None, (note or "").strip() or None, "decision", False, candidate["display"],
            _alternatives(field, candidate["key"]), previous,
        )
    if candidate.get("proposal_id"):
        raise ReviewError("Dieser Wert stammt aus einer erneuten Analyse. Bitte über die Analyse übernehmen.")
    if not confirm_change:
        raise ReviewError(
            f"Die Auswahl ändert den gespeicherten Wert von „{previous or 'leer'}“ zu „{candidate['display']}“. "
            "Bitte die Änderung ausdrücklich bestätigen."
        )
    labels = ", ".join(source["label"] for source in candidate["sources"])
    return DecisionPlan(
        "corrected", candidate["value"] if isinstance(candidate["value"], str) else candidate["display"],
        (note or "").strip() or f"Wert gewählt ({labels}).", "decision", True, candidate["display"],
        _alternatives(field, candidate["key"]), previous,
    )


def plan_evidence(field: dict, evidence_id: str, action: str, reason: Optional[str], note: Optional[str]) -> tuple[str, dict, Optional[str]]:
    """-> (Ereignisart, Nutzdaten, Notiz)."""
    if action not in EVIDENCE_ACTIONS:
        raise ReviewError("Unbekannte Nachweis-Aktion.")
    entry = next((item for item in field["evidence"] if item["evidence_id"] == evidence_id), None)
    if entry is None:
        raise ReviewError("Dieser Nachweis gehört nicht zu dieser Angabe.")
    if action == "primary":
        if entry["excluded"]:
            raise ReviewError("Ein ausgeschlossener Nachweis kann nicht Hauptnachweis sein. Bitte zuerst wiederherstellen.")
        return "primary_selected", {}, None
    if action == "restore":
        if not entry["excluded"]:
            raise ReviewError("Dieser Nachweis ist nicht ausgeschlossen.")
        return "evidence_restored", {}, None
    if entry["excluded"]:
        raise ReviewError("Dieser Nachweis ist bereits ausgeschlossen.")
    if reason not in EXCLUSION_REASONS:
        raise ReviewError("Bitte einen Grund für den Ausschluss wählen.")
    if reason == "other" and not (note or "").strip():
        raise ReviewError("Bitte den Grund kurz beschreiben.")
    return "evidence_excluded", {"reason": reason, "value_unchanged": True}, (note or "").strip() or None


def plan_finding(finding: dict, fields: list[dict], decision: str, target: Optional[str], note: Optional[str]) -> tuple[str, dict, Optional[str]]:
    if decision not in FINDING_DECISIONS:
        raise ReviewError("Unbekannte Entscheidung zur Information.")
    if decision == "restore":
        if finding["decision"] is None:
            raise ReviewError("Diese Information ist nicht ausgeblendet.")
        return "finding_restored", {}, None
    if finding["decision"] is not None:
        raise ReviewError("Zu dieser Information wurde bereits entschieden. Zum Ändern bitte zuerst wiederherstellen.")
    if decision == "dismiss":
        return "finding_dismissed", {}, (note or "").strip() or None
    if decision == "link":
        field = next((item for item in fields if item["fact_key"] == target and item["kind"] == "extracted"), None)
        if field is None:
            raise ReviewError("Bitte ein Feld wählen, dem die Information als Kandidat zugeordnet wird.")
        return "finding_linked", {"target_fact_key": field["fact_key"], "target_label": field["label"]}, None
    return "finding_note", {}, (note or "").strip() or None


def finding_note_text(finding: dict) -> str:
    """Text der Notiz zu einer Weiteren Information – mit Quelle (Seite, Wortlaut)."""
    page = f"Seite {finding['page']}" if finding.get("page") else "Dokument"
    quote = display(finding.get("snippet")) or ""
    return f"Aus dem Dokument ({page}): „{quote}“" + (f" – {finding['label']}" if finding.get("label") else "")
