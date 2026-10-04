import pytest

from database import connection
from database.connection import get_database_pool_settings, get_engine


def test_database_pool_settings_default_to_small_pool(monkeypatch):
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)
    monkeypatch.delenv("DB_POOL_TIMEOUT", raising=False)
    monkeypatch.delenv("DB_POOL_RECYCLE", raising=False)

    settings = get_database_pool_settings()

    assert settings.pool_size == 2
    assert settings.max_overflow == 1
    assert settings.pool_timeout == 10
    assert settings.pool_recycle == 300


def test_get_engine_uses_configured_small_pool(monkeypatch):
    captured = {}

    def fake_create_engine(database_url, **kwargs):
        captured["database_url"] = database_url
        captured["kwargs"] = kwargs
        return object()

    get_engine.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:password@example.test/db",
    )
    monkeypatch.setenv("DB_POOL_SIZE", "3")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "2")
    monkeypatch.setenv("DB_POOL_TIMEOUT", "7")
    monkeypatch.setenv("DB_POOL_RECYCLE", "120")
    monkeypatch.setattr(connection, "create_engine", fake_create_engine)

    try:
        get_engine()
    finally:
        get_engine.cache_clear()

    assert captured["database_url"] == (
        "postgresql+psycopg://user:password@example.test/db?sslmode=require"
    )
    assert captured["kwargs"] == {
        "pool_pre_ping": True,
        "pool_size": 3,
        "max_overflow": 2,
        "pool_timeout": 7,
        "pool_recycle": 120,
    }


@pytest.mark.parametrize("env_value", ["invalid", "-1"])
def test_database_pool_settings_fall_back_for_bad_values(monkeypatch, env_value):
    monkeypatch.setenv("DB_POOL_SIZE", env_value)

    settings = get_database_pool_settings()

    assert settings.pool_size == 2
