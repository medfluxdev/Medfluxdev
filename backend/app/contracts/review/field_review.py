"""Feldprüfung: ein Lesemodell für Karten und geführte Prüfung.

Ein offizielles Feld → ein oder mehrere Kandidatenwerte → je Kandidat ein oder mehrere Nachweise.

Quellen (nichts wird erfunden, alles kommt aus vorhandenen Daten):
- der aktuell gespeicherte Wert (Faktprüfung `fact_review`, sonst der Wert aus dem Dokument),
- der Wert der Extraktion samt aller Belege (gleiche Werte nach Normalisierung = ein Kandidat, die Belege
  bleiben getrennt erhalten),
- offene Vorschläge einer erneuten Analyse (`contract_reextraction_proposal`),
- Widersprüche der Berechnung (z. B. Vertragsende laut Dokument ↔ aus Beginn + Laufzeit),
- Weitere Informationen aus dem Dokument, die eine Person einem Feld als Kandidat zugeordnet hat.

Werte mit unterschiedlicher Bedeutung werden nie zusammengelegt: Kandidaten gelten immer nur innerhalb eines
Felds (Vertragsende ≠ Gewährleistungsende). Neuere Dokumente oder höhere KI-Sicherheit entscheiden nichts.

Wann eine Prüfung wieder nötig wird (und nur dann):
1. Der Wert im Dokument ist ein anderer als der bestätigte (nach Normalisierung),
2. eine neue Analyse schlägt einen anderen Wert vor oder
3. eine Person öffnet die Angabe ausdrücklich wieder.
Zeit, KI-Sicherheit oder bloßes Neuladen lösen nichts aus. Berechnete Werte verlangen nie eine eigene Bestätigung.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.review.events import EXCLUSION_REASONS, ReviewEvents, load_events
from app.contracts.review.field_spec import (
    CARD_LABELS,
    CONTACT_FINDINGS,
    TIER_ESSENTIAL,
    TIER_LABELS,
    TIERS,
    inputs_of,
    why_for,
)
from app.contracts.review.material import EVIDENCE_FACT_PREFIX, MATERIAL_FACTS, evidence_base
from app.database.models import ContractReextraction, ContractReextractionProposal, ContractReviewEvent

REVIEWED = ("confirmed", "corrected")
DONE_STATES = ("confirmed", "corrected", "auto_accepted", "derived", "voided")
_CARD_ORDER = {key: index for index, key in enumerate(CARD_LABELS)}
_FACT_ORDER = {key: index for index, (key, _label, _reader) in enumerate(MATERIAL_FACTS)}

# Funde, die Kosten oder Fristen berühren können: zur Einschätzung vorgemerkt, nie als Warnung gezählt.
_CONSEQUENTIAL = (
    "costs.", "termination.", "payment.", "dates.end", "dates.minimum",
)


# ---------------------------------------------------------------------------
# Normalisierung (Gleichheit von Werten)
# ---------------------------------------------------------------------------

_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ].*)?$")
_DE_DATE = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_PUNCT = re.compile(r"[\s.;:,]+$")

_BOOL_WORDS = {"ja": "ja", "true": "ja", "nein": "nein", "false": "nein"}


def display(value: Any) -> Optional[str]:
    """Anzeigetext eines Werts; None = leer."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "Ja" if value else "Nein"
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, (list, tuple)):
        parts = [display(item) for item in value]
        return "; ".join(part for part in parts if part) or None
    if isinstance(value, dict):
        for key in ("value", "display", "text"):
            if key in value:
                return display(value[key])
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    match = _ISO_DATE.match(text)
    if match:
        return f"{match.group(3)}.{match.group(2)}.{match.group(1)}"
    return text


def _canon_number(token: str) -> str:
    """„1.200,50“ / „1200.50“ -> „1200.5“; „12,0“ -> „12“."""
    if "," in token and "." in token:
        token = token.replace(".", "").replace(",", ".")
    elif "," in token:
        token = token.replace(",", ".")
    elif token.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", token):
        token = token.replace(".", "")
    try:
        number = float(token)
    except ValueError:
        return token
    return str(int(number)) if number == int(number) else f"{number:.6f}".rstrip("0").rstrip(".")


