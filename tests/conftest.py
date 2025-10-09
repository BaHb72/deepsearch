"""
Pytest configuration and fixtures for DeepSearch tests.
"""

import asyncio
import gc
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture(scope="function")
def event_loop():
    """
    Create an isolated event loop for each test function.

    使用function级别的作用域确保每个测试都有独立的事件循环，
    避免测试之间的状态污染和并发问题。
    """
    # 创建新的事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    yield loop

    # 清理：取消所有未完成的任务
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        # 等待所有任务完成取消
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    finally:
        # 关闭事件循环
        loop.close()

        # 清理事件循环引用
        asyncio.set_event_loop(None)

        # 强制垃圾回收
        gc.collect()


@pytest.fixture(autouse=True)
def reset_singletons():
    """
    自动重置单例对象，确保测试隔离。

    这个fixture会在每个测试前后自动运行，
    清理可能存在的单例状态。
    """
    # 测试前不需要做什么
    yield

    # 测试后清理单例
    # 这里可以添加具体的单例重置逻辑
    # 例如：ConfigManager._instance = None
    gc.collect()


@pytest.fixture
def mock_config():
    """Mock configuration for testing."""
    config = Mock()
    config.database.main.enabled = True
    config.database.cache.enabled = True
    config.data_providers.amazingdata.enabled = True
    config.data_providers.qmt.enabled = True
    config.data_providers.akshare.enabled = True
    config.data_providers.akshare.config = {"mode": "worker", "proxy": {"enabled": True}}
    config.data_providers.cloudflare.enabled = True
    config.webui.enabled = True  # 添加WebUI配置
    config.webui.backend_port = 8000
    config.webui.frontend_port = 3000
    return config


@pytest.fixture
async def isolated_redis_mock():
    """
    隔离的Redis mock，每个测试独立。

    使用新的名称避免与旧的fixture冲突，
    并提供更完整的mock实现。
    """
    redis = AsyncMock()

    # 模拟Redis基本操作
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=False)
    redis.expire = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=-2)

    # 模拟Redis批量操作
    redis.mget = AsyncMock(return_value=[])
    redis.mset = AsyncMock(return_value=True)
    redis.pipeline = AsyncMock(return_value=AsyncMock())

    # 模拟Redis连接管理
    redis.ping = AsyncMock(return_value=True)
    redis.close = AsyncMock()
    redis.wait_closed = AsyncMock()

    yield redis

    # 清理：确保mock被正确关闭
    await redis.close()
    await redis.wait_closed()


@pytest.fixture
async def mock_redis():
    """
    兼容性fixture，使用isolated_redis_mock。

    保留这个fixture是为了向后兼容。
    """
    redis = AsyncMock()

    # 模拟Redis基本操作
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.exists = AsyncMock(return_value=False)
    redis.expire = AsyncMock(return_value=True)
    redis.ttl = AsyncMock(return_value=-2)

    # 模拟Redis批量操作
    redis.mget = AsyncMock(return_value=[])
    redis.mset = AsyncMock(return_value=True)
    redis.pipeline = AsyncMock(return_value=AsyncMock())

    # 模拟Redis连接管理
    redis.ping = AsyncMock(return_value=True)
    redis.close = AsyncMock()
    redis.wait_closed = AsyncMock()

    return redis


@pytest.fixture
def test_data_provider():
    """Mock data provider for testing."""
    provider = AsyncMock()
    provider.get_realtime_quote = AsyncMock(
        return_value={
            "symbol": "000001",
            "name": "平安银行",
            "price": 10.5,
            "change": 0.5,
            "change_pct": 5.0,
            "volume": 1000000,
            "timestamp": "2025-09-13 10:00:00",
        }
    )
    provider.get_kline_data = AsyncMock(return_value=[])
    provider.is_connected = Mock(return_value=True)
    return provider
