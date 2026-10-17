"""Umsetzung einer Vertragsentscheidung: konkrete Schritte je Entscheidung.

Jeder Schritt sagt, was zu tun ist, bis wann und wo es erledigt wird. Erledigt ist
ein Schritt, wenn die gepflegten Vertragsdaten es zeigen (z. B. Status „Gekündigt“,
neues Vertragsende, Dokument nach der Entscheidung) oder eine Person ihn abhakt.
Pure Funktion ohne DB und ohne verstecktes „heute“.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

TERMINATION_DOCUMENT_TYPES = frozenset({"kuendigung", "kuendigungsbestaetigung", "aufhebung"})

TERM_TARGET = {"tab": "register", "section": "term"}
STATUS_TARGET = {"tab": "overview", "section": "status"}
ENTRIES_TARGET = {"tab": "finance", "section": "entries"}
ATTACHMENTS_TARGET = {"tab": "documents", "subtab": "attachments"}
# Kein Ort in der Akte: die Entscheidung selbst ändern (Frontend öffnet „Entscheidung ändern“).
CHANGE_DECISION = {"action": "change_decision"}


@dataclass(frozen=True)
class StepFacts:
    decision: str
    decided_on: date
    # Vertragsende, als entschieden wurde (sonst Wirksamkeit der Entscheidung).
    baseline_end: Optional[date]
    term_model: Optional[str]
    business_status: str
    cancel_by: Optional[date]
    current_end: Optional[date]
    partner: Optional[str]
    # Ausgaben-Eintrag deckt einen Tag nach `baseline_end` ab (bzw. ist offen).
    priced_after_baseline: bool = False
    # Ausgaben-Eintrag nach der Entscheidung angelegt oder geändert.
    entries_changed_since: bool = False
    # Dokumentarten der Dokumente, die nach der Entscheidung abgelegt wurden.
    documents_since: tuple[Optional[str], ...] = ()
    # Offene Erinnerung der Entscheidung (Fälligkeit), sonst None.
    reminder_due: Optional[date] = None
    # Von Personen abgehakt: key -> {"by": Name, "at": ISO-Zeitpunkt}.
    manual: dict[str, dict] = field(default_factory=dict)


def _de(day: Optional[date]) -> str:
    return day.strftime("%d.%m.%Y") if day else "–"


def _step(key: str, title: str, detail: str, *, due: Optional[date], auto: bool, target: Optional[dict], facts: StepFacts) -> dict:
    manual = facts.manual.get(key)
    return {
        "key": key,
        "title": title,
        "detail": detail,
        "due": due.isoformat() if due else None,
        "done": auto or manual is not None,
        # Woher „erledigt“ kommt: aus den Vertragsdaten erkannt oder von einer Person abgehakt.
        "done_how": "auto" if auto else ("manual" if manual is not None else None),
        "done_by": manual.get("by") if manual and not auto else None,
        "done_at": manual.get("at") if manual and not auto else None,
        "target": target,
    }


def decision_steps(facts: StepFacts) -> list[dict]:
    partner = facts.partner or "dem Vertragspartner"
    baseline = facts.baseline_end
    extended = bool(baseline and facts.current_end and facts.current_end > baseline)
    documents = facts.documents_since
    if facts.decision == "renew":
        steps = []
        if facts.term_model == "auto_renewal":
            steps.append(_step(
                "no_termination", "Keine Kündigung versenden",
                f"Der Vertrag verlängert sich automatisch, wenn bis {_de(facts.cancel_by)} nicht gekündigt wird.",
                due=facts.cancel_by, auto=extended, target=None, facts=facts,
            ))
        else:
            steps.append(_step(
                "agree", f"Verlängerung mit {partner} vereinbaren",
                "Angebot einholen, Konditionen abstimmen und den Anschlussvertrag unterschreiben.",
                due=facts.cancel_by or baseline, auto=extended, target=None, facts=facts,
            ))
        steps.append(_step(
            "term", "Neue Laufzeit eintragen",
            "Vertragsende in den Vertragsdaten auf den neuen Zeitraum setzen – erst dann laufen Fristen und Erinnerungen weiter."
            if facts.term_model != "auto_renewal" else "Nach der Verlängerung prüfen, ob das neue Vertragsende stimmt.",
            due=baseline, auto=extended, target=TERM_TARGET, facts=facts,
        ))
        steps.append(_step(
            "prices", "Kosten für den neuen Zeitraum erfassen",
            f"Finanzeintrag ab {_de(baseline + timedelta(days=1)) if baseline else 'dem neuen Zeitraum'} anlegen oder „Preis ändern ab …“ nutzen.",
            due=baseline, auto=facts.priced_after_baseline, target=ENTRIES_TARGET, facts=facts,
        ))
        if facts.term_model != "auto_renewal":
            steps.append(_step(
                "document", "Verlängerungsvereinbarung ablegen",
                "Nachtrag oder neuen Vertrag unter Dokumente → Anlagen hochladen.",
                due=baseline, auto=bool(documents), target=ATTACHMENTS_TARGET, facts=facts,
            ))
        return steps
    if facts.decision == "renegotiate":
        talk_due = facts.cancel_by - timedelta(days=30) if facts.cancel_by else None
        return [
            _step("talk", f"Gespräch mit {partner} führen",
                  "Ziele festlegen (Preis, Leistungen, Laufzeit) und ein Angebot anfordern.",
                  due=talk_due, auto=facts.entries_changed_since or bool(documents), target=None, facts=facts),
            _step("terms", "Neue Konditionen erfassen",
                  "Neue Preise als Finanzeintrag, eine geänderte Laufzeit in den Vertragsdaten.",
                  due=facts.cancel_by, auto=facts.entries_changed_since or extended, target=ENTRIES_TARGET, facts=facts),
            _step("document", "Nachtrag ablegen",
                  "Die unterschriebene Vereinbarung unter Dokumente → Anlagen hochladen.",
                  due=facts.cancel_by, auto=bool(documents), target=ATTACHMENTS_TARGET, facts=facts),
            _step("result", "Ergebnis festhalten",
                  "Steht das Ergebnis fest, die Entscheidung auf „Verlängern“ oder „Kündigen“ ändern.",
                  due=facts.cancel_by, auto=False, target=CHANGE_DECISION, facts=facts),
        ]
    if facts.decision == "terminate":
        terminated = facts.business_status in ("gekuendigt", "beendet")
        confirmed = any(kind in TERMINATION_DOCUMENT_TYPES for kind in documents)
        return [
            _step("send", f"Kündigung an {partner} senden",
                  f"Schriftlich und nachweisbar zugestellt – spätestens bis {_de(facts.cancel_by)}." if facts.cancel_by else "Schriftlich und nachweisbar zustellen.",
                  due=facts.cancel_by, auto=terminated or confirmed, target=None, facts=facts),
            _step("status", "Status auf „Gekündigt“ setzen",
                  "Mit Kündigungsdatum und Wirksamkeit – dann endet die Überwachung zum richtigen Tag.",
                  due=facts.cancel_by, auto=terminated, target=STATUS_TARGET, facts=facts),
            _step("confirmation", "Kündigungsbestätigung ablegen",
                  "Bestätigung des Vertragspartners unter Dokumente → Anlagen hochladen (Art „Kündigungsbestätigung“).",
                  due=None, auto=confirmed, target=ATTACHMENTS_TARGET, facts=facts),
            _step("followup", "Anschluss klären",
                  f"Ersatzvertrag, Geräterückgabe oder Datenlöschung bis zum Vertragsende ({_de(facts.current_end)}) planen.",
                  due=facts.current_end, auto=False, target=None, facts=facts),
        ]
    # Beobachten
    return [
        _step("watch", "Wiedervorlage festlegen",
              f"Erinnerung am {_de(facts.reminder_due)}." if facts.reminder_due else "Mit „Entscheidung ändern“ eine Erinnerung setzen, damit der Vertrag nicht aus dem Blick gerät.",
              due=None, auto=facts.reminder_due is not None, target=None if facts.reminder_due else CHANGE_DECISION, facts=facts),
        _step("decide", "Erneut entscheiden",
              f"Spätestens bis {_de(facts.cancel_by)}: verlängern, neu verhandeln oder kündigen." if facts.cancel_by else "Verlängern, neu verhandeln oder kündigen.",
              due=facts.reminder_due or facts.cancel_by, auto=False, target=CHANGE_DECISION, facts=facts),
    ]


STEP_KEYS = {
    "renew": {"no_termination", "agree", "term", "prices", "document"},
    "renegotiate": {"talk", "terms", "document", "result"},
    "terminate": {"send", "status", "confirmation", "followup"},
    "monitor": {"watch", "decide"},
}


def next_step(steps: list[dict]) -> Optional[dict]:
    """Der erste offene Schritt (Reihenfolge = empfohlene Reihenfolge)."""
    return next((step for step in steps if not step["done"]), None)
