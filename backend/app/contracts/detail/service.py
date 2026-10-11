"""STEP 14 – Contract-Detail-Read-Model (READ-ONLY, org-gebunden, deterministisch).

Baut die Detail-Ansicht eines Vertrags aus den AKZEPTIERTEN Laeufen:
- akzeptierte Extraktion (identity/scope/sla + Evidence-Provenienz),
- akzeptierte STEP-9-Berechnung (Dates/Costs, Status, Konflikte),
- STEP-11-Current-Warnungen (NICHT neu berechnet – GET rechnet nichts),
- akzeptiertes Equipment + verknuepfte Dokumente (sicher).

Kein N+1: gebundene Queries (Vertrag, akzeptierter Extraction+Evidence,
akzeptierte Berechnung, aktive Warnungen, Equipment, Dokument-/Version-/File-Map).
Generische 404 bei fehlend/nicht-org-gebunden; keine Warn-Neuberechnung.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import today_local
from app.contracts.calculation.costs import collect_price_development, derive_tax_breakdown
from app.contracts.calculation.models import (
    CalculationStatus,
    ContractCalculationResult,
    MoneyFieldResult,
    TaxBasis,
)
from app.contracts.detail.models import EvidenceBbox
from app.contracts.detail.recovery import (
    fix_text,
    load_canonical_pages,
    recover_financial_facts,
)
from app.work_queue.derive import task_items_only
from app.contracts.overrides.keys import (
    OVERRIDE_KEY_EVENT_START,
    OVERRIDE_KEY_TAX_BASIS,
    OVERRIDE_KEY_TAX_RATE_PERCENT,
)
from app.contracts.overrides.service import (
    audit_history,
    confirmed_fact_refs,
    effective_overrides,
)
from app.contracts.review.material import fact_label
from app.database.models import (
    CalculationRun,
    Contract,
    ContractDocument,
    ContractEquipment,
    ContractExtraction,
    ContractWarning,
    DocumentFile,
    DocumentVersion,
    ExtractionEvidence,
    Organization,
    WarningEvaluationRun,
    WorkItem,
)


class DetailError(Exception):
    detail_de = "Vertrag konnte nicht geladen werden."


# Deutsche Bezeichner der Vertragstypen (nur fuer die generische Titel-Ableitung).
_CONTRACT_TYPE_LABELS = {
    "maintenance": "Wartung / Service",
    "service": "Service-Vertrag",
    "full_service": "Full-Service-Vertrag",
    "rental": "Miete / Leasing",
    "software": "Software-Wartung",
    "delivery": "Liefervertrag",
    "sla": "Service-Level-Vereinbarung",
    "leasing": "Leasing-Vertrag",
}

# Generische Status-Woerter, die KEINE Ereignis-Regel bilden (z. B. ein
# Formular-"erforderlich"). Nur benennbare Ereignisse ("Übergabedatum") gelten
# als Bedingung und werden in der UI als "Ereignisbasiert" gezeigt.
_NON_EVENT_CONDITIONS = {
    "erforderlich", "required", "present", "gegeben", "angegeben", "vorgegeben",
    "angenommen", "nein", "ja", "none", "true", "false", "sowie", "bis",
}


def _is_event_rule(value):
    """True, wenn eine Formularbedingung eine benennbare Ereignis-Regel ist."""
    if not value:
        return False
    t = " ".join(str(value).split()).strip().lower()
    if not t:
        return False
    if t in _NON_EVENT_CONDITIONS:
        return False
    if any(ch.isdigit() for ch in t):
        return False
    return len(t) >= 3 and all(ch.isalpha() or ch in " -" for ch in t)


# UAT Re-Test (Defect 4): deutsche Bezeichner fuer wirksame Overrides/Fakten –
# damit im Review/Override-UI keine rohen internen Keys (z. B. `costs.
# monthly_cost` oder `dates.start_date`) erscheinen. Ohne Registry-Eintrag
# greift ein deterministischer Humanizer (kein roher Key).
_OVERRIDE_KEY_LABELS = {
    OVERRIDE_KEY_EVENT_START: "Vertragsbeginn (Ereignisdatum)",
    OVERRIDE_KEY_TAX_BASIS: "Steuerbasis",
    OVERRIDE_KEY_TAX_RATE_PERCENT: "Steuersatz (%)",
    "fact.confirm": "Fakt-Bestätigung",
    "cost.tax_basis": "Steuerbasis",
    "cost.tax_rate_percent": "Steuersatz (%)",
    "date.event_start": "Vertragsbeginn (Ereignisdatum)",
}


def _humanize_key(key: str) -> str:
    """Ersetzt interne Keys/pfade durch eine verstaendliche Anzeige (kein roher Key)."""
    text = str(key or "").strip()
    if not text:
        return ""
    for ch in (".", "_", "-"):
        text = text.replace(ch, " ")
    text = " ".join(text.split()).strip()
    return text[:1].upper() + text[1:]


def _fact_label_de(key: str) -> str:
    """Deutsche Bezeichnung eines Fakt-/Override-Keys fuer Anzeige-Zwecke."""
    label = fact_label(key)
    if label and label != key:
        return label
    return _OVERRIDE_KEY_LABELS.get(key) or _humanize_key(key)


def _build_contract_title(snapshot, recovered_identity, contract, equipment):
    """Leitet den anzeigenen Vertragstitel deterministisch ab (keine Erfindung).

    Bevorzugt die wörtliche Dokument-Überschrift, dann den expliziten KI-Titel,
    dann Typ + Gerät/System, dann Lieferant + Typ, dann sicherer Fallback.
    """
    explicit = None
    if recovered_identity is not None and recovered_identity.title:
        explicit = recovered_identity.title
    if explicit is None:
        explicit = _snap(snapshot, "identity", "contract_title")
    if explicit:
        return explicit
    type_label = _CONTRACT_TYPE_LABELS.get(_snap(snapshot, "identity", "contract_type"))
    device = None
    # UAT Re-Test (Defect 3): die im Dokument genannte SYSTEM-Identitaet ist
    # der vertragsprimäre Geräte-Fallback (vor einzelnen Komponenten-Zeilen).
    if recovered_identity is not None and recovered_identity.system_identity:
        device = recovered_identity.system_identity
    if device is None:
        for eq in equipment:
            candidate = (eq.system_name or eq.device_name or "") if hasattr(eq, "system_name") else (getattr(eq, "device_name", "") or "")
            if candidate:
                device = candidate
                break
    if type_label and device:
        return f"{type_label} – {device}"
    supplier = contract.supplier or _snap(snapshot, "identity", "supplier")
    if supplier and type_label:
        return f"{supplier} – {type_label}"
    if device:
        return device
    fallback = contract.contract_number or None
    return fallback or "Vertrag"


# ---------------------------------------------------------------------------
# Seiten-Index fuer deterministische Evidence-Seiten-Aufloesung (read-time).
# Persistierte `ExtractionEvidence.page` ist manchmal None (z. B. Equipment),
# obwohl der Snippet im kanonischen Seiten-Text steht. Wir suchen den Snippet
# deterministisch (keine KI) und tragen die Seite NUR ein, wenn gefunden.
# ---------------------------------------------------------------------------

def _match_text(value):
    if not value:
        return ""
    t = " ".join(str(value).split()).lower()
    t = t.replace("-", " ")
    for ch in ("\ufffd", "\u00ae", "\u2122", "\u00a0", "·", "•"):
        t = t.replace(ch, "")
    return t


def _build_page_index(pages):
    index = []
    for pg in pages or []:
        parts = [str(pg.get("text") or "")]
        for tbl in pg.get("tables") or []:
            for cell in (tbl.get("cells") or []):
                if isinstance(cell, dict):
                    parts.append(str(cell.get("text") or ""))
        for el in pg.get("elements") or []:
            if isinstance(el, dict):
                parts.append(str(el.get("text") or ""))
        corpus = " | ".join(parts)
        index.append((int(pg["page"]), _match_text(corpus)))
    return index


def _resolve_evidence_page(page_index, *, page_hint, snippet):
    if page_hint is not None:
        return page_hint
    core = _match_text(snippet)
    if len(core) < 16:
        return None
    for page_no, norm in page_index:
        if core in norm:
            return page_no
    probe = core[:80]
    if len(probe) >= 16:
        for page_no, norm in page_index:
            if probe in norm:
                return page_no
    return None


def _find_supplier_ref(pages, supplier):
    """Findet die Lieferanten-Fundstelle (Seite + Region + Snippet) auf der
    ersten Seite – deterministisch, keine Erfindung."""
    if not supplier:
        return None
    needle = _match_text(supplier)
    if len(needle) < 3:
        return None
    for pg in pages:
        if int(pg.get("page", 0)) != 1:
            continue
        for el in pg.get("elements") or []:
            if not isinstance(el, dict):
                continue
            t = _match_text(el.get("text") or "")
            if needle in t:
                return {
                    "page": pg["page"],
                    "region": _region_from(el),
                    "snippet": " ".join(str(el.get("text") or "").split())[:300],
                }
    return None


def _region_from(el):
    reg = el.get("region") if isinstance(el, dict) else None
    if isinstance(reg, dict) and all(reg.get(k) is not None for k in ("x0", "y0", "x1", "y1")):
        try:
            return {"x0": float(reg["x0"]), "y0": float(reg["y0"]),
                    "x1": float(reg["x1"]), "y1": float(reg["y1"])}
        except (TypeError, ValueError):
            return None
    return None


_WARNING_TITLES = {
    "contract_end_approaching": "Vertragsende nähert sich",
    "contract_expired": "Vertrag ausgelaufen",
    "cancellation_deadline_approaching": "Kündigungsfrist nähert sich",
    "cancellation_deadline_today": "Kündigungsfrist heute",
    "cancellation_deadline_passed": "Kündigungsfrist verstrichen",
    "automatic_renewal_attention": "Automatische Verlängerung beachten",
    "unclear_contract_data": "Vertragsdaten unklar",
    "calculation_conflict": "Berechnungskonflikt",
    "manual_review_required": "Manuelle Prüfung erforderlich",
    "missing_cost_data": "Fehlende verlässliche Kostenangabe",
    "cost_conflict": "Widersprüchliche Kostenangaben",
    "currency_conflict": "Mehrere Währungen",
}


def _snapshot_uses_harness(snapshot: dict | None) -> bool:
    """Return whether the accepted snapshot came from any Harness generation."""
    analysis = (snapshot or {}).get("analysis") or {}
    return bool(analysis.get("harness_version"))


def register_facts(contract, as_of: date) -> dict:
    """Fristen und gepflegte Kosten aus dem Vertragsregister (Vorrang vor KI-Werten im Kopf)."""
    from app.register.service import term_inputs
    from app.register.terms import compute_terms

    terms = compute_terms(term_inputs(contract), as_of)
    end = terms.actual_end or terms.possible_end
    return {
        "contract_start": contract.term_start_date.isoformat() if contract.term_start_date else None,
        # Vertragsart: bei fester Laufzeit endet der Vertrag ohne Kündigung (kein „Kündbar bis“).
        "term_model": contract.term_model,
        "cancel_by": terms.cancel_by.isoformat() if terms.cancel_by else None,
        "contract_end": end.isoformat() if end else None,
        "annual_cost": (
            {"amount": str(contract.maintained_annual_cost), "currency": contract.maintained_annual_currency or "EUR"}
            if contract.maintained_annual_cost is not None else None
        ),
    }


def build_contract_detail(
    session: Session, *, organization_id, contract_id
):
    contract = session.scalars(
        select(Contract).where(
            (Contract.id == contract_id)
            & (Contract.organization_id == organization_id)
            & (Contract.lifecycle_state == "active")
        )
    ).first()
    if contract is None:
        return None

    ext = None
    if contract.accepted_extraction_id is not None:
        ext = session.get(ContractExtraction, contract.accepted_extraction_id)
    calc_run = None
    if contract.accepted_calculation_run_id is not None:
        calc_run = session.get(CalculationRun, contract.accepted_calculation_run_id)

    calc = None
    if calc_run is not None and calc_run.result_snapshot:
        try:
            calc = ContractCalculationResult.model_validate(calc_run.result_snapshot)
        except Exception:
            calc = None

    evidences = []
    if ext is not None:
        evidences = session.scalars(
            select(ExtractionEvidence).where(
                (ExtractionEvidence.organization_id == organization_id)
                & (ExtractionEvidence.extraction_id == ext.id)
            )
        ).all()

    warnings = session.scalars(
        select(ContractWarning).where(
            (ContractWarning.organization_id == organization_id)
            & (ContractWarning.contract_id == contract.id)
            & (ContractWarning.active.is_(True))
        )
    ).all()

    equipment = session.scalars(
        select(ContractEquipment).where(
            (ContractEquipment.organization_id == organization_id)
            & (ContractEquipment.contract_id == contract.id)
            & (ContractEquipment.extraction_id == contract.accepted_extraction_id)
        )
    ).all()

    work_items = session.scalars(
        select(WorkItem).where(
            (WorkItem.organization_id == organization_id)
            & (WorkItem.contract_id == contract.id)
            & (WorkItem.active.is_(True))
            & task_items_only(WorkItem.item_type)
        )
    ).all()

    docs, version_to_file = _load_documents(session, organization_id, contract.id)

    # Akzeptierte Extraktion -> Version -> File (fuer Evidence-Anzeige + Viewer).
    if ext is not None and ext.document_version_id not in version_to_file:
        ver = session.get(DocumentVersion, ext.document_version_id)
        if ver is not None:
            f = session.get(DocumentFile, ver.document_file_id)
            if f is not None:
                version_to_file[ext.document_version_id] = {
                    "id": ver.id,
                    "original_filename": f.original_filename,
                    "mime_type": f.mime_type,
                    "file_extension": f.file_extension,
                }

    snapshot = ext.contract_snapshot if ext else None
    org_slug = _org_slug(session, organization_id)
    evidence_version_id = ext.document_version_id if ext else None
    evidence_texts = [e.source_text for e in evidences if e.source_text]

    evidence_by_ref = {e.field_ref: e for e in evidences if e.field_ref}

    # UAT Defect Batch A: wirksame manuelle Overrides + Audit-Historie.
    ov_effective = effective_overrides(
        session, organization_id=organization_id, contract_id=contract.id
    )
    ov_audit = audit_history(
        session, organization_id=organization_id, contract_id=contract.id
    )
    confirmed_refs = confirmed_fact_refs(
        session, organization_id=organization_id, contract_id=contract.id
    )

    # UAT Re-Test: Wiederherstellung vertraglich direkt belegter Fakten aus dem
    # PERSISTIERTEN kanonischen Dokumenttext der akzeptierten Verarbeitung
    # (keine neue OCR/LLM-Ingestion, keine erfundenen Werte). Bei jedem Fehler
    # faellt das Read-Model in den gewohnten Evidence-First-Pfad zurueck.
    recovered = None
    pages = []
    if ext is not None and ext.document_version_id is not None:
        pages = load_canonical_pages(
            session,
            organization_id=organization_id,
            document_version_id=ext.document_version_id,
        )
        if pages and not _snapshot_uses_harness(snapshot):
            recovered = recover_financial_facts(pages)

    recovered_laufzeit = recovered.laufzeit if recovered is not None else None
    recovered_money = recovered.money if recovered is not None else None
    recovered_identity = recovered.identity if recovered is not None else None

    # Deterministische Evidence-Seiten-Aufloesung (read-time, kein LLM): fuer
    # Evidence-Zeilen ohne persistierte Seite suchen wir den Snippet im
    # kanonischen Seiten-Text (Seiten-Ebene, keine erfundene Geometrie).
    page_index = _build_page_index(pages)
    evidence_page = {
        e.id: _resolve_evidence_page(
            page_index, page_hint=e.page, snippet=e.source_text
        )
        for e in evidences
    }

    # UAT Re-Test (ABIOMED 40015645): kanonische Identitaet (Vertragsnummer +
    # Überschrift) deterministisch aus dem persistierten Dokumenttext, wenn die
    # strukturierte Extraktion sie nicht trug. Die Vertragsnummer ist damit auch
    # im Detail sichtbar + belegt; Search bleibt ein Backfill (Script, gezielt).
    recovered_number = (
        recovered_identity.contract_number
        if recovered_identity is not None
        else None
    )
    contract_number = recovered_number or contract.contract_number
    contract_title = _build_contract_title(
        snapshot, recovered_identity, contract, equipment
    )
    supplier_ref = _find_supplier_ref(pages, contract.supplier)

    equipment_items = []
    for eq in equipment:
        eq_evidence = evidence_by_ref.get(eq.field_ref)
        equipment_items.append(
            _equipment_item(
                eq,
                eq_evidence,
                resolved_page=(
                    evidence_page.get(eq_evidence.id)
                    if eq_evidence is not None
                    else None
                ),
            )
        )

    scope, scope_evidence_refs = _scope_section(
        snapshot,
        pages=[] if _snapshot_uses_harness(snapshot) else pages,
        version_to_file=version_to_file,
        document_version_id=ext.document_version_id if ext else None,
    )

    return {
        "organization_slug": org_slug,
        "contract_id": contract.id,
        "is_archived": bool(contract.is_archived),
        "archived_at": (
            contract.archived_at.isoformat() if contract.archived_at is not None else None
        ),
        "contract_number": contract_number,
        "contract_title": contract.short_description or contract_title,
        "supplier": contract.supplier,
        "register_number": contract.register_number,
        "business_status": contract.business_status,
        "register_facts": register_facts(contract, today_local()),
        "extracted_terms": _extracted_terms(snapshot),
        "assignment": _assignment(session, contract),
        "sections": _sections(session, contract),
        "partner": _partner(session, contract),
        "risk": _risk(contract),
        "status": contract.status,
        "risk_level": contract.risk_level,
        "identity": _identity_section(
            snapshot,
            contract_number=contract_number,
            recovered_identity=recovered_identity,
        ),
        "dates": _dates_section(
            calc, snapshot, ov_effective, confirmed_refs, recovered_laufzeit
        ),
        "costs": _costs_section(
            calc, snapshot, ov_effective, evidence_texts, recovered
        ),
        "scope": scope,
        "sla": _sla_section(snapshot),
        "equipment": equipment_items,
        "review": _review_section(session, organization_id, contract.id, warnings),
        "warnings": [_warning_item(w) for w in warnings],
        "work_items": [_work_item_item(w) for w in work_items],
        "documents": docs,
        "evidence": _dedupe_evidence(
            _settle_canonical_evidence(
                [
                    _evidence_ref(
                        e, version_to_file, evidence_version_id,
                        resolved_page=evidence_page.get(e.id),
                    )
                    for e in evidences
                ]
                + _recovered_evidence_refs(
                    recovered,
                    version_to_file,
                    ext.document_version_id if ext else None,
                    supplier=contract.supplier,
                    supplier_ref=supplier_ref,
                )
                + scope_evidence_refs
            )
        ),
        "overrides": [
            {
                "key": key,
                "value": ov.get("value"),
                "note": ov.get("note"),
                "created_at": (
                    ov["created_at"].isoformat()
                    if ov.get("created_at") is not None
                    else None
                ),
                "is_development": bool(ov.get("is_development")),
                # UAT Re-Test (Defect 4): deutsche Bezeichnung, kein roher Key.
                "label_de": _fact_label_de(key),
            }
            for key, ov in ov_effective.items()
        ],
        "audit_log": [
            {**entry, "label_de": _fact_label_de(entry.get("key") or "")}
            for entry in ov_audit
        ],
    }


# ---------------------------------------------------------------------------
# Snapshot-Helfer
# ---------------------------------------------------------------------------

def _risk(contract) -> dict:
    from app.contracts.risk import risk_payload

    return risk_payload(contract)


def _partner(session: Session, contract) -> dict | None:
    """Zugeordneter Vertragspartner aus den Stammdaten (zum Oeffnen und Bearbeiten im Kopf)."""
    if contract.partner_id is None:
        return None
    from app.database.models.register import ContractPartner

    partner = session.get(ContractPartner, contract.partner_id)
    if partner is None or partner.organization_id != contract.organization_id:
        return None
    return {"id": str(partner.id), "name": partner.name1, "short_name": partner.short_name}


def _sections(session: Session, contract) -> Optional[dict]:
    """Typspezifische Abschnitte (register/sections.py); None ohne Vertragstyp = alle zeigen."""
    from app.database.models.register import CatalogContractType
    from app.register.sections import contract_sections

    kind = session.get(CatalogContractType, contract.contract_type_id) if contract.contract_type_id else None
    if kind is not None and kind.organization_id != contract.organization_id:
        kind = None
    return contract_sections(kind)


def _assignment(session: Session, contract) -> dict:
    """Organisationszuordnung zum Lesen (Uebersicht): Namen statt Kennungen, fuer alle Rollen."""
    from app.database.models import Account, ContractDepartment, CostCenter, Department, Hospital
    from app.database.models.register import CatalogContractCategory, CatalogContractType
    from app.ownership.service import further_responsible_ids

    hospital = session.get(Hospital, contract.hospital_id) if contract.hospital_id else None
    links = session.execute(
        select(ContractDepartment.relation_role, Department.name)
        .join(Department, Department.id == ContractDepartment.department_id)
        .where(ContractDepartment.contract_id == contract.id)
        .order_by(Department.name)
    ).all()
    center = session.get(CostCenter, contract.cost_center_id) if contract.cost_center_id else None
    further = further_responsible_ids(session, contract.id)
    people = [value for value in (contract.responsible_account_id, *further) if value]
    names = dict(session.execute(select(Account.id, Account.display_name).where(Account.id.in_(people))).all()) if people else {}
    kind = session.get(CatalogContractType, contract.contract_type_id) if contract.contract_type_id else None
    category = session.get(CatalogContractCategory, contract.contract_category_id) if contract.contract_category_id else None
    return {
        "contract_type": kind.label if kind and kind.organization_id == contract.organization_id else None,
        "contract_category": category.label if category and category.organization_id == contract.organization_id else None,
        "hospital": hospital.name if hospital else None,
        "responsible_department": next((name for role, name in links if role == "responsible"), None),
        "beneficiary_departments": [name for role, name in links if role == "beneficiary"],
        # Historische Zuordnungen ohne Rolle: nicht als verantwortlich/nutzend ausgeben, aber zeigen.
        "other_departments": [name for role, name in links if role is None],
        "cost_center": {"code": center.code, "name": center.name} if center else None,
        "responsible": names.get(contract.responsible_account_id) if contract.responsible_account_id else None,
        "further_responsible": [names[value] for value in further if value in names],
    }


def _extracted_terms(snapshot) -> dict:
    """Angaben zu Laufzeit und Kuendigung aus der Extraktion (deutsche Anzeige) fuer die Pruefung."""
    if not snapshot:
        return {}
    from app.models.contract import Contract as ExtractedContract
    from app.reextract import facts

    try:
        model = ExtractedContract.model_validate(snapshot)
    except Exception:
        return {}
    return {path: facts.display(facts.get_fact(model, path)) for path in facts.REVIEW_TERM_FACTS}


def _snap(snapshot, *keys):
    if not snapshot:
        return None
    node = snapshot
    for k in keys:
        if not isinstance(node, dict):
            return None
        node = node.get(k)
    return node


def _snap_bool(snapshot, *keys):
    raw = _snap(snapshot, *keys)
    if raw is True:
        return True
    if raw is False:
        return False
    if isinstance(raw, str):
        return True if raw.lower() == "true" else False if raw.lower() == "false" else None
    return None


def _identity_section(snapshot, contract_number=None, recovered_identity=None):
    identity = snapshot.get("identity") if snapshot else None
    if not isinstance(identity, dict):
        identity = {}
    keys = [
        "contract_number", "contract_type", "contractor", "customer",
        "contact_person", "service_email", "service_phone",
        "customer_number", "department", "location",
    ]
    out = {k: identity.get(k) for k in keys if identity.get(k) is not None}
    # UAT Re-Test: wiederhergestellte kanonische Vertragsnummer (wenn die
    # strukturierte Extraktion sie nicht trug) – deterministisch belegt.
    if not out.get("contract_number") and contract_number:
        out["contract_number"] = contract_number
    # UAT Re-Test (Defect 3): vertragsprimäre SYSTEM-Identitaet aus der
    # Betreff-Zeile (z. B. "Impella AIC System") – deterministisch belegt.
    if recovered_identity is not None and recovered_identity.system_identity:
        out["system_identity"] = recovered_identity.system_identity
        if recovered_identity.system_identity_page is not None:
            out["system_identity_page"] = recovered_identity.system_identity_page
    return out


def _dates_section(calc, snapshot, ov_effective=None, confirmed_refs=None, recovered_laufzeit=None):
    dates = {
        "automatic_renewal": _snap_bool(snapshot, "termination", "automatic_renewal"),
    }
    start = _snap(snapshot, "dates", "start_date", "date")
    start_cond = _snap(snapshot, "dates", "start_date", "condition")
    start_requires_review = _snap(snapshot, "dates", "start_date", "requires_review")
    start_condition_field = _snap(snapshot, "dates", "start_condition")

    # Nur benennbare Ereignis-Regeln gelten als Bedingung – generische
    # Status-Woerter (z. B. Formular-"erforderlich") sind KEINE Ereignisse.
    event_rule = None
    for candidate in (start_cond, start_condition_field):
        if _is_event_rule(candidate):
            event_rule = candidate
            break

    recovered_start = recovered_laufzeit.absolute_start if recovered_laufzeit else None
    if recovered_start is not None:
        dates["start_date"] = recovered_start.isoformat()
        dates["start_date_evidence"] = "dates.start_date"
    elif start is not None:
        dates["start_date"] = start

    # Vertragsbeginn-Status: was ist der Status des angezeigten Termins?
    # documented  -> wörtlich im Vertrag belegt (deterministisch wiederhergestellt)
    # explicit    -> aus der strukturierten Extraktion (KI) übernommen
    # provisional -> Extraktion nicht eindeutig (requires_review)
    # event_based -> Ereignis-Regel, kein absoluter Termin
    # needs_review-> absoluter Termin UND Ereignis-Bedingung vorhanden
    # overridden  -> manuell aufgelöst (wirksames tatsächliches Datum)
    if recovered_start is not None and event_rule:
        dates["start_date_status"] = "needs_review"
        dates["start_condition"] = event_rule
    elif event_rule:
        dates["start_condition"] = event_rule
        if start is None:
            dates["start_date_status"] = "event_based"
        else:
            dates["start_date_status"] = "needs_review"
    elif recovered_start is not None:
        dates["start_date_status"] = "documented"
    elif start is not None:
        dates["start_date_status"] = "provisional" if start_requires_review else "explicit"

    # UAT Re-Test: Zahlungsbeginn + Mindestvertragslaufzeit aus dem persistierten
    # Dokumenttext (ereignisbasiert, kein erfundener Termin).
    if recovered_laufzeit is not None:
        if recovered_laufzeit.start_event:
            current_cond = event_rule
            if not current_cond:
                dates["start_condition"] = recovered_laufzeit.start_event
                if dates.get("start_date") is None:
                    dates["start_date_status"] = "event_based"
        if recovered_laufzeit.payment_start_rule:
            dates["payment_start_rule"] = recovered_laufzeit.payment_start_rule
            dates["payment_start_status"] = "condition_based"
            dates["payment_start_evidence"] = "payment.payment_start"
        if recovered_laufzeit.minimum_duration_months:
            dates["minimum_duration_months"] = recovered_laufzeit.minimum_duration_months
            dates["minimum_duration_evidence"] = "dates.minimum_duration"
        # Absolut dokumentiertes Ende + Laufzeit + automatische Verlaengerung.
        if recovered_laufzeit.absolute_end is not None:
            dates["documented_end_date"] = recovered_laufzeit.absolute_end.isoformat()
            dates["documented_end_evidence"] = "dates.end_date"
        if recovered_laufzeit.duration_years:
            dates["duration_years"] = recovered_laufzeit.duration_years
            dates["duration_evidence"] = "dates.duration"
        # Automatische Verlaengerung: die wörtlich dokumentierte Klausel ist
        # maßgeblich. Weicht die Extraktion davon ab (z. B. Extrak "Ja", Text
        # "wird nicht automatisch verlängert"), zaehlt der dokumentierte Wert –
        # so passt der angezeigte Wert zur belegten Quell-Seite (Defect 1/2).
        if recovered_laufzeit.auto_renewal is not None:
            if (
                dates.get("automatic_renewal") is None
                or dates["automatic_renewal"] != recovered_laufzeit.auto_renewal
            ):
                dates["automatic_renewal"] = recovered_laufzeit.auto_renewal
            dates["auto_renewal_evidence"] = "termination.auto_renewal"
    # UAT Defect Batch A: manuell aufgelöstes (tatsächliches) Ereignis-Datum.
    if ov_effective:
        ev = (ov_effective.get(OVERRIDE_KEY_EVENT_START) or {}).get("value")
        if isinstance(ev, dict) and ev.get("date"):
            dates["overridden_start_date"] = ev["date"]
            dates["start_date_status"] = "overridden"
        elif isinstance(ev, str) and ev:
            dates["overridden_start_date"] = ev
            dates["start_date_status"] = "overridden"
    if calc is not None:
        d = calc.dates
        if getattr(d.calculated_end_date, "value", None) is not None:
            dates["calculated_end_date"] = d.calculated_end_date.value
            dates["calculated_end_status"] = d.calculated_end_date.status.value
        dates["calculated_end_basis"] = {
            "explanation": d.calculated_end_date.explanation or None,
            "inputs": dict(d.calculated_end_date.inputs or {}),
        }
        if getattr(d.latest_cancellation_date, "value", None) is not None:
            dates["latest_cancellation_date"] = d.latest_cancellation_date.value
            dates["latest_cancellation_status"] = d.latest_cancellation_date.status.value
        dates["latest_cancellation_basis"] = {
            "explanation": d.latest_cancellation_date.explanation or None,
            "inputs": dict(d.latest_cancellation_date.inputs or {}),
        }
        if getattr(d.next_renewal_date, "value", None) is not None:
            dates["next_renewal_date"] = d.next_renewal_date.value
            dates["next_renewal_status"] = d.next_renewal_date.status.value
        dates["next_renewal_basis"] = {
            "explanation": d.next_renewal_date.explanation or None,
            "inputs": dict(d.next_renewal_date.inputs or {}),
        }
        dates["current_status"] = d.current_contract_status.status.value
        dates["current_status_explanation"] = d.current_contract_status.explanation
        if getattr(d.days_until_end, "value", None) is not None:
            dates["days_until_end"] = d.days_until_end.value
        if getattr(d.days_until_latest_cancellation, "value", None) is not None:
            dates["days_until_latest_cancellation"] = d.days_until_latest_cancellation.value
        dates["renewal_boundaries"] = [
            {
                "period_index": b.period_index,
                "start_date": b.start_date,
                "end_date": b.end_date,
                "kind": b.kind.value if b.kind else None,
                "explanation": b.explanation,
                "review_required": bool(b.review_required),
            }
            for b in d.renewal_boundaries
        ]
        dates["review_required"] = bool(
            getattr(d.calculated_end_date, "review_required", False)
            or getattr(d.latest_cancellation_date, "review_required", False)
            or getattr(d.next_renewal_date, "review_required", False)
        )
    return dates


def _money(field):
    if field is None:
        return {}
    value = getattr(field, "value", None)
    return {
        "amount": value,
        "currency": getattr(field, "currency", None),
        "status": getattr(field, "status", None).value if getattr(field, "status", None) else None,
        "explanation": getattr(field, "explanation", None) or None,
    }


_MONTHLY_SOURCE_KEYS = ("monthly_cost", "maintenance_fee", "monthly_fee")


def _resolve_monthly(monthly, annual):
    """Stellt den kanonischen Monatsbetrag evidence-getreu wieder her.

    Die akzeptierte (ggf. bereits gespeicherte) Berechnung kann
    `normalized_recurring.monthly` leer lassen, obwohl ein monatlicher Fakt in
    den Jahres-Eingaben liegt (z. B. `annual.inputs['monthly_cost']=5916.67`).
    Dann wird der Monatsbetrag NUR aus diesem belegten Eingabefeld übernommen
    (status=explicit) – es wird KEIN Jahreswert/12-Wert als „Monat" erfunden.
    """
    if monthly is not None and monthly.value is not None:
        return monthly
    if annual is None or annual.value is None:
        return monthly
    for key in _MONTHLY_SOURCE_KEYS:
        raw = (annual.inputs or {}).get(key)
        if raw is None:
            continue
        try:
            value = Decimal(str(raw).replace(",", ".").strip())
        except Exception:
            continue
        return MoneyFieldResult(
            value=value,
            status=CalculationStatus.EXPLICIT,
            currency=annual.currency,
            inputs={key: str(raw)},
            explanation=(
                f"{key} {raw} (monthly) => monatlich {value} "
                "(belegt aus den Jahres-Eingaben der akzeptierten Berechnung)."
            ),
        )
    return monthly


_VAT_NET_MARKERS = ("zzgl", "netto")
_VAT_GROSS_MARKERS = ("inkl", "brutto")
_VAT_KEYWORDS = ("ust", "mwst", "umsatzsteuer", "steuer")


def _collect_source_texts(node, out):
    """Sammelt Quell-Text-Fragmente (source_text/text) rekursiv aus dem
    akzeptierten Snapshot – deckt sowohl grupierte (costs/payment.evidence) als
    auch feldeingebettete Strukturen ab."""
    if isinstance(node, dict):
        for key, val in node.items():
            if key in ("source_text", "text") and isinstance(val, str) and val.strip():
                out.append(val)
            else:
                _collect_source_texts(val, out)
    elif isinstance(node, list):
        for item in node:
            _collect_source_texts(item, out)


def _infer_tax_basis(snapshot, extra_texts=None):
    """Leitet die Steuer-Basis deterministisch aus BELEGTEM Quellen-Text ab.

    Regeln (bewusst konservativ, keine Erfindung):
    - „netto"/„brutto" am Wort gelten eindeutig.
    - Abkürzungen „zzgl."./. „inkl." zaehlen NUR zusammen mit einem USt.-Begriff
      (USt., MwSt., Umsatzsteuer, Steuer) – so verursacht z. B. „inkl. Ersatzteile"
      KEINE falsche Brutto-Basis. Kein Steuersatz-Raten; keine 19-%-Annahme.
    """
    if not isinstance(snapshot, dict) and not extra_texts:
        return None
    texts: list[str] = []
    if isinstance(snapshot, dict):
        _collect_source_texts(snapshot, texts)
    if extra_texts:
        texts.extend(str(t) for t in extra_texts if t)
    blob = " ".join(texts).lower()
    vat_hits = any(kw in blob for kw in _VAT_KEYWORDS)
    for marker in _VAT_NET_MARKERS:
        if marker in blob:
            if marker == "netto" or vat_hits:
                return TaxBasis.NET
    for marker in _VAT_GROSS_MARKERS:
        if marker in blob:
            if marker == "brutto" or vat_hits:
                return TaxBasis.GROSS
    return None


def _costs_section(calc, snapshot=None, ov_effective=None, evidence_texts=None, recovered=None):
    empty = {
        "annual_recurring": {},
        "annual_recurring_basis": {"explanation": None, "inputs": {}},
        "source_period": None,
        "monthly_recurring": {},
        "total_contract_value": {},
        "total_contract_value_status": None,
        "currency_conflict": False,
        "tax_basis": None,
        "tax_rate_percent": None,
        "category_totals": [],
        "tax_breakdown": {
            "computed": False,
            "base_tax_basis": None,
            "rate_percent": None,
            "currency": None,
            "monthly_net": None,
            "monthly_gross": None,
            "annual_net": None,
            "annual_gross": None,
            "monthly_tax": None,
            "annual_tax": None,
            "explanation": None,
            "source": None,
            "evidence_field_refs": {},
        },
        "price_development": [],
        "notes": [],
        "scheduled_prices": [],
        "variable_charges": [],
    }
    if calc is None:
        return {**empty, "availability": _cost_availability(snapshot, evidence_texts, recovered)}
    costs = calc.costs
    snapshot_costs = (
        snapshot.get("costs") if isinstance(snapshot, dict) else None
    )
    ann = costs.normalized_recurring.annual
    monthly = _resolve_monthly(costs.normalized_recurring.monthly, ann)

    rec_m = recovered.money if recovered is not None else None

    # Auflösung von Steuerbasis + Steuersatz:
    # 1) manueller Override,  2) akzeptierter Calc,  3) deterministische
    # Evidence-Inferenz (z. B. „zzgl. ... Umsatzsteuer" => netto),
    # 4) UAT Re-Test: vertraglich direkt belegter Satz/Basis aus dem
    #    persistierten Dokumenttext (recovery).
    # Der Steuersatz wird NIE geraten (keine 19-%-Annahme ohne Fundstelle).
    base_tax = (
        TaxBasis(costs.tax_basis.value)
        if costs.tax_basis is not None
        else TaxBasis.UNKNOWN
    )
    if base_tax == TaxBasis.UNKNOWN:
        inferred = _infer_tax_basis(snapshot, evidence_texts)
        if inferred is not None:
            base_tax = inferred
    if base_tax == TaxBasis.UNKNOWN and rec_m is not None and rec_m.basis in ("net", "gross"):
        base_tax = TaxBasis(rec_m.basis)
    rate_percent = getattr(costs, "tax_rate_percent", None)
    if rate_percent is None and rec_m is not None and rec_m.vat_rate is not None:
        rate_percent = float(rec_m.vat_rate)
    currency = (
        ann.currency
        or (monthly.currency if monthly is not None else None)
        or getattr(costs, "default_currency", None)
        or costs.tax_breakdown.currency
    )
    if ov_effective:
        tb = (ov_effective.get(OVERRIDE_KEY_TAX_BASIS) or {}).get("value")
        tr = (ov_effective.get(OVERRIDE_KEY_TAX_RATE_PERCENT) or {}).get("value")
        if isinstance(tb, dict) and tb.get("value") in ("net", "gross"):
            base_tax = TaxBasis(tb["value"])
        elif isinstance(tb, str) and tb in ("net", "gross"):
            base_tax = TaxBasis(tb)
        if isinstance(tr, dict) and tr.get("percent") is not None:
            rate_percent = tr["percent"]
        elif isinstance(tr, (int, float, str)):
            try:
                rate_percent = float(tr)
            except (TypeError, ValueError):
                rate_percent = None

    # Nur net/gross gelten als benennbare Basis. Die Gegen-Basis (brutto bei
    # netto) bleibt offen, bis ein Steuersatz belegt/bestätigt ist.
    has_basis = base_tax in (TaxBasis.NET, TaxBasis.GROSS)
    tax_breakdown = derive_tax_breakdown(
        annual=ann.value,
        monthly=monthly.value if (monthly is not None and monthly.value is not None) else None,
        tax_basis=base_tax if has_basis else TaxBasis.UNKNOWN,
        tax_rate_percent=rate_percent,
        currency=currency,
        recovered_vat_rate=rec_m.vat_rate if rec_m is not None else None,
        recovered_monthly_vat=rec_m.monthly_vat if rec_m is not None else None,
        recovered_monthly_gross=rec_m.monthly_gross if rec_m is not None else None,
        recovered_monthly_net=rec_m.monthly_net if rec_m is not None else None,
    )

    _TAX_EVIDENCE_MAP = {
        "monthly_net": ("monthly_net", "costs.tax_table.net"),
        "annual_net": ("annual_net", "costs.tax_table.net"),
        "vat_rate": ("rate_percent", "costs.tax_table.vat"),
        "monthly_vat": ("monthly_tax", "costs.tax_table.vat"),
        "annual_vat": ("annual_tax", "costs.tax_table.vat"),
        "monthly_gross": ("monthly_gross", "costs.tax_table.gross"),
        "annual_gross": ("annual_gross", "costs.tax_table.gross"),
    }
    evidence_field_refs = {}
    if rec_m is not None:
        for name, (attr, ref) in _TAX_EVIDENCE_MAP.items():
            if getattr(tax_breakdown, attr) is not None:
                evidence_field_refs[name] = ref

    # UAT Defect Batch C: wenn zwar ein Jahresbetrag berechnet wurde, aber
    # KEIN verlässlicher Wert steht, erklären wir das ehrlich (nie Neu-Rechnen).
    availability = None
    if ann.value is None:
        availability = _cost_availability(
            snapshot, evidence_texts, recovered,
            total_contract_value=getattr(costs, "total_contract_value", None),
        )

    return {
        **empty,
        "annual_recurring": _money(ann),
        "annual_recurring_basis": {
            "explanation": getattr(ann, "explanation", None) or None,
            "inputs": dict(getattr(ann, "inputs", None) or {}),
        },
        "source_period": costs.normalized_recurring.source_period,
        "monthly_recurring": _money(monthly),
        "total_contract_value": _money(getattr(costs, "total_contract_value", None)),
        "total_contract_value_status": (
            costs.total_contract_value_status.value
            if costs.total_contract_value_status
            else None
        ),
        "currency_conflict": bool(costs.currency_conflict),
        "tax_basis": base_tax.value if base_tax is not None else None,
        "tax_rate_percent": rate_percent,
        "category_totals": [
            {
                "key": cat.key,
                "label": cat.label,
                "currency": cat.currency,
                "amount": cat.amount,
                "status": cat.status.value if cat.status else None,
                "explanation": cat.explanation,
                "inputs": list(cat.inputs or []),
            }
            for cat in costs.category_totals
        ],
        "tax_breakdown": {
            "computed": tax_breakdown.computed,
            "base_tax_basis": (
                tax_breakdown.base_tax_basis.value
                if tax_breakdown.base_tax_basis
                else None
            ),
            "rate_percent": tax_breakdown.rate_percent,
            "currency": tax_breakdown.currency,
            "monthly_net": tax_breakdown.monthly_net,
            "monthly_gross": tax_breakdown.monthly_gross,
            "annual_net": tax_breakdown.annual_net,
            "annual_gross": tax_breakdown.annual_gross,
            "monthly_tax": tax_breakdown.monthly_tax,
            "annual_tax": tax_breakdown.annual_tax,
            "explanation": tax_breakdown.explanation,
            "source": (
                f"Zahlen direkt aus der Vertragszusammenfassung übernommen "
                f"(Seite {rec_m.page})."
                if rec_m is not None and rec_m.page is not None
                else None
            ),
            "evidence_field_refs": evidence_field_refs,
        },
        "price_development": _price_development_items(costs, snapshot),
        "notes": list(costs.notes or []),
        "scheduled_prices": _price_schedule_items(snapshot_costs),
        "variable_charges": _variable_charge_items(snapshot_costs),
        "availability": availability,
    }


_VARIABLE_UNIT_LABELS = {
    "per_call": "pro Einsatz",
    "per_hour": "pro Stunde",
    "per_device": "pro Gerät",
}

_VARIABLE_CHARGE_NOTE = (
    "Bedingte / verbrauchsabhängige Position – wird nie zum Fixwert addiert "
    "und ist nicht im wiederkehrenden Jahresbetrag enthalten."
)


def _price_schedule_items(costs_dict: Optional[dict]) -> list[dict]:
    """Belegter Preisplan (Staffeljahre) als deterministische Anzeige-Liste."""
    items: list[dict] = []
    for entry in (costs_dict or {}).get("scheduled_prices") or []:
        if not isinstance(entry, dict):
            continue
        amount = entry.get("amount") or {}
        if amount.get("amount") is None:
            continue
        items.append({
            "period_index": entry.get("period_index"),
            "period_label": entry.get("period_label"),
            "amount": amount.get("amount"),
            "currency": amount.get("currency") or "EUR",
            "condition": entry.get("condition"),
        })
    items.sort(key=lambda i: (i["period_index"] is None, i["period_index"] or 0))
    return items


def _variable_charge_items(costs_dict: Optional[dict]) -> list[dict]:
    """Bedingte Positionen (z. B. „Fixed per call") ehrlich getrennt anzeigen."""
    items: list[dict] = []
    for entry in (costs_dict or {}).get("variable_charges") or []:
        if not isinstance(entry, dict):
            continue
        amount = entry.get("amount") or {}
        if amount.get("amount") is None:
            continue
        unit = entry.get("unit")
        items.append({
            "label": entry.get("label") or "Variable Position",
            "amount": amount.get("amount"),
            "currency": amount.get("currency") or "EUR",
            "unit": unit,
            "unit_label_de": _VARIABLE_UNIT_LABELS.get(unit, unit),
            "condition": entry.get("condition"),
            "note_de": _VARIABLE_CHARGE_NOTE,
        })
    return items


def _format_amount(amount, currency=None):
    try:
        s = f"{float(amount):,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        s = str(amount)
    return f"{s} {currency}".strip() if currency else s


def _cost_availability(snapshot, evidence_texts, recovered, total_contract_value=None):
    """Beschreibt ehrlich, welche Kosten-Informationen der Vertrag enthält und
    warum der Jahresbetrag nicht automatisch berechenbar ist (keine Erfindung)."""
    lines = recovered.cost_lines if recovered is not None else []
    found_facts = []
    tax_mentioned = False
    for i, line in enumerate(lines):
        label = line.label or f"Preiszeile {i + 1}"
        found_facts.append({
            "key": f"costs.cost_line.{i}",
            "label_de": label[:120],
            "value": _format_amount(line.amount, line.currency),
            "period_hint": None,
            "page": line.page,
            "evidence_ref": f"costs.cost_line.{i}",
        })
        if any(kw in (line.label or "").lower() for kw in ("mwst", "umsatzsteuer", "ust.", "steuer")):
            tax_mentioned = True
    if lines and tax_mentioned:
        found_facts.append({
            "key": "costs.tax_note",
            "label_de": "Steuerangabe",
            "value": "zzgl. der jeweils geltenden gesetzlichen MwSt (in der Preistabelle genannt, kein Satz angegeben)",
            "period_hint": None,
            "page": lines[0].page,
            "evidence_ref": "costs.cost_line.0",
        })
    if evidence_texts:
        for text in evidence_texts:
            low = (text or "").lower()
            if "zahlung" in low and any(k in low for k in ("rhythmus", "jährlich", "monatlich", "regelmäßig", "rate", "viertel")):
                found_facts.append({
                    "key": "costs.payment_interval",
                    "label_de": "Zahlungsweise",
                    "value": " ".join(str(text).split())[:200],
                    "period_hint": None,
                    "page": None,
                    "evidence_ref": "payment.payment_start",
                })
                break

    missing_inputs = []
    total_value = getattr(total_contract_value, "value", None)
    total_currency = getattr(total_contract_value, "currency", None)
    total_status = getattr(getattr(total_contract_value, "status", None), "value", getattr(total_contract_value, "status", None))
    if total_value is not None:
        found_facts.append({
            "key": "costs.total_contract_value",
            "label_de": "Berechneter fixer Vertragswert",
            "value": _format_amount(total_value, total_currency),
            "period_hint": "vollständiger Preisplan",
            "page": lines[0].page if lines else None,
            "evidence_ref": "costs.scheduled_prices",
        })
    if total_value is None:
        if not lines:
            missing_inputs.append("Monetärer Betrag (Preistabelle)")
        else:
            missing_inputs.append("Vollständig belegter Preisplan über die gesamte Vertragslaufzeit")
    # Ein fehlender MwSt-Satz verhindert die Netto/Brutto-Gegenrechnung, nicht
    # die Addition expliziter Nettopreise über vollständig belegte Vertragsjahre.
    missing_inputs.append("Steuersatz (MwSt-%) für Netto/Brutto-Gegenrechnung")

    if total_value is not None:
        status = "staged_pricing_calculated"
        summary_de = (
            f"Der Vertrag enthält einen vollständigen gestaffelten Preisplan. "
            f"Der fixe Vertragswert beträgt {_format_amount(total_value, total_currency)}; "
            "bedingte/verbrauchsabhängige Zusatzkosten sind darin nicht enthalten."
        )
    elif not lines:
        status = "no_amount_cited"
        summary_de = (
            "Im Vertragtext ist kein monetärer Betrag belegt – die jährlichen Kosten "
            "sind aktuell nicht berechenbar. Bitte Betrag und Währung eintragen."
        )
    elif len(lines) > 1:
        status = "manual_input_required"
        summary_de = (
            "Im Vertrag sind Preise je Vertragszeitraum belegt (siehe unten), aber kein "
            "einheitlicher Jahres- oder Monatsbetrag. Bitte den maßgeblichen "
            "Jahresbetrag manuell festlegen."
        )
    else:
        status = "manual_input_required"
        summary_de = (
            "Im Vertrag ist ein Preis belegt, aber die jährlichen Kosten sind ohne "
            "einheitliche Laufzeit/Mengengerüst nicht verlässlich berechenbar. Bitte "
            "den Jahresbetrag manuell festlegen."
        )

    return {
        "status": status,
        "summary_de": summary_de,
        "currency_known": any(line.currency for line in lines) if lines else False,
        "found_facts": found_facts,
        "missing_inputs": missing_inputs,
        "manual_input_required": bool(lines) and total_value is None,
        "explanation_de": (
            "Der fixe Gesamtwert wurde deterministisch ausschließlich aus dem vollständig "
            "belegten Preisplan berechnet; variable Zusatzpositionen bleiben separat."
            if total_value is not None
            else "Keine verlässliche automatische Gesamtberechnung vorhanden. Die Angaben "
                 "stammen aus dem persistierten Vertragstext."
        ),
    }


_PRICE_FIXED_MARKERS = ("festpreis", "preisfixiert", "fixpreis", "indexierung", "preisindex")

MAX_SNIPPET_CHARS = 400

_FIXED_YEARS_RE = re.compile(
    r"(?:ueber|über|für|fuer|fuer|for)\s+(\d{1,2})\s*(?:jahre|jahr|years|year|j)?\b",
    re.IGNORECASE,
)


def _parse_fixed_period_years(text: Optional[str]):
    """Parst eine Fixpreis-Dauer (Jahre) deterministisch aus Fakten-Text.

    Beispiel: „Festpreis über 8 Jahre." => 8. Kein Raten – ohne Treffer None.
    """
    if not text:
        return None
    m = _FIXED_YEARS_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(1))
    except (TypeError, ValueError):
        return None


