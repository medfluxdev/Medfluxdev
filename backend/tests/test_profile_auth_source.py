from pathlib import Path


def test_profile_resolves_account_from_the_login_cookie():
    source = Path("app/api/routes/profile.py").read_text(encoding="utf-8")
    assert "account_from_selector(session, selector)" in source
    assert "request.cookies.get(settings.auth_cookie_name" in source
    assert 'getattr(request.state, "account_id", None)' not in source
