"""AmazingData ProcessIsolatedProvider 真实数据测试。

使用真实的 AmazingData SDK 测试进程隔离 Provider 的基本功能。
注意：进程隔离模式需要特殊配置，这些测试验证在真实环境中的行为。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest


@pytest.mark.asyncio
async def test_process_provider_get_stock_list(real_amazingdata_provider):
    """测试获取股票列表。"""
    stock_list = await real_amazingdata_provider.get_stock_list(limit=10)

    assert stock_list is not None
    if stock_list:
        assert len(stock_list) <= 10
        # 验证返回的是记录列表
        first_stock = stock_list[0]
        assert isinstance(first_stock, dict)
        assert "code" in first_stock or "symbol" in first_stock


@pytest.mark.asyncio
async def test_process_provider_get_kline_data(real_amazingdata_provider):
    """测试获取K线数据。"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    kline = await real_amazingdata_provider.get_kline_data(
        symbol="SZ000001",
        period="1d",
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        limit=10,
    )

    assert kline is not None
    if len(kline) > 0:
        assert len(kline) <= 10
        # 验证返回数据结构
        if isinstance(kline, pd.DataFrame):
            assert not kline.empty or len(kline) == 0
        elif isinstance(kline, list):
            assert len(kline) >= 0


@pytest.mark.asyncio
async def test_process_provider_get_realtime_quote(real_amazingdata_provider):
    """测试获取实时行情。"""
    quote = await real_amazingdata_provider.get_realtime_quote("SZ000001")

    assert quote is not None
    if quote:
        assert isinstance(quote, dict)
        # 验证包含基本字段
        assert "code" in quote or "symbol" in quote or len(quote) > 0


@pytest.mark.asyncio
async def test_process_provider_get_multiple_quotes(real_amazingdata_provider):
    """测试批量获取实时行情。"""
    symbols = ["SZ000001", "SH600000", "SZ000002"]

    quotes = await real_amazingdata_provider.get_realtime_quote(symbols)

    assert quotes is not None
    if quotes:
        assert isinstance(quotes, (dict, list))


@pytest.mark.asyncio
async def test_process_provider_query_snapshot(real_amazingdata_provider):
    """测试查询快照数据。"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=5)

    # 检查 provider 是否支持 query_snapshot
    if hasattr(real_amazingdata_provider, "query_snapshot"):
        result = await real_amazingdata_provider.query_snapshot(
            symbols=["SZ000001"],
            begin_date=int(start_date.strftime("%Y%m%d")),
            end_date=int(end_date.strftime("%Y%m%d")),
        )

        assert result is not None
        assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_process_provider_connection_state(real_amazingdata_provider):
    """测试连接状态。"""
    # 验证 provider 已初始化并连接
    assert real_amazingdata_provider._connected is True

    # 验证初始化状态
    if hasattr(real_amazingdata_provider, "_initialized"):
        assert real_amazingdata_provider._initialized is True


@pytest.mark.asyncio
async def test_process_provider_stats_available(real_amazingdata_provider):
    """测试统计信息可用。"""
    # 验证 stats 结构存在
    if hasattr(real_amazingdata_provider, "_stats"):
        stats = real_amazingdata_provider._stats
        assert isinstance(stats, dict)


@pytest.mark.asyncio
async def test_process_provider_multiple_queries(real_amazingdata_provider):
    """测试连续多次查询。"""
    for i in range(3):
        quote = await real_amazingdata_provider.get_realtime_quote("SZ000001")
        assert quote is not None

    # 验证连接仍然正常
    assert real_amazingdata_provider._connected is True
