"""Equipment-Master-Duplikat zusammenfuehren (MEDTRON, PR-5 Defect B).

Grundlage der Live-Diagnose: `Equipment` 01a07ed3-d245... ist die exakte
Master-Identitaet (serial 88024307, ident_q=exact); 01a07ed3-d25c... ist ein
Schatten-Duplikat (serial leer, ident_q=partial, gleicher Erzeugungszeitpunkt),
das stattdessen auf die Master-Identitaet verweisen muss.
Es wird NICHTS an legitimate Daten verloren:
- contract_equipment/work_item werden auf den Master umgehängt,
- der Schatten-Eintrag wird (nur das Duplikat selbst) entfernt.
Danach: reconcile_medtron_queue.py ausführen.
"""

from __future__ import annotations

import sys
from pathlib import Path

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import settings  # noqa: E402
from app.database import models as m  # noqa: E402
from app.database.session import create_session  # noqa: E402

KEEPER = "01a07ed3-d245-767b-8d2c-457e24320489"
SHADOW = "01a07ed3-d25c-71cc-935b-7451c40a1c47"
ORG_SLUG = "krankenhaus"


def main() -> None:
    from app.database.services import get_organization

    s = create_session()
    try:
        org = get_organization(s, ORG_SLUG)
        if org is None:
            sys.exit("Org nicht gefunden.")
        keeper = s.get(m.Equipment, KEEPER)
        shadow = s.get(m.Equipment, SHADOW)
        if keeper is None or shadow is None:
            sys.exit("Keeper/Schadow nicht gefunden - Abbruch (nichts geaendert).")
        if keeper.organization_id != org.id or shadow.organization_id != org.id:
            sys.exit("Org-Mismatch - Abbruch.")

        # Zeiger umhaengen: CEQ + Work-Items des Schattens -> Master.
        r1 = s.execute(
            sa.update(m.ContractEquipment)
            .where(m.ContractEquipment.equipment_id == shadow.id)
            .values(equipment_id=keeper.id)
        )
        r2 = s.execute(
            sa.update(m.WorkItem)
            .where(m.WorkItem.equipment_id == shadow.id)
            .values(equipment_id=keeper.id)
        )
        # Schatten-Eintrag entfernen (reines Duplikat, keine legitimen Daten).
        s.delete(shadow)
        s.flush()
        s.commit()
        print(f"Umgehaengt: contract_equipment={r1.rowcount}, work_item={r2.rowcount}; "
              f"Schatten-Duplikat entfernt.")
    finally:
        s.close()


if __name__ == "__main__":
    main()