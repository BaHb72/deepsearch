"""AmazingData SafeWrapper 真实数据测试。

使用真实的 AmazingData SDK 测试安全包装器功能。
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_safe_wrapper_connection(real_amazingdata_provider):
    """测试安全包装器连接状态。"""
    # 验证 provider 已连接
    assert real_amazingdata_provider._connected is True


@pytest.mark.asyncio
async def test_safe_wrapper_execute_query(real_amazingdata_provider):
    """测试安全包装器执行查询。"""
    from core.infrastructure.providers.implementations.amazingdata.query_manager import (
        AmazingDataQueryManager,
    )

    manager = AmazingDataQueryManager(real_amazingdata_provider)

    # 执行查询
    quotes = await manager.fetch_realtime_quote(symbols=["SZ000001"])

    assert quotes is not None


@pytest.mark.asyncio
async def test_safe_wrapper_multiple_queries(real_amazingdata_provider):
    """测试安全包装器多次查询。"""
    from core.infrastructure.providers.implementations.amazingdata.query_manager import (
        AmazingDataQueryManager,
    )

    manager = AmazingDataQueryManager(real_amazingdata_provider)

    # 多次查询
    for _ in range(3):
        quotes = await manager.fetch_realtime_quote(symbols=["SZ000001"])
        assert quotes is not None

    # 验证连接仍然正常
    assert real_amazingdata_provider._connected is True


@pytest.mark.asyncio
async def test_safe_wrapper_stats(real_amazingdata_provider):
    """测试安全包装器统计。"""
    if hasattr(real_amazingdata_provider, "_stats"):
        stats = real_amazingdata_provider._stats
        assert isinstance(stats, dict)
