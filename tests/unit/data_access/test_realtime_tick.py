"""
Realtime 和 Tick 能力单元测试。

测试 adapters 中的 Realtime 和 Tick 实现。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from decimal import Decimal

from deepsearch.ports.data.semantic_types import (
    AssetSpec,
    Timeframe,
    TimeRange,
)
from deepsearch.ports.data.requests import (
    RealtimeQuoteRequest,
    TickRequest,
)
from deepsearch.ports.data.responses import (
    Quote,
    RealtimeQuoteResponse,
    TickData,
    TickResponse,
)
from deepsearch.ports.data_sources import DataSourceType
from deepsearch.config.models.capability_routing import (
    ProviderCapabilitiesSpec,
    RealtimeQuoteCapabilitySpec,
    TickCapabilitySpec,
)


class TestMiniQMTRealtimeCapability:
    """MiniQMT Realtime 能力测试"""

    @pytest.fixture
    def mock_provider(self):
        """Mock MiniQMT Provider"""
        provider = MagicMock()
        provider.get_realtime_quotes = AsyncMock()
        provider.initialize = AsyncMock(return_value=True)
        return provider

    @pytest.fixture
    def adapter(self, mock_provider):
        """适配器实例"""
        from deepsearch.infrastructure.providers.adapters.miniqmt import MiniQMTAdapter

        return MiniQMTAdapter(provider=mock_provider)

    @pytest.mark.asyncio
    async def test_query_realtime_single_asset(self, adapter, mock_provider):
        """测试单个资产实时行情"""
        mock_provider.get_realtime_quotes.return_value = [
            {
                "symbol": "000001.SZ",
                "time": datetime(2024, 1, 1, 10, 30),
                "price": 10.50,
                "open": 10.00,
                "high": 10.80,
                "low": 9.90,
                "prev_close": 10.00,
                "volume": 5000000,
                "amount": 52500000,
            }
        ]

        request = RealtimeQuoteRequest(
            assets=[AssetSpec.from_code("000001.SZ")]
        )

        response = await adapter.query_realtime(request)

        assert isinstance(response, RealtimeQuoteResponse)
        assert len(response.quotes) == 1
        assert response.quotes[0].last_price == Decimal("10.5")
        assert response.source == DataSourceType.MINIQMT

    @pytest.mark.asyncio
    async def test_query_realtime_multiple_assets(self, adapter, mock_provider):
        """测试多个资产实时行情"""
        mock_provider.get_realtime_quotes.return_value = [
            {
                "symbol": "000001.SZ",
                "time": datetime.now(),
                "price": 10.50,
                "open": 10.00,
                "high": 10.80,
                "low": 9.90,
                "prev_close": 10.00,
                "volume": 5000000,
                "amount": 52500000,
            },
            {
                "symbol": "600000.SH",
                "time": datetime.now(),
                "price": 8.20,
                "open": 8.00,
                "high": 8.50,
                "low": 7.90,
                "prev_close": 8.10,
                "volume": 3000000,
                "amount": 24600000,
            },
        ]

        request = RealtimeQuoteRequest(
            assets=[
                AssetSpec.from_code("000001.SZ"),
                AssetSpec.from_code("600000.SH"),
            ]
        )

        response = await adapter.query_realtime(request)

        assert len(response.quotes) == 2

    @pytest.mark.asyncio
    async def test_query_realtime_with_depth(self, adapter, mock_provider):
        """测试带盘口的实时行情"""
        mock_provider.get_realtime_quotes.return_value = [
            {
                "symbol": "000001.SZ",
                "time": datetime.now(),
                "price": 10.50,
                "open": 10.00,
                "high": 10.80,
                "low": 9.90,
                "prev_close": 10.00,
                "volume": 5000000,
                "amount": 52500000,
                "bidPrice": 10.49,
                "bidVol": 10000,
                "askPrice": 10.51,
                "askVol": 8000,
            }
        ]

        request = RealtimeQuoteRequest(
            assets=[AssetSpec.from_code("000001.SZ")]
        )

        response = await adapter.query_realtime(request)

        assert len(response.quotes) == 1
        quote = response.quotes[0]
        assert len(quote.bid_prices) >= 1
        assert quote.bid_prices[0] == Decimal("10.49")


class TestMiniQMTTickCapability:
    """MiniQMT Tick 能力测试"""

    @pytest.fixture
    def mock_provider(self):
        """Mock MiniQMT Provider"""
        provider = MagicMock()
        provider.initialize = AsyncMock(return_value=True)
        return provider

    @pytest.fixture
    def adapter(self, mock_provider):
        """适配器实例"""
        from deepsearch.infrastructure.providers.adapters.miniqmt import MiniQMTAdapter

        return MiniQMTAdapter(provider=mock_provider)

    @pytest.mark.asyncio
    async def test_query_tick_returns_response(self, adapter):
        """测试 Tick 查询返回响应"""
        request = TickRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            range=TimeRange.last_n(100),
        )

        response = await adapter.query_tick(request)

        assert isinstance(response, TickResponse)
        assert response.asset == request.asset
        assert response.source == DataSourceType.MINIQMT


class TestAmazingDataRealtimeCapability:
    """AmazingData Realtime 能力测试"""

    @pytest.fixture
    def mock_provider(self):
        """Mock AmazingData Provider"""
        provider = MagicMock()
        provider.get_realtime_quotes = AsyncMock()
        provider.initialize = AsyncMock(return_value=True)
        return provider

    @pytest.fixture
    def adapter(self, mock_provider):
        """适配器实例"""
        from deepsearch.infrastructure.providers.adapters.amazingdata import (
            AmazingDataAdapter,
        )

        return AmazingDataAdapter(provider=mock_provider)

    @pytest.mark.asyncio
    async def test_query_realtime_success(self, adapter, mock_provider):
        """测试成功查询实时行情"""
        mock_provider.get_realtime_quotes.return_value = [
            {
                "code": "000001.SZ",
                "name": "平安银行",
                "price": 10.50,
                "open": 10.00,
                "high": 10.80,
                "low": 9.90,
                "prev_close": 10.00,
                "volume": 5000000,
                "amount": 52500000,
            }
        ]

        request = RealtimeQuoteRequest(
            assets=[AssetSpec.from_code("000001.SZ")]
        )

        response = await adapter.query_realtime(request)

        assert isinstance(response, RealtimeQuoteResponse)
        assert len(response.quotes) >= 1



class TestTickData:
    """TickData 测试"""

    def test_create_tick_data(self):
        """测试创建 Tick 数据"""
        tick = TickData(
            timestamp=datetime.now(),
            price=Decimal("10.50"),
            volume=1000,
            direction="B",  # 买入方向
        )
        assert tick.price == Decimal("10.50")
        assert tick.volume == 1000
        assert tick.direction == "B"

    def test_tick_data_with_order_id(self):
        """测试带订单ID的 Tick"""
        tick = TickData(
            timestamp=datetime.now(),
            price=Decimal("10.50"),
            volume=1000,
            direction="S",
            order_id="ORD12345",
        )
        assert tick.order_id == "ORD12345"



class TestRealtimeQuoteRequest:
    """RealtimeQuoteRequest 测试"""

    def test_request_with_single_asset(self):
        """测试单资产请求"""
        request = RealtimeQuoteRequest(
            assets=[AssetSpec.from_code("000001.SZ")]
        )
        assert len(request.assets) == 1

    def test_request_with_multiple_assets(self):
        """测试多资产请求"""
        request = RealtimeQuoteRequest(
            assets=[
                AssetSpec.from_code("000001.SZ"),
                AssetSpec.from_code("600000.SH"),
                AssetSpec.from_code("300001.SZ"),
            ]
        )
        assert len(request.assets) == 3

    def test_request_with_latency_hint(self):
        """测试带延迟提示的请求"""
        from deepsearch.ports.data.semantic_types import LatencyHint

        request = RealtimeQuoteRequest(
            assets=[AssetSpec.from_code("000001.SZ")],
            latency=LatencyHint.REALTIME,
        )
        assert request.latency == LatencyHint.REALTIME



class TestTickRequest:
    """TickRequest 测试"""

    def test_basic_request(self):
        """测试基本请求"""
        request = TickRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            range=TimeRange.last_n(100),
        )
        assert request.asset.symbol == "000001"

    def test_request_with_time_range(self):
        """测试带时间范围的请求"""
        request = TickRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            range=TimeRange.last_days(1),
        )
        assert request.range.is_bounded() is True