def normalize(value: Any) -> str:
    """Vergleichsschlüssel: gleiche Bedeutung -> gleicher Schlüssel (Datum, Zahl, Ja/Nein, Text).

    Bewusst vorsichtig: nur Schreibweisen werden angeglichen (Datumsformat, Dezimalzeichen, Groß-/Kleinschreibung,
    Leerraum), nie Wörter oder Einheiten ersetzt – „12 Monate“ und „1 Jahr“ bleiben zwei Kandidaten.
    """
    text = display(value)
    if not text:
        return ""
    text = _PUNCT.sub("", text.strip())
    lowered = text.casefold()
    if lowered in _BOOL_WORDS:
        return _BOOL_WORDS[lowered]
    match = _DE_DATE.match(text)
    if match:
        return f"{int(match.group(3)):04d}-{int(match.group(2)):02d}-{int(match.group(1)):02d}"
    match = _ISO_DATE.match(text)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return _NUMBER.sub(lambda m: _canon_number(m.group(0)), lowered)


# ---------------------------------------------------------------------------
# Nachweise
# ---------------------------------------------------------------------------

def _source_state(ref: dict, available: bool) -> str:
    """Wie belastbar ist die Fundstelle? Nie „geprüft“, wenn Quelle fehlt oder Stelle ungeklärt ist."""
    if not available:
        return "unavailable"
    if ref.get("location") == "exact" and ref.get("text_verified"):
        return "verified"
    if ref.get("location") in ("approx", "page"):
        return "located"
    return "unresolved"


SOURCE_STATE_LABELS = {
    "verified": "Fundstelle bestätigt",
    "located": "Seite bekannt, Stelle ungefähr",
    "unresolved": "Fundstelle nicht aufgelöst",
    "unavailable": "Dokument nicht verfügbar",
}


def _evidence_entries(state: dict, evidence_index: dict[str, dict], documents: set[str], events: ReviewEvents) -> list[dict]:
    primary = events.primary.get(state["fact_key"])
    out = []
    for link in state.get("linked_evidence") or []:
        eid = link.get("evidence_id")
        ref = evidence_index.get(eid) or {}
        version = ref.get("document_version_id")
        available = bool(version and version in documents)
        exclusion = events.excluded.get(eid)
        out.append({
            "evidence_id": eid,
            "page": ref.get("page", link.get("page")),
            "snippet": ref.get("snippet", link.get("snippet")),
            "location": ref.get("location") or "none",
            "text_verified": bool(ref.get("text_verified")),
            "confidence": ref.get("confidence"),
            "extraction_method": ref.get("extraction_method"),
            "requires_review": bool(link.get("requires_review")),
            "document_version_id": version,
            "original_filename": ref.get("original_filename"),
            "document_available": available,
            "source_state": _source_state(ref, available),
            "source_state_label": SOURCE_STATE_LABELS[_source_state(ref, available)],
            "excluded": exclusion is not None,
            "exclusion_reason": exclusion.reason if exclusion else None,
            "exclusion_reason_label": EXCLUSION_REASONS.get(exclusion.reason, exclusion.reason) if exclusion else None,
            "exclusion_note": exclusion.note if exclusion else None,
            "excluded_by": exclusion.by if exclusion else None,
            "excluded_at": exclusion.at.isoformat() if exclusion else None,
            "primary": False,
        })
    # Hauptnachweis: gewählter, sonst der erste nicht ausgeschlossene (Reihenfolge der Belege).
    active = [entry for entry in out if not entry["excluded"]]
    chosen = next((entry for entry in active if entry["evidence_id"] == primary), None) or (active[0] if active else None)
    if chosen is not None:
        chosen["primary"] = True
    return out


# ---------------------------------------------------------------------------
# Kandidaten
# ---------------------------------------------------------------------------

