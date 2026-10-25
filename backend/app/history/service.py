"""H6.2 Historie: Vertragshistorie (zusammengefuehrt) und organisationsweites Protokoll."""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.contracts.overrides.service import audit_history
from app.contracts.review.service import build_fact_review_history
from app.database.models import Contract
from app.database.models.activity_log import ActivityLog
from app.database.models.contract import ContractDocument
from app.database.models.deadlines import Notification, NotificationOutbox
from app.database.models.document import DocumentFile, DocumentVersion

EVENT_LABELS: dict[str, str] = {
    "contract.created_manual": "Vertrag angelegt",
    "contract.imported": "Vertrag importiert",
    "analysis.initial_done": "KI-Erstanalyse abgeschlossen",
    "analysis.initial_failed": "KI-Erstanalyse fehlgeschlagen",
    "analysis.run_ready": "KI-Analyse abgeschlossen",
    "analysis.run_failed": "KI-Analyse fehlgeschlagen",
    "analysis.run_cancelled": "KI-Analyse abgebrochen",
    "organization.review_mode_changed": "Prüfmodus geändert",
    "contract.register_updated": "Stammdaten geändert",
    "contract.status_changed": "Status geändert",
    "contract.remark_added": "Notiz hinzugefügt",
    "contract.remark_edited": "Notiz bearbeitet",
    "contract.remark_deleted": "Notiz gelöscht",
    "contract.evidence_reviewed": "Nachweise geprüft",
    "contract.value_from_document": "Angabe aus dem Dokument übernommen",
    "contract.risk_decided": "Risiko bestätigt oder festgelegt",
    "contract.reextraction_started": "Erneute Erfassung gestartet",
    "contract.reextraction_applied": "Erneute Erfassung übernommen",
    "contract.reextraction_discarded": "Erneute Erfassung verworfen",
    "contract.reextraction_decided": "KI-Analyse: Vorschläge entschieden",
    "contract.reextraction_confirmed_unchanged": "KI-Analyse: unveränderte Angaben bestätigt",
    "contract.reextraction_reset": "KI-Analyse: Bestätigungen zurückgesetzt",
    "contract.reextraction_rolled_back": "KI-Analyse: früheren Stand wiederhergestellt",
    "contract.register_proposal_dismissed": "KI-Vorschlag ignoriert",
    "contract.hospitals_updated": "Krankenhäuser geändert",
    "contract.confidentiality_updated": "Vertraulichkeit geändert",
    "contract.document_updated": "Dokument geändert",
    "contract.document_added": "Dokument hinzugefügt",
    "contract.document_attached": "Dokumente hochgeladen",
    "contract.document_removed": "Dokument entfernt",
    "contract.document_restored": "Dokument wiederhergestellt",
    "contract.device_types_updated": "Gerätearten geändert",
    "contract.reminders_updated": "Erinnerungen geändert",
    "catalog.device_type_created": "Geräteart angelegt",
    "catalog.device_type_updated": "Geräteart geändert",
    "contract.ai_values_applied": "KI-Werte in Stammdaten übernommen",
    "deadline.system_created": "Systemtermin angelegt",
    "deadline.system_updated": "Systemtermin angepasst",
    "deadline.system_cancelled": "Systemtermin entfernt",
    "notification.deadline_reminder": "Erinnerung zugestellt",
    "notification.deadline_overdue": "Überfälligkeit gemeldet",
    "notification.deadline_escalation": "Eskalation gemeldet",
    "partner.created": "Vertragspartner angelegt",
    "partner.updated": "Vertragspartner geändert",
    "partner.suggestion_dismissed": "Vorschlag für Vertragspartner ignoriert",
    "partner.merged": "Vertragspartner zusammengeführt",
    "partner.merged_into": "Vertragspartner in Dublette überführt",
    "partner.bulk_imported": "Vertragspartner importiert",
    "contract.partner_merged": "Vertragspartner durch Zusammenführung ersetzt",
    "department.bulk_imported": "Abteilungen importiert",
    "cost_center.bulk_imported": "Kostenstellen importiert",
    "catalog.lookup_bulk_imported": "Auswahlwerte importiert",
    "catalog.rule_created": "Vertragsregel angelegt",
    "catalog.rule_updated": "Vertragsregel geändert",
    "catalog.contract_type_created": "Vertragstyp angelegt",
    "catalog.contract_type_updated": "Vertragstyp geändert",
    "catalog.contract_category_created": "Kategorie angelegt",
    "catalog.contract_category_updated": "Kategorie geändert",
    "catalog.lookup_created": "Auswahlwert angelegt",
    "catalog.lookup_updated": "Auswahlwert geändert",
    "catalog.defaults_loaded": "Standardkatalog ergänzt",
    "number_range.updated": "Nummernkreis geändert",
    "number_range.reserved": "Vertragsnummern reserviert",
    "deputy.created": "Vertretung angelegt",
    "deputy.deactivated": "Vertretung beendet",
    "account.notification_settings_updated": "Benachrichtigungen geändert",
    "contract.lifecycle_decision_created": "Entscheidung erfasst",
    "contract.lifecycle_decision_updated": "Entscheidung geändert",
    "contract.lifecycle_decision_deleted": "Entscheidung gelöscht",
    "contract.lifecycle_completed": "Entscheidung abgeschlossen",
    "contract.lifecycle_cancelled": "Entscheidung storniert",
    "contract.lifecycle_in_progress": "Entscheidung in Bearbeitung",
    "contract.lifecycle_step_done": "Umsetzungsschritt erledigt",
    "contract.lifecycle_step_undone": "Umsetzungsschritt wieder offen",
    "contract.framework_linked": "Rahmenvertrag verknüpft",
    "contract.framework_unlinked": "Rahmenvertrag gelöst",
    "contract.ownership_updated": "Zuständigkeit geändert",
    "contract.department_roles_updated": "Abteilungsrollen geändert",
    "contract.archived": "Vertrag archiviert",
    "contract.unarchived": "Vertrag wiederhergestellt",
    "contracts.exported": "Verträge exportiert",
    "deadline.created": "Termin angelegt",
    "deadline.updated": "Termin geändert",
    "deadline.done": "Termin erledigt",
    "deadline.reopen": "Termin wieder geöffnet",
    "deadline.cancel": "Termin abgesagt",
    "finance.entry_created": "Finanzposten angelegt",
    "finance.entry_updated": "Finanzposten geändert",
    "finance.entry_deleted": "Finanzposten gelöscht",
    "finance.service_created": "Leistung angelegt",
    "finance.service_updated": "Leistung geändert",
    "finance.service_deleted": "Leistung gelöscht",
    "finance.allocations_updated": "Kostenstellenaufteilung geändert",
    "finance.suggestion_dismissed": "KI-Vorschlag verworfen",
    "finance.exported": "Finanzdaten exportiert",
    "fact_review.confirmed": "Fakt bestätigt",
    "fact_review.corrected": "Fakt korrigiert",
    "fact_review.reopened": "Fakt erneut geöffnet",
    "fact_review.voided": "Fakt verworfen",
    "field_review.keep": "Angabe geprüft: Wert beibehalten",
    "field_review.accept": "Angabe geprüft: Dokumentwert übernommen",
    "field_review.manual": "Angabe geprüft: Wert von Hand korrigiert",
    "field_review.defer": "Angabe zurückgestellt",
    "field_review.not_in_document": "Angabe: steht nicht im Dokument",
    "field_review.evidence_primary": "Nachweis als maßgeblich gewählt",
    "field_review.evidence_exclude": "Nachweis ausgeschlossen",
    "field_review.evidence_restore": "Nachweis wieder berücksichtigt",
    "field_review.finding_linked": "Weitere Information einer Angabe zugeordnet",
    "field_review.finding_note": "Weitere Information vermerkt",
    "field_review.finding_dismissed": "Weitere Information ausgeblendet",
    "field_review.finding_restored": "Weitere Information wiederhergestellt",
    "contract_review.started": "Vertragsprüfung geöffnet",
    "contract_review.completed": "Vertragsprüfung abgeschlossen",
    "override.set": "Wert manuell gesetzt",
    "override.void": "Manuellen Wert zurückgesetzt",
    "override.confirm": "Fakt manuell bestätigt",
    "notification.mail_sent": "Erinnerung per E-Mail versendet",
    "history.exported": "Historie exportiert",
    "register.exported": "Vertragsregister exportiert",
    "register.report_exported": "Bericht exportiert",
    "account.created": "Benutzer angelegt",
    "account.updated": "Benutzer geändert",
    "account.scope_updated": "Benutzerbereich geändert",
    "hospital.created": "Krankenhaus angelegt",
    "hospital.updated": "Krankenhaus geändert",
    "department.created": "Abteilung angelegt",
    "department.updated": "Abteilung geändert",
    "cost_center.created": "Kostenstelle angelegt",
    "cost_center.updated": "Kostenstelle geändert",
    "equipment.ownership_updated": "Gerätezuordnung geändert",
    "work_item.comment_added": "Aufgabe kommentiert",
}

