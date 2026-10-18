"""Stammdaten-Vorschlaege fuer Vertragspartner aus den Vertragsanalysen.

Findet die KI in einem Vertrag Angaben, die zum verknuepften Vertragspartner gehoeren
(Service-E-Mail, Service-Telefon, Anschrift aus dem woertlichen Nachweis des Partners),
bietet MedFlux an, sie in den Stammdaten des Partners zu ergaenzen. Nichts wird
automatisch geschrieben: leere Felder sind "neu", abweichende "abweichend"; eine Person
uebernimmt oder ignoriert. Ignorierte Werte (Feld + Wert) werden nicht erneut angeboten.

Die Anschrift wird im Code aus dem Zitat gelesen, nie vom Modell erfunden: nur wenn das
Zitat mit PLZ + Ort endet und davor Strasse + Hausnummer steht.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Contract
from app.database.models.register import ContractPartner, PartnerSuggestionDismissal
from app.models.contract import Contract as ExtractedContract
from app.reextract import facts
from app.register.service import load_extracted

LABELS = {
    "email": "E-Mail",
    "phone": "Telefon",
    "street": "Straße",
    "postal_code": "PLZ",
    "city": "Ort",
    "country": "Land",
}
FIELD_ORDER = tuple(LABELS)
_COUNTRY = {"D": "Deutschland", "DE": "Deutschland", "A": "Österreich", "AT": "Österreich", "CH": "Schweiz",
            "NL": "Niederlande", "B": "Belgien", "BE": "Belgien", "F": "Frankreich", "FR": "Frankreich"}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_LEGAL_FORM = re.compile(r"\b(?:GmbH\s*&\s*Co\.?\s*KG|GmbH|gGmbH|mbH|AG|KG|KGaA|SE|OHG|e\.\s?V\.|Inc\.?|Ltd\.?|LLC|B\.V\.|S\.A\.)\b\.?", re.I)
_PLACE = re.compile(r"(?:\b(?P<cc>[A-Z]{1,3})\s*[-–]\s*)?\b(?P<plz>\d{4,5})\s+(?P<city>[A-ZÄÖÜ][\wÄÖÜäöüß.\- ]{1,60}?)\s*[,.;]?\s*$")
_STREET = re.compile(r"(?P<street>[A-ZÄÖÜ][\wÄÖÜäöüß.\- ]{1,60}?\s\d{1,4}\s?[a-zA-Z]?(?:\s*[-–]\s*\d{1,4}\s?[a-zA-Z]?)?)\s*,?\s*$")


@dataclass
class Suggestion:
    field: str
    value: str
    current: Optional[str]
    contract_id: str
    register_number: Optional[str]
    contract_label: Optional[str]
    page: Optional[int] = None
    quote: Optional[str] = None
    kind: str = "new"  # new | deviating
    sources: int = 1

    def as_dict(self) -> dict:
        return {
            "field": self.field, "label": LABELS[self.field], "value": self.value, "current": self.current,
            "kind": self.kind, "page": self.page, "quote": self.quote, "contract_id": self.contract_id,
            "register_number": self.register_number, "contract_label": self.contract_label, "sources": self.sources,
        }


def _norm(field_key: str, value: Optional[str]) -> str:
    text = " ".join(str(value or "").split())
    if field_key == "email":
        return text.casefold()
    if field_key == "phone":
        return re.sub(r"\D", "", text)
    return re.sub(r"[\W_]+", "", text.casefold())


def parse_address(quote: Optional[str], partner_name: Optional[str] = None) -> dict[str, str]:
    """Strasse, PLZ, Ort (und Land aus dem Laenderkuerzel) aus einem Anschrift-Zitat; leer, wenn unklar."""
    text = " ".join(str(quote or "").split())
    if not text:
        return {}
    place = _PLACE.search(text)
    if not place:
        return {}
    head = text[: place.start()].strip(" ,;")
    # Firmenname vorne abtrennen: bis zur letzten Rechtsform bzw. bis nach dem bekannten Namen.
    forms = list(_LEGAL_FORM.finditer(head))
    if forms:
        head = head[forms[-1].end():]
    elif partner_name and head.casefold().startswith(partner_name.casefold()):
        head = head[len(partner_name):]
    street = _STREET.search(head.strip(" ,;"))
    if not street:
        return {}
    city = place.group("city").strip(" ,.;")
    words = street.group("street").strip().split(" ")
    # "… GmbH Frankfurt Steinbacher Hohl 2-26 … Frankfurt am Main": der Ortszusatz gehoert nicht zur Strasse.
    if len(words) > 2 and words[0].casefold() in {word.casefold() for word in city.split(" ")}:
        words = words[1:]
    out = {"street": " ".join(words), "postal_code": place.group("plz"), "city": city}
    if place.group("cc") and place.group("cc").upper() in _COUNTRY:
        out["country"] = _COUNTRY[place.group("cc").upper()]
    return out


_NAME_NOISE = {"gmbh", "ggmbh", "mbh", "ag", "kg", "se", "ev", "co", "und", "der", "die", "das", "fuer", "für", "europe", "deutschland", "germany"}


def _name_words(name: Optional[str]) -> list[str]:
    return [word for word in re.findall(r"[a-zäöüß]+", str(name or "").casefold()) if len(word) >= 3 and word not in _NAME_NOISE]


def _domain_names(name: Optional[str], domain: str) -> bool:
    """Steht die Domain fuer diesen Namen? Ein Namenswort im Domainnamen oder ein Kuerzel aus allen
    Namenswoertern in Reihenfolge (z. B. „khnw“ = Kranken-Haus Nord-West)."""
    words = _name_words(name)
    if not words:
        return False
    labels = [label for label in re.findall(r"[a-zäöüß0-9]+", domain.casefold()) if label not in {"de", "com", "net", "org", "eu", "www"}]
    for label in labels:
        if any(word in label or (len(label) >= 4 and label in word) for word in words):
            return True
        if len(label) >= 3 and label[0] == words[0][0]:
            position, used = 0, set()
            for char in label:
                while position < len(words) and char not in words[position][0 if position not in used else 1:]:
                    position += 1
                if position == len(words):
                    break
                used.add(position)
            else:
                if used == set(range(len(words))):
                    return True
    return False


def _customer_side(model: ExtractedContract, partner: ContractPartner, email: str) -> bool:
    """E-Mail des Auftraggebers (Krankenhaus), nicht des Partners: Domain steht fuer den Kunden, nicht fuer den Partner."""
    domain = email.rsplit("@", 1)[-1]
    if _domain_names(partner.name1, domain) or _domain_names(partner.short_name, domain) or _domain_names(model.identity.supplier, domain):
        return False
    return _domain_names(model.identity.customer, domain)


def _source(model: ExtractedContract, path: str) -> tuple[Optional[int], Optional[str]]:
    for row in facts.evidence_rows(model, path):
        source = row.get("source") or {}
        if source.get("source_text") or source.get("page"):
            return source.get("page"), source.get("source_text")
    return None, None


def found_in_contract(model: ExtractedContract, partner: ContractPartner) -> list[tuple[str, str, Optional[int], Optional[str]]]:
    """(Feld, Wert, Seite, Zitat) der Partner-Angaben, die diese Analyse belegt gefunden hat."""
    out: list[tuple[str, str, Optional[int], Optional[str]]] = []
    customer_pages: set = set()
    email = " ".join(str(model.identity.service_email or "").split())
    if email and _EMAIL.match(email):
        page, quote = _source(model, "identity.service_email")
        if _customer_side(model, partner, email):
            customer_pages.add(page)  # Kontaktblock des Krankenhauses: nicht dem Partner zuordnen
        else:
            out.append(("email", email, page, quote))
    phone = " ".join(str(model.identity.service_phone or "").split())
    if phone and len(re.sub(r"\D", "", phone)) >= 6:
        page, quote = _source(model, "identity.service_phone")
        if page is None or page not in customer_pages:
            out.append(("phone", phone, page, quote))
    for row in facts.evidence_rows(model, "identity.supplier"):
        source = row.get("source") or {}
        address = parse_address(source.get("source_text"), model.identity.supplier or partner.name1)
        if address:
            for key in ("street", "postal_code", "city", "country"):
                if address.get(key):
                    out.append((key, address[key], source.get("page"), source.get("source_text")))
            break
    return out


def _dismissed(session: Session, partner: ContractPartner) -> set[tuple[str, str]]:
    rows = session.execute(
        select(PartnerSuggestionDismissal.field_key, PartnerSuggestionDismissal.value)
        .where(PartnerSuggestionDismissal.partner_id == partner.id)
    ).all()
    return {(key, _norm(key, value)) for key, value in rows}


def suggestions(session: Session, partner: ContractPartner, contracts: Iterable[Contract]) -> list[Suggestion]:
    """Vorschlaege fuer einen Partner aus den angegebenen Vertraegen (je Feld + Wert einmal)."""
    dismissed = _dismissed(session, partner)
    seen: dict[tuple[str, str], Suggestion] = {}
    for contract in contracts:
        if contract.partner_id != partner.id or contract.accepted_extraction_id is None:
            continue
        model = load_extracted(session, contract.accepted_extraction_id)
        if model is None:
            continue
        for key, value, page, quote in found_in_contract(model, partner):
            norm = _norm(key, value)
            current = getattr(partner, key)
            if not norm or (key, norm) in dismissed or (current and _norm(key, current) == norm):
                continue
            if (key, norm) in seen:
                seen[(key, norm)].sources += 1
                continue
            seen[(key, norm)] = Suggestion(
                field=key, value=value, current=current or None, kind="deviating" if current else "new",
                contract_id=str(contract.id), register_number=contract.register_number,
                contract_label=contract.contract_title or contract.short_description, page=page, quote=quote,
            )
    return sorted(seen.values(), key=lambda item: (FIELD_ORDER.index(item.field), item.value))


def partner_contracts(session: Session, partner: ContractPartner, allowed: Optional[set] = None) -> list[Contract]:
    stmt = select(Contract).where(Contract.organization_id == partner.organization_id, Contract.partner_id == partner.id)
    if allowed is not None:
        stmt = stmt.where(Contract.id.in_(allowed or [uuid.uuid4()]))
    return list(session.scalars(stmt))


def find(session: Session, partner: ContractPartner, contracts: Iterable[Contract], field_key: str, value: str) -> Optional[Suggestion]:
    """Nur ein tatsaechlich angebotener Vorschlag darf uebernommen oder ignoriert werden."""
    norm = _norm(field_key, value)
    return next((item for item in suggestions(session, partner, contracts) if item.field == field_key and _norm(item.field, item.value) == norm), None)


def dismiss(session: Session, partner: ContractPartner, field_key: str, value: str, *, account_id, name: Optional[str]) -> None:
    session.add(PartnerSuggestionDismissal(
        organization_id=partner.organization_id, partner_id=partner.id, field_key=field_key, value=value[:500],
        dismissed_by_account_id=account_id, dismissed_by_name=name,
    ))
    session.flush()