def _price_development_items(costs, snapshot=None):
    items = []
    for pd in costs.price_development:
        items.append({
            "key": pd.key,
            "label": pd.label,
            "text": pd.text,
            "evidence_field_ref": pd.evidence_field_ref,
            "status": pd.status.value if pd.status else None,
            "period_years": _parse_fixed_period_years(pd.text or "")
            if getattr(pd, "period_years", None) is None
            else pd.period_years,
        })
    seen_keys = {i["key"] for i in items}
    # Preisfixierung aus der term()-Evidenz (z. B. „Festpreis über 8 Jahre")
    # als evidence-getragener Fakt einblenden – falls nicht schon aus dem
    # Kostenmodell abgedeckt. Key „termination.evidence" bleibt eindeutig.
    if snapshot and isinstance(snapshot.get("termination"), dict):
        tev = snapshot["termination"].get("evidence")
        if isinstance(tev, dict) and tev.get("source_text"):
            text = str(tev["source_text"])
            if any(m in text.lower() for m in _PRICE_FIXED_MARKERS):
                key = "price_fixed"
                if key not in seen_keys:
                    items.append({
                        "key": key,
                        "label": "Preisfixierung",
                        "text": text,
                        "evidence_field_ref": "termination.evidence",
                        "status": "explicit",
                        "period_years": _parse_fixed_period_years(text),
                    })
                    seen_keys.add(key)
    return items