CATEGORIES: dict[str, str] = {
    "contract": "Verträge",
    "deadline": "Termine",
    "finance": "Finanzen",
    "fact_review": "Prüfungen",
    "notes": "Notizen",
    "analysis": "KI-Analyse",
    "override": "Manuelle Werte",
    "account": "Benutzer",
    "organisation": "Organisation",
    "other": "Sonstiges",
}

_CATEGORY_PREFIXES: dict[str, tuple[str, ...]] = {
    "notes": ("contract.remark_",),
    "analysis": ("analysis.", "contract.reextraction_", "contract.ai_values_applied", "contract.register_proposal_dismissed", "contract.value_from_document"),
    "contract": ("contract.", "contracts.", "contract_review.", "register."),
    "deadline": ("deadline.", "notification."),
    "finance": ("finance.",),
    "fact_review": ("fact_review.", "field_review."),
    "override": ("override.",),
    "account": ("account.", "deputy."),
    "organisation": ("hospital.", "department.", "cost_center.", "partner.", "catalog.", "number_range."),
}


def event_label(event_name: str) -> str:
    if event_name in EVENT_LABELS:
        return EVENT_LABELS[event_name]
    prefix, _, rest = event_name.partition(".")
    return f"{prefix}: {rest.replace('_', ' ')}" if rest else event_name


