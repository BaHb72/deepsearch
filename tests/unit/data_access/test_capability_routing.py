"""
CapabilityRoutingConfig 单元测试。

测试 config/models/capability_routing.py 中的配置模型。
"""

from core.config.models.capability_routing import (
    CapabilityRoutingConfig,
    CapabilityRoutingRule,
    KlineCapabilitySpec,
    ProviderCapabilitiesSpec,
    RealtimeQuoteCapabilitySpec,
    RoutingConfig,
    ScenarioRouting,
    StockListCapabilitySpec,
    TickCapabilitySpec,
)
from core.ports.data.semantic_types import AdjustType, Timeframe


class TestKlineCapabilitySpec:
    """KlineCapabilitySpec 测试"""

    def test_default_values(self):
        """测试默认值"""
        spec = KlineCapabilitySpec()
        assert spec.supported is True
        assert spec.min_timeframe == Timeframe.D1
        assert spec.max_timeframe == Timeframe.MO1
        assert spec.history_days == 365

    def test_custom_values(self):
        """测试自定义值"""
        spec = KlineCapabilitySpec(
            min_timeframe=Timeframe.M1,
            max_timeframe=Timeframe.W1,
            history_days=90,
            adjust_types=[AdjustType.NONE, AdjustType.FORWARD],
            realtime_capable=True,
        )
        assert spec.min_timeframe == Timeframe.M1
        assert spec.realtime_capable is True
        assert len(spec.adjust_types) == 2


class TestProviderCapabilitiesSpec:
    """ProviderCapabilitiesSpec 测试"""

    def test_supports_kline(self):
        """测试 kline 支持检查"""
        spec = ProviderCapabilitiesSpec(
            kline=KlineCapabilitySpec(supported=True),
        )
        assert spec.supports("kline") is True
        assert spec.supports("realtime_quote") is False

    def test_supports_multiple(self):
        """测试多能力支持"""
        spec = ProviderCapabilitiesSpec(
            kline=KlineCapabilitySpec(),
            realtime_quote=RealtimeQuoteCapabilitySpec(),
            tick=TickCapabilitySpec(),
        )
        assert spec.supports("kline") is True
        assert spec.supports("realtime_quote") is True
        assert spec.supports("tick") is True
        assert spec.supports("stock_list") is False

    def test_get_capability_spec(self):
        """测试获取能力规格"""
        kline_spec = KlineCapabilitySpec(history_days=100)
        spec = ProviderCapabilitiesSpec(kline=kline_spec)
        retrieved = spec.get_capability_spec("kline")
        assert retrieved.history_days == 100


class TestScenarioRouting:
    """ScenarioRouting 测试"""

    def test_default_values(self):
        """测试默认值"""
        routing = ScenarioRouting(priority=["miniqmt", "amazingdata"])
        assert routing.fallback is True
        assert routing.priority == ["miniqmt", "amazingdata"]


class TestCapabilityRoutingRule:
    """CapabilityRoutingRule 测试"""

    def test_basic_rule(self):
        """测试基本规则"""
        rule = CapabilityRoutingRule(
            priority=["miniqmt", "amazingdata", "akshare"],
            fallback=True,
        )
        assert len(rule.priority) == 3
        assert rule.fallback is True

    def test_rule_with_scenarios(self):
        """测试带场景的规则"""
        rule = CapabilityRoutingRule(
            priority=["miniqmt"],
            scenarios={
                "realtime": ScenarioRouting(priority=["miniqmt"]),
                "historical": ScenarioRouting(priority=["akshare", "amazingdata"]),
            },
        )
        assert "realtime" in rule.scenarios
        assert rule.scenarios["historical"].priority == ["akshare", "amazingdata"]

    def test_rule_with_timeframe_routing(self):
        """测试按周期路由"""
        rule = CapabilityRoutingRule(
            priority=["miniqmt"],
            by_timeframe={
                "1m": ["miniqmt"],
                "1d": ["akshare", "amazingdata"],
            },
        )
        assert rule.by_timeframe["1m"] == ["miniqmt"]


class TestRoutingConfig:
    """RoutingConfig 测试"""

    def test_get_rule(self):
        """测试获取路由规则"""
        config = RoutingConfig(
            kline=CapabilityRoutingRule(priority=["miniqmt"]),
            realtime_quote=CapabilityRoutingRule(priority=["amazingdata"]),
        )
        kline_rule = config.get_rule("kline")
        assert kline_rule.priority == ["miniqmt"]

        tick_rule = config.get_rule("tick")
        assert tick_rule is None


class TestCapabilityRoutingConfig:
    """CapabilityRoutingConfig 测试"""

    def test_empty_config(self):
        """测试空配置"""
        config = CapabilityRoutingConfig()
        assert len(config.capabilities) == 0

    def test_full_config(self):
        """测试完整配置"""
        config = CapabilityRoutingConfig(
            capabilities={
                "miniqmt": ProviderCapabilitiesSpec(
                    kline=KlineCapabilitySpec(
                        min_timeframe=Timeframe.M1,
                        max_timeframe=Timeframe.D1,
                    ),
                    realtime_quote=RealtimeQuoteCapabilitySpec(),
                ),
                "akshare": ProviderCapabilitiesSpec(
                    kline=KlineCapabilitySpec(
                        min_timeframe=Timeframe.D1,
                        history_days=3650,
                    ),
                    stock_list=StockListCapabilitySpec(),
                ),
            },
            routing=RoutingConfig(
                kline=CapabilityRoutingRule(
                    priority=["miniqmt", "akshare"],
                ),
            ),
        )
        assert len(config.capabilities) == 2
        assert config.routing.kline.priority == ["miniqmt", "akshare"]

    def test_get_providers_for_capability(self):
        """测试获取支持某能力的 Provider"""
        config = CapabilityRoutingConfig(
            capabilities={
                "miniqmt": ProviderCapabilitiesSpec(
                    kline=KlineCapabilitySpec(),
                    realtime_quote=RealtimeQuoteCapabilitySpec(),
                ),
                "akshare": ProviderCapabilitiesSpec(
                    kline=KlineCapabilitySpec(),
                ),
                "other": ProviderCapabilitiesSpec(),
            },
        )
        kline_providers = config.get_providers_for_capability("kline")
        assert "miniqmt" in kline_providers
        assert "akshare" in kline_providers
        assert "other" not in kline_providers

        realtime_providers = config.get_providers_for_capability("realtime_quote")
        assert "miniqmt" in realtime_providers
        assert "akshare" not in realtime_providers

    def test_from_yaml_dict(self):
        """测试从 YAML 字典创建"""
        yaml_data = {
            "capabilities": {
                "miniqmt": {
                    "kline": {
                        "supported": True,
                        "min_timeframe": "1m",
                        "max_timeframe": "1d",
                        "history_days": 90,
                    },
                },
            },
            "routing": {
                "kline": {
                    "priority": ["miniqmt"],
                },
            },
        }
        config = CapabilityRoutingConfig.model_validate(yaml_data)
        assert "miniqmt" in config.capabilities
        assert config.capabilities["miniqmt"].kline.min_timeframe == Timeframe.M1
