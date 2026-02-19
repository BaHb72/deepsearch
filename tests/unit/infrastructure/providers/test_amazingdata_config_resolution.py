from core.infrastructure.providers.implementations.amazingdata.config import (
    ensure_amazingdata_provider_config,
)


def test_ensure_config_prefers_connection_over_legacy_top_level_fields() -> None:
    payload = {
        "mode": "distributed",
        "username": "demo_user",
        "password": "demo_password",
        "host": "1.2.3.4",
        "port": 8600,
        "connection": {
            "username": "real_user",
            "password": "real_password",
            "host": "101.230.159.234",
            "port": 8601,
            "timeout": 10,
        },
    }

    cfg = ensure_amazingdata_provider_config(payload)

    assert cfg.username == "real_user"
    assert cfg.password == "real_password"
    assert cfg.host == "101.230.159.234"
    assert cfg.port == 8601


def test_ensure_config_uses_top_level_when_connection_missing() -> None:
    payload = {
        "username": "top_user",
        "password": "top_password",
        "host": "9.9.9.9",
        "port": 8610,
    }

    cfg = ensure_amazingdata_provider_config(payload)

    assert cfg.username == "top_user"
    assert cfg.password == "top_password"
    assert cfg.host == "9.9.9.9"
    assert cfg.port == 8610
