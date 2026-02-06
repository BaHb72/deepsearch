"""数据源配置迁移工具的单元测试。

测试 migrate_data_source_config 的实际行为：
将旧格式 providers 节转换为新格式 data_sources 节。
"""

from core.config.migrations import migrate_data_source_config


def test_migrate_legacy_provider_blocks():
    """测试旧格式 providers 节迁移到 data_sources"""
    raw_config = {
        "providers": {
            "enabled": ["amazingdata", "akshare"],
            "default": "amazingdata",
            "amazingdata": {
                "ip": "127.0.0.1",
                "port": 8600,
                "username": "user",
                "password": "pass",
            },
            "akshare": {
                "mode": "proxy",
            },
        },
    }

    migrated, changed = migrate_data_source_config(raw_config, source_path=None)

    assert changed is True
    assert "providers" not in migrated
    assert "data_sources" in migrated

    ds = migrated["data_sources"]
    assert ds["default"] == "amazingdata"
    assert ds["fallback_order"] == ["amazingdata", "akshare"]

    providers = ds["providers"]
    assert providers["amazingdata"]["ip"] == "127.0.0.1"
    assert providers["amazingdata"]["port"] == 8600
    assert providers["akshare"]["mode"] == "proxy"


def test_preserve_existing_new_structure():
    """已有 data_sources 节时不做迁移"""
    raw_config = {
        "data_sources": {
            "providers": {
                "amazingdata": {
                    "ip": "127.0.0.1",
                }
            }
        },
        "providers": {
            "default": "amazingdata",
            "amazingdata": {"ip": "old"},
        },
    }

    migrated, changed = migrate_data_source_config(raw_config, source_path=None)

    # 已存在 data_sources 时，不会触发迁移
    assert changed is False
    # 原 data_sources 保持不变
    assert migrated["data_sources"]["providers"]["amazingdata"]["ip"] == "127.0.0.1"


def test_no_op_when_already_migrated():
    """既无 providers 也已有 data_sources 时无变更"""
    raw_config = {
        "data_sources": {
            "default": "amazingdata",
            "fallback_order": ["amazingdata"],
            "providers": {
                "amazingdata": {
                    "ip": "127.0.0.1",
                }
            },
        }
    }

    migrated, changed = migrate_data_source_config(raw_config, source_path=None)

    assert changed is False
    assert migrated == raw_config
