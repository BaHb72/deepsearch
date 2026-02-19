"""Provider FastAPI 集成兼容逻辑测试。"""

from __future__ import annotations

from types import SimpleNamespace

from core.config.models.data_sources import DataSourceProviderConfig, DataSourcesConfig
from core.infrastructure.providers.integration.fastapi import _iter_enabled_provider_configs


def test_iter_enabled_provider_configs_reads_datasources_model() -> None:
    settings = SimpleNamespace(
        data_sources=DataSourcesConfig(
            providers={
                "amazingdata": DataSourceProviderConfig(
                    enabled=True,
                    priority=10,
                    mode="distributed",
                    config={
                        "connection": {
                            "username": "u",
                            "password": "p",
                            "host": "127.0.0.1",
                            "port": 8600,
                        }
                    },
                ),
                "akshare": DataSourceProviderConfig(enabled=False, config={"proxy": True}),
            }
        )
    )

    providers = _iter_enabled_provider_configs(settings)

    assert len(providers) == 1
    name, config = providers[0]
    assert name == "amazingdata"
    assert config["enabled"] is True
    assert config["priority"] == 10
    assert config["mode"] == "distributed"
    assert "config" in config
    assert "connection" in config["config"]


def test_iter_enabled_provider_configs_keeps_nested_provider_config() -> None:
    settings = SimpleNamespace(
        data_sources=DataSourcesConfig(
            providers={
                "akshare": DataSourceProviderConfig(
                    enabled=True,
                    priority=3,
                    config={
                        "mode": "proxy",
                        "proxy": {"timeout": 15, "worker_url": "https://worker.example.com"},
                    },
                ),
            }
        )
    )

    providers = _iter_enabled_provider_configs(settings)

    assert len(providers) == 1
    name, payload = providers[0]
    assert name == "akshare"
    assert payload["enabled"] is True
    assert payload["priority"] == 3
    assert payload["config"]["mode"] == "proxy"
    assert payload["config"]["proxy"]["timeout"] == 15


def test_iter_enabled_provider_configs_returns_empty_when_missing_data_sources() -> None:
    settings = SimpleNamespace()
    providers = _iter_enabled_provider_configs(settings)
    assert providers == []
