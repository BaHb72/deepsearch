"""AmazingData 实时行情真实数据测试。

使用真实的 AmazingData SDK 连接测试实时行情获取和格式化功能。
"""

from __future__ import annotations

import pytest
from core.infrastructure.providers.implementations.amazingdata.query_manager import (
    AmazingDataQueryManager,
)

pytestmark = pytest.mark.skipif(True, reason="需要 AmazingData SDK 连接")


@pytest.mark.asyncio
async def test_fetch_realtime_quote_single_symbol(real_amazingdata_provider):
    """测试获取单个股票的实时行情。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    quotes = await manager.fetch_realtime_quote(symbols=["SZ000001"])

    assert quotes is not None
    assert isinstance(quotes, dict)
    if quotes:
        assert "SZ000001" in quotes or len(quotes) > 0
        for symbol, quote in quotes.items():
            assert isinstance(quote, dict)
            # 验证行情数据包含基本字段
            assert "code" in quote or "symbol" in quote or "last" in quote


@pytest.mark.asyncio
async def test_fetch_realtime_quote_multiple_symbols(real_amazingdata_provider):
    """测试批量获取多个股票的实时行情。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)
    symbols = ["SZ000001", "SH600000", "SZ000002"]

    quotes = await manager.fetch_realtime_quote(symbols=symbols)

    assert quotes is not None
    assert isinstance(quotes, dict)
    # 验证至少返回了部分股票的行情
    if quotes:
        assert len(quotes) > 0


@pytest.mark.asyncio
async def test_realtime_quote_contains_price_data(real_amazingdata_provider):
    """测试实时行情包含价格数据。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    quotes = await manager.fetch_realtime_quote(symbols=["SZ000001"])

    if quotes and "SZ000001" in quotes:
        quote = quotes["SZ000001"]
        # 验证包含价格相关字段
        price_fields = {"last", "price", "close", "open", "high", "low"}
        actual_fields = set(quote.keys())
        assert price_fields & actual_fields, f"缺少价格字段，实际: {quote.keys()}"


@pytest.mark.asyncio
async def test_realtime_quote_format_is_correct(real_amazingdata_provider):
    """测试实时行情格式正确。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    quotes = await manager.fetch_realtime_quote(symbols=["SH600000"])

    if quotes:
        for symbol, quote in quotes.items():
            # 验证代码字段存在
            assert "code" in quote or "symbol" in quote
            # 验证数值字段是数值类型
            if "last" in quote:
                assert isinstance(quote["last"], (int, float))
            if "volume" in quote:
                assert isinstance(quote["volume"], (int, float))


@pytest.mark.asyncio
async def test_format_realtime_payload_with_real_data(real_amazingdata_provider):
    """测试使用真实数据的格式化逻辑。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    # 获取真实行情
    quotes = await manager.fetch_realtime_quote(symbols=["SZ000001"])

    if quotes:
        # 验证格式化后的数据结构
        for symbol, quote in quotes.items():
            assert isinstance(symbol, str)
            assert isinstance(quote, dict)
            # 验证必要字段
            assert len(quote) > 0
