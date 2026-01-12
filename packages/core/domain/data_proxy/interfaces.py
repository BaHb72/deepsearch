"""
Data Source Adapter Interfaces

定义数据源适配器的抽象协议，所有数据源必须实现这些接口。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, Sequence, runtime_checkable

if TYPE_CHECKING:
    import pandas as pd
    from core.ports.market_data import MarketSnapshot


@runtime_checkable
class DataSourceAdapter(Protocol):
    """数据源适配器协议

    所有数据源（AmazingData、MiniQMT、AkShare）必须实现此协议。
    """

    @property
    def name(self) -> str:
        """数据源名称"""
        ...

    @property
    def capabilities(self) -> set[str]:
        """支持的能力集合

        Returns:
            能力集合，如 {"kline", "realtime", "calendar", "stock_list"}
        """
        ...

    async def is_available(self) -> bool:
        """检查数据源是否可用

        Returns:
            True 如果数据源可用
        """
        ...

    async def get_latency(self) -> float:
        """获取当前延迟估计（毫秒）

        Returns:
            最近请求的平均延迟
        """
        ...


@runtime_checkable
class KlineCapable(Protocol):
    """K 线数据能力"""

    async def get_kline(
        self,
        symbol: str,
        period: str = "1d",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> "pd.DataFrame":
        """获取 K 线数据

        Args:
            symbol: 股票代码 (如 "000001")
            period: 周期 ("1m", "5m", "15m", "30m", "60m", "1d", "1w", "1M")
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            limit: 返回数量限制

        Returns:
            包含 OHLCV 数据的 DataFrame
        """
        ...


@runtime_checkable
class RealtimeCapable(Protocol):
    """实时行情能力"""

    async def get_realtime_quotes(
        self,
        symbols: Sequence[str],
    ) -> Sequence["MarketSnapshot"]:
        """获取实时行情

        Args:
            symbols: 股票代码列表

        Returns:
            MarketSnapshot 列表
        """
        ...


@runtime_checkable
class CalendarCapable(Protocol):
    """交易日历能力"""

    async def get_calendar(
        self,
        market: str = "SH",
    ) -> list[int]:
        """获取交易日历

        Args:
            market: 市场代码 ("SH", "SZ", "BJ")

        Returns:
            交易日列表 (格式: 20250102)
        """
        ...


@runtime_checkable
class StockListCapable(Protocol):
    """股票列表能力"""

    async def get_stock_list(
        self,
        market: str | None = None,
        board: str | None = None,
    ) -> Sequence[dict[str, Any]]:
        """获取股票列表

        Args:
            market: 市场过滤 ("SH", "SZ", "BJ")
            board: 板块过滤 ("主板", "创业板", "科创板")

        Returns:
            股票信息列表
        """
        ...


@runtime_checkable
class SubscriptionCapable(Protocol):
    """实时订阅能力"""

    async def subscribe(
        self,
        symbols: Sequence[str],
        callback_topic: str,
    ) -> None:
        """订阅实时行情

        Args:
            symbols: 股票代码列表
            callback_topic: 消息总线回调主题
        """
        ...

    async def unsubscribe(
        self,
        symbols: Sequence[str],
    ) -> None:
        """取消订阅

        Args:
            symbols: 股票代码列表
        """
        ...


# 能力常量
CAPABILITY_KLINE = "kline"
CAPABILITY_REALTIME = "realtime"
CAPABILITY_CALENDAR = "calendar"
CAPABILITY_STOCK_LIST = "stock_list"
CAPABILITY_SUBSCRIPTION = "subscription"

# 所有能力
ALL_CAPABILITIES = frozenset(
    {
        CAPABILITY_KLINE,
        CAPABILITY_REALTIME,
        CAPABILITY_CALENDAR,
        CAPABILITY_STOCK_LIST,
        CAPABILITY_SUBSCRIPTION,
    }
)