def event_category(event_name: str) -> str:
    for key, prefixes in _CATEGORY_PREFIXES.items():
        if event_name.startswith(prefixes):
            return key
    return "other"


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def field_labels(details: Optional[dict]) -> dict[str, str]:
    """Deutsche Feldnamen (eine Quelle: register.fields.FIELDS) für Felddiffs im Verlauf (U9)."""
    from app.register.fields import FIELDS

    fields = (details or {}).get("fields")
    if not isinstance(fields, dict):
        return {}
    return {key: FIELDS[key].label_de for key in fields if key in FIELDS}


def _activity_entry(row: ActivityLog) -> dict:
    details = row.context_data or {}
    return {
        "id": f"activity:{row.id}",
        "kind": "activity",
        "category": event_category(row.event_name),
        "at": _iso(row.created_at),
        "actor": row.display_name_snapshot,
        "event": row.event_name,
        "label": event_label(row.event_name),
        "details": details,
        "field_labels": field_labels(details),
    }


def _entry(kind: str, entry_id: Any, at: Optional[str], actor: Optional[str], event: str, label: str, details: dict) -> dict:
    return {
        "id": f"{kind}:{entry_id}",
        "kind": kind,
        "category": event_category(event),
        "at": at,
        "actor": actor,
        "event": event,
        "label": label,
        "details": details,
        "field_labels": field_labels(details),
    }


