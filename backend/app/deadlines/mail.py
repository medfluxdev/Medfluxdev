"""E-Mail-Versand (SMTP, Standardbibliothek) und ICS-Kalendereinladungen.

Datenschutz: Mails enthalten nur Vertragsnummer, Kurzbeschreibung, Termin,
ToDo und einen Link in MedFlux, keine Vertragsinhalte.
"""

from __future__ import annotations

import smtplib
import ssl
import uuid
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Callable, Optional, Protocol

from app.core.config import settings

ICS_PRODID = "-//MedFlux//Vertragsfristen//DE"


class MailTransport(Protocol):
    def send(self, message: EmailMessage) -> None: ...


def smtp_configured() -> bool:
    return bool(settings.smtp_host.strip() and settings.smtp_from.strip())


class SmtpTransport:
    def send(self, message: EmailMessage) -> None:
        timeout = settings.smtp_timeout_seconds
        if settings.smtp_use_ssl:
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=timeout, context=ssl.create_default_context()
            )
        else:
            client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout)
        try:
            if settings.smtp_starttls and not settings.smtp_use_ssl:
                client.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
        finally:
            try:
                client.quit()
            except smtplib.SMTPException:
                pass


TransportFactory = Callable[[], MailTransport]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, current = [], b""
    for char in line:
        encoded = char.encode("utf-8")
        if len(current) + len(encoded) > 74:
            parts.append(current.decode("utf-8"))
            current = b""
        current += encoded
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def build_ics(*, uid: str, due: date, summary: str, description: str, alarm_days: int = 1, now: Optional[datetime] = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{ICS_PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{due.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{(due + timedelta(days=1)).strftime('%Y%m%d')}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        "TRANSP:TRANSPARENT",
        "BEGIN:VALARM",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_escape(summary)}",
        f"TRIGGER:-P{alarm_days}D",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"


def build_message(*, recipient: str, subject: str, body: str, ics: Optional[str]) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = recipient
    message["Subject"] = subject
    message["Message-ID"] = f"<{uuid.uuid4()}@medflux.local>"
    message.set_content(body)
    if ics:
        message.add_attachment(
            ics.encode("utf-8"), maintype="text", subtype="calendar", filename="frist.ics",
            params={"method": "PUBLISH"},
        )
    return message
