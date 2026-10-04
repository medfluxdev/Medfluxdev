"""Security-Posture-Regressions-Tests (Security Phase-1, P1-3).

Sichern die fail-closed Defaults (P0-1) und die PostgreSQL-TLS-Policy (P1-1)
dauerhaft gegen Regressionen ab. DB-frei; baut nur Settings-Instanzen.
"""

import pytest

from app.core.config import Settings


def _settings(**overrides) -> Settings:
    base = {
        "app_env": "development",
        "auth_enabled": True,
        "app_secret_key": "security-posture-test-secret-2026",
        "auth_cookie_secure": False,
        "medflux_insecure_dev": False,
        "database_url": "postgresql+psycopg://medflux@127.0.0.1:5432/medflux",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_default_host_is_loopback():
    assert Settings.model_fields["backend_host"].default == "127.0.0.1"


def test_default_runtime_is_authenticated():
    assert Settings.model_fields["auth_enabled"].default is True
    assert Settings.model_fields["medflux_insecure_dev"].default is False


def test_default_runtime_does_not_silently_expose_unauthenticated_access():
    defaults = _settings(app_secret_key="change-me")
    with pytest.raises(RuntimeError, match="APP_SECRET_KEY"):
        defaults.validate_auth_runtime()


def test_insecure_dev_requires_explicit_opt_in():
    settings = _settings(auth_enabled=False)
    with pytest.raises(RuntimeError, match="MEDFLUX_INSECURE_DEV=true"):
        settings.validate_auth_runtime()
    ok = _settings(auth_enabled=False, medflux_insecure_dev=True)
    ok.validate_auth_runtime()


def test_insecure_dev_rejected_for_pilot():
    settings = _settings(
        app_env="pilot",
        auth_cookie_secure=True,
        medflux_insecure_dev=True,
    )
    with pytest.raises(RuntimeError, match="MEDFLUX_INSECURE_DEV=true"):
        settings.validate_auth_runtime()


def test_insecure_dev_rejected_for_production():
    settings = _settings(
        app_env="production",
        auth_cookie_secure=True,
        medflux_insecure_dev=True,
    )
    with pytest.raises(RuntimeError, match="MEDFLUX_INSECURE_DEV=true"):
        settings.validate_auth_runtime()


def test_auth_enabled_rejects_change_me_secret():
    settings = _settings(app_secret_key="change-me")
    with pytest.raises(RuntimeError, match="APP_SECRET_KEY"):
        settings.validate_auth_runtime()


def test_pilot_production_requires_auth():
    settings = _settings(app_env="pilot", auth_enabled=False, medflux_insecure_dev=True)
    with pytest.raises(RuntimeError, match="AUTH_ENABLED=true"):
        settings.validate_auth_runtime()
    settings = _settings(app_env="production", auth_enabled=False, medflux_insecure_dev=True)
    with pytest.raises(RuntimeError, match="AUTH_ENABLED=true"):
        settings.validate_auth_runtime()


def test_pilot_production_requires_secure_cookie():
    settings = _settings(app_env="pilot", auth_cookie_secure=False)
    with pytest.raises(RuntimeError, match="AUTH_COOKIE_SECURE=true"):
        settings.validate_auth_runtime()
    settings = _settings(app_env="production", auth_cookie_secure=False)
    with pytest.raises(RuntimeError, match="AUTH_COOKIE_SECURE=true"):
        settings.validate_auth_runtime()


def test_remote_pilot_postgres_without_tls_is_rejected():
    settings = _settings(
        app_env="pilot",
        auth_cookie_secure=True,
        database_url="postgresql+psycopg://user:pw@db.example.org:5432/medflux",
    )
    with pytest.raises(RuntimeError, match="sslmode"):
        settings.validate_database_tls()


def test_remote_production_postgres_without_tls_is_rejected():
    settings = _settings(
        app_env="production",
        auth_cookie_secure=True,
        database_url="postgresql+psycopg://user:pw@db.example.org:5432/medflux",
    )
    with pytest.raises(RuntimeError, match="sslmode"):
        settings.validate_database_tls()


def test_remote_postgres_with_secure_sslmode_is_accepted():
    for sslmode in ("require", "verify-ca", "verify-full"):
        settings = _settings(
            app_env="production",
            auth_cookie_secure=True,
            database_url=(
                "postgresql+psycopg://user:pw@db.example.org:5432/medflux"
                f"?sslmode={sslmode}"
            ),
        )
        settings.validate_database_tls()


def test_loopback_postgres_is_accepted_without_tls():
    for host in ("localhost", "127.0.0.1", "[::1]"):
        settings = _settings(
            app_env="production",
            auth_cookie_secure=True,
            database_url=f"postgresql+psycopg://medflux@{host}:5432/medflux",
        )
        settings.validate_database_tls()


def test_non_postgres_backend_is_not_policed():
    settings = _settings(
        app_env="production",
        auth_cookie_secure=True,
        database_url="sqlite:///./data/unit.db",
    )
    settings.validate_database_tls()


def test_dev_test_explicit_remote_exception_ignores_tls_policy():
    for env in ("development", "test"):
        settings = _settings(
            app_env=env,
            auth_enabled=False,
            medflux_insecure_dev=True,
            database_url="postgresql+psycopg://user:pw@db.example.org:5432/medflux",
        )
        settings.validate_auth_runtime()
        settings.validate_database_tls()