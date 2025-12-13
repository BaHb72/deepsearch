"""数据源配置迁移工具的单元测试。"""

from deepsearch.config.migrations import migrate_data_source_config


def test_migrate_legacy_provider_blocks():
    raw_config = {
        "amazingdata": {
            "enabled": True,
            "username": "legacy_user",
            "password": "legacy_pass",
            "host": "127.0.0.1",
            "port": 8600,
            "timeout": 10,
            "heartbeat_interval": 60,
            "auto_reconnect": True,
            "reconnect_interval": 5,
            "network_provider": "telecom",
            "local_path": "D://cache",
            "use_local": True,
            "subscription_enabled": True,
            "subscription_batch_size": 200,
            "max_subscriptions": 600,
        },
        "cloudflare_workers": {
            "worker_url": "https://example.workers.dev",
            "api_key": "test-key",
            "timeout": 30,
            "retry_count": 3,
            "cache_enabled": True,
            "cache_ttl": 180,
        },
        "qmt": {
            "enabled": True,
            "host": "localhost",
            "port": 8888,
        },
        "data_providers": {
            "amazingdata": {"enabled": True, "priority": 0},
            "cloudflare_proxy": {"enabled": True, "priority": 1},
            "akshare": {"enabled": False, "priority": 2, "config": {"mode": "worker"}},
            "qmt": {"enabled": False, "priority": 3},
            "circuit_breaker": {"enabled": True, "failure_threshold": 5},
            "failover": {"enabled": True, "retry_count": 2},
        },
    }

    migrated, changed = migrate_data_source_config(raw_config, source_path=None)

    assert changed is True
    providers = migrated["data_sources"]["providers"]

    amazing = providers["amazingdata"]
    assert amazing["enabled"] is True
    assert amazing["priority"] == 0
    connection = amazing["config"]["connection"]
    assert connection["username"] == "legacy_user"
    assert connection["password"] == "legacy_pass"
    assert amazing["has_saved_credential"] is True
    assert "amazingdata" not in migrated

    # cloudflare 配置被合并到 akshare 的 proxy 配置中
    akshare = providers["akshare"]
    assert akshare["enabled"] is True
    assert akshare["config"]["mode"] == "proxy"
    proxy_config = akshare["config"]["proxy"]
    assert proxy_config["worker_url"] == "https://example.workers.dev"
    assert proxy_config["cache"]["ttl"] == 180
    assert "cloudflare_workers" not in migrated

    qmt = providers["qmt"]
    assert qmt["config"]["connection"]["host"] == "localhost"
    assert "qmt" not in migrated

    assert migrated["data_sources"]["default"] == "amazingdata"
    assert migrated["data_sources"]["fallback_order"][0] == "amazingdata"
    assert migrated["data_sources"]["circuit_breaker"]["enabled"] is True


def test_preserve_existing_new_structure():
    raw_config = {
        "data_sources": {
            "providers": {
                "amazingdata": {
                    "enabled": False,
                    "priority": 5,
                    "config": {
                        "connection": {
                            "username": "new_user",
                            "password": "new_pass",
                        }
                    },
                }
            }
        },
        "amazingdata": {"username": "legacy_user"},
    }

    migrated, changed = migrate_data_source_config(raw_config, source_path=None)

    providers = migrated["data_sources"]["providers"]
    connection = providers["amazingdata"]["config"]["connection"]
    assert connection["username"] == "new_user"
    assert providers["amazingdata"]["has_saved_credential"] is True
    assert changed is True


def test_no_op_when_already_migrated():
    raw_config = {
        "data_sources": {
            "default": "amazingdata",
            "fallback_order": ["amazingdata", "cloudflare"],
            "providers": {
                "amazingdata": {
                    "enabled": True,
                    "priority": 0,
                    "config": {
                        "connection": {
                            "username": "user",
                            "password": "pass",
                        }
                    },
                    "has_saved_credential": True,
                }
            },
        }
    }

    migrated, changed = migrate_data_source_config(raw_config, source_path=None)

    assert changed is False
    assert migrated == raw_config