def contract_history(session: Session, contract: Contract, limit: int = 500) -> list[dict]:
    """Alle Spuren eines Vertrags, neueste zuerst: Benutzeraktionen, Fakt-Pruefungen,
    manuelle Werte, Dokumente und versendete Erinnerungen."""
    entries: list[dict] = [
        _activity_entry(row)
        for row in session.scalars(
            select(ActivityLog)
            .where(
                ActivityLog.organization_id == contract.organization_id,
                ActivityLog.object_type == "contract",
                ActivityLog.object_id == contract.id,
            )
            .order_by(ActivityLog.created_at.desc())
            .limit(limit)
        ).all()
    ]

    for review in build_fact_review_history(session, contract_id=contract.id):
        entries.append(_entry(
            "fact_review", review["id"], review["created_at"], review["reviewer_display_name"],
            f"fact_review.{review['action']}", f"{review['action_label_de']}: {review['fact_label_de']}",
            {key: review[key] for key in ("previous_effective_value", "new_effective_value", "note") if review.get(key) is not None},
        ))

    for override in audit_history(session, organization_id=contract.organization_id, contract_id=contract.id):
        event = f"override.{override['action']}"
        entries.append(_entry(
            "override", override["id"], override["created_at"], override["actor_display_name"],
            event, f"{event_label(event)}: {override['key']}",
            {key: override[key] for key in ("old_value", "value", "note") if override.get(key) is not None},
        ))

    for link, filename in session.execute(
        select(ContractDocument, DocumentFile.original_filename)
        .join(DocumentVersion, DocumentVersion.id == ContractDocument.document_version_id)
        .join(DocumentFile, DocumentFile.id == DocumentVersion.document_file_id)
        .where(ContractDocument.contract_id == contract.id)
    ).all():
        entries.append(_entry(
            "document", link.id, _iso(link.created_at), link.added_by_name, "contract.document_added",
            "Hauptdokument hinzugefügt" if link.is_main else "Dokument hinzugefügt",
            {key: value for key, value in (("title", link.title or filename), ("attachment_type", link.attachment_type)) if value},
        ))

    # Entfernte Dokumente: das Hinzufügen bleibt im Verlauf sichtbar.
    from app.database.models.contract import ContractDocumentRemoved

    for removed, filename in session.execute(
        select(ContractDocumentRemoved, DocumentFile.original_filename)
        .join(DocumentVersion, DocumentVersion.id == ContractDocumentRemoved.document_version_id)
        .join(DocumentFile, DocumentFile.id == DocumentVersion.document_file_id)
        .where(ContractDocumentRemoved.contract_id == contract.id, ContractDocumentRemoved.added_at.is_not(None))
    ).all():
        entries.append(_entry(
            "document", removed.id, _iso(removed.added_at), removed.added_by_name, "contract.document_added", "Dokument hinzugefügt",
            {key: value for key, value in (("title", removed.title or filename), ("attachment_type", removed.attachment_type)) if value},
        ))

    for outbox, title in session.execute(
        select(NotificationOutbox, Notification.title)
        .join(Notification, Notification.id == NotificationOutbox.notification_id)
        .where(Notification.contract_id == contract.id, NotificationOutbox.status == "sent")
    ).all():
        entries.append(_entry(
            "mail", outbox.id, _iso(outbox.sent_at or outbox.created_at), "System", "notification.mail_sent",
            EVENT_LABELS["notification.mail_sent"], {"recipient": outbox.recipient, "subject": outbox.subject or title},
        ))

    entries.extend(_analysis_entries(session, contract))

    entries.sort(key=lambda entry: entry["at"] or "", reverse=True)
    return entries[:limit]


