import pytest

def test_default_settings():
    from core.config import Settings
    settings = Settings()
    assert settings.APP_NAME == "ERP9lli API"
    assert settings.APP_DEBUG is False
    assert isinstance(settings.REDIS_PORT, int)
    assert settings.REDIS_PORT == 6379
    assert isinstance(settings.SMTP_ENABLED, bool)
    assert settings.is_module_enabled("orders") is True

def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Custom Bio ERP")
    monkeypatch.setenv("SMTP_ENABLED", "true")
    monkeypatch.setenv("REDIS_PORT", "7000")
    monkeypatch.setenv("ENABLED_MODULES", "orders,invoicing")

    from core.config import Settings
    settings = Settings()
    assert settings.APP_NAME == "Custom Bio ERP"
    assert settings.SMTP_ENABLED is True
    assert settings.REDIS_PORT == 7000
    assert settings.is_module_enabled("orders") is True
    assert settings.is_module_enabled("invoicing") is True
    assert settings.is_module_enabled("warehouse") is False

def test_get_settings_cached():
    from core.config import get_settings
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