# ---------------------------------------------------------------------------
# Leistungsumfang (Scope) – deterministische Drei-Stufen-Semantik (UAT Re-Test
# Defect 2). Die KI liefert die Fakten; ob eine Leistung ausdrücklich IM
# Vertragsumfang ("included"), ausdrücklich AUSGENOMMEN ("excluded"), nur
# ERWÄHNT ("mentioned") oder nicht belegt ("not_established") ist, entscheidet
# die deterministische Analyse des persistierten kanonischen Vertragstexts.
# Kein erfundener Ja/Nein-Wert ohne Quellen-Anker.
# ---------------------------------------------------------------------------

_SCOPE_KEYS = [
    "maintenance", "inspection", "repair", "calibration",
    "software_updates", "remote_support", "technical_support",
    "spare_parts_included", "consumables_included", "emergency_service",
]

_SCOPE_LABELS_DE = {
    "maintenance": "Wartung",
    "inspection": "Inspektion / Sichtprüfung",
    "repair": "Reparatur",
    "calibration": "Kalibrierung",
    "software_updates": "Softwarepflege / Updates",
    "remote_support": "Fernwartung",
    "technical_support": "Technischer Support",
    "spare_parts_included": "Ersatzteile im Wartungsumfang",
    "consumables_included": "Verbrauchsmaterial",
    "emergency_service": "Notdienst / Einsatz außerhalb der Arbeitszeit",
}

