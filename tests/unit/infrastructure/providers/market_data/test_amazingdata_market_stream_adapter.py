"""AmazingData Market Stream Adapter 真实数据测试。

使用真实的 AmazingData SDK 测试行情流适配器功能。
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_market_stream_connection(real_amazingdata_provider):
    """测试行情流连接。"""
    assert real_amazingdata_provider._connected is True


@pytest.mark.asyncio
async def test_market_stream_realtime_quote(real_amazingdata_provider):
    """测试行情流实时行情。"""
    from deepsearch.infrastructure.providers.implementations.amazingdata.query_manager import (
        AmazingDataQueryManager,
    )

    manager = AmazingDataQueryManager(real_amazingdata_provider)
    quotes = await manager.fetch_realtime_quote(symbols=["SZ000001", "SH600000"])

    assert quotes is not None
    if quotes:
        assert isinstance(quotes, dict)


@pytest.mark.asyncio
async def test_market_stream_multiple_symbols(real_amazingdata_provider):
    """测试行情流多个股票。"""
    from deepsearch.infrastructure.providers.implementations.amazingdata.query_manager import (
        AmazingDataQueryManager,
    )

    manager = AmazingDataQueryManager(real_amazingdata_provider)
    symbols = ["SZ000001", "SH600000", "SZ000002"]

    quotes = await manager.fetch_realtime_quote(symbols=symbols)

    assert quotes is not None
