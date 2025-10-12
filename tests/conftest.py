"""项目级 pytest 固件。

除 WebUI 的 ``client`` 固件外，这里还集中提供在多个测试模块中
复用的简单数据提供者与配置对象模拟，避免各测试文件重复定义
或遗漏导致的 "fixture not found" 错误。
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from deepsearch.webui.server import app


@pytest.fixture(scope="function")
def client() -> TestClient:
    """提供轻量级 FastAPI TestClient。"""

    with TestClient(app) as c:
        yield c


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