_SCOPE_TERMS = {
    "maintenance": ("wartung",),
    "inspection": ("sichtprüfung", "sichtpruefung", "inspektion"),
    "repair": ("reparatur",),
    "calibration": ("kalibrier", "justier", "prüfmittel", "pruefmittel"),
    "software_updates": ("softwarepflege", "softwareupdate", "software", "fcn", "firmware"),
    "remote_support": ("fernwartung", "ferndiagnose", "remote"),
    "technical_support": ("hotline", "helpdesk", "technischer support", "technischen support", "anwendersupport"),
    "spare_parts_included": ("ersatzteil", "verschleißteil", "verschleißteile", "verschleiss"),
    "consumables_included": ("verbrauchsmaterial", "akkus", "batterien", "lüfter", "leuchtelement", "verbrauchsteil"),
    "emergency_service": ("notdienst", "notfall", "samstag", "sonntag", "feiertag", "zuschlag", "außerhalb der arbeitszeit", "außerhalb der geschäftszeit", "emergency"),
}

# Anker: die wörtliche Einleitungs-Zeile der INKLUSIV-Leistungsliste.
_SCOPE_INCLUDED_ANCHOR_RE = re.compile(r"umfasst\s+die\s+folgenden\s+leistungen")

# Ausschluss-Marker: Formulierungen, die eine Leistung ausdrücklich aus dem
# Leistungsumfang nehmen bzw. als separat abgerechnet ausweisen.
_SCOPE_STRONG_EXCLUSION_MARKERS = (
    "nicht in diesem vertrag enthalten",
    "nicht gegenstand des vertrages",
    "nicht gegenstand dieses vertrages",
    "fallen nicht in den rahmen dieses vertrages",
    "nicht mit zum leistungsumfang",
    "ausgenommen",
    "50 %-zuschlag",
    "50-%-zuschlag",
    "50 % zuschlag",
)
_SCOPE_EXCLUSION_MARKERS = _SCOPE_STRONG_EXCLUSION_MARKERS + (
    "gesondert verrechnet",
    "gesondert vergütet",
    "gesondert in rechnung gestellt",
    "separat verrechnet",
    "separat angeboten",
    "zusätzliche leistungen",
    "zusatzlich leistungen",
)

