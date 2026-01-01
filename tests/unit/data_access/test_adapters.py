"""
Adapter 单元测试。

测试 infrastructure/providers/adapters/ 中的适配器。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from decimal import Decimal

import pandas as pd

from deepsearch.ports.data.semantic_types import (
    AssetSpec,
    Timeframe,
    AdjustType,
    TimeRange,
)
from deepsearch.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from deepsearch.ports.data.responses import KlineResponse
from deepsearch.ports.data_sources import DataSourceType
from deepsearch.infrastructure.providers.adapters.base import CapabilityNotSupportedError


class TestMiniQMTRequestMapper:
    """MiniQMT 请求映射器测试"""

    def test_timeframe_mapping(self):
        """测试周期映射"""
        from deepsearch.infrastructure.providers.adapters.miniqmt import MiniQMTRequestMapper

        mapper = MiniQMTRequestMapper()

        assert mapper.TIMEFRAME_MAP[Timeframe.M1] == "1m"
        assert mapper.TIMEFRAME_MAP[Timeframe.M5] == "5m"
        assert mapper.TIMEFRAME_MAP[Timeframe.D1] == "1d"

    def test_adjust_mapping(self):
        """测试复权映射"""
        from deepsearch.infrastructure.providers.adapters.miniqmt import MiniQMTRequestMapper

        mapper = MiniQMTRequestMapper()

        assert mapper.ADJUST_MAP[AdjustType.NONE] == 0
        assert mapper.ADJUST_MAP[AdjustType.FORWARD] == 1

    def test_map_kline_request(self):
        """测试请求转换"""
        from deepsearch.infrastructure.providers.adapters.miniqmt import MiniQMTRequestMapper

        mapper = MiniQMTRequestMapper()
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_n(100),
        )

        params = mapper.map_kline_request(request)

        assert params["symbol"] == "000001.SZ"
        assert params["period"] == "1d"
        assert params["limit"] == 100


class TestAmazingDataRequestMapper:
    """AmazingData 请求映射器测试"""

    def test_timeframe_mapping(self):
        """测试周期映射"""
        from deepsearch.infrastructure.providers.adapters.amazingdata import AmazingDataRequestMapper

        mapper = AmazingDataRequestMapper()

        assert mapper.TIMEFRAME_MAP[Timeframe.M1] == "1m"
        assert mapper.TIMEFRAME_MAP[Timeframe.H1] == "60m"
        assert mapper.TIMEFRAME_MAP[Timeframe.MO1] == "1M"

    def test_adjust_mapping(self):
        """测试复权映射"""
        from deepsearch.infrastructure.providers.adapters.amazingdata import AmazingDataRequestMapper

        mapper = AmazingDataRequestMapper()

        assert mapper.ADJUST_MAP[AdjustType.NONE] == "none"
        assert mapper.ADJUST_MAP[AdjustType.FORWARD] == "qfq"
        assert mapper.ADJUST_MAP[AdjustType.BACKWARD] == "hfq"


class TestAKShareRequestMapper:
    """AKShare 请求映射器测试"""

    def test_timeframe_mapping(self):
        """测试周期映射"""
        from deepsearch.infrastructure.providers.adapters.akshare import AKShareRequestMapper

        mapper = AKShareRequestMapper()

        assert mapper.TIMEFRAME_MAP[Timeframe.D1] == "daily"
        assert mapper.TIMEFRAME_MAP[Timeframe.W1] == "weekly"
        assert mapper.TIMEFRAME_MAP[Timeframe.MO1] == "monthly"

    def test_supports_timeframe(self):
        """测试周期支持检查"""
        from deepsearch.infrastructure.providers.adapters.akshare import AKShareRequestMapper

        mapper = AKShareRequestMapper()

        assert mapper.supports_timeframe(Timeframe.D1) is True
        assert mapper.supports_timeframe(Timeframe.M1) is False
        assert mapper.supports_timeframe(Timeframe.M5) is False


class TestMiniQMTAdapter:
    """MiniQMT 适配器测试"""

    @pytest.fixture
    def mock_provider(self):
        """Mock MiniQMT Provider"""
        provider = MagicMock()
        provider.get_kline_data = AsyncMock()
        provider.initialize = AsyncMock(return_value=True)
        return provider

    @pytest.fixture
    def adapter(self, mock_provider):
        """适配器实例"""
        from deepsearch.infrastructure.providers.adapters.miniqmt import MiniQMTAdapter

        return MiniQMTAdapter(provider=mock_provider)

    @pytest.mark.asyncio
    async def test_query_kline_success(self, adapter, mock_provider):
        """测试成功查询 K线"""
        mock_provider.get_kline_data.return_value = [
            {
                "time": datetime(2024, 1, 1, 9, 30),
                "open": 10.0,
                "high": 10.5,
                "low": 9.8,
                "close": 10.2,
                "volume": 1000000,
                "amount": 10200000,
            },
        ]

        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(30),
        )

        response = await adapter.query_kline(request)

        assert isinstance(response, KlineResponse)
        assert len(response.bars) == 1
        assert response.bars[0].open == Decimal("10.0")
        assert response.source == DataSourceType.MINIQMT

    @pytest.mark.asyncio
    async def test_query_kline_unsupported_timeframe(self, adapter):
        """测试不支持的周期"""
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.MO1,  # MiniQMT 不支持月线
            range=TimeRange.last_n(12),
        )

        with pytest.raises(CapabilityNotSupportedError):
            await adapter.query_kline(request)


class TestAmazingDataAdapter:
    """AmazingData 适配器测试"""

    @pytest.fixture
    def mock_provider(self):
        """Mock AmazingData Provider"""
        provider = MagicMock()
        provider.get_kline = AsyncMock()
        provider.initialize = AsyncMock(return_value=True)
        return provider

    @pytest.fixture
    def adapter(self, mock_provider):
        """适配器实例"""
        from deepsearch.infrastructure.providers.adapters.amazingdata import AmazingDataAdapter

        return AmazingDataAdapter(provider=mock_provider)

    @pytest.mark.asyncio
    async def test_query_kline_with_dataframe(self, adapter, mock_provider):
        """测试从 DataFrame 解析 K线"""
        df = pd.DataFrame(
            {
                "open": [10.0, 10.5],
                "high": [10.5, 11.0],
                "low": [9.8, 10.0],
                "close": [10.2, 10.8],
                "volume": [1000000, 1200000],
                "amount": [10200000, 12960000],
            },
            index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
        )
        mock_provider.get_kline.return_value = df

        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(30),
        )

        response = await adapter.query_kline(request)

        assert len(response.bars) == 2
        assert response.bars[0].open == Decimal("10.0")
        assert response.source == DataSourceType.AMAZINGDATA


class TestAKShareAdapter:
    """AKShare 适配器测试"""

    @pytest.fixture
    def mock_provider(self):
        """Mock AKShare Provider"""
        provider = MagicMock()
        provider.get_history_data = AsyncMock()
        provider.initialize = AsyncMock(return_value=True)
        return provider

    @pytest.fixture
    def adapter(self, mock_provider):
        """适配器实例"""
        from deepsearch.infrastructure.providers.adapters.akshare import AKShareAdapter

        return AKShareAdapter(provider=mock_provider)

    @pytest.mark.asyncio
    async def test_query_kline_daily(self, adapter, mock_provider):
        """测试日线查询"""
        df = pd.DataFrame(
            {
                "date": ["2024-01-01", "2024-01-02"],
                "open": [10.0, 10.5],
                "high": [10.5, 11.0],
                "low": [9.8, 10.0],
                "close": [10.2, 10.8],
                "volume": [1000000, 1200000],
                "amount": [10200000, 12960000],
            }
        )
        mock_provider.get_history_data.return_value = df

        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(30),
        )

        response = await adapter.query_kline(request)

        assert len(response.bars) == 2
        assert response.source == DataSourceType.AKSHARE

    @pytest.mark.asyncio
    async def test_query_kline_unsupported_intraday(self, adapter):
        """测试不支持的分钟线"""
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.M1,  # AKShare 不支持分钟线
            range=TimeRange.last_n(100),
        )

        with pytest.raises(CapabilityNotSupportedError):
            await adapter.query_kline(request)
