"""Erneute Erfassung aus dem Vertragsdokument: Analysen, Vorschlaege, Entscheidungen, Zuruecknahme.

Ablauf: `start` legt eine Analyse #N an (wartend) -> `drain` verarbeitet die
Warteschlange nacheinander (eine GPU, Advisory-Lock ueber alle Prozesse) und
speichert nur einen Kandidaten -> daraus werden Vorschlaege je Angabe (neu,
abweichend, nicht mehr gefunden, unveraendert) mit altem und neuem Wert
-> uebernommen wird nur, was eine Person entscheidet (`prepare_apply`), ueber den
normalen Akzeptanzweg. Jede Uebernahme haelt den alten Stand fest, sodass
`rollback_plan` einen frueheren Stand wiederherstellen kann.

Grundsatz: eine Analyse schreibt nie in die Vertragsdaten, nur Vorschlaege.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.contract import Contract as ExtractedContract
from app.core.config import settings
from app.database.models import Contract, ContractDocument, DocumentVersion, ProcessingRun
from app.database.models.reextraction import (
    REEXTRACTION_ACTIVE,
    ContractReextraction,
    ContractReextractionProposal,
)
from app.database.session import create_session, get_engine
from app.reextract import facts
from app.register.service import RegisterActor, load_extracted, log_activity

logger = logging.getLogger(__name__)

# Fester Schluessel fuer pg_advisory_lock: hoechstens eine erneute Erfassung gleichzeitig.
_LOCK_KEY = 0x4D46_5245  # "MFRE"
# Tests setzen SYNC = True und rufen drain() selbst auf.
SYNC = False

MODES = ("supplement", "sections", "full")
MODE_LABELS = {"supplement": "Ergänzen", "sections": "Bereich neu erfassen", "full": "Vollständig neu bewerten",
               "rollback": "Zurückgenommen"}
# Pruefaufwand je Nachweis fuer die Schaetzung "ca. M Min. Prüfung".
SECONDS_PER_EVIDENCE = 25
# Packs der Harness als Fortschrittsschritte.
PACK_LABELS = {"core": "Vertragsdaten & Fristen", "commercial": "Finanzen", "payment": "Finanzen (Zahlung)", "operations": "Leistungen & SLA"}
_KIND = {"new": "new", "changed": "deviating", "missing_again": "missing", "same": "unchanged"}
# Entscheidbare Vorschlaege (unveraendert ist nur zu bestaetigen).
OPEN_KINDS = ("new", "deviating", "missing")
# Von Hand gesetzte Werte, die "Manuell schuetzen" vor Vorschlaegen bewahrt.
_MANUAL_ORIGINS = frozenset({"manual", "ai_corrected", "imported_legacy"})
SAFE_CONFIDENCE = 0.95


class ReextractError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class RunCancelled(Exception):
    """Abbruch zwischen zwei Modellaufrufen (aus dem Fortschritts-Rueckruf)."""


def main_document_version(session: Session, contract: Contract) -> Optional[uuid.UUID]:
    row = session.scalars(
        select(ContractDocument.document_version_id)
        .where(
            ContractDocument.organization_id == contract.organization_id,
            ContractDocument.contract_id == contract.id,
            ContractDocument.role == "main",
        )
        .order_by(ContractDocument.created_at.desc())
    ).first()
    return row


def latest_run(session: Session, contract: Contract) -> Optional[ContractReextraction]:
    """Neueste Analyse (ohne Zuruecknahme-Eintraege)."""
    return session.scalars(
        select(ContractReextraction)
        .where(
            ContractReextraction.organization_id == contract.organization_id,
            ContractReextraction.contract_id == contract.id,
            ContractReextraction.mode != "rollback",
        )
        .order_by(ContractReextraction.number.desc())
    ).first()


def runs(session: Session, contract: Contract) -> list[ContractReextraction]:
    return list(session.scalars(
        select(ContractReextraction)
        .where(
            ContractReextraction.organization_id == contract.organization_id,
            ContractReextraction.contract_id == contract.id,
        )
        .order_by(ContractReextraction.number.desc())
    ))


def queue_position(session: Session, run: ContractReextraction) -> int:
    """Wie viele Laeufe vor diesem warten oder laufen (0 = ist dran bzw. laeuft)."""
    if run.status not in REEXTRACTION_ACTIVE:
        return 0
    return int(session.scalar(
        select(func.count()).select_from(ContractReextraction).where(
            ContractReextraction.status.in_(REEXTRACTION_ACTIVE),
            ContractReextraction.created_at < run.created_at,
        )
    ) or 0)


def missing_facts(session: Session, contract: Contract) -> list[str]:
    """Fakten, die fuer die fehlenden Vertragsdaten in Frage kommen ("Im Dokument suchen")."""
    from app.register.service import build_register

    actor = RegisterActor(organization_id=contract.organization_id, account_id=None, display_name=None, role="admin")
    data = build_register(session, contract, actor)
    keys = list(data.get("missing_for_valid") or []) + list((data.get("terms") or {}).get("missing") or [])
    out: list[str] = []
    for key in keys:
        for path in facts.facts_for_register_key(key):
            if path not in out:
                out.append(path)
    return out


def open_facts(session: Session, contract: Contract) -> list[str]:
    """Angaben ohne Wert in der akzeptierten Extraktion (Modus "Ergaenzen")."""
    accepted = load_extracted(session, contract.accepted_extraction_id) if contract.accepted_extraction_id else None
    return facts.empty_paths(accepted)


def evidence_count(session: Session, contract: Contract) -> int:
    """Nachweise der akzeptierten Extraktion (Umfang von "Vollstaendig neu bewerten")."""
    accepted = load_extracted(session, contract.accepted_extraction_id) if contract.accepted_extraction_id else None
    return len((accepted.analysis.harness or {}).get("evidence") or []) if accepted is not None else 0


def next_number(session: Session, contract: Contract) -> int:
    top = session.scalar(
        select(func.max(ContractReextraction.number)).where(
            ContractReextraction.organization_id == contract.organization_id,
            ContractReextraction.contract_id == contract.id,
        )
    )
    if top:
        return int(top) + 1
    # #1 ist die Erstanalyse beim Import (ohne eigene Zeile).
    return 2 if contract.accepted_extraction_id else 1


def start(
    session: Session,
    *,
    contract: Contract,
    actor: RegisterActor,
    mode: str,
    fields: Iterable[str],
    page_hint: Iterable[int],
    reread: bool,
    provider_id: Optional[str],
    model_id: Optional[str],
    sections: Iterable[str] = (),
    hint: Optional[str] = None,
    protect_manual: bool = True,
    reset_confirmations: bool = False,
) -> ContractReextraction:
    if contract.lifecycle_state != "active":
        raise ReextractError(409, "Dieser Vertrag kann nicht erneut erfasst werden.")
    # Ohne frühere KI-Analyse (z. B. von Hand erfasster Vertrag mit Dokument) ist die erste Erfassung
    # ein Lauf gegen eine leere Grundlage: alles Gefundene ist „neu“, übernommen wird nur Ausgewähltes.
    version_id = main_document_version(session, contract)
    if version_id is None:
        raise ReextractError(409, "Kein Vertragsdokument hinterlegt.")
    mode = "supplement" if mode == "missing_fields" else mode
    if mode not in MODES:
        raise ReextractError(422, "Unbekannter Modus.")
    wanted = [str(item) for item in fields]
    if any(item not in facts.LABELS for item in wanted):
        raise ReextractError(422, "Unbekannte Angaben ausgewählt.")
    chosen_sections = [str(item) for item in dict.fromkeys(sections)]
    if any(item not in facts.SECTIONS for item in chosen_sections):
        raise ReextractError(422, "Unbekannter Bereich.")
    if mode == "sections":
        if not chosen_sections:
            raise ReextractError(422, "Bitte mindestens einen Bereich wählen.")
        wanted = facts.paths_for_sections(chosen_sections)
    elif mode == "supplement":
        wanted = wanted or open_facts(session, contract)
        if not wanted:
            raise ReextractError(422, "Es gibt keine offenen Angaben zum Ergänzen.")
    else:
        wanted = []
    if reset_confirmations and mode != "full":
        raise ReextractError(422, "Bestätigungen lassen sich nur bei „Vollständig neu bewerten“ zurücksetzen.")
    pages = sorted({int(page) for page in page_hint if int(page) > 0})[:20]
    hint_text = " ".join(str(hint or "").split())[:500] or None

    # Ein neuer Lauf beendet einen noch offenen, fertigen Lauf (seine Entscheidungen bleiben).
    session.execute(
        update(ContractReextraction)
        .where(
            ContractReextraction.organization_id == contract.organization_id,
            ContractReextraction.contract_id == contract.id,
            ContractReextraction.status == "ready",
        )
        .values(status="discarded", finished_at=datetime.now(timezone.utc))
    )
    run = ContractReextraction(
        organization_id=contract.organization_id,
        contract_id=contract.id,
        document_version_id=version_id,
        number=next_number(session, contract),
        mode=mode,
        fields=wanted,
        sections=chosen_sections if mode == "sections" else [],
        page_hint=pages,
        hint=hint_text,
        protect_manual=bool(protect_manual),
        reset_confirmations=bool(reset_confirmations),
        reread_document=bool(reread),
        provider_id=provider_id,
        model_id=model_id,
        status="queued",
        base_extraction_id=contract.accepted_extraction_id,
        requested_by_account_id=actor.account_id,
        requested_by_name=actor.display_name,
    )
    session.add(run)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ReextractError(409, "Für diesen Vertrag läuft bereits eine erneute Erfassung.") from exc
    log_activity(session, actor, contract.id, "contract.reextraction_started", {
        "run_id": str(run.id), "number": run.number, "mode": mode, "sections": run.sections,
        "fields": run.fields if mode == "supplement" else [], "pages": pages, "hint": bool(hint_text),
        "protect_manual": run.protect_manual, "reset_confirmations": run.reset_confirmations,
        "reread": bool(reread), "model": model_id,
    })
    return run


def kick() -> None:
    """Startet die Abarbeitung der Warteschlange im Hintergrund (idempotent)."""
    if SYNC:
        return
    threading.Thread(target=drain, name="medflux-reextraction", daemon=True).start()


def drain(processing=None) -> int:
    """Arbeitet wartende Laeufe nacheinander ab; gibt die Anzahl zurueck.

    Ein Postgres-Advisory-Lock sorgt dafuer, dass auch bei mehreren Prozessen nur
    eine erneute Erfassung gleichzeitig das lokale Modell belegt.
    """
    done = 0
    engine = get_engine()
    with engine.connect() as lock_conn:
        if not lock_conn.execute(select(func.pg_try_advisory_lock(_LOCK_KEY))).scalar():
            return 0
        try:
            _fail_stale()
            while process_next(processing):
                done += 1
        finally:
            lock_conn.execute(select(func.pg_advisory_unlock(_LOCK_KEY)))
            lock_conn.commit()
    # Ein Lauf, der waehrend des Freigebens dazukam, wird nicht vergessen.
    if not SYNC and _has_queued():
        kick()
    return done


def _has_queued() -> bool:
    with create_session() as session:
        return session.scalar(
            select(func.count()).select_from(ContractReextraction).where(ContractReextraction.status == "queued")
        ) > 0


def _fail_stale() -> None:
    """Laeufe, deren Prozess beendet wurde, bleiben nicht ewig "laeuft"."""
    limit = datetime.now(timezone.utc) - timedelta(minutes=max(5, settings.document_processing_stale_minutes))
    with create_session() as session:
        session.execute(
            update(ContractReextraction)
            .where(ContractReextraction.status == "running", ContractReextraction.started_at < limit)
            .values(status="failed", finished_at=datetime.now(timezone.utc),
                    message="Die erneute Erfassung wurde unterbrochen. Bitte erneut starten.")
        )
        session.commit()


def _progress_writer(run_id: uuid.UUID):
    """Fortschritt je Pack speichern; bei "Abbrechen" die Analyse vor dem naechsten Pack beenden."""
    def report(step: int, steps: int, pack: str, found: int) -> None:
        with create_session() as session:
            run = session.get(ContractReextraction, run_id)
            if run is None:
                return
            run.progress = {"step": int(step), "steps": int(steps), "label": PACK_LABELS.get(pack, pack), "found": int(found)}
            cancelled = bool(run.cancel_requested)
            session.commit()
        if cancelled:
            raise RunCancelled()
    return report


def process_next(processing=None) -> bool:
    with create_session() as session:
        run = session.scalars(
            select(ContractReextraction)
            .where(ContractReextraction.status == "queued")
            .order_by(ContractReextraction.created_at.asc())
            .with_for_update(skip_locked=True)
        ).first()
        if run is None:
            return False
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        run.progress = {}
        run_id, organization_id, contract_id = run.id, run.organization_id, run.contract_id
        version_id, reread, model_id = run.document_version_id, run.reread_document, run.model_id
        focus_fields = list(run.fields or []) or None
        focus_pages = list(run.page_hint or []) or None
        hint = run.hint
        session.commit()

    if processing is None:
        from app.api.routes.documents import _processing_service as processing

    try:
        result = processing.extract_candidate(
            organization_id=organization_id,
            contract_id=contract_id,
            document_version_id=version_id,
            reread=reread,
            model_override=model_id,
            focus_fields=focus_fields,
            focus_pages=focus_pages,
            user_hint=hint,
            on_progress=_progress_writer(run_id),
        )
    except Exception:
        logger.exception("Re-extraction run %s failed", run_id)
        result = None

    with create_session() as session:
        run = session.get(ContractReextraction, run_id)
        run.finished_at = datetime.now(timezone.utc)
        if run.cancel_requested:
            run.status = "cancelled"
            run.message = "Abgebrochen."
        elif result is not None and result.status == "candidate" and result.extraction_id:
            run.candidate_extraction_id = uuid.UUID(result.extraction_id)
            run.status = "ready"
            try:
                build_proposals(session, run)
            except Exception:
                logger.exception("Re-extraction comparison failed for run %s", run_id)
                run.status = "failed"
                run.message = "Das Ergebnis konnte nicht verglichen werden."
            if run.status == "ready" and run.reset_confirmations:
                try:
                    reset_reviews(session, run)
                except Exception:
                    logger.exception("Resetting confirmations failed for run %s", run_id)
        else:
            run.status = "failed"
            run.message = ((result.message if result is not None else None)
                           or "Die erneute Erfassung ist fehlgeschlagen.")[:500]
        _notify(session, run)
        session.commit()
    return True


def _notify(session: Session, run: ContractReextraction) -> None:
    """Glocke: Ergebnis fuer die Person, die den Lauf gestartet hat."""
    if run.requested_by_account_id is None or run.status not in {"ready", "failed"}:
        return
    from app.database.models.deadlines import Notification

    contract = session.get(Contract, run.contract_id)
    name = (contract.short_description or contract.register_number or "Vertrag") if contract else "Vertrag"
    if run.status == "ready":
        found = open_count(run.summary)
        title = (f"Analyse #{run.number} fertig – {found} Vorschl{'ag' if found == 1 else 'äge'} prüfen" if found
                 else f"Analyse #{run.number} fertig – keine neuen Vorschläge")
    else:
        title = f"Analyse #{run.number} fehlgeschlagen"
    session.add(Notification(
        organization_id=run.organization_id,
        account_id=run.requested_by_account_id,
        kind="reextraction",
        title=title[:200],
        body=name[:500],
        contract_id=run.contract_id,
        dedupe_key=f"reextraction:{run.id}",
    ))


def open_count(summary: Optional[dict]) -> int:
    summary = summary or {}
    return sum(int(summary.get(kind, 0)) for kind in OPEN_KINDS)


# --- Vorschlaege ----------------------------------------------------------------------------


def _protected_facts(session: Session, contract: Contract) -> set[str]:
    """Angaben, deren Wert eine Person gesetzt hat (Vertragsdaten "Manuell" oder Korrektur in der Pruefung)."""
    from app.contracts.review.service import _latest_fact_reviews
    from app.database.models.register import ContractFieldProvenance

    out: set[str] = set()
    for key in session.scalars(
        select(ContractFieldProvenance.field_key).where(
            ContractFieldProvenance.contract_id == contract.id,
            ContractFieldProvenance.origin.in_(_MANUAL_ORIGINS),
        )
    ):
        out.update(facts.facts_for_register_key(key))
    corrected = {key for key, row in _latest_fact_reviews(session, contract.id).items() if row.action == "corrected"}
    for path in facts.all_paths():
        if path in corrected or any(fact in corrected for fact in facts.REVIEW_FACTS.get(path, ())[:1]):
            out.add(path)
    return out


def build_proposals(session: Session, run: ContractReextraction) -> list[ContractReextractionProposal]:
    """Vorschlaege aus dem Kandidaten (einmal je Lauf); Statistik in `run.summary`."""
    existing = proposals(session, run)
    if existing or run.candidate_extraction_id is None:
        return existing
    candidate = load_extracted(session, run.candidate_extraction_id)
    if candidate is None:
        return []
    accepted = load_extracted(session, run.base_extraction_id) if run.base_extraction_id else None
    contract = session.get(Contract, run.contract_id)
    protected = _protected_facts(session, contract) if run.protect_manual and contract is not None else set()
    applied = set(run.applied_keys or [])
    empty = ExtractedContract()
    out: list[ContractReextractionProposal] = []
    for row in facts.compare(accepted, candidate, only=run.fields or None):
        kind = _KIND[row.group]
        is_protected = row.key in protected and kind != "unchanged"
        new_evidence = facts.evidence_rows(candidate, row.key)
        proposal = ContractReextractionProposal(
            organization_id=run.organization_id,
            run_id=run.id,
            field_key=row.key,
            label=row.label,
            section=facts.section_of(row.key),
            kind="unchanged" if is_protected else kind,
            protected=is_protected,
            old_display=row.current,
            new_display=row.proposed,
            old_value=facts.dump_fact(facts.get_fact(accepted if accepted is not None else empty, row.key)),
            new_value=facts.dump_fact(facts.get_fact(candidate, row.key)),
            old_evidence=facts.evidence_rows(accepted, row.key),
            new_evidence=new_evidence,
            confidence=facts.confidence_of(new_evidence),
            # Vor der Umstellung uebernommene Angaben (Altlaeufe) gelten als uebernommen.
            decision="accepted" if row.key in applied else "pending",
        )
        session.add(proposal)
        out.append(proposal)
    session.flush()
    run.summary = stats(out)
    return out


def stats(items: Iterable[ContractReextractionProposal]) -> dict[str, int]:
    out = {"unchanged": 0, "new": 0, "deviating": 0, "missing": 0, "protected": 0, "accepted": 0, "decided": 0}
    for item in items:
        out[item.kind] += 1
        out["protected"] += int(item.protected)
        out["accepted"] += int(item.decision == "accepted")
        out["decided"] += int(item.decision != "pending" and item.kind in OPEN_KINDS)
    return out


def proposals(session: Session, run: ContractReextraction) -> list[ContractReextractionProposal]:
    return list(session.scalars(
        select(ContractReextractionProposal)
        .where(ContractReextractionProposal.run_id == run.id)
        .order_by(ContractReextractionProposal.created_at.asc(), ContractReextractionProposal.field_key.asc())
    ))


def proposal_payload(item: ContractReextractionProposal) -> dict:
    return {
        "id": str(item.id),
        "key": item.field_key,
        "label": item.label,
        "section": item.section,
        "kind": item.kind,
        "protected": item.protected,
        "current": item.old_display,
        "proposed": item.new_display,
        "confidence": item.confidence,
        "evidence": facts.evidence_detail(item.new_evidence or []),
        "register_keys": list(facts.REGISTER_KEYS.get(item.field_key, ())),
        "decision": item.decision,
        "decided_by_name": item.decided_by_name,
        "decided_at": item.decided_at.isoformat() if item.decided_at else None,
    }


def rows(session: Session, run: ContractReextraction) -> list[dict]:
    """Vorschlaege eines fertigen Laufs (Altlaeufe werden beim ersten Lesen nachgebaut)."""
    if run.status not in {"ready", "applied", "discarded"} or run.mode == "rollback":
        return []
    items = build_proposals(session, run)
    order = {"new": 0, "deviating": 1, "missing": 2, "unchanged": 3}
    return [proposal_payload(item) for item in sorted(items, key=lambda item: (order[item.kind], item.label))]


def run_payload(session: Session, run: Optional[ContractReextraction]) -> Optional[dict]:
    if run is None:
        return None
    return {
        "id": str(run.id),
        "number": run.number,
        "status": run.status,
        "mode": run.mode,
        "mode_label": MODE_LABELS.get(run.mode, run.mode),
        "sections": [{"key": key, "label": facts.SECTIONS[key][0]} for key in (run.sections or []) if key in facts.SECTIONS],
        "fields": [{"key": key, "label": facts.LABELS.get(key, key)} for key in (run.fields or [])] if run.mode == "supplement" else [],
        "page_hint": run.page_hint or [],
        "hint": run.hint,
        "protect_manual": run.protect_manual,
        "reset_confirmations": run.reset_confirmations,
        "reread_document": run.reread_document,
        "model_id": run.model_id,
        "progress": run.progress or {},
        "summary": run.summary or {},
        "applied_keys": run.applied_keys or [],
        "requested_by_name": run.requested_by_name,
        "message": run.message,
        "queue_position": queue_position(session, run),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "stale": bool(run.status == "ready" and run.base_extraction_id is not None
                      and _contract_extraction(session, run) != run.base_extraction_id),
    }


def _contract_extraction(session: Session, run: ContractReextraction):
    return session.scalar(select(Contract.accepted_extraction_id).where(Contract.id == run.contract_id))


def get_run(session: Session, contract: Contract, run_id: uuid.UUID, *, for_update: bool = False) -> ContractReextraction:
    stmt = select(ContractReextraction).where(
        ContractReextraction.id == run_id,
        ContractReextraction.organization_id == contract.organization_id,
        ContractReextraction.contract_id == contract.id,
    )
    if for_update:
        stmt = stmt.with_for_update()
    run = session.scalars(stmt).first()
    if run is None:
        raise ReextractError(404, "Erneute Erfassung nicht gefunden.")
    return run


# --- Entscheidungen -------------------------------------------------------------------------


def prepare_apply(session: Session, contract: Contract, run: ContractReextraction, keys: Iterable[str]):
    """Prueft die Auswahl und baut die zusammengefuehrte Extraktion."""
    if run.status != "ready":
        raise ReextractError(409, "Dieses Ergebnis kann nicht mehr übernommen werden.")
    if contract.accepted_extraction_id != run.base_extraction_id:
        raise ReextractError(409, "Die Vertragsdaten haben sich seit dem Start geändert. Bitte erneut erfassen.")
    selectable = {item.field_key for item in build_proposals(session, run)
                  if item.decision == "pending" and item.kind in {"new", "deviating"}}
    chosen = [key for key in dict.fromkeys(str(item) for item in keys)]
    if not chosen:
        raise ReextractError(422, "Bitte mindestens eine Angabe auswählen.")
    if any(key not in selectable for key in chosen):
        raise ReextractError(422, "Diese Angabe kann nicht übernommen werden.")
    accepted = load_extracted(session, run.base_extraction_id) if run.base_extraction_id else ExtractedContract()
    candidate = load_extracted(session, run.candidate_extraction_id)
    if accepted is None or candidate is None:
        raise ReextractError(409, "Das Ergebnis ist nicht mehr vollständig vorhanden.")
    return facts.merge(accepted, candidate, chosen, run_id=str(run.id)), chosen


def _decide(items: Iterable[ContractReextractionProposal], decision: str, actor: RegisterActor) -> None:
    now = datetime.now(timezone.utc)
    for item in items:
        item.decision = decision
        item.decided_at = now
        item.decided_by_account_id = actor.account_id
        item.decided_by_name = actor.display_name


def _settle(session: Session, run: ContractReextraction) -> None:
    """Sind alle entscheidbaren Vorschlaege entschieden, ist die Analyse abgeschlossen."""
    items = proposals(session, run)
    run.summary = stats(items)
    if any(item.decision == "pending" and item.kind in OPEN_KINDS for item in items):
        return
    run.status = "applied" if any(item.decision == "accepted" for item in items) else "discarded"
    run.finished_at = run.finished_at or datetime.now(timezone.utc)


def mark_applied(session: Session, actor: RegisterActor, run: ContractReextraction, keys: list[str]) -> None:
    """Nach der Uebernahme: Vorschlaege entschieden, Grundlage ist der neue Vertragsstand."""
    chosen = set(keys)
    _decide([item for item in proposals(session, run) if item.field_key in chosen], "accepted", actor)
    run.applied_keys = list(dict.fromkeys([*(run.applied_keys or []), *keys]))
    run.base_extraction_id = _contract_extraction(session, run)
    _settle(session, run)
    log_activity(session, actor, run.contract_id, "contract.reextraction_applied", {
        "run_id": str(run.id), "number": run.number,
        "fields": [{"key": key, "label": facts.LABELS.get(key, key)} for key in keys],
    })


def decide(session: Session, actor: RegisterActor, run: ContractReextraction, keys: Iterable[str], decision: str) -> int:
    """Behalten (kept_old), selbst erfassen (manual) oder ablehnen (rejected) – ohne Wertaenderung."""
    if decision not in {"kept_old", "manual", "rejected"}:
        raise ReextractError(422, "Unbekannte Entscheidung.")
    if run.status != "ready":
        raise ReextractError(409, "Dieses Ergebnis ist nicht mehr offen.")
    chosen = set(str(key) for key in keys)
    items = [item for item in proposals(session, run)
             if item.field_key in chosen and item.decision == "pending" and item.kind in OPEN_KINDS]
    if not items:
        raise ReextractError(422, "Keine offene Angabe ausgewählt.")
    _decide(items, decision, actor)
    _settle(session, run)
    log_activity(session, actor, run.contract_id, "contract.reextraction_decided", {
        "run_id": str(run.id), "number": run.number, "decision": decision,
        "fields": [{"key": item.field_key, "label": item.label} for item in items],
    })
    return len(items)


def mark_decided(session: Session, actor: RegisterActor, run: ContractReextraction,
                 items: list[ContractReextractionProposal], decision: str) -> None:
    _decide(items, decision, actor)
    run.summary = stats(proposals(session, run))


def proposals_by_id(session: Session, ids: Iterable[uuid.UUID]) -> list[ContractReextractionProposal]:
    wanted = list(ids)
    if not wanted:
        return []
    return list(session.scalars(select(ContractReextractionProposal).where(ContractReextractionProposal.id.in_(wanted))))


def safe_unchanged(session: Session, run: ContractReextraction) -> list[ContractReextractionProposal]:
    """Unveraenderte, nicht geschuetzte Angaben mit Sicherheit >= 0,95 (Sammelbestaetigung)."""
    return [item for item in proposals(session, run)
            if item.kind == "unchanged" and not item.protected and item.decision == "pending"
            and item.confidence is not None and item.confidence >= SAFE_CONFIDENCE]


def discard(session: Session, actor: RegisterActor, run: ContractReextraction) -> None:
    """Alles verwerfen: offene Vorschlaege abgelehnt, bereits Uebernommenes bleibt."""
    if run.status != "ready":
        raise ReextractError(409, "Dieses Ergebnis ist nicht mehr offen.")
    items = build_proposals(session, run)
    _decide([item for item in items if item.decision == "pending"], "rejected", actor)
    run.summary = stats(items)
    run.status = "applied" if any(item.decision == "accepted" for item in items) else "discarded"
    run.finished_at = run.finished_at or datetime.now(timezone.utc)
    log_activity(session, actor, run.contract_id, "contract.reextraction_discarded", {"run_id": str(run.id), "number": run.number})


def cancel(session: Session, run: ContractReextraction) -> None:
    if run.status == "queued":
        run.status = "cancelled"
        run.finished_at = datetime.now(timezone.utc)
        run.message = "Abgebrochen."
    elif run.status == "running":
        # Abgebrochen wird vor dem naechsten Modellaufruf (Fortschritts-Rueckruf); das Ergebnis wird verworfen.
        run.cancel_requested = True
    else:
        raise ReextractError(409, "Dieser Lauf ist bereits beendet.")


def reset_reviews(session: Session, run: ContractReextraction) -> int:
    """"Bestaetigungen zuruecksetzen": jede gepruefte Angabe und jeder Nachweis gilt wieder als ungeprueft.

    Werte bleiben unveraendert; nur der Pruefstand wird geoeffnet.
    """
    from app.api.routes.contracts import _build_augmented_detail
    from app.contracts.review.material import material_report
    from app.contracts.review.service import reopen_after_reextraction
    from app.database.models import ContractEvidenceReview

    detail = _build_augmented_detail(session, organization_id=run.organization_id, contract_id=run.contract_id)
    report = material_report(detail or {})
    values = {key: (entry or {}).get("value") for key, entry in report.items()}
    reopened = reopen_after_reextraction(
        session, organization_id=run.organization_id, contract_id=run.contract_id, values=values,
        reviewer_display_name=run.requested_by_name or "Analyse",
    )
    cleared = session.execute(
        delete(ContractEvidenceReview).where(
            ContractEvidenceReview.organization_id == run.organization_id,
            ContractEvidenceReview.contract_id == run.contract_id,
        )
    ).rowcount or 0
    actor = RegisterActor(organization_id=run.organization_id, account_id=run.requested_by_account_id,
                          display_name=run.requested_by_name, role="contract_manager")
    log_activity(session, actor, run.contract_id, "contract.reextraction_reset", {
        "run_id": str(run.id), "number": run.number, "facts": len(reopened), "evidence": int(cleared),
    })
    return len(reopened) + int(cleared)


# --- Verlauf und Zuruecknahme ---------------------------------------------------------------


def history(session: Session, contract: Contract) -> list[dict]:
    """Analysen neueste zuerst, mit Statistik und "Auf diesen Stand zurueck" (wo moeglich)."""
    items = runs(session, contract)
    accepted_after: dict[int, int] = {}
    accepted_by_run = {
        run_id: count for run_id, count in session.execute(
            select(ContractReextractionProposal.run_id, func.count())
            .where(
                ContractReextractionProposal.organization_id == contract.organization_id,
                ContractReextractionProposal.run_id.in_([item.id for item in items] or [uuid.uuid4()]),
                ContractReextractionProposal.decision == "accepted",
            )
            .group_by(ContractReextractionProposal.run_id)
        )
    }
    later = 0
    for item in items:  # neueste zuerst: Uebernahmen spaeterer Analysen aufsummieren
        accepted_after[item.number] = later
        later += int(accepted_by_run.get(item.id, 0))
    out = [{
        "id": str(item.id),
        "number": item.number,
        "mode": item.mode,
        "mode_label": MODE_LABELS.get(item.mode, item.mode),
        "status": item.status,
        "date": (item.finished_at or item.created_at).isoformat() if (item.finished_at or item.created_at) else None,
        "requested_by_name": item.requested_by_name,
        "summary": item.summary or {},
        "accepted": int(accepted_by_run.get(item.id, 0)),
        "can_rollback": item.mode != "rollback" and accepted_after[item.number] > 0,
    } for item in items]
    first = min((item.number for item in items), default=None)
    if contract.accepted_extraction_id is not None and (first is None or first > 1):
        out.append({
            "id": None, "number": 1, "mode": "initial", "mode_label": "Erstanalyse", "status": "applied",
            "date": contract.created_at.isoformat() if contract.created_at else None, "requested_by_name": None,
            "summary": {}, "accepted": 0, "can_rollback": later > 0,
        })
    return out


def rollback_plan(session: Session, contract: Contract, target: int):
    """Stand nach Analyse #target: Uebernahmen spaeterer Analysen zuruecknehmen (neueste zuerst).

    Gibt (Modell, Eintraege, Vorschlaege) zurueck. Steht im Vertrag nicht mehr der uebernommene
    Wert (spaeter geaendert), wird die Angabe uebersprungen und genannt – nie ueberschrieben.
    """
    if any(item.status in REEXTRACTION_ACTIVE for item in runs(session, contract)):
        raise ReextractError(409, "Während eine Analyse läuft, lässt sich kein Stand zurücknehmen.")
    accepted = load_extracted(session, contract.accepted_extraction_id) if contract.accepted_extraction_id else None
    if accepted is None:
        raise ReextractError(409, "Für diesen Vertrag gibt es keinen übernommenen Stand.")
    later = [item for item in runs(session, contract) if item.number > target and item.mode != "rollback"]
    if not later and target != 1 and not any(item.number == target for item in runs(session, contract)):
        raise ReextractError(404, "Analyse nicht gefunden.")
    model = accepted
    entries: list[dict] = []
    undo: list[ContractReextractionProposal] = []
    for run in later:  # neueste zuerst
        for item in proposals(session, run):
            if item.decision != "accepted":
                continue
            current = facts.get_fact(model, item.field_key)
            entry = {"key": item.field_key, "label": item.label, "number": run.number,
                     "current": item.new_display, "restored": item.old_display}
            if not facts.same_snapshot(current, item.new_value):
                entries.append({**entry, "conflict": True, "current": facts.display(current)})
                continue
            model = facts.with_evidence(facts.with_fact(model, item.field_key, item.old_value),
                                        item.field_key, item.old_evidence or [])
            entries.append({**entry, "conflict": False})
            undo.append(item)
    return model, entries, undo


def record_rollback(session: Session, actor: RegisterActor, contract: Contract, target: int,
                    undone: list[ContractReextractionProposal], entries: list[dict], base_extraction_id) -> ContractReextraction:
    """Nach der Zuruecknahme: Vorschlaege markieren und einen Eintrag im Verlauf anlegen."""
    _decide(undone, "rolled_back", actor)
    run = ContractReextraction(
        organization_id=contract.organization_id,
        contract_id=contract.id,
        document_version_id=main_document_version(session, contract),
        number=next_number(session, contract),
        mode="rollback",
        status="applied",
        base_extraction_id=base_extraction_id,
        summary={"rolled_back": len(undone), "skipped": sum(1 for entry in entries if entry["conflict"]), "target": target},
        applied_keys=[item.field_key for item in undone],
        requested_by_account_id=actor.account_id,
        requested_by_name=actor.display_name,
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )
    session.add(run)
    session.flush()
    log_activity(session, actor, contract.id, "contract.reextraction_rolled_back", {
        "run_id": str(run.id), "number": run.number, "target": target,
        "fields": [{"key": item.field_key, "label": item.label} for item in undone],
        "skipped": [{"key": entry["key"], "label": entry["label"]} for entry in entries if entry["conflict"]],
    })
    return run


def new_document(session: Session, contract: Contract) -> Optional[dict]:
    """Neues Hauptdokument seit der letzten Analyse: "Neues Dokument – Ergänzen starten?"."""
    from app.database.models import ContractExtraction

    version_id = main_document_version(session, contract)
    if version_id is None or contract.accepted_extraction_id is None:
        return None
    analysed = session.scalar(select(ContractExtraction.document_version_id).where(ContractExtraction.id == contract.accepted_extraction_id))
    last = latest_run(session, contract)
    if analysed == version_id or (last is not None and last.document_version_id == version_id):
        return None
    version = session.get(DocumentVersion, version_id)
    return {"document_version_id": str(version_id), "filename": _filename(session, version)}


def _filename(session: Session, version: Optional[DocumentVersion]) -> Optional[str]:
    return version.document_file.original_filename if version is not None and version.document_file else None


def reread_suggested(session: Session, version_id: Optional[uuid.UUID]) -> bool:
    """Neu lesen vorschlagen, wenn das PDF bisher ohne Texterkennung verarbeitet wurde."""
    if version_id is None:
        return False
    version = session.get(DocumentVersion, version_id)
    if version is None or not str(version.storage_key or "").lower().endswith(".pdf"):
        return False
    run = session.scalars(
        select(ProcessingRun)
        .where(ProcessingRun.document_version_id == version_id, ProcessingRun.status == "succeeded")
        .order_by(ProcessingRun.created_at.asc())
    ).first()
    return bool(run is not None and run.do_ocr is False)
