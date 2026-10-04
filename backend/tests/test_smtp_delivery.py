"""H5: Versand ueber echtes SMTP-Protokoll gegen einen lokalen Test-Server (kein externer Dienst)."""

from __future__ import annotations

import base64
import email
import socketserver
import threading
from datetime import date, timedelta
from email import policy
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.database.models import Account, AccountMembership, Contract
from app.database.models.deadlines import ContractDeadline, NotificationOutbox
from app.database.models.organization import Organization
from app.database.session import create_session
from app.deadlines.notify import run_daily


class _SmtpHandler(socketserver.StreamRequestHandler):
    def _reply(self, line: str) -> None:
        self.wfile.write((line + "\r\n").encode("ascii"))

    def handle(self) -> None:
        server = self.server
        self._reply("220 medflux-test ESMTP")
        recipients: list[str] = []
        sender = None
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            command = line.split(" ", 1)[0].upper()
            if command in ("EHLO", "HELO"):
                self.wfile.write(b"250-medflux-test\r\n250-AUTH PLAIN\r\n250 8BITMIME\r\n")
            elif command == "AUTH":
                decoded = base64.b64decode(line.split(" ")[2]).split(b"\x00")
                server.auth.append((decoded[1].decode(), decoded[2].decode()))
                self._reply("235 2.7.0 Authentication successful")
            elif command == "MAIL":
                sender = line.split(":", 1)[1].strip().strip("<>").split(">")[0]
                self._reply("250 OK")
            elif command == "RCPT":
                recipients.append(line.split(":", 1)[1].strip().strip("<>"))
                self._reply("250 OK")
            elif command == "DATA":
                self._reply("354 End data with <CR><LF>.<CR><LF>")
                chunks = []
                while True:
                    data = self.rfile.readline()
                    if data in (b".\r\n", b".\n", b""):
                        break
                    chunks.append(data[1:] if data.startswith(b"..") else data)
                server.messages.append((sender, list(recipients), b"".join(chunks)))
                self._reply("250 OK queued")
            elif command == "QUIT":
                self._reply("221 Bye")
                return
            else:
                self._reply("250 OK")


class _SmtpServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _SmtpHandler)
        self.messages: list = []
        self.auth: list = []


def test_reminder_is_delivered_over_smtp_with_calendar_invite(monkeypatch):
    server = _SmtpServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setattr(settings, "smtp_host", "127.0.0.1")
        monkeypatch.setattr(settings, "smtp_port", server.server_address[1])
        monkeypatch.setattr(settings, "smtp_starttls", False)
        monkeypatch.setattr(settings, "smtp_use_ssl", False)
        monkeypatch.setattr(settings, "smtp_username", "medflux")
        monkeypatch.setattr(settings, "smtp_password", "test-only")
        monkeypatch.setattr(settings, "smtp_from", "medflux@klinik.invalid")

        org, account, contract_id = uuid4(), uuid4(), uuid4()
        session = create_session()
        try:
            session.add(Organization(id=org, name="SMTP Test", slug=f"smtp-{org.hex[:10]}"))
            session.add(Account(id=account, login_name=f"anna-{org.hex[:6]}@klinik.invalid", display_name="Anna Müller", credential_digest="t"))
            session.flush()
            session.add(AccountMembership(organization_id=org, account_id=account, role="contract_manager"))
            session.add(Contract(id=contract_id, organization_id=org, register_number="000123", short_description="Wartung MRT",
                                 business_status="gueltig", responsible_account_id=account))
            session.flush()
            session.add(ContractDeadline(
                organization_id=org, contract_id=contract_id, source="manual", kind="sonstiges", title="Angebot einholen",
                due_date=date.today() + timedelta(days=10), remind_on=date.today(), status="open",
                assignee_account_id=account, send_email=True, send_ics=True,
            ))
            session.commit()
        finally:
            session.close()

        result = run_daily(as_of=date.today(), trigger="manual", organization_id=org)
        assert result.counts.get("emails_sent") == 1, result.counts
    finally:
        server.shutdown()
        server.server_close()

    assert server.auth == [("medflux", "test-only")]
    [(sender, recipients, raw)] = server.messages
    assert sender == "medflux@klinik.invalid" and recipients == [f"anna-{org.hex[:6]}@klinik.invalid"]
    message = email.message_from_bytes(raw, policy=policy.default)
    assert "Angebot einholen" in message["Subject"]
    body = message.get_body(preferencelist=("plain",)).get_content()
    assert "000123" in body
    calendars = [part for part in message.walk() if part.get_content_type() == "text/calendar"]
    assert calendars and "BEGIN:VEVENT" in calendars[0].get_content()

    session = create_session()
    try:
        outbox = session.scalars(select(NotificationOutbox).where(NotificationOutbox.organization_id == org)).one()
        assert outbox.status == "sent" and outbox.sent_at is not None
    finally:
        session.close()