_INTAKE_LABEL = {
    "ai_human_review": "KI-Analyse mit Prüfung durch Menschen",
    "ai_direct": "KI-Analyse, direkt übernommen",
    "manual": "von Hand erfassen (ohne KI)",
}
_RUN_MODE_LABEL = {
    "supplement": "Ergänzen", "sections": "Bereich neu erfassen", "full": "Vollständig neu bewerten", "missing_fields": "Ergänzen",
}


def _analysis_entries(session: Session, contract: Contract) -> list[dict]:
    """Abgeleitete Spuren, die sonst fehlen: Import, Erstanalyse und das Ende jeder erneuten KI-Analyse."""
    from app.database.models.extraction import ContractExtraction
    from app.database.models.reextraction import ContractReextraction

    out: list[dict] = []
    if contract.created_at is not None and getattr(contract, "intake_mode", None) is not None:
        out.append(_entry(
            "analysis", f"import-{contract.id}", _iso(contract.created_at), None, "contract.imported", EVENT_LABELS["contract.imported"],
            {"intake": _INTAKE_LABEL.get(contract.intake_mode, contract.intake_mode)},
        ))

    versions = list(session.scalars(select(ContractDocument.document_version_id).where(ContractDocument.contract_id == contract.id)).all())
    first = session.scalars(
        select(ContractExtraction).where(ContractExtraction.document_version_id.in_(versions)).order_by(ContractExtraction.created_at.asc()).limit(1)
    ).first() if versions and getattr(contract, "intake_mode", None) != "manual" else None
    if first is not None:
        failed = first.status == "failed"
        details: dict[str, Any] = {}
        if first.model:
            details["model"] = first.model
        if first.processing_duration is not None:
            details["duration"] = f"{round(float(first.processing_duration) / 60, 1)} Min."
        if failed and first.message:
            details["note"] = str(first.message)[:240]
        event = "analysis.initial_failed" if failed else "analysis.initial_done"
        out.append(_entry("analysis", f"first-{first.id}", _iso(first.created_at), None, event, EVENT_LABELS[event], details))

    for run in session.scalars(
        select(ContractReextraction).where(
            ContractReextraction.contract_id == contract.id,
            ContractReextraction.mode != "rollback",
            ContractReextraction.finished_at.is_not(None),
        )
    ).all():
        if run.status == "failed":
            event = "analysis.run_failed"
        elif run.status == "cancelled":
            event = "analysis.run_cancelled"
        else:
            event = "analysis.run_ready"
        details = {"title": f"Analyse #{run.number} · {_RUN_MODE_LABEL.get(run.mode, run.mode)}"}
        if run.model_id:
            details["model"] = run.model_id
        if run.message and event != "analysis.run_ready":
            details["note"] = run.message
        out.append(_entry("analysis", f"run-{run.id}", _iso(run.finished_at), run.requested_by_name, event, EVENT_LABELS[event], details))
    return out


@dataclass(frozen=True)
class HistoryFilter:
    account_id: Optional[uuid.UUID] = None
    category: Optional[str] = None
    contract_id: Optional[uuid.UUID] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    object_type: Optional[str] = None
    object_id: Optional[uuid.UUID] = None