# Teilmengen-Marker: schließen nur einen TEIL der Leistung aus (z. B. Arbeiten
# infolge unsachgemäßer Bedienung) und dürfen die Leistung als Ganzes nicht
# als "ausgenommen" einstufen.
_SCOPE_SUBSET_QUALIFIERS = (
    "welche", "welche nicht",
    "die nicht dem", "der nicht dem",
    "zurückzuführen",
    "soweit", "sofern",
    "verursacht",
    "unsachgemäße bedienung", "unsachgemässe bedienung", "unsachgemäße bedienung",
)


def _scope_text_analysis(pages) -> dict:
    """Baut die kanonische Text-Struktur fuer die Leistungs-Verdikte (read-time,
    deterministisch). Liefert `sentences` (Sätze mit Ausschluss-Marker inkl.
    Teilmengen-Kennzeichen), `chunks` (feinkörnige Text-Stuecke je Seite, fuer
    Inklusiv/Erwaehnt-Kontextpruefung) und `included_anchor` (Seite+Snippet
    der Inklusiv-Listen-Einleitung)."""
    result = {"pages": [], "sentences": [], "chunks": [], "included_anchor": None}
    for pg in pages or []:
        raw = " ".join(str(pg.get("text") or "").split())
        norm = _match_text(raw)
        page_no = int(pg.get("page", 0))
        result["pages"].append({"page": page_no, "norm": norm, "raw": raw})
        for raw_chunk in re.split(r"(?<=[.!?])\s+", raw):
            raw_chunk = raw_chunk.strip()
            chunk_norm = _match_text(raw_chunk)
            if len(chunk_norm) < 12:
                continue
            result["sentences"].append({
                "raw": raw_chunk,
                "norm": chunk_norm,
                "page": page_no,
                "subset": any(q in chunk_norm for q in _SCOPE_SUBSET_QUALIFIERS),
                "exclusion": any(m in chunk_norm for m in _SCOPE_EXCLUSION_MARKERS),
            })
        if result["included_anchor"] is None and _SCOPE_INCLUDED_ANCHOR_RE.search(norm):
            idx = raw.lower().find("umfasst die folgenden leistungen")
            start = max(0, idx - 90)
            end = min(len(raw), idx + 190)
            result["included_anchor"] = {
                "page": page_no,
                "snippet": _cap(" ".join(raw[start:end].split())),
            }
        # Feinkörnig (Leistungsliste der Anlage: Items enden mit ; oder Zeilen-
        # umbrüchen) – fuer Inklusiv-/Erwaehnt-Kontextpruefung.
        for chunk in re.split(r"[;.!?\n]+", norm):
            chunk = " ".join(chunk.split()).strip()
            if len(chunk) < 5:
                continue
            result["chunks"].append({
                "norm": chunk,
                "page": page_no,
                "strong_exclusion": any(m in chunk for m in _SCOPE_STRONG_EXCLUSION_MARKERS),
            })
    return result


