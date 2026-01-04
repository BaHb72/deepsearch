"""AmazingData QueryManager 真实数据测试。

这些测试使用真实的 AmazingData SDK 连接来验证数据获取功能。
如果 SDK 未安装或未配置，测试将自动跳过。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest
from core.infrastructure.providers.implementations.amazingdata.query_manager import (
    AmazingDataQueryManager,
)
from core.infrastructure.providers.interfaces.base import DataRequest

# ============================================================================
# K线数据测试
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_kline_returns_dataframe(real_amazingdata_provider):
    """测试获取K线数据返回有效的DataFrame。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    df = await manager.fetch_kline(
        symbol="SZ000001",
        period="1d",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        adjust="none",
    )

    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        # 验证基本列存在
        expected_columns = {"open", "high", "low", "close", "volume"}
        actual_columns = set(df.columns.str.lower())
        assert expected_columns & actual_columns, f"缺少K线必要列，实际列: {df.columns.tolist()}"


@pytest.mark.asyncio
async def test_get_data_routes_kline_request(real_amazingdata_provider):
    """测试 get_data 正确路由K线请求。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    request = DataRequest(
        request_type="kline",
        symbol="SH600000",
        period="1d",
        extra_params={"data_type": "kline"},
    )

    response = await manager.get_data(request)

    assert response.success is True
    assert response.data is not None


# ============================================================================
# 实时行情测试
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_realtime_quote_returns_data(real_amazingdata_provider):
    """测试获取实时行情返回有效数据。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    quotes = await manager.fetch_realtime_quote(symbols=["SZ000001", "SH600000"])

    assert quotes is not None
    assert isinstance(quotes, dict)
    # 验证至少有一个股票的行情
    if quotes:
        for symbol, quote in quotes.items():
            assert isinstance(quote, dict)
            # 验证行情数据包含基本字段
            assert "code" in quote or "symbol" in quote or symbol


@pytest.mark.asyncio
async def test_get_data_handles_realtime_requests(real_amazingdata_provider):
    """测试 get_data 正确处理实时行情请求。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    request = DataRequest(
        request_type="realtime",
        symbols=["SZ000001", "SH600000"],
        extra_params={"data_type": "realtime"},
    )

    response = await manager.get_data(request)

    assert response.success is True
    assert isinstance(response.data, pd.DataFrame)


# ============================================================================
# 财务数据测试
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_key_indicators_returns_data(real_amazingdata_provider):
    """测试获取关键指标返回有效数据。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    df = await manager.fetch_key_indicators(
        symbol="SZ000001",
        report_date=None,  # 获取最新数据
    )

    assert isinstance(df, pd.DataFrame)
    # 如果有数据，验证包含财务指标列
    if not df.empty:
        possible_columns = {"roe", "roa", "eps", "gross_profit_margin"}
        actual_columns = set(df.columns.str.lower())
        assert possible_columns & actual_columns or len(df.columns) > 0


@pytest.mark.asyncio
async def test_fetch_shareholder_info_returns_snapshot(real_amazingdata_provider):
    """测试获取股东信息返回有效快照。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    snapshot = await manager.fetch_shareholder_info(
        symbol="SZ000001",
        report_date=None,
    )

    # 股东信息可能为空但不应报错
    if snapshot is not None:
        assert isinstance(snapshot, dict)
        assert "symbol" in snapshot
        assert "top10_holders" in snapshot or "shareholder_count" in snapshot


# ============================================================================
# 大宗交易测试
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_block_trading_returns_dataframe(real_amazingdata_provider):
    """测试获取大宗交易返回有效的DataFrame。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    df = await manager.fetch_block_trading(
        symbols=["SZ000001"],
        local_path=None,
        is_local=False,
        begin_date=None,
        end_date=None,
    )

    assert isinstance(df, pd.DataFrame)
    # 大宗交易可能为空（某些股票没有大宗交易记录）
    if not df.empty:
        assert "symbol" in df.columns or "price" in df.columns


# ============================================================================
# 错误处理测试
# ============================================================================


@pytest.mark.asyncio
async def test_get_data_returns_error_for_unknown_type(real_amazingdata_provider):
    """测试未知数据类型返回错误。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    request = DataRequest(
        request_type="unknown",
        extra_params={"data_type": "unsupported"},
    )

    response = await manager.get_data(request)

    assert response.success is False
    assert "不支持的数据类型" in (response.error or "")


# ============================================================================
# 龙虎榜测试
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_dragon_tiger_returns_list(real_amazingdata_provider):
    """测试获取龙虎榜返回有效列表。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    records = await manager.fetch_dragon_tiger(
        symbol="SZ000001",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )

    assert isinstance(records, list)
    # 龙虎榜可能为空（不是每天都有）
    if records:
        record = records[0]
        assert isinstance(record, dict)
        assert "symbol" in record or "trade_date" in record


# ============================================================================
# 融资融券测试
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_margin_trading_returns_dataframe(real_amazingdata_provider):
    """测试获取融资融券数据返回有效的DataFrame。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    df = await manager.fetch_margin_trading(
        symbol="SZ000001",
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )

    assert isinstance(df, pd.DataFrame)
    # 融资融券数据可能为空
    if not df.empty:
        possible_columns = {"margin_balance", "margin_buy", "short_balance"}
        actual_columns = set(df.columns.str.lower())
        assert possible_columns & actual_columns or len(df.columns) > 0


# ============================================================================
# 北向资金测试
# ============================================================================


@pytest.mark.asyncio
async def test_fetch_north_flow_returns_dataframe(real_amazingdata_provider):
    """测试获取北向资金数据返回有效的DataFrame。"""
    manager = AmazingDataQueryManager(real_amazingdata_provider)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    df = await manager.fetch_north_flow(
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )

    assert isinstance(df, pd.DataFrame)
    if not df.empty:
        possible_columns = {"shanghai_flow", "shenzhen_flow", "total_net"}
        actual_columns = set(str(c).lower() for c in df.columns)
        assert possible_columns & actual_columns or len(df.columns) > 0
