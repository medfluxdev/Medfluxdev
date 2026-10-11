"""Erneute Erfassung aus dem Vertragsdokument: Warteschlange, Vergleich, Uebernahme.

Ablauf: `start` legt einen Lauf an (wartend) -> `drain` verarbeitet die
Warteschlange nacheinander (eine GPU, Advisory-Lock ueber alle Prozesse) und
speichert nur einen Kandidaten -> `rows` vergleicht ihn mit der Vertragswahrheit
-> `apply` uebernimmt die ausgewaehlten Angaben ueber den normalen Akzeptanzweg.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.contract import Contract as ExtractedContract
from app.core.config import settings
from app.database.models import Contract, ContractDocument, DocumentVersion, ProcessingRun
from app.database.models.reextraction import REEXTRACTION_ACTIVE, ContractReextraction
from app.database.session import create_session, get_engine
from app.reextract import facts
from app.register.service import RegisterActor, load_extracted, log_activity

logger = logging.getLogger(__name__)

# Fester Schluessel fuer pg_advisory_lock: hoechstens eine erneute Erfassung gleichzeitig.
_LOCK_KEY = 0x4D46_5245  # "MFRE"
# Tests setzen SYNC = True und rufen drain() selbst auf.
SYNC = False


class ReextractError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


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
    return session.scalars(
        select(ContractReextraction)
        .where(
            ContractReextraction.organization_id == contract.organization_id,
            ContractReextraction.contract_id == contract.id,
        )
        .order_by(ContractReextraction.created_at.desc())
    ).first()


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
    """Fakten, die fuer die fehlenden Vertragsdaten in Frage kommen ("Nur fehlende Angaben")."""
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
) -> ContractReextraction:
    if contract.lifecycle_state != "active":
        raise ReextractError(409, "Dieser Vertrag kann nicht erneut erfasst werden.")
    # Ohne frühere KI-Analyse (z. B. von Hand erfasster Vertrag mit Dokument) ist die erste Erfassung
    # ein Lauf gegen eine leere Grundlage: alles Gefundene ist „neu“, übernommen wird nur Ausgewähltes.
    version_id = main_document_version(session, contract)
    if version_id is None:
        raise ReextractError(409, "Kein Vertragsdokument hinterlegt.")
    wanted = [str(item) for item in fields]
    unknown = [item for item in wanted if item not in facts.LABELS]
    if unknown:
        raise ReextractError(422, "Unbekannte Angaben ausgewählt.")
    if mode == "missing_fields" and not wanted:
        raise ReextractError(422, "Bitte mindestens eine fehlende Angabe auswählen.")
    pages = sorted({int(page) for page in page_hint if int(page) > 0})[:20]

    # Ein neuer Lauf ersetzt einen noch nicht uebernommenen, fertigen Lauf.
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
        mode=mode,
        fields=wanted if mode == "missing_fields" else [],
        page_hint=pages,
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
        "run_id": str(run.id), "mode": mode, "fields": run.fields, "pages": pages,
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
        run_id, organization_id, contract_id = run.id, run.organization_id, run.contract_id
        version_id, reread, model_id = run.document_version_id, run.reread_document, run.model_id
        focus_fields = list(run.fields or []) if run.mode == "missing_fields" else None
        focus_pages = list(run.page_hint or []) or None
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
                run.summary = facts.summary(_rows(session, run))
            except Exception:
                logger.exception("Re-extraction comparison failed for run %s", run_id)
                run.status = "failed"
                run.message = "Das Ergebnis konnte nicht verglichen werden."
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
        found = int((run.summary or {}).get("new", 0)) + int((run.summary or {}).get("changed", 0))
        title = f"Erneute Erfassung: {found} Angabe(n) zum Prüfen" if found else "Erneute Erfassung: keine neuen Angaben"
    else:
        title = "Erneute Erfassung fehlgeschlagen"
    session.add(Notification(
        organization_id=run.organization_id,
        account_id=run.requested_by_account_id,
        kind="reextraction",
        title=title[:200],
        body=name[:500],
        contract_id=run.contract_id,
        dedupe_key=f"reextraction:{run.id}",
    ))


def _rows(session: Session, run: ContractReextraction) -> list[facts.FactRow]:
    candidate = load_extracted(session, run.candidate_extraction_id) if run.candidate_extraction_id else None
    if candidate is None:
        return []
    accepted = load_extracted(session, run.base_extraction_id) if run.base_extraction_id else None
    return facts.compare(accepted, candidate, only=run.fields or None)


def rows(session: Session, run: ContractReextraction) -> list[dict]:
    return [row.as_dict() for row in _rows(session, run)] if run.status == "ready" else []


def run_payload(session: Session, run: Optional[ContractReextraction]) -> Optional[dict]:
    if run is None:
        return None
    return {
        "id": str(run.id),
        "status": run.status,
        "mode": run.mode,
        "fields": [{"key": key, "label": facts.LABELS.get(key, key)} for key in (run.fields or [])],
        "page_hint": run.page_hint or [],
        "reread_document": run.reread_document,
        "model_id": run.model_id,
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


def prepare_apply(session: Session, contract: Contract, run: ContractReextraction, keys: Iterable[str]):
    """Prueft die Auswahl und baut die zusammengefuehrte Extraktion."""
    if run.status != "ready":
        raise ReextractError(409, "Dieses Ergebnis kann nicht mehr übernommen werden.")
    if contract.accepted_extraction_id != run.base_extraction_id:
        raise ReextractError(409, "Die Vertragsdaten haben sich seit dem Start geändert. Bitte erneut erfassen.")
    selectable = {row.key for row in _rows(session, run) if row.group in {"new", "changed"}}
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


def mark_applied(session: Session, actor: RegisterActor, run: ContractReextraction, keys: list[str]) -> None:
    run.status = "applied"
    run.applied_keys = keys
    log_activity(session, actor, run.contract_id, "contract.reextraction_applied", {
        "run_id": str(run.id), "fields": [{"key": key, "label": facts.LABELS.get(key, key)} for key in keys],
    })


def discard(session: Session, actor: RegisterActor, run: ContractReextraction) -> None:
    if run.status != "ready":
        raise ReextractError(409, "Dieses Ergebnis ist nicht mehr offen.")
    run.status = "discarded"
    run.finished_at = run.finished_at or datetime.now(timezone.utc)
    log_activity(session, actor, run.contract_id, "contract.reextraction_discarded", {"run_id": str(run.id)})


def cancel(session: Session, run: ContractReextraction) -> None:
    if run.status == "queued":
        run.status = "cancelled"
        run.finished_at = datetime.now(timezone.utc)
        run.message = "Abgebrochen."
    elif run.status == "running":
        # Ein laufender Modellaufruf laesst sich nicht unterbrechen; das Ergebnis wird verworfen.
        run.cancel_requested = True
    else:
        raise ReextractError(409, "Dieser Lauf ist bereits beendet.")


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