def _scope_chunks_contain(analysis, page, terms):
    """Liefert (snippet, chunk) wenn ein Stueck der Seite einen Begriff traegt."""
    for c in analysis["chunks"]:
        if c["page"] != page:
            continue
        if any(t in c["norm"] for t in terms):
            return c
    return None


def _scope_sentence_in_anchor(analysis, anchor_page, terms):
    """Findet den konkreten Leistungs-Satz (Beleg-Snippet) zur Inklusiv-Liste."""
    for s in analysis["sentences"]:
        if s["page"] != anchor_page:
            continue
        if any(t in s["norm"] for t in terms):
            return _cap(s["raw"])
    return None


def _scope_mentioned(analysis, terms):
    for s in analysis["sentences"]:
        if any(t in s["norm"] for t in terms):
            return s["page"], _cap(s["raw"])
    return None, None


def _scope_concept_verdict(key, terms, included_items, excluded_items, analysis):
    """Liefert (status, page, snippet, evidence_ref) fuer eine Leistungsart.

    Reihenfolge: ausdrücklich im Umfang (Inklusiv-Liste) > ausdrücklich
    ausgenommen (Ausschluss-Liste/Text) > nur erwähnt > nicht belegt.
    """
    anchor = analysis["included_anchor"]

    # 1a) Ausdrücklich im Vertragsumfang (Inklusiv-Leistungsliste der KI).
    for item in included_items:
        ni = _match_text(item)
        if ni and any(t in ni for t in terms):
            if anchor is not None:
                page = anchor["page"]
                snippet = _scope_sentence_in_anchor(analysis, page, terms) or anchor["snippet"]
                return ("included", page, snippet, "scope.included_services")
            return ("included", None, None, "scope.included_services")

    # 1b) Ausdrücklich im Vertragsumfang laut der Inklusiv-Listen-Seite – aber
    #     nur, wenn der Begriff NICHT in einem ausdrücklich ausgenommenen
    #     Stueck steht (z. B. "Austausch von Verschleißteilen ... Akkus und
    #     Batterien" ist im Umfang). Der Anker-Satz selbst darf nie als
    #     Voll-Ausschluss gewertet werden (Fußnoten im selben Block).
    if anchor is not None:
        chunk = _scope_chunks_contain(analysis, anchor["page"], terms)
        if chunk is not None and not chunk["strong_exclusion"]:
            snippet = _scope_sentence_in_anchor(analysis, anchor["page"], terms) or anchor["snippet"]
            return ("included", anchor["page"], snippet, "scope.included_services")

    # 2a) Ausdrücklich ausgenommen laut der abgegrenzten Leistungsliste (KI).
    for item in excluded_items:
        ni = _match_text(item)
        if ni and any(t in ni for t in terms):
            for s in analysis["sentences"]:
                if s["page"] == (anchor["page"] if anchor else -1):
                    continue
                if not s["subset"] and any(t in s["norm"] for t in terms):
                    return ("excluded", s["page"], _cap(s["raw"]), "scope.excluded_services")
            return ("excluded", None, _cap(item), "scope.excluded_services")

    # 2b) Ausdrücklich ausgenommen laut Vertragstext (deterministisch) – auf
    #     Gegen-Seiten (die Inklusiv-Listen-Seite zaehlt nicht als Ausschluss).
    anchor_page = anchor["page"] if anchor is not None else -1
    for s in analysis["sentences"]:
        if s["page"] == anchor_page or s["subset"]:
            continue
        if any(t in s["norm"] for t in terms):
            return ("excluded", s["page"], _cap(s["raw"]), "scope.excluded_services")

    # 3) Nur erwähnt (keine ausdrückliche Ja/Nein-Aussage).
    page, snippet = _scope_mentioned(analysis, terms)
    if page is not None:
        return ("mentioned", page, snippet, None)
    # 4) Nicht belegt.
    return ("not_established", None, None, None)


def _scope_section(snapshot, pages=None, version_to_file=None, document_version_id=None):
    services = snapshot.get("services") if snapshot else None
    if not isinstance(services, dict):
        services = {}
    ai_bools = {}
    for k in _SCOPE_KEYS:
        v = services.get(k)
        if v is not None:
            ai_bools[k] = bool(v)
    included_items = [str(s) for s in (services.get("included_services") or []) if s]
    excluded_items = [str(s) for s in (services.get("excluded_services") or []) if s]

    analysis = _scope_text_analysis(pages)
    has_canonical_text = bool(analysis["pages"])

    scope_status = {}
    booleans = {}
    refs = []
    derived_exclusions = []
    anchor_page = (
        analysis["included_anchor"]["page"]
        if analysis["included_anchor"] is not None
        else -1
    )
    exclusion_sentence = next(
        (s for s in analysis["sentences"] if s["page"] != anchor_page and not s["subset"] and s["exclusion"]),
        None,
    )

    for k in _SCOPE_KEYS:
        terms = _SCOPE_TERMS[k]
        if has_canonical_text:
            status, page, snippet, evidence_ref = _scope_concept_verdict(
                k, terms, included_items, excluded_items, analysis
            )
        else:
            # Kein kanonischer Volltext verfügbar: KI-Angabe transparent als
            # "erwähnt" übernehmen (kein fundierter Ja/Nein-Entscheid).
            status = "mentioned" if ai_bools.get(k) is not None else "not_established"
            page, snippet, evidence_ref = None, None, None
        booleans[k] = True if status == "included" else False if status == "excluded" else (ai_bools.get(k) if status == "mentioned" else None)
        item = {
            "status": status,
            "page": page,
            "snippet": snippet,
            "evidence_ref": evidence_ref,
        }
        scope_status[k] = item
        if status == "excluded" and snippet:
            derived_exclusions.append(
                f"{snippet} (ausgenommen vom Wartungsumfang)"[:220]
            )

    # Quell-Navigation fuer die Inklusiv-/Ausschluss-Anker (nur mit Seite).
    anchor = analysis["included_anchor"]
    if anchor is not None:
        refs.append(
            _recovered_evidence_ref(
                field_ref="scope.included_services",
                page=anchor["page"],
                snippet=anchor["snippet"],
                region=None,
                version_to_file=version_to_file or {},
                document_version_id=document_version_id,
            )
        )
    if exclusion_sentence is not None:
        refs.append(
            _recovered_evidence_ref(
                field_ref="scope.excluded_services",
                page=exclusion_sentence["page"],
                snippet=_cap(exclusion_sentence["raw"]),
                region=None,
                version_to_file=version_to_file or {},
                document_version_id=document_version_id,
            )
        )

    included = [c for c in _SCOPE_KEYS if scope_status[c]["status"] == "included"]
    excluded = [c for c in _SCOPE_KEYS if scope_status[c]["status"] == "excluded"]
    mentioned = [c for c in _SCOPE_KEYS if scope_status[c]["status"] == "mentioned"]
    unsettled = [c for c in _SCOPE_KEYS if scope_status[c]["status"] == "not_established"]
    note_parts = []
    if included:
        note_parts.append("Im Vertragsumfang: " + ", ".join(_SCOPE_LABELS_DE[c] for c in included) + ".")
    if excluded:
        note_parts.append("Ausgenommen / separat abgerechnet: " + ", ".join(_SCOPE_LABELS_DE[c] for c in excluded) + ".")
    if mentioned:
        note_parts.append("Nur erwähnt, bitte prüfen: " + ", ".join(_SCOPE_LABELS_DE[c] for c in mentioned) + ".")
    if unsettled:
        note_parts.append("Im Vertragstext nicht zweifelsfrei belegt: " + ", ".join(_SCOPE_LABELS_DE[c] for c in unsettled) + ".")
    note_de = " ".join(note_parts).strip() if note_parts else None

    out = {
        "included_services": included_items,
        "excluded_services": excluded_items + derived_exclusions,
        "scope_status": scope_status,
        "note_de": note_de,
    }
    out.update(booleans)
    return out, refs


