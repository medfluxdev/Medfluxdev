"""DB-free regression tests for deployment/auth safety posture."""

import pytest

from app.core.config import Settings


def _settings(**overrides) -> Settings:
    base = {
        "app_env": "development",
        "auth_enabled": False,
        "app_secret_key": "change-me",
        "auth_cookie_secure": False,
        "medflux_insecure_dev": False,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def test_development_may_run_without_auth_only_with_explicit_opt_in():
    settings = _settings(medflux_insecure_dev=True)
    settings.validate_auth_runtime()
    with pytest.raises(RuntimeError, match="MEDFLUX_INSECURE_DEV=true"):
        Settings(
            _env_file=None,
            app_env="development",
            auth_enabled=False,
            medflux_insecure_dev=False,
        ).validate_auth_runtime()


def test_insecure_dev_opt_in_rejected_for_pilot():
    settings = _settings(
        app_env="pilot",
        auth_enabled=True,
        app_secret_key="test-secret-not-default",
        auth_cookie_secure=True,
        medflux_insecure_dev=True,
    )
    with pytest.raises(RuntimeError, match="MEDFLUX_INSECURE_DEV=true"):
        settings.validate_auth_runtime()


def test_insecure_dev_opt_in_rejected_for_production():
    settings = _settings(
        app_env="production",
        auth_enabled=True,
        app_secret_key="production-secret-placeholder-for-test",
        auth_cookie_secure=True,
        medflux_insecure_dev=True,
    )
    with pytest.raises(RuntimeError, match="MEDFLUX_INSECURE_DEV=true"):
        settings.validate_auth_runtime()


def test_production_cannot_run_without_auth():
    settings = _settings(app_env="production")
    with pytest.raises(RuntimeError, match="AUTH_ENABLED=true"):
        settings.validate_auth_runtime()


def test_pilot_requires_secure_cookie():
    settings = _settings(
        app_env="pilot",
        auth_enabled=True,
        app_secret_key="test-secret-not-default",
        auth_cookie_secure=False,
    )
    with pytest.raises(RuntimeError, match="AUTH_COOKIE_SECURE=true"):
        settings.validate_auth_runtime()


def test_auth_cannot_use_default_secret():
    settings = _settings(auth_enabled=True, app_secret_key="change-me")
    with pytest.raises(RuntimeError, match="APP_SECRET_KEY"):
        settings.validate_auth_runtime()


def test_valid_production_security_posture_passes():
    settings = _settings(
        app_env="production",
        auth_enabled=True,
        app_secret_key="production-secret-placeholder-for-test",
        auth_cookie_secure=True,
    )
    settings.validate_auth_runtime()


def test_unknown_deployment_mode_is_rejected():
    settings = _settings(app_env="mystery")
    with pytest.raises(RuntimeError, match="APP_ENV"):
        settings.validate_auth_runtime()


def test_samesite_none_requires_secure_cookie():
    settings = _settings(
        auth_cookie_samesite="none",
        auth_cookie_secure=False,
    )
    with pytest.raises(RuntimeError, match="AUTH_COOKIE_SECURE=true"):
        settings.validate_auth_runtime()


def test_authenticated_runtime_rejects_cors_wildcard():
    settings = _settings(
        auth_enabled=True,
        app_secret_key="test-secret-not-default",
        cors_origins="*",
    )
    with pytest.raises(RuntimeError, match="CORS-Wildcard"):
        settings.validate_auth_runtime()


def test_auth_disabled_runtime_rejects_cors_wildcard():
    settings = _settings(
        auth_enabled=False,
        cors_origins="*",
    )
    with pytest.raises(RuntimeError, match="CORS-Wildcard"):
        settings.validate_auth_runtime()
