"""
Provider 数据能力协议

定义各种数据查询能力接口。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# 导入现有的 Request/Response 类型
from core.ports.data.requests import (
    KlineRequest,
    RealtimeQuoteRequest,
    StockListRequest,
    TickRequest,
)
from core.ports.data.responses import (
    KlineResponse,
    RealtimeQuoteResponse,
    StockListResponse,
    TickResponse,
)


@runtime_checkable
class IKlineProvider(Protocol):
    """K线数据能力"""

    async def query_kline(self, request: KlineRequest) -> KlineResponse:
        """查询K线数据

        Args:
            request: K线请求参数

        Returns:
            KlineResponse: K线响应数据

        Raises:
            ProviderDataError: 数据查询失败
            ProviderTimeoutError: 查询超时
        """
        ...


@runtime_checkable
class IRealtimeProvider(Protocol):
    """实时行情能力"""

    async def query_realtime(self, request: RealtimeQuoteRequest) -> RealtimeQuoteResponse:
        """查询实时行情

        Args:
            request: 实时行情请求参数

        Returns:
            RealtimeQuoteResponse: 实时行情响应数据

        Raises:
            ProviderDataError: 数据查询失败
            ProviderTimeoutError: 查询超时
        """
        ...


@runtime_checkable
class ITickProvider(Protocol):
    """Tick数据能力"""

    async def query_tick(self, request: TickRequest) -> TickResponse:
        """查询Tick数据

        Args:
            request: Tick请求参数

        Returns:
            TickResponse: Tick响应数据

        Raises:
            ProviderDataError: 数据查询失败
            ProviderTimeoutError: 查询超时
        """
        ...


@runtime_checkable
class IStockListProvider(Protocol):
    """股票列表能力"""

    async def query_stock_list(self, request: StockListRequest) -> StockListResponse:
        """查询股票列表

        Args:
            request: 股票列表请求参数

        Returns:
            StockListResponse: 股票列表响应数据

        Raises:
            ProviderDataError: 数据查询失败
            ProviderTimeoutError: 查询超时
        """
        ...
