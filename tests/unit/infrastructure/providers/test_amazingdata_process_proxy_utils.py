"""AmazingData Process Proxy Utils 真实数据测试。

使用真实的 AmazingData SDK 测试代理工具功能。
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_proxy_connection_valid(real_amazingdata_provider):
    """测试代理连接有效。"""
    assert real_amazingdata_provider._connected is True


@pytest.mark.asyncio
async def test_proxy_query_execution(real_amazingdata_provider):
    """测试通过代理执行查询。"""
    from core.infrastructure.providers.implementations.amazingdata.query_manager import (
        AmazingDataQueryManager,
    )

    manager = AmazingDataQueryManager(real_amazingdata_provider)
    quotes = await manager.fetch_realtime_quote(symbols=["SZ000001"])

    assert quotes is not None


@pytest.mark.asyncio
async def test_proxy_stats_available(real_amazingdata_provider):
    """测试代理统计可用。"""
    if hasattr(real_amazingdata_provider, "_stats"):
        stats = real_amazingdata_provider._stats
        assert isinstance(stats, dict)
