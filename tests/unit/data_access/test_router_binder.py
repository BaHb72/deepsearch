"""
CapabilityRouter 和 UnifiedDataFeed 单元测试。

测试 infrastructure/providers/capability_router.py 和 binder.py。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from decimal import Decimal

from deepsearch.ports.data.semantic_types import (
    AssetSpec,
    Timeframe,
    AdjustType,
    TimeRange,
    LatencyHint,
)
from deepsearch.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from deepsearch.ports.data.responses import KlineBar, KlineResponse
from deepsearch.ports.data.capabilities import DataCapability
from deepsearch.ports.data_sources import DataSourceType
from deepsearch.config.models.capability_routing import (
    CapabilityRoutingConfig,
    CapabilityRoutingRule,
    KlineCapabilitySpec,
    ProviderCapabilitiesSpec,
    RealtimeQuoteCapabilitySpec,
    RoutingConfig,
    ScenarioRouting,
)
from deepsearch.infrastructure.providers.capability_router import (
    CapabilityRouter,
    NoProviderAvailableError,
)
from deepsearch.infrastructure.providers.binder import (
    UnifiedDataFeed,
    FallbackStrategy,
    AllProvidersFailedError,
)
from deepsearch.infrastructure.providers.adapters.base import (
    BaseProviderAdapter,
    IKlineProvider,
)


class MockKlineAdapter(BaseProviderAdapter, IKlineProvider):
    """Mock K线适配器"""

    def __init__(self, name: str, capabilities: ProviderCapabilitiesSpec):
        super().__init__(name=name, capabilities=capabilities)
        self._query_kline_mock = AsyncMock()

    async def initialize(self) -> bool:
        return True

    async def query_kline(self, request: KlineRequest) -> KlineResponse:
        return await self._query_kline_mock(request)


class TestCapabilityRouter:
    """CapabilityRouter 测试"""

    @pytest.fixture
    def router_config(self):
        """路由配置"""
        return CapabilityRoutingConfig(
            capabilities={
                "miniqmt": ProviderCapabilitiesSpec(
                    kline=KlineCapabilitySpec(
                        min_timeframe=Timeframe.M1,
                        max_timeframe=Timeframe.D1,
                        adjust_types=[AdjustType.NONE, AdjustType.FORWARD],
                    ),
                ),
                "akshare": ProviderCapabilitiesSpec(
                    kline=KlineCapabilitySpec(
                        min_timeframe=Timeframe.D1,
                        max_timeframe=Timeframe.MO1,
                        adjust_types=[AdjustType.NONE, AdjustType.FORWARD, AdjustType.BACKWARD],
                    ),
                ),
            },
            routing=RoutingConfig(
                kline=CapabilityRoutingRule(
                    priority=["miniqmt", "akshare"],
                    scenarios={
                        "realtime": ScenarioRouting(priority=["miniqmt"]),
                        "historical": ScenarioRouting(priority=["akshare", "miniqmt"]),
                    },
                ),
            ),
        )

    @pytest.fixture
    def mock_adapters(self, router_config):
        """Mock 适配器"""
        miniqmt = MockKlineAdapter(
            name="miniqmt",
            capabilities=router_config.capabilities["miniqmt"],
        )
        akshare = MockKlineAdapter(
            name="akshare",
            capabilities=router_config.capabilities["akshare"],
        )
        return {"miniqmt": miniqmt, "akshare": akshare}

    @pytest.fixture
    def router(self, router_config, mock_adapters):
        """路由器实例"""
        return CapabilityRouter(config=router_config, adapters=mock_adapters)

    def test_resolve_kline_default(self, router):
        """测试默认 K线路由"""
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.M5,
            range=TimeRange.last_n(100),
        )
        adapter = router.resolve(request)
        assert adapter.name == "miniqmt"

    def test_resolve_kline_realtime_scenario(self, router):
        """测试实时场景路由"""
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.M1,
            range=TimeRange.last_n(50),
            latency=LatencyHint.REALTIME,
        )
        adapter = router.resolve(request)
        assert adapter.name == "miniqmt"

    def test_resolve_kline_batch_scenario(self, router):
        """测试批量场景路由"""
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(365),
            latency=LatencyHint.BATCH,
        )
        adapter = router.resolve(request)
        # BATCH 场景走 historical 路由，优先 akshare
        assert adapter.name == "akshare"

    def test_resolve_fallback_when_capability_not_supported(self, router):
        """测试能力不支持时降级"""
        # 请求月线，miniqmt 不支持，应降级到 akshare
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.MO1,
            range=TimeRange.last_n(12),
        )
        adapter = router.resolve(request)
        assert adapter.name == "akshare"

    def test_resolve_no_provider_available(self, router):
        """测试无可用 Provider"""
        # 请求后复权，但 miniqmt 不支持后复权，akshare 支持
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.M1,  # akshare 不支持分钟线
            range=TimeRange.last_n(100),
            adjust=AdjustType.BACKWARD,  # miniqmt 不支持后复权
        )
        with pytest.raises(NoProviderAvailableError):
            router.resolve(request)

    def test_resolve_all(self, router):
        """测试获取所有可处理的适配器"""
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(30),
        )
        adapters = router.resolve_all(request)
        assert len(adapters) == 2

    def test_register_adapter(self, router):
        """测试注册适配器"""
        new_adapter = MockKlineAdapter(
            name="new_provider",
            capabilities=ProviderCapabilitiesSpec(kline=KlineCapabilitySpec()),
        )
        router.register_adapter("new_provider", new_adapter)
        assert "new_provider" in router.adapters

    def test_unregister_adapter(self, router):
        """测试注销适配器"""
        router.unregister_adapter("miniqmt")
        assert "miniqmt" not in router.adapters


class TestUnifiedDataFeed:
    """UnifiedDataFeed 测试"""

    @pytest.fixture
    def mock_router(self):
        """Mock 路由器"""
        router = MagicMock(spec=CapabilityRouter)
        return router

    @pytest.fixture
    def feed(self, mock_router):
        """UnifiedDataFeed 实例"""
        return UnifiedDataFeed(router=mock_router)

    @pytest.mark.asyncio
    async def test_query_kline(self, feed, mock_router):
        """测试查询 K线"""
        # 设置 mock
        mock_adapter = MockKlineAdapter(
            name="test",
            capabilities=ProviderCapabilitiesSpec(kline=KlineCapabilitySpec()),
        )
        expected_response = KlineResponse(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            bars=[
                KlineBar(
                    timestamp=datetime(2024, 1, 1),
                    open=Decimal("10"),
                    high=Decimal("11"),
                    low=Decimal("9"),
                    close=Decimal("10.5"),
                    volume=100,
                    amount=Decimal("1000"),
                )
            ],
            source=DataSourceType.MINIQMT,
        )
        mock_adapter._query_kline_mock.return_value = expected_response
        mock_router.resolve.return_value = mock_adapter

        # 执行查询
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(30),
        )
        response = await feed.query(request)

        assert response == expected_response
        mock_router.resolve.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_query_with_fallback_success(self, feed, mock_router):
        """测试降级成功"""
        # 第一个适配器失败，第二个成功
        adapter1 = MockKlineAdapter(
            name="failing",
            capabilities=ProviderCapabilitiesSpec(kline=KlineCapabilitySpec()),
        )
        adapter1._query_kline_mock.side_effect = Exception("Connection failed")

        adapter2 = MockKlineAdapter(
            name="working",
            capabilities=ProviderCapabilitiesSpec(kline=KlineCapabilitySpec()),
        )
        expected_response = KlineResponse(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            bars=[],
            source=DataSourceType.AKSHARE,
        )
        adapter2._query_kline_mock.return_value = expected_response

        mock_router.resolve_all.return_value = [adapter1, adapter2]
        mock_router._infer_capability.return_value = DataCapability.KLINE

        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(30),
        )
        response = await feed.query_with_fallback(
            request,
            strategy=FallbackStrategy.SEQUENTIAL,
        )

        assert response == expected_response

    @pytest.mark.asyncio
    async def test_query_with_fallback_all_failed(self, feed, mock_router):
        """测试所有 Provider 都失败"""
        adapter1 = MockKlineAdapter(
            name="failing1",
            capabilities=ProviderCapabilitiesSpec(kline=KlineCapabilitySpec()),
        )
        adapter1._query_kline_mock.side_effect = Exception("Error 1")

        adapter2 = MockKlineAdapter(
            name="failing2",
            capabilities=ProviderCapabilitiesSpec(kline=KlineCapabilitySpec()),
        )
        adapter2._query_kline_mock.side_effect = Exception("Error 2")

        mock_router.resolve_all.return_value = [adapter1, adapter2]
        mock_router._infer_capability.return_value = DataCapability.KLINE

        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(30),
        )

        with pytest.raises(AllProvidersFailedError) as exc_info:
            await feed.query_with_fallback(request, strategy=FallbackStrategy.SEQUENTIAL)

        assert "failing1" in exc_info.value.errors
        assert "failing2" in exc_info.value.errors

    @pytest.mark.asyncio
    async def test_get_kline_type_safety(self, feed, mock_router):
        """测试类型安全的便捷方法"""
        mock_adapter = MockKlineAdapter(
            name="test",
            capabilities=ProviderCapabilitiesSpec(kline=KlineCapabilitySpec()),
        )
        expected_response = KlineResponse(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            bars=[],
            source=DataSourceType.MINIQMT,
        )
        mock_adapter._query_kline_mock.return_value = expected_response
        mock_router.resolve.return_value = mock_adapter

        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(30),
        )
        response = await feed.get_kline(request)

        assert isinstance(response, KlineResponse)
