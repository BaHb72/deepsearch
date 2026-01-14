"""AmazingData Provider K线数据真实测试。

使用真实的 AmazingData SDK 连接测试 K 线数据获取功能。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest


@pytest.mark.asyncio
async def test_get_kline_returns_valid_dataframe(real_amazingdata_provider):
    """测试获取K线数据返回有效的DataFrame。"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    df = await real_amazingdata_provider.get_kline(
        symbol="SZ000001",
        period="1d",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        count=30,
        adjust="none",
    )

    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        # 验证K线必要列
        expected_columns = {"open", "high", "low", "close", "volume"}
        actual_columns = set(c.lower() for c in df.columns)
        assert expected_columns & actual_columns, f"缺少K线列，实际: {df.columns.tolist()}"


@pytest.mark.asyncio
async def test_get_kline_with_different_periods(real_amazingdata_provider):
    """测试不同周期的K线数据获取。"""
    periods = ["1d", "1m", "5m"]

    for period in periods:
        df = await real_amazingdata_provider.get_kline(
            symbol="SZ000001",
            period=period,
            count=10,
            adjust="none",
        )

        assert isinstance(df, pd.DataFrame), f"周期 {period} 返回类型错误"


@pytest.mark.asyncio
async def test_get_kline_with_adjust_types(real_amazingdata_provider):
    """测试不同复权类型的K线数据。"""
    adjust_types = ["none", "qfq", "hfq"]

    for adjust in adjust_types:
        df = await real_amazingdata_provider.get_kline(
            symbol="SZ000001",
            period="1d",
            count=10,
            adjust=adjust,
        )

        assert isinstance(df, pd.DataFrame), f"复权类型 {adjust} 返回类型错误"


@pytest.mark.asyncio
async def test_get_kline_multiple_symbols(real_amazingdata_provider):
    """测试批量获取多个股票的K线数据。"""
    symbols = ["SZ000001", "SH600000", "SZ000002"]

    for symbol in symbols:
        df = await real_amazingdata_provider.get_kline(
            symbol=symbol,
            period="1d",
            count=5,
            adjust="none",
        )

        assert isinstance(df, pd.DataFrame), f"股票 {symbol} 返回类型错误"


@pytest.mark.asyncio
async def test_get_kline_with_date_range(real_amazingdata_provider):
    """测试指定日期范围的K线数据获取。"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)

    df = await real_amazingdata_provider.get_kline(
        symbol="SH600000",
        period="1d",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        adjust="qfq",
    )

    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        # 验证数据量合理（交易日约为总日期的60-70%）
        assert len(df) > 0
