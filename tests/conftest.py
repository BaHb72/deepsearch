"""项目级 pytest 固件。

除 WebUI 的 ``client`` 固件外，这里还集中提供在多个测试模块中
复用的简单数据提供者与配置对象模拟，避免各测试文件重复定义
或遗漏导致的 "fixture not found" 错误。
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from apps.api.server import app

os.environ.setdefault("DEEPSEARCH_TEST_MODE", "true")


@pytest.fixture(scope="function")
def client() -> TestClient:
    """提供轻量级 FastAPI TestClient。"""

    app.state.rate_limit_test_mode = True
    client = TestClient(app, headers={"X-Test-Mode": "true"})
    try:
        yield client
    finally:
        client.close()


@pytest.fixture(scope="function")
def mock_config() -> SimpleNamespace:
    """构造可变的配置对象模拟。

    采用 ``SimpleNamespace`` 便于在测试内部直接修改字段，
    同时包含最常用的 ``app``、``database`` 与 ``amazingdata``
    结构，以满足配置相关测试的读取需求。
    """

    def _build_main_db() -> SimpleNamespace:
        main_db = SimpleNamespace(
            enabled=True,
            type="postgresql",
            host="localhost",
            port=5432,
            database="deepsearch",
            username="postgres",
            password="",
            auto_connect=False,
        )

        def _get_url() -> str:
            user = main_db.username
            password_part = f":{main_db.password}" if main_db.password else ""
            return (
                f"postgresql://{user}{password_part}@{main_db.host}:{main_db.port}/"
                f"{main_db.database}"
            )

        main_db.get_url = _get_url  # type: ignore[attr-defined]
        return main_db

    config = SimpleNamespace(
        app=SimpleNamespace(name="DeepSearch", env="test", debug=False),
        database=SimpleNamespace(
            main=_build_main_db(),
            cache=SimpleNamespace(
                enabled=True,
                host="localhost",
                port=6379,
                username="",
                password="",
                db=0,
            ),
        ),
        amazingdata=SimpleNamespace(
            connection=SimpleNamespace(
                username="demo_user",
                password="demo_password",
                host="localhost",
                port=8600,
                timeout=10,
            ),
        ),
        data_providers={
            "amazingdata": {"enabled": True, "priority": 1},
            "cloudflare": {"enabled": True, "priority": 2},
        },
    )

    return config


@pytest.fixture(scope="function")
def test_data_provider() -> AsyncMock:
    """创建通用的数据提供者模拟。"""

    provider = AsyncMock()
    provider.is_connected = Mock(return_value=True)
    provider.get_realtime_quote = AsyncMock(
        return_value={
            "symbol": "000001",
            "price": 10.5,
            "change": 0.12,
            "change_pct": 1.15,
            "volume": 1_200_000,
        }
    )
    provider.get_multiple_quotes = AsyncMock(
        return_value=[
            {
                "symbol": "000001",
                "price": 10.5,
                "change": 0.12,
                "change_pct": 1.15,
                "volume": 1_200_000,
            },
            {
                "symbol": "000002",
                "price": 11.2,
                "change": -0.05,
                "change_pct": -0.45,
                "volume": 980_000,
            },
        ]
    )
    provider.supported_data_types = ["realtime_quote", "multiple_quotes"]
    return provider


@pytest.fixture(scope="function")
def mock_redis() -> SimpleNamespace:
    """提供可按需配置的 Redis 客户端模拟。"""

    redis_methods: Dict[str, Any] = {
        "info": AsyncMock(),
        "flushall": AsyncMock(),
        "keys": AsyncMock(),
        "delete": AsyncMock(),
        "ttl": AsyncMock(),
        "expire": AsyncMock(),
    }
    redis_namespace = SimpleNamespace(**redis_methods)
    redis_namespace.connection_pool = SimpleNamespace()  # 便于额外属性访问
    return redis_namespace


# ============================================================================
# 真实数据测试 Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def real_amazingdata_sdk():
    """提供真实的 AmazingData SDK 连接。

    如果 SDK 未安装或配置无效，自动跳过测试。
    使用 module scope 避免重复登录。
    """
    try:
        import AmazingData as ad
    except ImportError:
        pytest.skip("AmazingData SDK 未安装")

    from core.config import get_config

    config = get_config()

    # 尝试获取配置 (兼容Pydantic模型和字典两种格式)
    credentials = None
    try:
        ds = config.data_sources
        if ds and hasattr(ds, "providers"):
            providers = ds.providers
            # providers 可能是字典或 Pydantic 模型
            if isinstance(providers, dict):
                ad_provider = providers.get("amazingdata")
            else:
                ad_provider = getattr(providers, "amazingdata", None) or providers.get(
                    "amazingdata", None
                )

            if ad_provider:
                # 获取 enabled 状态
                enabled = (
                    getattr(ad_provider, "enabled", False)
                    if hasattr(ad_provider, "enabled")
                    else ad_provider.get("enabled", False)
                )

                if enabled:
                    # 获取连接配置
                    ad_config = getattr(ad_provider, "config", None) or ad_provider.get(
                        "config", {}
                    )
                    if ad_config:
                        conn = getattr(ad_config, "connection", None) or ad_config.get(
                            "connection", {}
                        )
                        if conn:
                            credentials = {
                                "host": getattr(conn, "host", "") or conn.get("host", ""),
                                "port": getattr(conn, "port", 8600) or conn.get("port", 8600),
                                "username": getattr(conn, "username", "")
                                or conn.get("username", ""),
                                "password": getattr(conn, "password", "")
                                or conn.get("password", ""),
                            }
    except Exception as e:
        pytest.skip(f"获取AmazingData配置失败: {e}")

    if not credentials or not credentials.get("username"):
        pytest.skip("AmazingData 未配置有效凭证")

    # 登录
    try:
        result = ad.login(
            username=credentials["username"],
            password=credentials["password"],
            host=credentials["host"],
            port=credentials["port"],
        )
        if result not in (0, True):
            pytest.skip(f"AmazingData 登录失败: {result}")
    except Exception as e:
        pytest.skip(f"AmazingData 连接失败: {e}")

    yield ad

    # 清理
    try:
        ad.logout()
    except Exception:
        pass


@pytest.fixture(scope="function")
async def real_amazingdata_provider():
    """提供真实的 AmazingData Provider 实例。

    使用 DataSourceManager 获取已配置的 Provider。
    如果未配置或未启用，自动跳过测试。
    """
    from core.infrastructure.providers.managers.data_source_manager import get_data_source_manager
    from core.ports.data_sources import DataSourceType

    manager = get_data_source_manager()
    await manager.initialize()

    if not manager.is_provider_enabled(DataSourceType.AMAZINGDATA):
        pytest.skip("AmazingData 未启用")

    provider = manager.get_provider(DataSourceType.AMAZINGDATA)
    if provider is None:
        pytest.skip("无法获取 AmazingData Provider 实例")

    yield provider


@pytest.fixture(scope="function")
def real_query_manager(real_amazingdata_provider):
    """提供真实的 AmazingDataQueryManager 实例。"""
    from core.infrastructure.providers.implementations.amazingdata.query_manager import (
        AmazingDataQueryManager,
    )

    return AmazingDataQueryManager(real_amazingdata_provider)