def _filtered(
    organization_id: uuid.UUID,
    filters: HistoryFilter,
    visible: Optional[set[uuid.UUID]],
    hospital_id: Optional[uuid.UUID],
    department_id: Optional[uuid.UUID],
) -> Select:
    stmt = select(ActivityLog).where(ActivityLog.organization_id == organization_id)
    if visible is not None:
        stmt = stmt.where(or_(ActivityLog.object_type != "contract", ActivityLog.object_id.in_(visible)))
    if department_id is not None:
        stmt = stmt.where(or_(ActivityLog.object_type == "contract", ActivityLog.department_id == department_id))
    elif hospital_id is not None:
        stmt = stmt.where(or_(ActivityLog.object_type == "contract", ActivityLog.hospital_id == hospital_id))
    if filters.account_id is not None:
        stmt = stmt.where(ActivityLog.account_id == filters.account_id)
    if filters.contract_id is not None:
        stmt = stmt.where(ActivityLog.object_type == "contract", ActivityLog.object_id == filters.contract_id)
    if filters.object_type is not None and filters.object_id is not None:
        stmt = stmt.where(ActivityLog.object_type == filters.object_type, ActivityLog.object_id == filters.object_id)
    if filters.category == "other":
        known = [prefix for prefixes in _CATEGORY_PREFIXES.values() for prefix in prefixes]
        stmt = stmt.where(*[~ActivityLog.event_name.startswith(prefix) for prefix in known])
    elif filters.category:
        stmt = stmt.where(or_(*[ActivityLog.event_name.startswith(prefix) for prefix in _CATEGORY_PREFIXES[filters.category]]))
    if filters.date_from is not None:
        stmt = stmt.where(ActivityLog.created_at >= datetime.combine(filters.date_from, time.min, tzinfo=timezone.utc))
    if filters.date_to is not None:
        stmt = stmt.where(ActivityLog.created_at < datetime.combine(filters.date_to + timedelta(days=1), time.min, tzinfo=timezone.utc))
    return stmt


def organization_history(
    session: Session,
    organization_id: uuid.UUID,
    filters: HistoryFilter,
    *,
    visible: Optional[set[uuid.UUID]],
    hospital_id: Optional[uuid.UUID] = None,
    department_id: Optional[uuid.UUID] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    stmt = _filtered(organization_id, filters, visible, hospital_id, department_id)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.scalars(
        stmt.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 10000))
    ).all()
    contract_ids = {row.object_id for row in rows if row.object_type == "contract" and row.object_id}
    contracts = {
        cid: (number, title)
        for cid, number, title in session.execute(
            select(Contract.id, Contract.register_number, Contract.short_description).where(Contract.id.in_(contract_ids))
        ).all()
    } if contract_ids else {}
    items = []
    for row in rows:
        number, title = contracts.get(row.object_id, (None, None)) if row.object_type == "contract" else (None, None)
        items.append({
            **_activity_entry(row),
            "role": row.role_snapshot,
            "object_type": row.object_type,
            "object_id": str(row.object_id) if row.object_id else None,
            "contract_number": number,
            "contract_title": title,
        })
    return {"total": total, "items": items}


def history_actors(session: Session, organization_id: uuid.UUID) -> list[dict]:
    rows = session.execute(
        select(ActivityLog.account_id, func.max(ActivityLog.display_name_snapshot))
        .where(ActivityLog.organization_id == organization_id, ActivityLog.account_id.is_not(None))
        .group_by(ActivityLog.account_id)
        .order_by(func.max(ActivityLog.display_name_snapshot))
    ).all()
    return [{"account_id": str(account_id), "display_name": name} for account_id, name in rows]


def _detail_text(details: Any) -> str:
    if isinstance(details, dict):
        return "; ".join(f"{key}: {_detail_text(value)}" for key, value in details.items())
    if isinstance(details, list):
        return ", ".join(_detail_text(value) for value in details)
    return "" if details is None else str(details)


def _csv_cell(value: str) -> str:
    # Formel-Injektion in Excel verhindern.
    return f"'{value}" if value[:1] in ("=", "+", "-", "@") else value


def history_csv(items: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(["Zeitpunkt", "Benutzer", "Rolle", "Bereich", "Aktion", "Vertragsnummer", "Vertrag", "Details"])
    for item in items:
        writer.writerow([_csv_cell(str(value)) for value in (
            item["at"] or "",
            item.get("actor") or "",
            item.get("role") or "",
            CATEGORIES.get(item["category"], item["category"]),
            item["label"],
            item.get("contract_number") or "",
            item.get("contract_title") or "",
            _detail_text(item.get("details")),
        )])
    return "﻿" + buffer.getvalue()
