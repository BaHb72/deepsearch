"""
Requests 和 Responses 单元测试。

测试 ports/data/requests.py 和 ports/data/responses.py。
"""

import pytest
from datetime import datetime
from decimal import Decimal

from deepsearch.ports.data.semantic_types import (
    AssetSpec,
    Exchange,
    Timeframe,
    AdjustType,
    TimeRange,
    LatencyHint,
)
from deepsearch.ports.data.requests import (
    KlineRequest,
    RealtimeQuoteRequest,
    TickRequest,
    StockListRequest,
)
from deepsearch.ports.data.responses import (
    KlineBar,
    KlineResponse,
    Quote,
    RealtimeQuoteResponse,
    TickData,
    TickResponse,
    StockInfo,
    StockListResponse,
)
from deepsearch.ports.data_sources import DataSourceType


class TestKlineRequest:
    """KlineRequest 测试"""

    def test_create_basic_request(self):
        """测试创建基本请求"""
        asset = AssetSpec.from_code("000001.SZ")
        request = KlineRequest(
            asset=asset,
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(30),
        )
        assert request.asset == asset
        assert request.timeframe == Timeframe.D1
        assert request.adjust == AdjustType.NONE  # 默认值

    def test_request_with_adjust(self):
        """测试带复权的请求"""
        request = KlineRequest(
            asset=AssetSpec.from_code("600000.SH"),
            timeframe=Timeframe.M5,
            range=TimeRange.last_n(100),
            adjust=AdjustType.FORWARD,
        )
        assert request.adjust == AdjustType.FORWARD

    def test_request_with_latency_hint(self):
        """测试带延迟提示的请求"""
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.M1,
            range=TimeRange.last_n(50),
            latency=LatencyHint.REALTIME,
        )
        assert request.latency == LatencyHint.REALTIME


class TestRealtimeQuoteRequest:
    """RealtimeQuoteRequest 测试"""

    def test_single_asset(self):
        """测试单个资产"""
        asset = AssetSpec.from_code("000001.SZ")
        request = RealtimeQuoteRequest(assets=[asset])
        assert len(request.assets) == 1
        assert request.assets[0] == asset

    def test_multiple_assets(self):
        """测试多个资产"""
        assets = [
            AssetSpec.from_code("000001.SZ"),
            AssetSpec.from_code("600000.SH"),
            AssetSpec.from_code("300001.SZ"),
        ]
        request = RealtimeQuoteRequest(assets=assets)
        assert len(request.assets) == 3


class TestKlineBar:
    """KlineBar 测试"""

    def test_create_bar(self):
        """测试创建K线"""
        bar = KlineBar(
            timestamp=datetime(2024, 1, 1, 9, 30),
            open=Decimal("10.00"),
            high=Decimal("10.50"),
            low=Decimal("9.80"),
            close=Decimal("10.20"),
            volume=1000000,
            amount=Decimal("10200000"),
        )
        assert bar.open == Decimal("10.00")
        assert bar.volume == 1000000

    def test_bar_with_optional_fields(self):
        """测试带可选字段的K线"""
        bar = KlineBar(
            timestamp=datetime(2024, 1, 1),
            open=Decimal("10"),
            high=Decimal("11"),
            low=Decimal("9"),
            close=Decimal("10.5"),
            volume=100,
            amount=Decimal("1000"),
            turnover=Decimal("0.01"),
        )
        assert bar.turnover == Decimal("0.01")


class TestKlineResponse:
    """KlineResponse 测试"""

    def test_create_response(self):
        """测试创建响应"""
        bars = [
            KlineBar(
                timestamp=datetime(2024, 1, 1),
                open=Decimal("10"),
                high=Decimal("11"),
                low=Decimal("9"),
                close=Decimal("10.5"),
                volume=100,
                amount=Decimal("1000"),
            ),
            KlineBar(
                timestamp=datetime(2024, 1, 2),
                open=Decimal("10.5"),
                high=Decimal("12"),
                low=Decimal("10"),
                close=Decimal("11.5"),
                volume=200,
                amount=Decimal("2300"),
            ),
        ]
        response = KlineResponse(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            bars=bars,
            source=DataSourceType.MINIQMT,
            latency_ms=50,
        )
        assert len(response.bars) == 2
        assert response.source == DataSourceType.MINIQMT
        assert response.latency_ms == 50

    def test_empty_response(self):
        """测试空响应"""
        response = KlineResponse(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            bars=[],
            source=DataSourceType.AKSHARE,
        )
        assert len(response.bars) == 0
        assert response.is_empty


class TestQuote:
    """Quote 测试"""

    def test_create_quote(self):
        """测试创建行情"""
        quote = Quote(
            asset=AssetSpec.from_code("000001.SZ"),
            timestamp=datetime.now(),
            last_price=Decimal("10.50"),
            open=Decimal("10.00"),
            high=Decimal("10.80"),
            low=Decimal("9.90"),
            pre_close=Decimal("10.00"),
            volume=5000000,
            amount=Decimal("52500000"),
        )
        assert quote.last_price == Decimal("10.50")

    def test_quote_with_depth(self):
        """测试带盘口的行情"""
        quote = Quote(
            asset=AssetSpec.from_code("000001.SZ"),
            timestamp=datetime.now(),
            last_price=Decimal("10.50"),
            open=Decimal("10"),
            high=Decimal("11"),
            low=Decimal("10"),
            pre_close=Decimal("10"),
            volume=100,
            amount=Decimal("1000"),
            bid_prices=(Decimal("10.49"), Decimal("10.48")),
            bid_volumes=(100, 200),
            ask_prices=(Decimal("10.51"), Decimal("10.52")),
            ask_volumes=(150, 300),
        )
        assert len(quote.bid_prices) == 2
        assert quote.bid_prices[0] == Decimal("10.49")


class TestStockInfo:
    """StockInfo 测试"""

    def test_create_stock_info(self):
        """测试创建股票信息"""
        info = StockInfo(
            asset=AssetSpec.from_code("000001.SZ"),
            name="平安银行",
        )
        assert info.name == "平安银行"
        assert info.is_st is False

    def test_st_stock(self):
        """测试 ST 股票"""
        info = StockInfo(
            asset=AssetSpec.from_code("000001.SZ"),
            name="*ST某某",
            is_st=True,
        )
        assert info.is_st is True


class TestStockListResponse:
    """StockListResponse 测试"""

    def test_create_response(self):
        """测试创建股票列表响应"""
        stocks = [
            StockInfo(asset=AssetSpec.from_code("000001.SZ"), name="平安银行"),
            StockInfo(asset=AssetSpec.from_code("600000.SH"), name="浦发银行"),
        ]
        response = StockListResponse(
            stocks=stocks,
            source=DataSourceType.AKSHARE,
            latency_ms=200,
        )
        assert len(response.stocks) == 2
