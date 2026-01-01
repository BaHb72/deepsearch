"""
适配器基类和能力接口定义。

该模块定义：
- 能力接口（Protocol）：IKlineProvider, IRealtimeProvider 等
- 基础适配器类：用于包装现有 Provider
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from deepsearch.config.models.capability_routing import ProviderCapabilitiesSpec
from deepsearch.ports.data.capabilities import DataCapability
from deepsearch.ports.data.requests import (
    KlineRequest,
    OrderbookRequest,
    RealtimeQuoteRequest,
    StockListRequest,
    TickRequest,
)
from deepsearch.ports.data.responses import (
    KlineResponse,
    RealtimeQuoteResponse,
    StockListResponse,
    TickResponse,
)

if TYPE_CHECKING:
    pass


class CapabilityNotSupportedError(Exception):
    """能力不支持异常"""

    def __init__(self, capability: str, provider: str, reason: str = ""):
        self.capability = capability
        self.provider = provider
        self.reason = reason
        message = f"Provider '{provider}' does not support capability '{capability}'"
        if reason:
            message += f": {reason}"
        super().__init__(message)


# ============================================================================
# 能力接口定义（Protocol）
# ============================================================================


@runtime_checkable
class IKlineProvider(Protocol):
    """K线数据能力接口"""

    async def query_kline(self, request: KlineRequest) -> KlineResponse:
        """查询K线数据"""
        ...


@runtime_checkable
class IRealtimeProvider(Protocol):
    """实时行情能力接口"""

    async def query_realtime(self, request: RealtimeQuoteRequest) -> RealtimeQuoteResponse:
        """查询实时行情"""
        ...


@runtime_checkable
class ITickProvider(Protocol):
    """Tick数据能力接口"""

    async def query_tick(self, request: TickRequest) -> TickResponse:
        """查询Tick数据"""
        ...


@runtime_checkable
class IStockListProvider(Protocol):
    """股票列表能力接口"""

    async def query_stock_list(self, request: StockListRequest) -> StockListResponse:
        """查询股票列表"""
        ...


@runtime_checkable
class IOrderbookProvider(Protocol):
    """盘口数据能力接口"""

    async def query_orderbook(self, request: OrderbookRequest) -> RealtimeQuoteResponse:
        """查询盘口数据"""
        ...


# 能力接口类型联合
ProviderAdapter = IKlineProvider | IRealtimeProvider | ITickProvider | IStockListProvider | IOrderbookProvider


# ============================================================================
# 基础适配器类
# ============================================================================


class BaseProviderAdapter(ABC):
    """
    适配器基类。

    包装现有的 DataProvider，实现新的能力接口。
    """

    def __init__(self, name: str, capabilities: ProviderCapabilitiesSpec):
        self._name = name
        self._capabilities = capabilities
        self._last_latency_ms: int = 0

    @property
    def name(self) -> str:
        """适配器名称"""
        return self._name

    @property
    def capabilities(self) -> ProviderCapabilitiesSpec:
        """能力声明"""
        return self._capabilities

    @property
    def last_latency_ms(self) -> int:
        """最后一次请求的延迟"""
        return self._last_latency_ms

    def supports(self, capability: DataCapability) -> bool:
        """检查是否支持某能力"""
        return self._capabilities.supports(capability.value)

    @abstractmethod
    async def initialize(self) -> bool:
        """初始化适配器"""
        ...


__all__ = [
    "CapabilityNotSupportedError",
    "IKlineProvider",
    "IRealtimeProvider",
    "ITickProvider",
    "IStockListProvider",
    "IOrderbookProvider",
    "ProviderAdapter",
    "BaseProviderAdapter",
]
