"""Vertragsregister-Service: Lesen, Bearbeiten, KI-Abgleich, Nummernkreis,
Status-Workflow und Bemerkungen.

Herkunftsregeln (Grundsatz 2 des HYDMedia-Plans):
- `ai`: Wert stammt aus der akzeptierten Extraktion; eine Reanalyse darf ihn
  ersetzen.
- `manual`, `ai_corrected`, `ai_confirmed`, `imported_legacy`: Mensch hat den
  Wert gesetzt/bestaetigt; eine Reanalyse ueberschreibt ihn NIE. Weicht die KI
  ab, wird der KI-Wert nur als `ai_proposed_value` vorgeschlagen.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.database.models import (
    Account,
    AccountMembership,
    ActivityLog,
    Contract,
    ContractDepartment,
    ContractExtraction,
    FactReview,
    Hospital,
)
from app.database.models.fact_review import ContractReview
from app.database.models.register import (
    CatalogContractCategory,
    CatalogContractType,
    ContractAccessGrant,
    ContractFieldProvenance,
    ContractHospital,
    ContractPartner,
    ContractRemark,
    NumberAllocation,
    NumberRange,
)
from app.models.contract import Contract as ExtractedContract
from app.register.ai_mapping import proposals_from_extraction
from app.register.fields import FIELD_SPECS, FIELDS, REQUIRED_FOR_VALID, coerce_value, to_json, validate_pairs
from app.register.status import STATUS_LABELS, TransitionError, allowed_targets, plan_transition
from app.register.terms import TermInputs, compute_terms, period

HUMAN_ORIGINS = frozenset({"manual", "ai_corrected", "ai_confirmed", "imported_legacy"})
CONTRACT_NUMBER_PURPOSE = "contract"
DEFAULT_PADDING = 6


class RegisterError(ValueError):
    def __init__(self, status_code: int, detail_de: str, field_key: Optional[str] = None, missing: Optional[list[str]] = None):
        super().__init__(detail_de)
        self.status_code = status_code
        self.detail_de = detail_de
        self.field_key = field_key
        self.missing = missing or []


@dataclass(frozen=True)
class RegisterActor:
    organization_id: uuid.UUID
    account_id: Optional[uuid.UUID]
    display_name: Optional[str]
    role: str
    is_developer: bool = False
    hospital_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None

    @property
    def role_snapshot(self) -> str:
        return "developer" if self.is_developer else self.role


# --------------------------------------------------------------------------- helpers


def _values(contract: Contract) -> dict[str, Any]:
    return {spec.key: getattr(contract, spec.key) for spec in FIELD_SPECS}


def _same(left: Any, right: Any) -> bool:
    return to_json(left) == to_json(right)


def _provenance(session: Session, contract_id: uuid.UUID) -> dict[str, ContractFieldProvenance]:
    rows = session.scalars(
        select(ContractFieldProvenance).where(ContractFieldProvenance.contract_id == contract_id)
    ).all()
    return {row.field_key: row for row in rows}


def log_activity(session: Session, actor: RegisterActor, contract_id: uuid.UUID, event_name: str, context: Optional[dict]) -> None:
    session.add(
        ActivityLog(
            organization_id=actor.organization_id,
            hospital_id=actor.hospital_id,
            department_id=actor.department_id,
            account_id=actor.account_id,
            display_name_snapshot=actor.display_name,
            role_snapshot=actor.role_snapshot,
            event_name=event_name,
            object_type="contract",
            object_id=contract_id,
            context_data=context,
        )
    )


def log_system_activity(
    session: Session, contract: Contract, event_name: str, context: Optional[dict], display_name: str = "System"
) -> None:
    """Protokolliert automatische Aenderungen (Tageslauf, Fristenabgleich, KI-Analyse)."""
    session.add(
        ActivityLog(
            organization_id=contract.organization_id,
            hospital_id=contract.hospital_id,
            account_id=None,
            display_name_snapshot=display_name,
            role_snapshot="system",
            event_name=event_name,
            object_type="contract",
            object_id=contract.id,
            context_data=context,
        )
    )


def review_pending(session: Session, contract: Contract) -> bool:
    if contract.accepted_extraction_id is None:
        return False
    status = session.scalar(select(ContractReview.status).where(ContractReview.contract_id == contract.id))
    return status != "reviewed"


# --------------------------------------------------------------------------- numbering


def format_number(range_row: NumberRange, value: int) -> str:
    return f"{range_row.prefix}{str(value).zfill(range_row.padding)}"


def locked_number_range(session: Session, organization_id: uuid.UUID) -> NumberRange:
    """Nummernkreis unter Zeilensperre; Anlage ist nebenlaeufigkeitssicher.

    Ein neu angelegter Kreis startet bei 1; bereits vergebene oder reservierte
    Nummern werden bei der Vergabe uebersprungen.
    """
    session.execute(
        pg_insert(NumberRange)
        .values(
            organization_id=organization_id,
            purpose=CONTRACT_NUMBER_PURPOSE,
            prefix="",
            padding=DEFAULT_PADDING,
            next_value=1,
        )
        .on_conflict_do_nothing(constraint="uq_number_range_org_purpose")
    )
    return session.scalars(
        select(NumberRange)
        .where(NumberRange.organization_id == organization_id, NumberRange.purpose == CONTRACT_NUMBER_PURPOSE)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


def allocate_contract_number(
    session: Session, *, organization_id: uuid.UUID, contract_id: uuid.UUID, account_id: Optional[uuid.UUID]
) -> str:
    """Naechste freie Nummer (reservierte werden uebersprungen), unter Zeilensperre."""
    range_row = locked_number_range(session, organization_id)
    value = range_row.next_value
    taken = set(
        session.scalars(
            select(NumberAllocation.value).where(
                NumberAllocation.organization_id == organization_id,
                NumberAllocation.purpose == CONTRACT_NUMBER_PURPOSE,
                NumberAllocation.value >= value,
            )
        ).all()
    )
    while value in taken:
        value += 1
    formatted = format_number(range_row, value)
    session.add(
        NumberAllocation(
            organization_id=organization_id,
            purpose=CONTRACT_NUMBER_PURPOSE,
            value=value,
            formatted=formatted,
            state="used",
            contract_id=contract_id,
            account_id=account_id,
        )
    )
    range_row.next_value = value + 1
    session.flush()
    return formatted


def reserve_contract_numbers(
    session: Session, *, organization_id: uuid.UUID, values: list[int], account_id: Optional[uuid.UUID], note: Optional[str]
) -> list[str]:
    range_row = locked_number_range(session, organization_id)
    existing = set(
        session.scalars(
            select(NumberAllocation.value).where(
                NumberAllocation.organization_id == organization_id,
                NumberAllocation.purpose == CONTRACT_NUMBER_PURPOSE,
                NumberAllocation.value.in_(values),
            )
        ).all()
    )
    if existing:
        raise RegisterError(409, f"Nummer(n) bereits vergeben oder reserviert: {', '.join(str(v) for v in sorted(existing))}.")
    out = []
    for value in sorted(set(values)):
        if value < 1:
            raise RegisterError(422, "Nummern müssen positiv sein.")
        formatted = format_number(range_row, value)
        session.add(
            NumberAllocation(
                organization_id=organization_id,
                purpose=CONTRACT_NUMBER_PURPOSE,
                value=value,
                formatted=formatted,
                state="reserved",
                account_id=account_id,
                note=note,
            )
        )
        out.append(formatted)
    session.flush()
    return out


def ensure_register_number(session: Session, contract: Contract, account_id: Optional[uuid.UUID] = None) -> str:
    if contract.register_number:
        return contract.register_number
    contract.register_number = allocate_contract_number(
        session, organization_id=contract.organization_id, contract_id=contract.id, account_id=account_id
    )
    session.flush()
    return contract.register_number


# --------------------------------------------------------------------------- AI sync


def _fact_review_overrides(session: Session, contract_id: uuid.UUID) -> dict[str, FactReview]:
    latest: dict[str, FactReview] = {}
    for row in session.scalars(
        select(FactReview).where(FactReview.contract_id == contract_id).order_by(FactReview.created_at)
    ).all():
        latest[row.fact_key] = row
    return latest


def _review_value(row: FactReview, field_key: str) -> Any:
    payload = row.new_effective_value
    raw = payload.get("value") if isinstance(payload, dict) else payload
    try:
        return coerce_value(field_key, raw)
    except ValueError:
        return None


def sync_from_extraction(
    session: Session,
    *,
    contract: Contract,
    extracted: ExtractedContract,
    extraction_id: Optional[uuid.UUID],
    replace_ai_values: bool = True,
) -> dict[str, str]:
    """Uebernimmt KI-Vorschlaege in KI-eigene/leere Felder; Menschwerte bleiben.

    Gibt je beruehrtem Feld die Aktion zurueck (set | cleared | proposed | kept).
    """
    proposals = proposals_from_extraction(extracted)
    reviews = _fact_review_overrides(session, contract.id)
    provenance = _provenance(session, contract.id)
    actions: dict[str, str] = {}

    for spec in FIELD_SPECS:
        key = spec.key
        proposal = proposals.get(key)
        row = provenance.get(key)
        current = getattr(contract, key)
        origin = row.origin if row is not None else None
        ai_value = proposal.value if proposal is not None else None
        source = proposal.source_field if proposal is not None else None

        # Fakt-Pruefungen (Korrektur/Bestaetigung) gelten fuer Datumsfelder,
        # deren Prueffakt-Schluessel der Extraktionsquelle entspricht.
        review = reviews.get(source) if source and spec.kind == "date" else None
        review_origin = None
        if review is not None and review.action == "corrected":
            corrected = _review_value(review, key)
            if corrected is not None:
                ai_value, review_origin = corrected, "ai_corrected"
        elif review is not None and review.action == "confirmed" and proposal is not None:
            review_origin = "ai_confirmed"

        if origin in HUMAN_ORIGINS:
            if proposal is not None and not _same(ai_value, current):
                row.ai_proposed_value = {"value": to_json(ai_value), "source_field": source}
                row.extraction_id = extraction_id
                actions[key] = "proposed"
            elif row.ai_proposed_value is not None:
                row.ai_proposed_value = None
                actions[key] = "kept"
            continue

        if proposal is None:
            if origin == "ai" and replace_ai_values and current is not None:
                setattr(contract, key, None)
                session.delete(row)
                actions[key] = "cleared"
            continue
        if current is not None and origin is None:
            # Vor dem Register gepflegter Wert ohne Herkunft: als manuell behandeln.
            session.add(
                ContractFieldProvenance(
                    organization_id=contract.organization_id,
                    contract_id=contract.id,
                    field_key=key,
                    origin="manual",
                    ai_proposed_value=None if _same(ai_value, current) else {"value": to_json(ai_value), "source_field": source},
                    extraction_id=extraction_id,
                )
            )
            actions[key] = "kept"
            continue

        setattr(contract, key, ai_value)
        new_origin = review_origin or "ai"
        if row is None:
            session.add(
                ContractFieldProvenance(
                    organization_id=contract.organization_id,
                    contract_id=contract.id,
                    field_key=key,
                    origin=new_origin,
                    extraction_id=extraction_id,
                    source_field=source,
                    confirmed_by_name=review.reviewer_display_name if review_origin else None,
                    confirmed_at=review.created_at if review_origin else None,
                )
            )
        else:
            row.origin = new_origin
            row.extraction_id = extraction_id
            row.source_field = source
            row.ai_proposed_value = None
        actions[key] = "set"
    changed = {key: action for key, action in actions.items() if action in ("set", "cleared", "proposed")}
    if changed:
        log_system_activity(session, contract, "contract.ai_values_applied", {
            "fields": {
                key: {"action": action, "value": to_json(getattr(contract, key)) if action == "set" else None}
                for key, action in changed.items()
            },
            "extraction_id": str(extraction_id) if extraction_id else None,
        }, display_name="KI-Analyse")
    session.flush()
    return actions


def load_extracted(session: Session, extraction_id: uuid.UUID) -> Optional[ExtractedContract]:
    snapshot = session.scalar(
        select(ContractExtraction.contract_snapshot).where(ContractExtraction.id == extraction_id)
    )
    if not snapshot:
        return None
    try:
        return ExtractedContract.model_validate(snapshot)
    except ValueError:
        return None


def ensure_synced(session: Session, contract: Contract) -> bool:
    """Einmaliger Abgleich fuer Bestandsvertraege (vor dem Register analysiert)."""
    if contract.accepted_extraction_id is None:
        return False
    already = session.scalar(
        select(func.count(ContractFieldProvenance.id)).where(
            ContractFieldProvenance.contract_id == contract.id,
            ContractFieldProvenance.extraction_id == contract.accepted_extraction_id,
        )
    )
    if already:
        return False
    extracted = load_extracted(session, contract.accepted_extraction_id)
    if extracted is None:
        return False
    sync_from_extraction(
        session, contract=contract, extracted=extracted, extraction_id=contract.accepted_extraction_id
    )
    ensure_register_number(session, contract)
    return True


# --------------------------------------------------------------------------- read model


def term_inputs(contract: Contract) -> TermInputs:
    return TermInputs(
        term_model=contract.term_model,
        start_date=contract.term_start_date,
        fixed_end_date=contract.term_fixed_end_date,
        initial_term=period(contract.initial_term_value, contract.initial_term_unit),
        minimum_term=period(contract.minimum_term_value, contract.minimum_term_unit),
        notice_period=period(contract.notice_period_value, contract.notice_period_unit),
        notice_to=contract.notice_to,
        renewal_period=period(contract.renewal_period_value, contract.renewal_period_unit),
        reminder_lead_months=contract.reminder_lead_months,
        terminated_effective=contract.terminated_effective,
        ended_on=contract.ended_on,
    )


def _reference_labels(session: Session, contract: Contract) -> dict[str, Optional[str]]:
    labels: dict[str, Optional[str]] = {}
    if contract.partner_id:
        partner = session.get(ContractPartner, contract.partner_id)
        labels["partner_id"] = partner.short_name if partner else None
    if contract.contract_type_id:
        row = session.get(CatalogContractType, contract.contract_type_id)
        labels["contract_type_id"] = row.label if row else None
    if contract.contract_category_id:
        row = session.get(CatalogContractCategory, contract.contract_category_id)
        labels["contract_category_id"] = row.label if row else None
    for key in ("reminder_recipient_account_id", "escalation_recipient_account_id"):
        account_id = getattr(contract, key)
        if account_id:
            account = session.get(Account, account_id)
            labels[key] = account.display_name if account else None
    return labels


def effective_retention_years(session: Session, contract: Contract) -> tuple[Optional[int], Optional[str]]:
    if contract.retention_years_after_end is not None:
        return contract.retention_years_after_end, "contract"
    if contract.contract_type_id is not None:
        years = session.scalar(
            select(CatalogContractType.retention_years).where(CatalogContractType.id == contract.contract_type_id)
        )
        if years is not None:
            return years, "contract_type"
    return None, None


def retention_dates(contract: Contract, terms, years: Optional[int]) -> tuple[Optional[date], Optional[date]]:
    ended = contract.business_status in ("beendet", "gekuendigt") or contract.term_model == "fixed_term"
    end = terms.actual_end or (terms.possible_end if ended else None)
    deletion_from = date(end.year + years + 1, 1, 1) if end is not None and years is not None else None
    return end, deletion_from


def retention_info(session: Session, contract: Contract, terms) -> dict:
    """H9: Aufbewahrung beginnt mit Schluss des Kalenderjahres des Vertragsendes
    (§ 257 Abs. 5 HGB / § 147 Abs. 4 AO); geloescht werden darf ab dem 1.1. danach."""
    years, source = effective_retention_years(session, contract)
    end, deletion_from = retention_dates(contract, terms, years)
    return {
        "years": years,
        "source": source,
        "contract_end": end.isoformat() if end else None,
        "deletion_from": deletion_from.isoformat() if deletion_from else None,
    }


def confidentiality(session: Session, contract: Contract) -> dict:
    type_confidential = False
    if contract.contract_type_id is not None:
        type_confidential = bool(session.scalar(
            select(CatalogContractType.is_confidential).where(CatalogContractType.id == contract.contract_type_id)
        ))
    grants = session.execute(
        select(ContractAccessGrant.account_id, Account.display_name)
        .join(Account, Account.id == ContractAccessGrant.account_id)
        .where(ContractAccessGrant.contract_id == contract.id)
        .order_by(Account.display_name)
    ).all()
    return {
        "is_confidential": contract.is_confidential,
        "type_confidential": type_confidential,
        "effective": contract.is_confidential or type_confidential,
        "grants": [{"account_id": str(account_id), "display_name": name} for account_id, name in grants],
    }


def set_confidentiality(
    session: Session, *, contract: Contract, actor: RegisterActor, is_confidential: bool, grant_account_ids: list[uuid.UUID]
) -> None:
    for account_id in grant_account_ids:
        member = session.scalar(select(AccountMembership.id).where(
            AccountMembership.account_id == account_id,
            AccountMembership.organization_id == contract.organization_id,
            AccountMembership.is_active.is_(True),
        ))
        if member is None:
            raise RegisterError(422, "Freigabe: Benutzer ist für diese Organisation nicht verfügbar.")
    before = confidentiality(session, contract)
    contract.is_confidential = is_confidential
    existing = {
        row.account_id: row for row in session.scalars(
            select(ContractAccessGrant).where(ContractAccessGrant.contract_id == contract.id)
        ).all()
    }
    wanted = set(grant_account_ids)
    for account_id, row in existing.items():
        if account_id not in wanted:
            session.delete(row)
    for account_id in wanted - set(existing):
        session.add(ContractAccessGrant(
            organization_id=contract.organization_id, contract_id=contract.id, account_id=account_id,
            granted_by_name=actor.display_name,
        ))
    log_activity(session, actor, contract.id, "contract.confidentiality_updated", {
        "before": {"is_confidential": before["is_confidential"], "grants": [g["account_id"] for g in before["grants"]]},
        "after": {"is_confidential": is_confidential, "grants": sorted(str(value) for value in wanted)},
    })
    session.flush()


def build_register(session: Session, contract: Contract, actor: RegisterActor, as_of: Optional[date] = None) -> dict:
    as_of = as_of or date.today()
    provenance = _provenance(session, contract.id)
    labels = _reference_labels(session, contract)
    values = _values(contract)
    fields = {}
    for spec in FIELD_SPECS:
        row = provenance.get(spec.key)
        fields[spec.key] = {
            "value": to_json(values[spec.key]),
            "label": spec.label_de,
            "group": spec.group,
            "display": labels.get(spec.key),
            "origin": row.origin if row else None,
            "source_field": row.source_field if row else None,
            "extraction_id": str(row.extraction_id) if row and row.extraction_id else None,
            "ai_proposed_value": row.ai_proposed_value if row else None,
            "confirmed_by_name": row.confirmed_by_name if row else None,
            "confirmed_at": row.confirmed_at.isoformat() if row and row.confirmed_at else None,
            "updated_by_name": row.updated_by_name if row else None,
            "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        }
    missing_for_valid = [key for key in REQUIRED_FOR_VALID if values.get(key) in (None, "")]
    if contract.partner_id is None and not contract.supplier:
        missing_for_valid.append("partner_id")
    terms = compute_terms(term_inputs(contract), as_of)
    return {
        "contract_id": str(contract.id),
        "register_number": contract.register_number,
        "business_status": contract.business_status,
        "business_status_label": STATUS_LABELS.get(contract.business_status, contract.business_status),
        "allowed_transitions": [
            {"target": target, "label": STATUS_LABELS[target]}
            for target in allowed_targets(contract.business_status, actor.role, actor.is_developer)
        ],
        "supplier_text": contract.supplier,
        "has_ai_analysis": contract.accepted_extraction_id is not None,
        "review_pending": review_pending(session, contract),
        "ended_on": contract.ended_on.isoformat() if contract.ended_on else None,
        "fields": fields,
        "terms": terms.as_dict(),
        "retention": retention_info(session, contract, terms),
        "confidentiality": confidentiality(session, contract),
        "missing_for_valid": missing_for_valid,
        "as_of": as_of.isoformat(),
    }


# --------------------------------------------------------------------------- write


def _validate_references(session: Session, organization_id: uuid.UUID, updates: dict[str, Any]) -> None:
    checks = {
        "partner_id": ContractPartner,
        "contract_type_id": CatalogContractType,
        "contract_category_id": CatalogContractCategory,
    }
    for key, model in checks.items():
        value = updates.get(key)
        if value is None:
            continue
        row = session.get(model, value)
        if row is None or row.organization_id != organization_id:
            raise RegisterError(422, f"{FIELDS[key].label_de}: Auswahl nicht verfügbar.", key)
        if not row.is_active:
            raise RegisterError(422, f"{FIELDS[key].label_de}: Eintrag ist deaktiviert.", key)
    for key in ("reminder_recipient_account_id", "escalation_recipient_account_id"):
        value = updates.get(key)
        if value is None:
            continue
        member = session.scalar(
            select(AccountMembership.id)
            .join(Account, Account.id == AccountMembership.account_id)
            .where(
                AccountMembership.account_id == value,
                AccountMembership.organization_id == organization_id,
                AccountMembership.is_active.is_(True),
                Account.is_active.is_(True),
            )
        )
        if member is None:
            raise RegisterError(422, f"{FIELDS[key].label_de}: Benutzer ist für diese Organisation nicht verfügbar.", key)


def update_register(
    session: Session,
    *,
    contract: Contract,
    actor: RegisterActor,
    changes: dict[str, Any],
    confirm: list[str],
) -> dict[str, dict]:
    """Setzt Felder (Herkunft manual/ai_corrected) und bestaetigt KI-Werte.

    Gibt die Feld-Diffs {key: {before, after}} zurueck (fuer das Audit).
    """
    if contract.business_status == "geloescht":
        raise RegisterError(409, "Gelöschte Verträge können nicht bearbeitet werden.")
    try:
        coerced = {key: coerce_value(key, raw) for key, raw in changes.items()}
    except ValueError as exc:
        raise RegisterError(422, getattr(exc, "detail_de", str(exc)), getattr(exc, "field_key", None))
    unknown_confirm = [key for key in confirm if key not in FIELDS]
    if unknown_confirm:
        raise RegisterError(422, f"Unbekannte Felder: {', '.join(unknown_confirm)}.")

    merged = {**_values(contract), **coerced}
    try:
        validate_pairs(merged)
    except ValueError as exc:
        raise RegisterError(422, getattr(exc, "detail_de", str(exc)), getattr(exc, "field_key", None))
    _validate_references(session, contract.organization_id, coerced)

    provenance = _provenance(session, contract.id)
    now = datetime.now(timezone.utc)
    diffs: dict[str, dict] = {}
    for key, value in coerced.items():
        before = getattr(contract, key)
        row = provenance.get(key)
        if _same(before, value):
            continue
        setattr(contract, key, value)
        diffs[key] = {"before": to_json(before), "after": to_json(value)}
        new_origin = "ai_corrected" if row is not None and row.origin in ("ai", "ai_confirmed", "ai_corrected") else "manual"
        if row is None:
            row = ContractFieldProvenance(
                organization_id=contract.organization_id,
                contract_id=contract.id,
                field_key=key,
                origin=new_origin,
            )
            session.add(row)
            provenance[key] = row
        row.origin = new_origin
        if row.ai_proposed_value and _same(row.ai_proposed_value.get("value"), value):
            row.ai_proposed_value = None
        row.updated_by_account_id = actor.account_id
        row.updated_by_name = actor.display_name

    for key in confirm:
        if key in diffs:
            continue
        row = provenance.get(key)
        if row is None or row.origin != "ai":
            continue
        row.origin = "ai_confirmed"
        row.confirmed_by_account_id = actor.account_id
        row.confirmed_by_name = actor.display_name
        row.confirmed_at = now
        diffs[key] = {"confirmed": True, "value": to_json(getattr(contract, key))}

    if diffs:
        ensure_register_number(session, contract, actor.account_id)
        log_activity(session, actor, contract.id, "contract.register_updated", {"fields": diffs})
    session.flush()
    if diffs:
        from app.finance.service import refresh_maintained_cost

        refresh_maintained_cost(session, contract)
    return diffs


def accept_ai_proposal(session: Session, *, contract: Contract, actor: RegisterActor, field_key: str) -> dict:
    row = _provenance(session, contract.id).get(field_key)
    if row is None or not row.ai_proposed_value:
        raise RegisterError(404, "Kein KI-Vorschlag für dieses Feld.", field_key)
    value = row.ai_proposed_value.get("value")
    diffs = update_register(session, contract=contract, actor=actor, changes={field_key: value}, confirm=[])
    row.origin = "ai_confirmed"
    row.ai_proposed_value = None
    row.confirmed_by_account_id = actor.account_id
    row.confirmed_by_name = actor.display_name
    row.confirmed_at = datetime.now(timezone.utc)
    session.flush()
    return diffs


def create_manual_contract(
    session: Session,
    *,
    actor: RegisterActor,
    values: dict[str, Any],
    hospital_id: Optional[uuid.UUID],
    department_id: Optional[uuid.UUID] = None,
) -> Contract:
    """Vertrag ohne Dokument anlegen; Abteilungsnutzer werden verantwortliche Abteilung."""
    contract = Contract(
        organization_id=actor.organization_id,
        hospital_id=hospital_id,
        responsible_account_id=actor.account_id,
        business_status="in_arbeit",
        scope_type="department" if department_id else ("hospital" if hospital_id else "organization"),
    )
    session.add(contract)
    session.flush()
    if department_id is not None:
        session.add(
            ContractDepartment(
                organization_id=actor.organization_id,
                contract_id=contract.id,
                department_id=department_id,
                relation_role="responsible",
            )
        )
    if hospital_id is not None:
        session.add(
            ContractHospital(
                organization_id=actor.organization_id, contract_id=contract.id, hospital_id=hospital_id, is_primary=True
            )
        )
    ensure_register_number(session, contract, actor.account_id)
    if values:
        update_register(session, contract=contract, actor=actor, changes=values, confirm=[])
    log_activity(session, actor, contract.id, "contract.created_manual", {"register_number": contract.register_number})
    session.flush()
    return contract


def transition_status(
    session: Session,
    *,
    contract: Contract,
    actor: RegisterActor,
    target: str,
    effective_date: Optional[date],
    terminated_on: Optional[date],
    note: Optional[str],
    acknowledge_unreviewed: bool,
) -> None:
    values = {**_values(contract), "supplier": contract.supplier, "terminated_effective": contract.terminated_effective}
    try:
        plan = plan_transition(
            current=contract.business_status,
            target=target,
            role=actor.role,
            is_developer=actor.is_developer,
            values=values,
            effective_date=effective_date,
            terminated_on=terminated_on,
            review_pending=review_pending(session, contract),
            acknowledge_unreviewed=acknowledge_unreviewed,
        )
    except TransitionError as exc:
        raise RegisterError(exc.status_code, exc.detail_de, missing=exc.missing)
    previous = contract.business_status
    before = {key: to_json(getattr(contract, key)) for key in plan.updates}
    for key, value in plan.updates.items():
        setattr(contract, key, value)
    contract.business_status = plan.target
    log_activity(
        session,
        actor,
        contract.id,
        "contract.status_changed",
        {
            "from": previous,
            "to": plan.target,
            "note": note,
            "acknowledged_unreviewed": bool(acknowledge_unreviewed and previous == "in_arbeit"),
            "fields": {key: {"before": before[key], "after": to_json(value)} for key, value in plan.updates.items()},
        },
    )
    session.flush()


def add_remark(session: Session, *, contract: Contract, actor: RegisterActor, body: str) -> ContractRemark:
    text = (body or "").strip()
    if not text:
        raise RegisterError(422, "Die Bemerkung ist leer.")
    if len(text) > 10000:
        raise RegisterError(422, "Die Bemerkung ist zu lang (max. 10.000 Zeichen).")
    remark = ContractRemark(
        organization_id=contract.organization_id,
        contract_id=contract.id,
        account_id=actor.account_id,
        author_name=actor.display_name,
        body=text,
    )
    session.add(remark)
    session.flush()
    log_activity(session, actor, contract.id, "contract.remark_added", {"remark_id": str(remark.id)})
    return remark


def list_remarks(session: Session, contract_id: uuid.UUID) -> list[dict]:
    rows = session.scalars(
        select(ContractRemark)
        .where(ContractRemark.contract_id == contract_id)
        .order_by(ContractRemark.created_at.desc(), ContractRemark.id.desc())
    ).all()
    return [
        {
            "id": str(row.id),
            "author_name": row.author_name,
            "body": row.body,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def contract_hospitals(session: Session, contract_id: uuid.UUID) -> list[dict]:
    rows = session.execute(
        select(ContractHospital, Hospital)
        .join(Hospital, Hospital.id == ContractHospital.hospital_id)
        .where(ContractHospital.contract_id == contract_id)
        .order_by(ContractHospital.is_primary.desc(), Hospital.name)
    ).all()
    return [
        {"hospital_id": str(link.hospital_id), "name": hospital.name, "code": hospital.code, "is_primary": link.is_primary}
        for link, hospital in rows
    ]


def set_contract_hospitals(
    session: Session,
    *,
    contract: Contract,
    actor: RegisterActor,
    hospital_ids: list[uuid.UUID],
    primary_hospital_id: Optional[uuid.UUID],
) -> None:
    """D3: Vertrag mehreren Gesellschaften zuordnen; die Hauptgesellschaft
    bleibt `contract.hospital_id` (Abteilungen/Kostenstellen haengen daran)."""
    wanted = list(dict.fromkeys(hospital_ids))
    if primary_hospital_id is not None and primary_hospital_id not in wanted:
        wanted.insert(0, primary_hospital_id)
    for hospital_id in wanted:
        hospital = session.get(Hospital, hospital_id)
        if hospital is None or hospital.organization_id != contract.organization_id:
            raise RegisterError(422, "Krankenhaus ist nicht verfügbar.")
    primary = primary_hospital_id or (wanted[0] if wanted else None)
    if contract.hospital_id is not None and contract.hospital_id != primary:
        has_departments = session.scalar(
            select(func.count(ContractDepartment.id)).where(ContractDepartment.contract_id == contract.id)
        )
        if has_departments:
            raise RegisterError(
                409,
                "Die Hauptgesellschaft kann nicht gewechselt werden, solange Abteilungen zugeordnet sind.",
            )
    existing = {
        row.hospital_id: row
        for row in session.scalars(select(ContractHospital).where(ContractHospital.contract_id == contract.id)).all()
    }
    before = sorted(str(value) for value in existing)
    for hospital_id, row in existing.items():
        if hospital_id not in wanted:
            session.delete(row)
    for hospital_id in wanted:
        row = existing.get(hospital_id)
        if row is None:
            row = ContractHospital(
                organization_id=contract.organization_id, contract_id=contract.id, hospital_id=hospital_id
            )
            session.add(row)
        row.is_primary = hospital_id == primary
    contract.hospital_id = primary
    log_activity(
        session,
        actor,
        contract.id,
        "contract.hospitals_updated",
        {"before": before, "after": sorted(str(value) for value in wanted), "primary": str(primary) if primary else None},
    )
    session.flush()