class _Candidates:
    """Kandidaten eines Felds, gleiche Werte (nach Normalisierung) zusammengefasst."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = {}

    def add(
        self, value: Any, *, source: str, label: str, evidence_ids: Optional[list[str]] = None,
        inline: Optional[list[dict]] = None, detail: Optional[str] = None, current: bool = False,
        proposal_id: Optional[str] = None, run_number: Optional[int] = None, confidence: Optional[float] = None,
        raw: Any = None,
    ) -> Optional[dict]:
        shown = display(value)
        key = normalize(value)
        if not shown or not key:
            return None
        item = self.items.get(key)
        if item is None:
            item = self.items[key] = {
                "key": key, "display": shown, "value": raw if raw is not None else value if isinstance(value, (str, int, float, bool)) else shown,
                "is_current": False, "sources": [], "evidence_ids": [], "inline_evidence": [],
                "proposal_id": None, "run_number": None, "detail": None, "confidence": None,
            }
        item["is_current"] = item["is_current"] or current
        if source not in [entry["source"] for entry in item["sources"]]:
            item["sources"].append({"source": source, "label": label})
        for eid in evidence_ids or []:
            if eid and eid not in item["evidence_ids"]:
                item["evidence_ids"].append(eid)
        item["inline_evidence"].extend(inline or [])
        item["proposal_id"] = item["proposal_id"] or proposal_id
        item["run_number"] = item["run_number"] or run_number
        item["detail"] = item["detail"] or detail
        if confidence is not None:
            item["confidence"] = max(confidence, item["confidence"] or 0)
        return item


def _open_proposals(session: Session, contract_id) -> list[tuple[ContractReextractionProposal, ContractReextraction]]:
    return list(session.execute(
        select(ContractReextractionProposal, ContractReextraction)
        .join(ContractReextraction, ContractReextraction.id == ContractReextractionProposal.run_id)
        .where(
            ContractReextraction.contract_id == contract_id,
            ContractReextraction.status == "ready",
            ContractReextractionProposal.decision == "pending",
            ContractReextractionProposal.kind.in_(("new", "deviating")),
            ContractReextractionProposal.protected.is_(False),
        )
        .order_by(ContractReextraction.number.desc())
    ).all())


# Vorschlags-Schlüssel (Extraktion) -> Prüf-Angabe, deren Wert er direkt ersetzt.
_PROPOSAL_TARGET = {
    "identity.supplier": "identity.supplier",
    "identity.contract_title": "identity.contract_title",
    "identity.contract_type": "identity.contract_type",
    "identity.contract_number": "identity.contract_number",
    "dates.start_date": "dates.start_date",
    "dates.end_date": "dates.end_date",
    "dates.duration": "dates.duration",
    "dates.minimum_duration": "dates.minimum_duration",
    "termination.cancellation_period": "termination.cancellation_period",
    "termination.cancellation_condition": "termination.cancellation_condition",
    "termination.automatic_renewal": "termination.auto_renewal",
    "termination.renewal_period": "termination.renewal_period",
    "costs.monthly_cost": "costs.monthly_recurring",
    "costs.price_indexation": "costs.price_indexation",
    "payment.billing_interval": "payment.billing_interval",
    "sla.response_time": "sla.response_time",
    "sla.resolution_time": "sla.resolution_time",
    "sla.service_hours": "sla.service_hours",
    "sla.emergency_availability": "sla.emergency_availability",
    "sla.sla_notes": "sla.sla_notes",
}


def _build_candidates(
    state: dict, evidence: list[dict], conflicts: list[dict], proposals: list[tuple], linked_findings: list[dict],
) -> list[dict]:
    cands = _Candidates()
    active_ids = [entry["evidence_id"] for entry in evidence if not entry["excluded"]]
    all_ids = [entry["evidence_id"] for entry in evidence]
    confirmed_value = state["effective_value"] if state["state"] in REVIEWED else None
    # Der Wert aus dem Dokument: alle Belege, auch ausgeschlossene (sichtbar, aber nicht mitgezählt).
    cands.add(state.get("document_value"), source="document", label="Aus dem Dokument gelesen", evidence_ids=all_ids,
              confidence=state.get("ai_confidence"), current=confirmed_value is None)
    if confirmed_value is not None:
        cands.add(confirmed_value, source="stored", label="Gespeicherter Wert", evidence_ids=[], current=True)
    for conflict in conflicts:
        for option in conflict.get("options") or []:
            if option.get("value"):
                cands.add(option["value"], source="conflict", label=option.get("label_de") or "Berechnung",
                          detail=option.get("detail_de"),
                          evidence_ids=active_ids if option.get("key") == "document" else [])
    for proposal, run in proposals:
        cands.add(
            proposal.new_value if proposal.new_display is None else proposal.new_display,
            source="analysis", label=f"Analyse #{run.number}", proposal_id=str(proposal.id), run_number=run.number,
            inline=[{"page": row.get("page"), "quote": row.get("quote")} for row in (_detail(proposal.new_evidence))],
            confidence=proposal.confidence, raw=proposal.new_display,
        )
    for finding in linked_findings:
        cands.add(finding["snippet"], source="finding", label="Weitere Information aus dem Dokument",
                  detail=finding.get("label"), inline=[{"page": finding.get("page"), "quote": finding.get("snippet")}])
    items = list(cands.items.values())
    for item in items:
        # Wie viele nicht ausgeschlossene Belege stützen diesen Wert (Übereinstimmung, kein Mehrfachprüfen)?
        item["support_count"] = len([eid for eid in item["evidence_ids"] if eid in active_ids]) + len(item["inline_evidence"])
    # Reihenfolge: aktueller Wert zuerst, dann nach Herkunft (Dokument, Berechnung, Analyse, Fund).
    rank = {"stored": 0, "document": 1, "conflict": 2, "analysis": 3, "finding": 4}
    items.sort(key=lambda item: (not item["is_current"], min(rank.get(src["source"], 9) for src in item["sources"])))
    return items


def _detail(rows: list[dict]) -> list[dict]:
    from app.reextract import facts

    return facts.evidence_detail(rows or [])


# ---------------------------------------------------------------------------
# Feld-Lesemodell
# ---------------------------------------------------------------------------

STATUS_LABELS = {
    "decided": "Entschieden",
    "open": "Zu entscheiden",
    "conflict": "Widerspruch",
    "changed": "Neu zu prüfen",
    "deferred": "Zurückgestellt",
    "missing": "Nicht gefunden",
    "absent": "Nicht im Dokument",
    "derived": "Berechnet",
    "waiting": "Berechnet – Eingaben offen",
}
#: Zustände, in denen eine Person entscheiden muss.
DECISION_STATUSES = ("open", "conflict", "changed", "deferred", "missing")

_HISTORY_LABELS = {
    "decision": "Entscheidung", "deferred": "Zurückgestellt", "not_in_document": "Als „nicht im Dokument“ markiert",
    "primary_selected": "Hauptnachweis gewählt", "evidence_excluded": "Nachweis ausgeschlossen",
    "evidence_restored": "Nachweis wiederhergestellt",
}


def _history(state: dict, events: ReviewEvents, reviews: list[dict]) -> list[dict]:
    key = state["fact_key"]
    rows = [
        {
            "at": item.get("created_at"), "kind": item.get("action"), "label": item.get("action_label_de"),
            "by": item.get("reviewer_display_name"), "detail": item.get("note"),
            "from": item.get("previous_effective_value") if item.get("action") == "corrected" else None,
            "to": item.get("new_effective_value") if item.get("action") == "corrected" else None,
        }
        for item in reviews if item.get("fact_key") == key
    ]
    for event in events.history.get(key, []):
        payload = event.payload or {}
        detail = event.note
        if event.kind == "evidence_excluded":
            detail = f"{EXCLUSION_REASONS.get(payload.get('reason'), payload.get('reason') or '')}" + (f" – {event.note}" if event.note else "")
        rows.append({
            "at": event.created_at.isoformat(), "kind": event.kind, "label": _HISTORY_LABELS.get(event.kind, event.kind),
            "by": event.actor_name, "detail": detail,
            "from": None, "to": None,
            "alternatives": payload.get("alternatives") if event.kind == "decision" else None,
        })
    rows.sort(key=lambda row: row.get("at") or "", reverse=True)
    return rows


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


def _field_status(state: dict, tier: str, events: ReviewEvents, candidates: list[dict], has_proposal: bool) -> tuple[str, Optional[str]]:
    key = state["fact_key"]
    reviewed_at = _parse_time(state.get("reviewed_at"))
    present = state["present"]
    if not present and state["state"] not in REVIEWED:
        absent_at = events.absent.get(key)
        if absent_at is not None:
            return "absent", "Ausdrücklich als „nicht im Dokument“ festgehalten."
        return "missing", "Im Dokument nicht gefunden – Wert eintragen oder „nicht im Dokument“ festhalten."
    st = state["state"]
    if st in ("confirmed", "corrected", "auto_accepted", "voided", "derived"):
        if has_proposal:
            return "changed", "Eine neue Analyse schlägt einen anderen Wert vor."
        if st == "confirmed" and state.get("document_value") is not None:
            confirmed_original = normalize(state.get("original_value"))
            now_document = normalize(state.get("document_value"))
            if confirmed_original and now_document and confirmed_original != now_document:
                return "changed", "Der Wert im Dokument hat sich seit der Bestätigung geändert."
        return "decided", None
    deferred_at = events.deferred.get(key)
    if deferred_at is not None and (reviewed_at is None or deferred_at > reviewed_at):
        return "deferred", "Zurückgestellt – noch zu entscheiden."
    if state.get("reopen_note"):
        return "changed", state["reopen_note"]
    if len(candidates) > 1:
        return "conflict", "Mehrere Werte kommen in Frage – bitte einen wählen."
    return "open", None


def _findings(states: list[dict], events: ReviewEvents, evidence_index: dict[str, dict]) -> list[dict]:
    out = []
    for state in states:
        if not state.get("is_evidence_item"):
            continue
        key = state["fact_key"]
        base = key[len(EVIDENCE_FACT_PREFIX):]
        last = events.findings.get(key)
        decision = None
        if last is not None:
            decision = {"finding_linked": "linked", "finding_note": "note", "finding_dismissed": "dismissed"}.get(last.kind)
        first = (state.get("linked_evidence") or [{}])[0]
        ref = evidence_index.get(first.get("evidence_id")) or {}
        out.append({
            "finding_key": key,
            "label": state["label_de"].replace("Nachweis: ", ""),
            "source_field": base,
            "snippet": state.get("document_value") or first.get("snippet"),
            "page": ref.get("page", first.get("page")),
            "evidence_id": first.get("evidence_id"),
            "evidence_ids": [item.get("evidence_id") for item in state.get("linked_evidence") or []],
            "decision": decision,
            "target_fact_key": (last.payload or {}).get("target_fact_key") if decision == "linked" else None,
            "note": last.note if decision == "note" else None,
            "decided_by": last.actor_name if last is not None else None,
            "decided_at": last.created_at.isoformat() if last is not None else None,
            "contact": base in CONTACT_FINDINGS,
            # Zur Einschätzung vorgemerkt – keine Warnung, kein Zähler, keine Berechnung.
            "consequential": decision is None and any(base.startswith(prefix) for prefix in _CONSEQUENTIAL),
        })
    out.sort(key=lambda item: (item["decision"] is not None, item["label"]))
    return out


def build_field_review(session: Session, *, contract_id, data: dict, states: list[dict], events: Optional[ReviewEvents] = None) -> dict:
    """Lesemodell der Feldprüfung (siehe Modulbeschreibung)."""
    events = events or load_events(session, contract_id)
    evidence_index = {ref["evidence_id"]: ref for ref in data.get("evidence") or [] if ref.get("evidence_id")}
    documents = {doc.get("document_version_id") for doc in data.get("documents") or [] if doc.get("document_version_id")}
    reviews = data.get("fact_reviews") or []
    proposals = _open_proposals(session, contract_id)
    proposals_by_fact: dict[str, list[tuple]] = {}
    for proposal, run in proposals:
        target = _PROPOSAL_TARGET.get(proposal.field_key)
        if target:
            proposals_by_fact.setdefault(target, []).append((proposal, run))

    findings = _findings(states, events, evidence_index)
    linked_by_target: dict[str, list[dict]] = {}
    for finding in findings:
        if finding["decision"] == "linked" and finding["target_fact_key"]:
            linked_by_target.setdefault(finding["target_fact_key"], []).append(finding)

    conflicts_by_fact: dict[str, list[dict]] = {}
    for warning in data.get("warnings") or []:
        conflict = warning.get("conflict")
        if conflict and conflict.get("fact_key") and conflict.get("options") and not warning.get("review_resolved"):
            conflicts_by_fact.setdefault(conflict["fact_key"], []).append(conflict)

    sections = data.get("sections")
    by_key = {state["fact_key"]: state for state in states}
    fields: list[dict] = []
    for state in states:
        if state.get("is_evidence_item"):
            continue
        key = state["fact_key"]
        tier = state["tier"]
        evidence = _evidence_entries(state, evidence_index, documents, events)
        candidates = _build_candidates(
            state, evidence, conflicts_by_fact.get(key, []), proposals_by_fact.get(key, []), linked_by_target.get(key, []),
        )
        calculated = state["is_calculated"]
        if calculated:
            input_entries = [
                {"fact_key": name, "label": by_key[name]["label_de"], "present": by_key[name]["present"],
                 "decided": by_key[name]["state"] in DONE_STATES}
                for name in inputs_of(key) if name in by_key and by_key[name]["present"]
            ]
            settled = bool(input_entries) and all(item["decided"] for item in input_entries)
            status = "derived" if settled or state["state"] in REVIEWED else "waiting"
            reason = None if status == "derived" else "Wird aus noch nicht geklärten Angaben berechnet."
        else:
            input_entries = []
            now = normalize(state["effective_value"] if state["state"] in REVIEWED else state.get("document_value"))
            competing = any(normalize(item["display"]) != now for item in candidates if item["proposal_id"])
            status, reason = _field_status(state, tier, events, candidates, competing)
        needs = status in DECISION_STATUSES and (status != "missing" or tier == TIER_ESSENTIAL)
        # Nur wesentliche Lücken verlangen eine Entscheidung; fehlende optionale Angaben bleiben still.
        if status == "missing" and tier != TIER_ESSENTIAL:
            needs = False
        primary = next((entry for entry in evidence if entry["primary"]), None)
        fields.append({
            "fact_key": key,
            "label": state["label_de"],
            "card": state["card"],
            "card_label": CARD_LABELS.get(state["card"], state["card"]),
            "tier": tier,
            "tier_label": TIER_LABELS[tier],
            "why": why_for(key, sections),
            "kind": "calculated" if calculated else "extracted",
            "status": status,
            "status_label": STATUS_LABELS[status],
            "reason": reason,
            "decision_needed": needs,
            "present": state["present"],
            "current": display(state["effective_value"]) if state["state"] in REVIEWED else display(state.get("document_value")),
            "current_origin": "reviewed" if state["state"] in REVIEWED else "document" if state["present"] else None,
            "document_value": display(state.get("document_value")),
            "stored_value": state.get("stored_value"),
            "register_field": state.get("register_field"),
            "candidates": candidates,
            "evidence": evidence,
            "primary_evidence_id": primary["evidence_id"] if primary else None,
            "source_state": primary["source_state"] if primary else ("unresolved" if state["present"] else None),
            "source_state_label": SOURCE_STATE_LABELS[primary["source_state"]] if primary else None,
            "active_evidence_count": len([entry for entry in evidence if not entry["excluded"]]),
            "inputs": input_entries,
            "ai_confidence": state.get("ai_confidence"),
            "found_by_rule": state.get("found_by_rule"),
            "is_critical": state.get("is_critical"),
            "reviewed_at": state.get("reviewed_at"),
            "reviewer": state.get("reviewer_display_name"),
            "version": state.get("version"),
            "fact_state": state["state"],
            "history": _history(state, events, reviews),
        })
    fields.sort(key=lambda f: (TIERS.index(f["tier"]), _CARD_ORDER.get(f["card"], 9), _FACT_ORDER.get(f["fact_key"], 99)))

    stages = []
    counted = [f for f in fields if f["kind"] == "extracted" and f["fact_state"] != "voided" and (f["present"] or f["status"] in ("missing", "absent"))
               and not (f["status"] in ("missing", "absent") and f["tier"] != TIER_ESSENTIAL)]
    for tier in TIERS:
        group = [f for f in counted if f["tier"] == tier]
        stages.append({
            "tier": tier,
            "label": TIER_LABELS[tier],
            "total": len(group),
            "open": len([f for f in group if f["decision_needed"]]),
            "decided": len([f for f in group if not f["decision_needed"]]),
            "missing": len([f for f in group if f["status"] == "missing"]),
            "conflicts": len([f for f in group if f["status"] in ("conflict", "changed")]),
            "deferred": len([f for f in group if f["status"] == "deferred"]),
        })
    essential = stages[0]
    open_findings = [f for f in findings if f["decision"] is None]
    return {
        "stages": stages,
        "essential_complete": essential["total"] > 0 and essential["open"] == 0,
        "essential_open": essential["open"],
        "decisions_open": sum(stage["open"] for stage in stages),
        "fields": fields,
        "findings": findings,
        # Weitere Informationen sind kein Pflichtpunkt: eigene Zahl, nie Teil der Prüfzähler.
        "findings_open": len(open_findings),
        "findings_consequential": len([f for f in open_findings if f["consequential"]]),
        "exclusion_reasons": [{"key": key, "label": label} for key, label in EXCLUSION_REASONS.items()],
    }