def _sla_section(snapshot):
    sla = snapshot.get("sla") if snapshot else None
    if not isinstance(sla, dict):
        return {}
    out = {}
    for k in ["response_time", "resolution_time", "service_hours",
              "emergency_availability", "availability_24_7", "sla_notes"]:
        v = sla.get(k)
        if v is None:
            continue
        if k == "availability_24_7":
            out[k] = bool(v)
        elif isinstance(v, dict):
            out[k] = _sla_value_str(v)
        else:
            out[k] = str(v)
    return out


_TIME_UNIT_LABELS = {
    "days": "Tage",
    "weeks": "Wochen",
    "months": "Monate",
    "years": "Jahre",
    "hours": "Stunden",
}


def _sla_value_str(v: dict) -> str:
    """Formatiert ein TimeValue-Snapshot deterministisch als Anzeige-String."""
    value = v.get("value")
    if value is None:
        return str(v.get("text") or v.get("original_text") or "")
    unit = v.get("unit") or "hours"
    label = _TIME_UNIT_LABELS.get(unit, unit)
    try:
        formatted = f"{float(value):g}"
    except (TypeError, ValueError):
        formatted = str(value)
    return f"{formatted} {label}"


def _equipment_item(eq, evidence=None, resolved_page=None) -> dict:
    if resolved_page is not None:
        page = resolved_page
    elif evidence is not None:
        page = evidence.page
    else:
        page = None
    return {
        "id": str(eq.id),
        "equipment_id": str(eq.equipment_id) if eq.equipment_id else None,
        "device_name": eq.device_name,
        "manufacturer": eq.manufacturer,
        "model": eq.model,
        "serial_number": eq.serial_number,
        "inventory_number": eq.inventory_number,
        "system_name": eq.system_name,
        "equipment_category": eq.equipment_category,
        "equipment_type": eq.equipment_type,
        "location": eq.location,
        "department": eq.department,
        "service_scope": eq.service_scope,
        "coverage_start": eq.coverage_start,
        "coverage_end": eq.coverage_end,
        "included_services": list(eq.included_services or []),
        "excluded_services": list(eq.excluded_services or []),
        "sla_notes": eq.sla_notes,
        "identification_quality": eq.identification_quality,
        "relationship_quality": eq.relationship_quality,
        "requires_review": bool(eq.requires_review),
        "review_reasons": list(eq.review_reasons or []),
        # Provenienz -> ExtractionEvidence (Quell-Navigation, PR-2/PR-4).
        "field_ref": eq.field_ref,
        "page": page,
        "source_type": evidence.source_type if evidence is not None else None,
    }


def _work_item_item(w) -> dict:
    return {
        "work_item_id": str(w.id),
        "item_type": w.item_type,
        "severity": w.severity,
        "status": w.status,
        "title_de": w.title_de,
        "why_de": w.why_de,
        "action_hint_de": w.action_hint_de,
        "target_date": w.target_date,
        "days_remaining": w.days_remaining,
        "requires_review": bool(w.requires_review),
        "source_warning_id": str(w.source_warning_id) if w.source_warning_id else None,
        "contract_equipment_id": str(w.contract_equipment_id) if w.contract_equipment_id else None,
        "equipment_id": str(w.equipment_id) if w.equipment_id else None,
    }


def _warning_item(w) -> dict:
    return {
        "warning_type": w.warning_type,
        "severity": w.severity,
        "title_de": _WARNING_TITLES.get(w.warning_type, w.warning_type),
        "target_kind": w.target_kind,
        "target_date": w.target_date,
        "days_remaining": w.days_remaining,
        "requires_action": bool(w.requires_action),
        "requires_review": bool(w.requires_review),
        "action_state": w.action_state,
    }


def _review_section(session, organization_id, contract_id, warnings):
    as_of = session.scalars(
        select(func.max(WarningEvaluationRun.as_of_date)).where(
            (WarningEvaluationRun.organization_id == organization_id)
            & (WarningEvaluationRun.contract_id == contract_id)
        )
    ).first()
    reasons = []
    for w in warnings:
        if w.requires_review:
            reasons.append(_WARNING_TITLES.get(w.warning_type, w.warning_type))
    freshness = "none" if as_of is None else ("stale" if as_of < today_local() else "current")
    return {
        "requires_manual_review": any(w.requires_review for w in warnings),
        "review_reasons": reasons,
        "data_freshness": freshness,
        "warning_evaluation_as_of_date": as_of,
    }


def _load_documents(session, organization_id, contract_id):
    links = session.scalars(
        select(ContractDocument).where(
            (ContractDocument.organization_id == organization_id)
            & (ContractDocument.contract_id == contract_id)
        )
    ).all()

    version_ids = [l.document_version_id for l in links]
    versions = {}
    if version_ids:
        for v in session.scalars(
            select(DocumentVersion).where(DocumentVersion.id.in_(version_ids))
        ).all():
            versions[v.id] = v

    file_ids = [v.document_file_id for v in versions.values()]
    files = {}
    if file_ids:
        for f in session.scalars(
            select(DocumentFile).where(DocumentFile.id.in_(file_ids))
        ).all():
            files[f.id] = f

    version_to_file = {}
    for v in versions.values():
        f = files.get(v.document_file_id)
        if f is not None:
            version_to_file[v.id] = {
                "id": v.id,
                "original_filename": f.original_filename,
                "mime_type": f.mime_type,
                "file_extension": f.file_extension,
            }

    docs = []
    for link in links:
        ver = versions.get(link.document_version_id)
        if ver is None:
            continue
        f = files.get(ver.document_file_id)
        ext = (f.file_extension or "").lower() if f else ""
        docs.append({
            "document_version_id": str(ver.id),
            "role": link.role,
            "original_filename": f.original_filename if f else None,
            "mime_type": f.mime_type if f else None,
            "file_size_bytes": f.file_size_bytes if f else None,
            "viewer_supported": ext == ".pdf",
        })
    return docs, version_to_file


def _evidence_ref(e, version_to_file, evidence_version_id, resolved_page=None) -> dict:
    bbox_obj = None
    raw_bbox = e.bounding_box
    if isinstance(raw_bbox, dict):
        try:
            bbox_obj = EvidenceBbox(
                x0=float(raw_bbox.get("x0")), y0=float(raw_bbox.get("y0")),
                x1=float(raw_bbox.get("x1")), y1=float(raw_bbox.get("y1")),
            )
        except (TypeError, ValueError):
            bbox_obj = None
        if bbox_obj is not None and not (
            bbox_obj.is_finite and bbox_obj.is_ordered and not bbox_obj.is_negative
        ):
            bbox_obj = None
    normalized = bool(bbox_obj is not None and bbox_obj.is_normalized)

    file_info = None
    document_version_id = None
    if evidence_version_id is not None and evidence_version_id in version_to_file:
        file_info = version_to_file[evidence_version_id]
        document_version_id = str(evidence_version_id)

    return {
        "evidence_id": str(e.id),
        "field_ref": e.field_ref,
        "document_version_id": document_version_id,
        "original_filename": file_info["original_filename"] if file_info else None,
        "page": resolved_page if resolved_page is not None else e.page,
        "paragraph_index": e.paragraph_index,
        "table_index": e.table_index,
        "source_type": e.source_type,
        "snippet": _cap(e.source_text),
        "confidence": float(e.confidence) if e.confidence is not None else None,
        "requires_review": bool(e.requires_review),
        "bbox": bbox_obj.model_dump() if bbox_obj else None,
        "precision": "coarse" if bbox_obj else "none",
        "geometry_normalized": normalized,
        # PR-2: bbox liegt in PDF-Punkten der Original-Seite (SourceBox-Semantik,
        # values > 1). Der Client normalisiert gegen die echten Seitenmaße des
        # gerenderten PDFs. Mit bbox + Seite ist exakte (regionale) Navigation
        # moeglich; ohne eins von beiden niemals eine erfundene Hervorhebung.
        "bbox_space": "pdf_points",
        "supports_exact_navigation": bool(bbox_obj is not None and e.page is not None),
    }


def _recovered_evidence_ref(
    *, field_ref, page, snippet, region, version_to_file, document_version_id
) -> dict:
    """Baut einen EvidenceRef fuer einen wiederhergestellten, dokumentierten
    Quell-Beleg.

    Gleiche Shape/Policy wie `_evidence_ref` (JSON-Serializer-frei, PDF-Punkte,
    `supports_exact_navigation` nur mit gültiger Geometrie + Seite).
    """
    bbox_obj = None
    if isinstance(region, dict):
        try:
            bbox_obj = EvidenceBbox(
                x0=float(region.get("x0")),
                y0=float(region.get("y0")),
                x1=float(region.get("x1")),
                y1=float(region.get("y1")),
            )
        except (TypeError, ValueError, AttributeError):
            bbox_obj = None
        if bbox_obj is not None and not (
            bbox_obj.is_finite and bbox_obj.is_ordered and not bbox_obj.is_negative
        ):
            bbox_obj = None
    normalized = bool(bbox_obj is not None and bbox_obj.is_normalized)

    file_info = None
    version_id = None
    if document_version_id is not None and document_version_id in version_to_file:
        file_info = version_to_file[document_version_id]
        version_id = str(document_version_id)

    return {
        "evidence_id": f"recovered:{field_ref}",
        "field_ref": field_ref,
        "document_version_id": version_id,
        "original_filename": file_info["original_filename"] if file_info else None,
        "page": page,
        "paragraph_index": None,
        "table_index": None,
        "source_type": "table" if bbox_obj else "paragraph",
        "snippet": _cap(snippet),
        "confidence": None,
        "requires_review": False,
        "bbox": bbox_obj.model_dump() if bbox_obj else None,
        "precision": "coarse" if bbox_obj else "none",
        "geometry_normalized": normalized,
        "bbox_space": "pdf_points",
        "supports_exact_navigation": bool(bbox_obj is not None and page is not None),
    }


