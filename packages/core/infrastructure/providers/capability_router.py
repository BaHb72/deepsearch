"""
能力路由器。

根据请求类型和配置规则，路由到最佳的 Provider Adapter。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, TypeVar

from core.config.models.capability_routing import CapabilityRoutingConfig
from core.ports.data.capabilities import DataCapability
from core.ports.data.requests import (
    DataRequest,
    KlineRequest,
    OrderbookRequest,
    RealtimeQuoteRequest,
    StockListRequest,
    TickRequest,
)
from core.ports.data.semantic_types import LatencyHint
from loguru import logger

from .adapters.base import BaseProviderAdapter

if TYPE_CHECKING:
    pass


T = TypeVar("T", bound=BaseProviderAdapter)


class NoProviderAvailableError(Exception):
    """无可用 Provider 异常"""

    def __init__(self, capability: DataCapability, request: DataRequest):
        self.capability = capability
        self.request = request
        super().__init__(
            f"No provider available for capability '{capability}' with request {type(request).__name__}"
        )


class CapabilityRouter:
    """
    能力路由器。

    根据请求类型和配置规则，选择最佳的 Provider。
    支持：
    - 场景路由（realtime vs historical）
    - timeframe 路由
    - 降级策略
    """

    def __init__(
        self,
        config: CapabilityRoutingConfig,
        adapters: Dict[str, BaseProviderAdapter],
    ):
        """
        初始化路由器。

        Args:
            config: 能力路由配置
            adapters: 已注册的适配器字典 {name: adapter}
        """
        self._config = config
        self._adapters = adapters

    @property
    def adapters(self) -> Dict[str, BaseProviderAdapter]:
        """已注册的适配器"""
        return self._adapters

    def register_adapter(self, name: str, adapter: BaseProviderAdapter) -> None:
        """注册适配器"""
        self._adapters[name] = adapter
        logger.info(f"注册适配器: {name}")

    def unregister_adapter(self, name: str) -> None:
        """注销适配器"""
        if name in self._adapters:
            del self._adapters[name]
            logger.info(f"注销适配器: {name}")

    def resolve(self, request: DataRequest) -> BaseProviderAdapter:
        """
        解析请求到最佳适配器。

        Args:
            request: 数据请求

        Returns:
            最佳适配器

        Raises:
            NoProviderAvailableError: 无可用 Provider
        """
        capability = self._infer_capability(request)
        priority_list = self._get_priority_list(request, capability)

        for provider_name in priority_list:
            adapter = self._adapters.get(provider_name)
            if adapter and self._can_handle(adapter, request, capability):
                logger.debug(f"路由到: {provider_name} for {capability}")
                return adapter

        raise NoProviderAvailableError(capability, request)

    def resolve_all(self, request: DataRequest) -> List[BaseProviderAdapter]:
        """
        获取所有可处理该请求的适配器。

        Args:
            request: 数据请求

        Returns:
            适配器列表（按优先级排序）
        """
        capability = self._infer_capability(request)
        priority_list = self._get_priority_list(request, capability)
        result = []

        for provider_name in priority_list:
            adapter = self._adapters.get(provider_name)
            if adapter and self._can_handle(adapter, request, capability):
                result.append(adapter)

        return result

    def _infer_capability(self, request: DataRequest) -> DataCapability:
        """从请求类型推断能力类型"""
        if isinstance(request, KlineRequest):
            return DataCapability.KLINE
        elif isinstance(request, RealtimeQuoteRequest):
            return DataCapability.REALTIME_QUOTE
        elif isinstance(request, TickRequest):
            return DataCapability.TICK
        elif isinstance(request, StockListRequest):
            return DataCapability.STOCK_LIST
        elif isinstance(request, OrderbookRequest):
            return DataCapability.ORDERBOOK
        else:
            raise ValueError(f"Unknown request type: {type(request)}")

    def _get_priority_list(
        self,
        request: DataRequest,
        capability: DataCapability,
    ) -> List[str]:
        """
        获取 Provider 优先级列表。

        支持场景路由和 timeframe 路由。
        """
        routing_rule = self._config.routing.get_rule(capability.value)
        if routing_rule is None:
            # 无路由规则，返回所有注册的适配器
            return list(self._adapters.keys())

        # 1. 检查场景路由
        if routing_rule.scenarios:
            scenario = self._detect_scenario(request)
            if scenario in routing_rule.scenarios:
                return routing_rule.scenarios[scenario].priority

        # 2. 检查 timeframe 路由（仅 Kline）
        if routing_rule.by_timeframe and isinstance(request, KlineRequest):
            tf_key = request.timeframe.value
            if tf_key in routing_rule.by_timeframe:
                return routing_rule.by_timeframe[tf_key]

        # 3. 默认优先级
        return routing_rule.priority

    def _detect_scenario(self, request: DataRequest) -> str:
        """检测请求场景"""
        if isinstance(request, KlineRequest):
            if request.latency == LatencyHint.REALTIME:
                return "realtime"
            return "historical"
        elif isinstance(request, (RealtimeQuoteRequest, TickRequest)):
            return "realtime"
        return "default"

    def _can_handle(
        self,
        adapter: BaseProviderAdapter,
        request: DataRequest,
        capability: DataCapability,
    ) -> bool:
        """检查适配器是否能处理该请求"""
        # 基础能力检查
        if not adapter.supports(capability):
            return False

        # 详细能力检查（针对 Kline）
        if isinstance(request, KlineRequest):
            spec = adapter.capabilities.kline
            if spec is None:
                return False

            # 检查 timeframe 范围
            if request.timeframe < spec.min_timeframe:
                return False
            if request.timeframe > spec.max_timeframe:
                return False

            # 检查复权类型
            if request.adjust not in spec.adjust_types:
                return False

        return True


__all__ = [
    "CapabilityRouter",
    "NoProviderAvailableError",
]
