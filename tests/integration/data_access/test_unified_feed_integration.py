"""
UnifiedDataFeed 集成测试。

这些测试需要实际的数据源连接，使用 Mock 无法完全验证。
运行前需要确保:
1. APP__ENV=dev
2. MiniQMT/AmazingData 服务可用（或使用 skip markers）
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from deepsearch.ports.data.semantic_types import (
    AssetSpec,
    Timeframe,
    AdjustType,
    TimeRange,
    LatencyHint,
)
from deepsearch.ports.data.requests import (
    KlineRequest,
    RealtimeQuoteRequest,
    StockListRequest,
)
from deepsearch.ports.data.responses import (
    KlineResponse,
    RealtimeQuoteResponse,
    StockListResponse,
)
from deepsearch.config.models.capability_routing import (
    CapabilityRoutingConfig,
    CapabilityRoutingRule,
    KlineCapabilitySpec,
    ProviderCapabilitiesSpec,
    RealtimeQuoteCapabilitySpec,
    RoutingConfig,
    ScenarioRouting,
)
from deepsearch.infrastructure.providers.capability_router import CapabilityRouter
from deepsearch.infrastructure.providers.binder import UnifiedDataFeed, FallbackStrategy


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_config():
    """示例配置"""
    return CapabilityRoutingConfig(
        capabilities={
            "miniqmt": ProviderCapabilitiesSpec(
                kline=KlineCapabilitySpec(
                    min_timeframe=Timeframe.M1,
                    max_timeframe=Timeframe.D1,
                    history_days=90,
                    adjust_types=[AdjustType.NONE, AdjustType.FORWARD],
                    realtime_capable=True,
                ),
                realtime_quote=RealtimeQuoteCapabilitySpec(
                    max_symbols=500,
                    latency_ms=100,
                ),
            ),
            "amazingdata": ProviderCapabilitiesSpec(
                kline=KlineCapabilitySpec(
                    min_timeframe=Timeframe.M1,
                    max_timeframe=Timeframe.MO1,
                    history_days=365,
                    adjust_types=[AdjustType.NONE, AdjustType.FORWARD, AdjustType.BACKWARD],
                ),
                realtime_quote=RealtimeQuoteCapabilitySpec(
                    max_symbols=1000,
                    latency_ms=200,
                ),
            ),
            "akshare": ProviderCapabilitiesSpec(
                kline=KlineCapabilitySpec(
                    min_timeframe=Timeframe.D1,
                    max_timeframe=Timeframe.MO1,
                    history_days=3650,
                    adjust_types=[AdjustType.NONE, AdjustType.FORWARD, AdjustType.BACKWARD],
                    realtime_capable=False,
                ),
            ),
        },
        routing=RoutingConfig(
            kline=CapabilityRoutingRule(
                priority=["miniqmt", "amazingdata", "akshare"],
                scenarios={
                    "realtime": ScenarioRouting(priority=["miniqmt", "amazingdata"]),
                    "historical": ScenarioRouting(priority=["akshare", "amazingdata"]),
                },
            ),
            realtime_quote=CapabilityRoutingRule(
                priority=["amazingdata", "miniqmt"],
            ),
        ),
    )


# =============================================================================
# 路由逻辑集成测试
# =============================================================================


class TestRoutingIntegration:
    """路由逻辑集成测试"""

    def test_realtime_scenario_routes_to_miniqmt(self, sample_config):
        """实时场景应路由到 MiniQMT"""
        from deepsearch.infrastructure.providers.adapters.base import (
            BaseProviderAdapter,
            IKlineProvider,
        )

        class MockAdapter(BaseProviderAdapter, IKlineProvider):
            async def initialize(self):
                return True

            async def query_kline(self, request):
                return None

        adapters = {
            "miniqmt": MockAdapter("miniqmt", sample_config.capabilities["miniqmt"]),
            "amazingdata": MockAdapter("amazingdata", sample_config.capabilities["amazingdata"]),
            "akshare": MockAdapter("akshare", sample_config.capabilities["akshare"]),
        }
        router = CapabilityRouter(sample_config, adapters)

        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.M5,
            range=TimeRange.last_n(100),
            latency=LatencyHint.REALTIME,
        )

        adapter = router.resolve(request)
        assert adapter.name == "miniqmt"

    def test_historical_scenario_routes_to_akshare(self, sample_config):
        """历史场景应路由到 AKShare"""
        from deepsearch.infrastructure.providers.adapters.base import (
            BaseProviderAdapter,
            IKlineProvider,
        )

        class MockAdapter(BaseProviderAdapter, IKlineProvider):
            async def initialize(self):
                return True

            async def query_kline(self, request):
                return None

        adapters = {
            "miniqmt": MockAdapter("miniqmt", sample_config.capabilities["miniqmt"]),
            "amazingdata": MockAdapter("amazingdata", sample_config.capabilities["amazingdata"]),
            "akshare": MockAdapter("akshare", sample_config.capabilities["akshare"]),
        }
        router = CapabilityRouter(sample_config, adapters)

        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(365),
            latency=LatencyHint.BATCH,
        )

        adapter = router.resolve(request)
        assert adapter.name == "akshare"

    def test_monthly_timeframe_routes_to_capable_provider(self, sample_config):
        """月线请求应路由到支持的 Provider"""
        from deepsearch.infrastructure.providers.adapters.base import (
            BaseProviderAdapter,
            IKlineProvider,
        )

        class MockAdapter(BaseProviderAdapter, IKlineProvider):
            async def initialize(self):
                return True

            async def query_kline(self, request):
                return None

        adapters = {
            "miniqmt": MockAdapter("miniqmt", sample_config.capabilities["miniqmt"]),
            "amazingdata": MockAdapter("amazingdata", sample_config.capabilities["amazingdata"]),
            "akshare": MockAdapter("akshare", sample_config.capabilities["akshare"]),
        }
        router = CapabilityRouter(sample_config, adapters)

        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.MO1,  # MiniQMT 不支持
            range=TimeRange.last_n(12),
        )

        adapter = router.resolve(request)
        # MiniQMT 不支持月线，应路由到 amazingdata 或 akshare
        assert adapter.name in ["amazingdata", "akshare"]


# =============================================================================
# 配置加载集成测试
# =============================================================================


class TestConfigLoading:
    """配置加载集成测试"""

    @pytest.mark.skipif(
        not pytest.importorskip("deepsearch.config", reason="Config module not available"),
        reason="Config module required",
    )
    def test_load_capability_routing_from_config(self):
        """测试从配置文件加载 capability_routing"""
        import os

        os.environ["APP__ENV"] = "dev"

        from deepsearch.config import get_config

        config = get_config()
        cr = config.capability_routing

        if cr is not None:
            assert "miniqmt" in cr.capabilities or "amazingdata" in cr.capabilities
            assert cr.routing.kline is not None

    def test_parse_yaml_capability_spec(self):
        """测试解析 YAML 格式的能力声明"""
        from deepsearch.config.models.capability_routing import (
            CapabilityRoutingConfig,
        )

        yaml_data = {
            "capabilities": {
                "test_provider": {
                    "kline": {
                        "supported": True,
                        "min_timeframe": "1m",
                        "max_timeframe": "1d",
                        "history_days": 90,
                        "adjust_types": ["none", "qfq"],
                    },
                },
            },
            "routing": {
                "kline": {
                    "priority": ["test_provider"],
                },
            },
        }

        config = CapabilityRoutingConfig.model_validate(yaml_data)
        assert config.capabilities["test_provider"].kline is not None
        assert config.capabilities["test_provider"].kline.min_timeframe == Timeframe.M1
        assert AdjustType.FORWARD in config.capabilities["test_provider"].kline.adjust_types


# =============================================================================
# 端到端流程测试（Mock 方式）
# =============================================================================


class TestEndToEndWithMocks:
    """使用 Mock 的端到端测试"""

    @pytest.mark.asyncio
    async def test_complete_kline_query_flow(self, sample_config):
        """完整的 Kline 查询流程"""
        from deepsearch.infrastructure.providers.adapters.base import (
            BaseProviderAdapter,
            IKlineProvider,
        )
        from deepsearch.ports.data_sources import DataSourceType

        class MockKlineAdapter(BaseProviderAdapter, IKlineProvider):
            def __init__(self, name, capabilities):
                super().__init__(name=name, capabilities=capabilities)
                self.call_count = 0

            async def initialize(self):
                return True

            async def query_kline(self, request):
                self.call_count += 1
                from deepsearch.ports.data.responses import KlineBar, KlineResponse

                return KlineResponse(
                    asset=request.asset,
                    timeframe=request.timeframe,
                    bars=[
                        KlineBar(
                            timestamp=datetime(2024, 1, 1),
                            open=Decimal("10"),
                            high=Decimal("11"),
                            low=Decimal("9"),
                            close=Decimal("10.5"),
                            volume=100000,
                            amount=Decimal("1050000"),
                        ),
                    ],
                    source=DataSourceType.MINIQMT,
                    latency_ms=50,
                )

        # 创建所有适配器
        miniqmt = MockKlineAdapter("miniqmt", sample_config.capabilities["miniqmt"])
        amazingdata = MockKlineAdapter("amazingdata", sample_config.capabilities["amazingdata"])
        akshare = MockKlineAdapter("akshare", sample_config.capabilities["akshare"])

        adapters = {"miniqmt": miniqmt, "amazingdata": amazingdata, "akshare": akshare}
        router = CapabilityRouter(sample_config, adapters)
        feed = UnifiedDataFeed(router)

        # 使用 REALTIME 延迟提示，触发 miniqmt 优先
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(30),
            latency=LatencyHint.REALTIME,
        )

        response = await feed.query(request)

        # 验证
        assert isinstance(response, KlineResponse)
        assert len(response.bars) == 1
        assert response.bars[0].close == Decimal("10.5")
        assert miniqmt.call_count == 1


    @pytest.mark.asyncio
    async def test_fallback_on_first_provider_failure(self, sample_config):
        """第一个 Provider 失败时降级"""
        from deepsearch.infrastructure.providers.adapters.base import (
            BaseProviderAdapter,
            IKlineProvider,
        )
        from deepsearch.ports.data_sources import DataSourceType

        class FailingAdapter(BaseProviderAdapter, IKlineProvider):
            async def initialize(self):
                return True

            async def query_kline(self, request):
                raise Exception("Connection failed")

        class WorkingAdapter(BaseProviderAdapter, IKlineProvider):
            async def initialize(self):
                return True

            async def query_kline(self, request):
                from deepsearch.ports.data.responses import KlineResponse

                return KlineResponse(
                    asset=request.asset,
                    timeframe=request.timeframe,
                    bars=[],
                    source=DataSourceType.AKSHARE,
                    latency_ms=100,
                )

        adapters = {
            "miniqmt": FailingAdapter("miniqmt", sample_config.capabilities["miniqmt"]),
            "amazingdata": WorkingAdapter(
                "amazingdata", sample_config.capabilities["amazingdata"]
            ),
        }

        router = CapabilityRouter(sample_config, adapters)
        feed = UnifiedDataFeed(router)

        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(30),
        )

        # 使用降级策略
        response = await feed.query_with_fallback(
            request, strategy=FallbackStrategy.SEQUENTIAL
        )

        assert isinstance(response, KlineResponse)

    @pytest.mark.asyncio
    async def test_type_safe_convenience_methods(self, sample_config):
        """测试类型安全的便捷方法"""
        from deepsearch.infrastructure.providers.adapters.base import (
            BaseProviderAdapter,
            IKlineProvider,
        )
        from deepsearch.ports.data_sources import DataSourceType

        class MockAdapter(BaseProviderAdapter, IKlineProvider):
            async def initialize(self):
                return True

            async def query_kline(self, request):
                from deepsearch.ports.data.responses import KlineResponse

                return KlineResponse(
                    asset=request.asset,
                    timeframe=request.timeframe,
                    bars=[],
                    source=DataSourceType.MINIQMT,
                )

        # 注册所有适配器
        adapters = {
            "miniqmt": MockAdapter("miniqmt", sample_config.capabilities["miniqmt"]),
            "amazingdata": MockAdapter("amazingdata", sample_config.capabilities["amazingdata"]),
            "akshare": MockAdapter("akshare", sample_config.capabilities["akshare"]),
        }
        router = CapabilityRouter(sample_config, adapters)
        feed = UnifiedDataFeed(router)

        # 使用 REALTIME 延迟确保路由到 miniqmt
        request = KlineRequest(
            asset=AssetSpec.from_code("000001.SZ"),
            timeframe=Timeframe.D1,
            range=TimeRange.last_days(30),
            latency=LatencyHint.REALTIME,
        )

        # 使用类型安全方法
        response = await feed.get_kline(request)

        assert isinstance(response, KlineResponse)



# =============================================================================
# Realtime 能力测试
# =============================================================================


class TestRealtimeCapability:
    """Realtime 能力测试"""

    @pytest.mark.asyncio
    async def test_realtime_quote_request(self, sample_config):
        """测试实时行情请求"""
        from deepsearch.infrastructure.providers.adapters.base import (
            BaseProviderAdapter,
            IRealtimeProvider,
        )
        from deepsearch.ports.data_sources import DataSourceType

        class MockRealtimeAdapter(BaseProviderAdapter, IRealtimeProvider):
            async def initialize(self):
                return True

            async def query_realtime(self, request):
                from deepsearch.ports.data.responses import Quote, RealtimeQuoteResponse

                quotes = []
                for asset in request.assets:
                    quotes.append(
                        Quote(
                            asset=asset,
                            timestamp=datetime.now(),
                            last_price=Decimal("10.50"),
                            open=Decimal("10.00"),
                            high=Decimal("10.80"),
                            low=Decimal("9.90"),
                            pre_close=Decimal("10.00"),
                            volume=5000000,
                            amount=Decimal("52500000"),
                        )
                    )
                return RealtimeQuoteResponse(
                    quotes=quotes,
                    source=DataSourceType.AMAZINGDATA,
                    latency_ms=100,
                )

        adapters = {
            "amazingdata": MockRealtimeAdapter(
                "amazingdata", sample_config.capabilities["amazingdata"]
            ),
        }

        router = CapabilityRouter(sample_config, adapters)
        feed = UnifiedDataFeed(router)

        request = RealtimeQuoteRequest(
            assets=[
                AssetSpec.from_code("000001.SZ"),
                AssetSpec.from_code("600000.SH"),
            ]
        )

        response = await feed.get_realtime(request)

        assert isinstance(response, RealtimeQuoteResponse)
        assert len(response.quotes) == 2
        assert response.quotes[0].last_price == Decimal("10.50")