def _settle_canonical_evidence(refs):
    """UAT Re-Test (Defect 1): pro Fakt gibt es EINE kanonische Quell-Seite.

    Wiederhergestellte, wörtlich belegte Evidence-Refs (`recovered:...`)
    ersetzen fuer denselben `field_ref` dekorative/AI-Extraktions-Refs – so
    projizieren Detail, Review und Evidence-Button denselben Quell-Beleg.
    """
    settled: list[dict] = []
    index: dict[str, int] = {}
    for r in refs or []:
        fr = r.get("field_ref")
        if not fr:
            settled.append(r)
            continue
        is_rec = str(r.get("evidence_id") or "").startswith("recovered:")
        existing_idx = index.get(fr)
        if existing_idx is None:
            index[fr] = len(settled)
            settled.append(r)
            continue
        existing = settled[existing_idx]
        existing_rec = str(existing.get("evidence_id") or "").startswith("recovered:")
        if is_rec and not existing_rec:
            settled[existing_idx] = r
    return settled


def _dedupe_key(ref: dict) -> tuple:
    """Deterministischer Duplikats-Schluessel fuer die Read-Layer-Dedupe.

    Zwei Belege sind NUR Duplikate, wenn sie denselben Fakt (`field_ref`)
    an derselben physischen Quelle (Dokument, Seite, Paragraf-/Tabellen-Index,
    `source_type`) mit derselben normalisierten Aussage (Snippet) tragen.
    Unterschiedliche Fakten, Seiten, Quellen oder Aussagen bilden bewusst
    verschiedene Schluessel – sie werden nie zusammengefuehrt.
    """
    return (
        ref.get("field_ref") or "",
        ref.get("document_version_id"),
        ref.get("page"),
        ref.get("paragraph_index"),
        ref.get("table_index"),
        ref.get("source_type"),
        " ".join(str(ref.get("snippet") or "").split()).casefold(),
    )


def _is_recovered_ref(ref: dict) -> bool:
    return str(ref.get("evidence_id") or "").startswith("recovered:")


def _ref_confidence(ref: dict) -> float:
    try:
        return float(ref["confidence"]) if ref.get("confidence") is not None else -1.0
    except (TypeError, ValueError):
        return -1.0


def _merge_evidence_duplicate(target: dict, other: dict) -> None:
    """Aggregiert eine exakte Duplikat-Zeile in den kanonischen Repraesentanten.

    Es wird nichts geloescht/erfunden: `requires_review` wird ODER-verkntuepft,
    der woeertlich belegte (`recovered:`) Beleg bevorzugt, hoehere Konfidenz
    und eine vorhandene Geometrie uebernehmen.
    """
    target["requires_review"] = bool(
        target.get("requires_review") or other.get("requires_review")
    )
    # Keep every original ID addressable after read-layer deduplication.
    target["merged_evidence_ids"] = sorted(set(
        [*target.get("merged_evidence_ids", []), *other.get("merged_evidence_ids", []),
         str(target.get("evidence_id") or ""), str(other.get("evidence_id") or "")]
    ) - {""})
    if _is_recovered_ref(other) and not _is_recovered_ref(target):
        target["evidence_id"] = other.get("evidence_id")
    if _ref_confidence(other) > _ref_confidence(target):
        target["confidence"] = other.get("confidence")
    if (target.get("bbox") is None) and other.get("bbox") is not None:
        target["bbox"] = other.get("bbox")
        target["precision"] = other.get("precision")
        target["geometry_normalized"] = other.get("geometry_normalized")
        target["bbox_space"] = other.get("bbox_space")


def _dedupe_evidence(refs: list[dict]) -> list[dict]:
    """UAT Round-3 Fix 3: deterministische Read-Layer-Dedupe der Detail-Antwort.

    Jeder physische Quellen-Beleg erscheint dem Nutzer genau einmal – auch wenn
    persistierte (Audit-)Zeilen Duplikate tragen. Die zugrunde liegenden
    Extraktions-/Audit-Zeilen bleiben in der Datenbank unveraendert. Sortierung
    und Merge sind deterministisch (von der DB-Lieferreihenfolge unabhaengig).
    """
    if not refs:
        return []
    sorted_refs = sorted(
        refs,
        key=lambda ref: (_dedupe_key(ref), str(ref.get("evidence_id") or "")),
    )
    merged: list[dict] = []
    index: dict[tuple, int] = {}
    for ref in sorted_refs:
        key = _dedupe_key(ref)
        existing_index = index.get(key)
        if existing_index is None:
            index[key] = len(merged)
            merged.append({**ref, "merged_evidence_ids": list(ref.get("merged_evidence_ids", []))})
            continue
        _merge_evidence_duplicate(merged[existing_index], ref)
    deterministic = sorted(
        merged,
        key=lambda ref: (_dedupe_key(ref), str(ref.get("evidence_id") or "")),
    )
    for ref in deterministic:
        if ref.get("bbox") is not None:
            ref["supports_exact_navigation"] = bool(ref.get("page") is not None)
    return deterministic


def _recovered_evidence_refs(recovered, version_to_file, document_version_id, *, supplier=None, supplier_ref=None):
    """Sammelt die Quell-Navigation fuer alle wiederhergestellten Fakten."""
    refs = []
    if recovered is None or document_version_id is None:
        return refs
    # UAT Re-Test Defect A/B: wiederhergestellte Identitaet (Vertragsnummer,
    # wörtliche Vertragsüberschrift) mit wörtlichem Dokument-Beleg.
    identity = recovered.identity
    if identity is not None:
        if identity.contract_number_page is not None and identity.contract_number:
            refs.append(
                _recovered_evidence_ref(
                    field_ref="identity.contract_number",
                    page=identity.contract_number_page,
                    snippet=identity.contract_number_snippet or identity.contract_number,
                    region=identity.contract_number_region,
                    version_to_file=version_to_file,
                    document_version_id=document_version_id,
                )
            )
        if identity.title_page is not None and identity.title:
            refs.append(
                _recovered_evidence_ref(
                    field_ref="identity.contract_title",
                    page=identity.title_page,
                    snippet=identity.title_snippet or identity.title,
                    region=identity.title_region,
                    version_to_file=version_to_file,
                    document_version_id=document_version_id,
                )
            )
        # UAT Re-Test (Defect 3): System-Identitaet ("für das <System>").
        if identity.system_identity_page is not None and identity.system_identity:
            refs.append(
                _recovered_evidence_ref(
                    field_ref="identity.system_identity",
                    page=identity.system_identity_page,
                    snippet=identity.system_identity_snippet or identity.system_identity,
                    region=identity.system_identity_region,
                    version_to_file=version_to_file,
                    document_version_id=document_version_id,
                )
            )
    # UAT Re-Test: Lieferant-Fundstelle (Seite 1-Element) – deterministisch.
    if supplier_ref is not None and supplier:
        refs.append(
            _recovered_evidence_ref(
                field_ref="identity.supplier",
                page=supplier_ref["page"],
                snippet=supplier_ref["snippet"],
                region=supplier_ref.get("region"),
                version_to_file=version_to_file,
                document_version_id=document_version_id,
            )
        )
    money = recovered.money
    if money is not None and money.page is not None:
        for field_ref, region, key in (
            ("costs.tax_table.net", money.net_region, "net"),
            ("costs.tax_table.vat", money.vat_region, "vat"),
            ("costs.tax_table.gross", money.gross_region, "gross"),
        ):
            snippet = (money.snippets or {}).get(key)
            if not snippet:
                continue
            refs.append(
                _recovered_evidence_ref(
                    field_ref=field_ref,
                    page=money.page,
                    snippet=snippet,
                    region=region,
                    version_to_file=version_to_file,
                    document_version_id=document_version_id,
                )
            )
    laufzeit = recovered.laufzeit
    if laufzeit is not None:
        if laufzeit.payment_start_page is not None:
            refs.append(
                _recovered_evidence_ref(
                    field_ref="payment.payment_start",
                    page=laufzeit.payment_start_page,
                    snippet=laufzeit.payment_start_snippet,
                    region=laufzeit.payment_start_region,
                    version_to_file=version_to_file,
                    document_version_id=document_version_id,
                )
            )
        if laufzeit.minimum_duration_page is not None:
            refs.append(
                _recovered_evidence_ref(
                    field_ref="dates.minimum_duration",
                    page=laufzeit.minimum_duration_page,
                    snippet=laufzeit.minimum_duration_snippet,
                    region=laufzeit.minimum_duration_region,
                    version_to_file=version_to_file,
                    document_version_id=document_version_id,
                )
            )
        # UAT Defect Batch A/D: absoluter Vertragsbeginn + dokumentiertes Ende,
        # Laufzeit (Jahre) und automatische Verlaengerung – wörtlich belegt.
        if laufzeit.absolute_start_page is not None:
            refs.append(
                _recovered_evidence_ref(
                    field_ref="dates.start_date",
                    page=laufzeit.absolute_start_page,
                    snippet=laufzeit.absolute_start_snippet,
                    region=laufzeit.absolute_start_region,
                    version_to_file=version_to_file,
                    document_version_id=document_version_id,
                )
            )
        if laufzeit.absolute_end_page is not None:
            refs.append(
                _recovered_evidence_ref(
                    field_ref="dates.end_date",
                    page=laufzeit.absolute_end_page,
                    snippet=laufzeit.absolute_end_snippet,
                    region=laufzeit.absolute_end_region,
                    version_to_file=version_to_file,
                    document_version_id=document_version_id,
                )
            )
        if laufzeit.duration_page is not None and laufzeit.duration_years:
            refs.append(
                _recovered_evidence_ref(
                    field_ref="dates.duration",
                    page=laufzeit.duration_page,
                    snippet=laufzeit.duration_snippet,
                    region=laufzeit.duration_region,
                    version_to_file=version_to_file,
                    document_version_id=document_version_id,
                )
            )
        if laufzeit.auto_renewal_page is not None and laufzeit.auto_renewal is not None:
            refs.append(
                _recovered_evidence_ref(
                    field_ref="termination.auto_renewal",
                    page=laufzeit.auto_renewal_page,
                    snippet=laufzeit.auto_renewal_snippet,
                    region=laufzeit.auto_renewal_region,
                    version_to_file=version_to_file,
                    document_version_id=document_version_id,
                )
            )
    # UAT Defect Batch C: belegte Preiszeilen (Preistabelle) als Quell-Navigation.
    if recovered.cost_lines:
        for i, line in enumerate(recovered.cost_lines):
            if line.page is None:
                continue
            snippet = f"{line.label} -> {line.amount} {line.currency}".strip()
            refs.append(
                _recovered_evidence_ref(
                    field_ref=f"costs.cost_line.{i}",
                    page=line.page,
                    snippet=snippet,
                    region=line.region,
                    version_to_file=version_to_file,
                    document_version_id=document_version_id,
                )
            )
    return refs


def _cap(text):
    if not text:
        return None
    text = " ".join(str(text).split())
    if len(text) > MAX_SNIPPET_CHARS:
        return text[:MAX_SNIPPET_CHARS] + "…"
    return text


def _org_slug(session, organization_id) -> str:
    slug = session.execute(
        select(Organization.slug).where(Organization.id == organization_id)
    ).scalar()
    return slug or ""
