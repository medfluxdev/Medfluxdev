"""Testdaten fuer die Browser-Tests (Playwright) – nur fuer eine Wegwerf-Datenbank.

Sicherheitsregeln (fail-closed):
- APP_ENV muss development oder test sein.
- Die Datenbank muss lokal sein, darf NICHT Port 5432 nutzen und NICHT `medflux` heissen
  (so kann die Produkt-/Pilotdatenbank nie getroffen werden).
- Das Passwort kommt aus E2E_ADMIN_PASSWORD (siehe frontend/e2e/.env.example).

Idempotent: eine bereits vorhandene Test-Organisation wird wiederverwendet.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.engine import make_url

from app.auth.credential_store import derive_password
from app.core.config import settings
from app.database.models import Account, AccountMembership, Organization
from app.database.models.organization_structure import CostCenter, Department, Hospital
from app.database.models.register import ContractPartner
from app.database.session import create_session
from app.deadlines.system import sync_system_deadlines
from app.finance.service import create_entry
from app.register.catalogs import ensure_defaults
from app.register.service import RegisterActor, create_manual_contract, update_register

ORG_SLUG = "e2e-klinik"
ADMIN_LOGIN = "e2e-admin@medflux.test"


def _guard() -> str:
    if settings.app_env.strip().casefold() not in {"development", "test"}:
        raise SystemExit("Abbruch: nur mit APP_ENV=development/test.")
    url = make_url(settings.database_url)
    host = (url.host or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"} or (url.port or 5432) == 5432 or url.database == "medflux":
        raise SystemExit("Abbruch: nur gegen eine lokale Wegwerf-Datenbank (nicht Port 5432, nicht 'medflux').")
    password = os.getenv("E2E_ADMIN_PASSWORD", "")
    if len(password) < 10:
        raise SystemExit("E2E_ADMIN_PASSWORD fehlt oder ist zu kurz (siehe frontend/e2e/.env.example).")
    return password


def seed() -> None:
    password = _guard()
    session = create_session()
    try:
        org = session.scalar(select(Organization).where(Organization.slug == ORG_SLUG))
        if org is None:
            org = Organization(name="E2E Klinikum", slug=ORG_SLUG, is_active=True)
            session.add(org)
            session.flush()
        account = session.scalar(select(Account).where(Account.login_name == ADMIN_LOGIN))
        if account is None:
            account = Account(login_name=ADMIN_LOGIN, display_name="E2E Admin", credential_digest=derive_password(password), is_active=True)
            session.add(account)
            session.flush()
            session.add(AccountMembership(organization_id=org.id, account_id=account.id, role="admin", is_active=True, is_default=True))
        else:
            account.credential_digest = derive_password(password)
        if session.scalar(select(Hospital).where(Hospital.organization_id == org.id)) is not None:
            session.commit()
            print("E2E-Daten bereits vorhanden; Passwort aktualisiert.")
            return

        hospital = Hospital(organization_id=org.id, name="Klinikum Nord", code="NORD")
        session.add(hospital)
        session.flush()
        radiology = Department(organization_id=org.id, hospital_id=hospital.id, name="Radiologie", code="RAD")
        session.add(radiology)
        session.flush()
        session.add(CostCenter(organization_id=org.id, hospital_id=hospital.id, department_id=radiology.id, code="471100", name="Radiologie"))
        ensure_defaults(session, org.id)
        siemens = ContractPartner(organization_id=org.id, short_name="SIEMENS", name1="Siemens Healthcare GmbH", city="Erlangen")
        clean = ContractPartner(organization_id=org.id, short_name="CLEANMED", name1="CleanMed Service GmbH", city="Hamburg")
        session.add_all([siemens, clean])
        session.flush()

        actor = RegisterActor(organization_id=org.id, account_id=account.id, display_name="E2E Admin", role="admin")
        today = date.today()
        specs = [
            ("Wartung CT Somatom", siemens.id, {
                "term_model": "auto_renewal", "term_start_date": date(today.year - 2, 1, 1).isoformat(),
                "initial_term_value": 3, "initial_term_unit": "years", "notice_period_value": 3, "notice_period_unit": "months",
                "notice_to": "contract_end", "renewal_period_value": 1, "renewal_period_unit": "years",
            }, [("Wartungspauschale", "3500", "monthly")]),
            ("Reinigung OP-Bereich", clean.id, {
                "term_model": "terminable", "term_start_date": (today - timedelta(days=500)).isoformat(),
                "notice_period_value": 1, "notice_period_unit": "months", "notice_to": "month_end",
            }, [("Reinigung", "1200", "monthly")]),
            ("Softwarepflege PACS", siemens.id, {
                "term_model": "fixed_term", "term_start_date": date(today.year, 1, 1).isoformat(),
                "term_fixed_end_date": date(today.year + 2, 12, 31).isoformat(),
            }, [("Lizenzpflege", "18000", "annual")]),
        ]
        for title, partner_id, values, entries in specs:
            contract = create_manual_contract(session, actor=actor, values={"short_description": title}, hospital_id=hospital.id)
            update_register(session, contract=contract, actor=actor, changes={**values, "partner_id": str(partner_id)}, confirm=[])
            for label, amount, interval in entries:
                create_entry(session, contract=contract, actor=actor, values={
                    "label": label, "amount": Decimal(amount), "vat_rate": Decimal("19"), "interval": interval,
                    "valid_from": values["term_start_date"],
                })
            sync_system_deadlines(session, contract, today)
        session.commit()
        print("E2E-Daten angelegt.")
    finally:
        session.close()


if __name__ == "__main__":
    seed()
