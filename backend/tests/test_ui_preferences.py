"""U8: Darstellungs-Einstellungen folgen dem Benutzer auf andere Geraete."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import profile
from app.auth.service import create_login_session
from app.core.config import settings
from app.database.models import Account
from app.database.session import create_session


def _client_for(is_developer: bool) -> TestClient:
    session = create_session()
    try:
        account = Account(login_name=f"prefs-{uuid4().hex[:8]}@x.invalid", display_name="Pref", credential_digest="t", is_developer=is_developer)
        session.add(account)
        session.flush()
        selector, _ = create_login_session(session, account.id)
        session.commit()
    finally:
        session.close()
    app = FastAPI()
    app.include_router(profile.router)
    client = TestClient(app)
    client.cookies.set(settings.auth_cookie_name, selector)
    return client


def test_preferences_round_trip_and_validation():
    client = _client_for(is_developer=False)
    assert client.get("/api/profile/preferences").json() == {"preferences": None}

    saved = client.put("/api/profile/preferences", json={"theme": "dark", "text_size": "large", "density": "compact", "sidebar_collapsed": True, "developer_mode": True})
    assert saved.status_code == 200
    # Entwicklermodus nur fuer Entwicklerkonten
    assert saved.json()["preferences"]["developer_mode"] is False
    assert client.get("/api/profile/preferences").json()["preferences"] == {
        "theme": "dark", "text_size": "large", "density": "compact", "sidebar_collapsed": True, "developer_mode": False, "list_text_size": "same",
    }

    assert client.put("/api/profile/preferences", json={"theme": "pink"}).status_code == 422
    assert client.put("/api/profile/preferences", json={"theme": "dark", "script": "x"}).status_code == 422


def test_developer_may_keep_developer_mode_and_anonymous_is_rejected():
    client = _client_for(is_developer=True)
    assert client.put("/api/profile/preferences", json={"developer_mode": True}).json()["preferences"]["developer_mode"] is True
    anonymous = TestClient(client.app)
    assert anonymous.get("/api/profile/preferences").status_code == 401


def test_preferences_accept_the_smaller_sizes_and_a_list_size():
    from app.api.routes.profile import UiPreferences

    value = UiPreferences(text_size="xsmall", list_text_size="small")
    assert (value.text_size, value.list_text_size) == ("xsmall", "small")
    assert UiPreferences().list_text_size == "same"
    try:
        UiPreferences(text_size="huge")
    except ValueError:
        pass
    else:
        raise AssertionError("unbekannte Größe muss abgelehnt werden")
