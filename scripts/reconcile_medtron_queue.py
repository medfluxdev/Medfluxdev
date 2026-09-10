"""Weiche Ableitung: MEDTRON-Work-Items neu ableiten + Duplikate zusammenfuehren.

Nur fuer die echten Produktdaten (Org 'krankenhaus', MEDTRON-Vertrag):
re-derive aktive Warnungen + Equipment-Zeilen (wie die Verarbeitungspipeline)
und reconcile. _collapse_sibling_duplicates macht aus zwei identischen
'Geräte-Zuordnung prüfen'-Items eines; nichts wird geloescht.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.database import models as m  # noqa: E402
from app.database.session import create_session  # noqa: E402

MEDTRON_CONTRACT = "01a07ed3-d22c-7527-831d-3a0fd0fc75e2"


def main() -> None:
    from app.work_queue.derive import derive_work_items
    from app.work_queue.service import reconcile_work_items

    session = create_session()
    try:
        contract = session.get(m.Contract, MEDTRON_CONTRACT)
        if contract is None:
            sys.exit("MEDTRON-Vertrag nicht gefunden.")
        org_id = contract.organization_id
        active_warnings = session.scalars(
            sa.select(m.ContractWarning).where(
                (m.ContractWarning.organization_id == org_id)
                & (m.ContractWarning.contract_id == contract.id)
                & (m.ContractWarning.active.is_(True))
            )
        ).all()
        equipment_rows = session.scalars(
            sa.select(m.ContractEquipment).where(
                (m.ContractEquipment.organization_id == org_id)
                & (m.ContractEquipment.contract_id == contract.id)
            )
        ).all()
        derived = derive_work_items(
            contract_id=str(contract.id),
            warnings=active_warnings,
            equipment_rows=equipment_rows,
            as_of_date=date.today(),
            policy_version="v1",
        )
        reconcile_work_items(
            session,
            organization_id=org_id,
            contract_id=contract.id,
            derived=derived,
        )
        session.commit()
        actives = session.scalars(
            sa.select(m.WorkItem).where(
                (m.WorkItem.organization_id == org_id) & (m.WorkItem.active.is_(True))
            )
        ).all()
        print(f"Derived: {len(derived)}, aktive Items danach: {len(actives)}")
        for wi in actives:
            title = (wi.title_de or "")[:60]
            print(f"  {'active' if wi.active else 'HIDDEN'} | {wi.status} | {title}")
    finally:
        session.close()


if __name__ == "__main__":
    main()