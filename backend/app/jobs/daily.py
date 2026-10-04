"""Tageslauf fuer Fristen und Erinnerungen.

Zwei Betriebsarten (Entscheidung D5):
- Windows-Aufgabenplanung: `python -m app.jobs.daily` (aus `backend\\`).
- Im Backend-Prozess: `REMINDER_SCHEDULER_ENABLED=true`; ein Hintergrund-
  Thread startet den Lauf taeglich ab `REMINDER_RUN_HOUR` (lokale Zeit) und
  holt einen verpassten Lauf nach dem Start nach.
Beide Wege sind ueber einen Datenbank-Lock gegen Doppellaeufe geschuetzt.
"""

from __future__ import annotations

import argparse
import logging
import threading
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select

from app.core.config import settings
from app.database.models.deadlines import JobRun
from app.database.session import create_session
from app.deadlines.notify import JOB_NAME, run_daily

logger = logging.getLogger("medflux.jobs")

_CHECK_INTERVAL_SECONDS = 15 * 60
_stop = threading.Event()
_thread: Optional[threading.Thread] = None


def _already_ran(as_of: date) -> bool:
    session = create_session()
    try:
        return session.scalar(
            select(JobRun.id).where(
                JobRun.job_name == JOB_NAME,
                JobRun.organization_id.is_(None),
                JobRun.as_of_date == as_of,
                JobRun.status == "succeeded",
            ).limit(1)
        ) is not None
    finally:
        session.close()


def due_now(now: datetime, run_hour: int, ran_today: bool) -> bool:
    return not ran_today and now.hour >= run_hour


def _loop() -> None:
    while not _stop.is_set():
        try:
            now = datetime.now()
            if due_now(now, settings.reminder_run_hour, _already_ran(now.date())):
                result = run_daily(as_of=now.date(), trigger="scheduler")
                logger.info("Tageslauf %s: %s", now.date(), result.counts)
        except Exception:  # noqa: BLE001 - the scheduler must survive transient DB errors
            logger.exception("Tageslauf-Planer: Fehler, nächster Versuch später")
        _stop.wait(_CHECK_INTERVAL_SECONDS)


def start_scheduler() -> bool:
    global _thread
    if not settings.reminder_scheduler_enabled or (_thread is not None and _thread.is_alive()):
        return False
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="medflux-daily-deadlines", daemon=True)
    _thread.start()
    return True


def stop_scheduler() -> None:
    _stop.set()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MedFlux-Tageslauf: Fristen, Erinnerungen, E-Mails.")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="Stichtag JJJJ-MM-TT (Standard: heute)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run_daily(as_of=args.as_of, trigger="cli")
    if result.skipped_locked:
        print("Tageslauf läuft bereits – übersprungen.")
        return 0
    print(f"Tageslauf {result.as_of}: {result.counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
