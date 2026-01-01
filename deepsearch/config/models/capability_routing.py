"""
能力路由配置模型。

该模块为 settings.<env>.yaml 中 capability_routing 区块提供 Pydantic 支持。
配置结构：
- capabilities: 各数据源的能力声明
- routing: 按能力类型的路由规则
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from deepsearch.ports.data.semantic_types import AdjustType, Timeframe


# ============================================================================
# 能力规格定义
# ============================================================================


class KlineCapabilitySpec(BaseModel):
    """K线能力规格"""

    model_config = ConfigDict(extra="ignore")

    supported: bool = True
    min_timeframe: Timeframe = Timeframe.D1
    max_timeframe: Timeframe = Timeframe.MO1
    history_days: int = Field(default=365, ge=1, description="历史数据天数")
    adjust_types: List[AdjustType] = Field(
        default_factory=lambda: [AdjustType.NONE],
        description="支持的复权类型",
    )
    realtime_capable: bool = Field(default=False, description="是否支持实时K线")


class RealtimeQuoteCapabilitySpec(BaseModel):
    """实时行情能力规格"""

    model_config = ConfigDict(extra="ignore")

    supported: bool = True
    max_symbols: int = Field(default=100, ge=1, description="最大订阅数量")
    latency_ms: int = Field(default=1000, ge=1, description="预期延迟毫秒")
    premarket: bool = Field(default=False, description="支持盘前")
    afterhours: bool = Field(default=False, description="支持盘后")


class TickCapabilitySpec(BaseModel):
    """Tick 能力规格"""

    model_config = ConfigDict(extra="ignore")

    supported: bool = True
    max_symbols: int = Field(default=50, ge=1)
    include_depth: bool = Field(default=True, description="是否包含盘口")


class StockListCapabilitySpec(BaseModel):
    """股票列表能力规格"""

    model_config = ConfigDict(extra="ignore")

    supported: bool = True
    cache_ttl: int = Field(default=86400, ge=0, description="缓存秒数")


class OrderbookCapabilitySpec(BaseModel):
    """盘口能力规格"""

    model_config = ConfigDict(extra="ignore")

    supported: bool = True
    depth_levels: int = Field(default=5, ge=1, description="档位深度")


class QualityMetrics(BaseModel):
    """数据质量指标"""

    model_config = ConfigDict(extra="ignore")

    reliability: float = Field(default=0.9, ge=0, le=1, description="可靠性评分")
    avg_latency_ms: int = Field(default=500, ge=0, description="平均延迟")
    rate_limit_per_minute: Optional[int] = Field(default=None, description="每分钟限流")


# ============================================================================
# Provider 能力声明
# ============================================================================


class ProviderCapabilitiesSpec(BaseModel):
    """单个 Provider 的能力声明"""

    model_config = ConfigDict(extra="ignore")

    kline: Optional[KlineCapabilitySpec] = None
    realtime_quote: Optional[RealtimeQuoteCapabilitySpec] = None
    tick: Optional[TickCapabilitySpec] = None
    stock_list: Optional[StockListCapabilitySpec] = None
    orderbook: Optional[OrderbookCapabilitySpec] = None
    quality: QualityMetrics = Field(default_factory=QualityMetrics)

    def supports(self, capability: str) -> bool:
        """检查是否支持某能力"""
        spec = getattr(self, capability, None)
        if spec is None:
            return False
        return getattr(spec, "supported", False)

    def get_capability_spec(self, capability: str) -> BaseModel | None:
        """获取能力规格"""
        return getattr(self, capability, None)


# ============================================================================
# 路由规则定义
# ============================================================================


class ScenarioRouting(BaseModel):
    """场景路由规则"""

    model_config = ConfigDict(extra="ignore")

    priority: List[str] = Field(default_factory=list, description="Provider 优先级列表")
    fallback: bool = Field(default=True, description="是否启用降级")


class CapabilityRoutingRule(BaseModel):
    """单个能力的路由规则"""

    model_config = ConfigDict(extra="ignore")

    priority: List[str] = Field(default_factory=list, description="默认优先级")
    fallback: bool = Field(default=True, description="是否启用降级")
    cache_ttl: Optional[int] = Field(default=None, description="响应缓存秒数")

    # 场景路由：如 realtime / historical
    scenarios: Optional[Dict[str, ScenarioRouting]] = Field(
        default=None,
        description="按场景的路由规则",
    )

    # 按 timeframe 路由（仅 kline）
    by_timeframe: Optional[Dict[str, List[str]]] = Field(
        default=None,
        description="按周期的路由规则",
    )


class RoutingConfig(BaseModel):
    """路由规则配置"""

    model_config = ConfigDict(extra="ignore")

    kline: Optional[CapabilityRoutingRule] = None
    realtime_quote: Optional[CapabilityRoutingRule] = None
    tick: Optional[CapabilityRoutingRule] = None
    stock_list: Optional[CapabilityRoutingRule] = None
    orderbook: Optional[CapabilityRoutingRule] = None

    def get_rule(self, capability: str) -> CapabilityRoutingRule | None:
        """获取能力的路由规则"""
        return getattr(self, capability, None)


# ============================================================================
# 顶层配置
# ============================================================================


class CapabilityRoutingConfig(BaseModel):
    """
    capability_routing 顶层配置。

    用于读取 settings.yaml 中的 capability_routing 节。
    """

    model_config = ConfigDict(extra="ignore")

    capabilities: Dict[str, ProviderCapabilitiesSpec] = Field(
        default_factory=dict,
        description="各 Provider 的能力声明",
    )
    routing: RoutingConfig = Field(
        default_factory=RoutingConfig,
        description="路由规则",
    )

    def get_providers_for_capability(self, capability: str) -> List[str]:
        """获取支持某能力的所有 Provider"""
        return [
            name
            for name, spec in self.capabilities.items()
            if spec.supports(capability)
        ]

    def get_provider_capability(
        self, provider: str, capability: str
    ) -> BaseModel | None:
        """获取指定 Provider 的能力规格"""
        spec = self.capabilities.get(provider)
        if spec is None:
            return None
        return spec.get_capability_spec(capability)


__all__ = [
    "KlineCapabilitySpec",
    "RealtimeQuoteCapabilitySpec",
    "TickCapabilitySpec",
    "StockListCapabilitySpec",
    "OrderbookCapabilitySpec",
    "QualityMetrics",
    "ProviderCapabilitiesSpec",
    "ScenarioRouting",
    "CapabilityRoutingRule",
    "RoutingConfig",
    "CapabilityRoutingConfig",
]
