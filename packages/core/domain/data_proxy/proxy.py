"""
Unified Data Proxy

统一数据代理，应用层唯一的数据访问入口。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Sequence

from loguru import logger

from .interfaces import (
    CAPABILITY_CALENDAR,
    CAPABILITY_KLINE,
    CAPABILITY_REALTIME,
    CAPABILITY_STOCK_LIST,
    CAPABILITY_SUBSCRIPTION,
    CalendarCapable,
    KlineCapable,
    RealtimeCapable,
    StockListCapable,
    SubscriptionCapable,
)
from .router import DataSourceRouter

if TYPE_CHECKING:
    import pandas as pd
    from core.ports.market_data import MarketSnapshot

    from .interfaces import DataSourceAdapter


# 全局单例
_global_proxy: "UnifiedDataProxy | None" = None


class UnifiedDataProxy:
    """统一数据代理

    应用层唯一的数据访问入口，提供数据源无感的接口。

    Features:
        - 自动路由：根据延迟选择最佳数据源
        - 故障降级：不可用时自动切换备用数据源
        - 延迟追踪：记录每个数据源的响应时间
        - 统一接口：抹平不同数据源的差异

    Example:
        >>> proxy = get_data_proxy()
        >>> data = await proxy.get_kline("000001", period="1d")
        >>> quotes = await proxy.get_realtime_quotes(["000001", "000002"])
    """

    def __init__(
        self,
        router: DataSourceRouter | None = None,
        default_preference: str = "latency",
    ):
        """初始化数据代理

        .. deprecated:: 2026-01
            UnifiedDataProxy 已废弃，请使用新的 DataAccessProxy:
            from core.infrastructure.providers.unified_proxy import get_data_proxy

        Args:
            router: 路由器实例
            default_preference: 默认路由偏好 ("latency" | "priority")
        """
        import warnings

        warnings.warn(
            "UnifiedDataProxy 已废弃，请使用 core.infrastructure.providers.unified_proxy.DataAccessProxy",
            DeprecationWarning,
            stacklevel=2,
        )

        self._router = router or DataSourceRouter()
        self._default_preference = default_preference
        self._initialized = False

    def register_adapter(self, adapter: "DataSourceAdapter") -> None:
        """注册数据源适配器

        Args:
            adapter: 数据源适配器实例
        """
        self._router.register_adapter(adapter)

    async def initialize(self) -> None:
        """初始化所有适配器

        .. deprecated:: 2026-01
            UnifiedDataProxy 已废弃，请使用新的 DataAccessProxy:
            from core.infrastructure.providers.unified_proxy import get_data_proxy

            新实现已包含完整的初始化逻辑、熔断器、监控和重试功能。
        """
        import warnings

        warnings.warn(
            "UnifiedDataProxy 已废弃，请使用 core.infrastructure.providers.unified_proxy.DataAccessProxy",
            DeprecationWarning,
            stacklevel=2,
        )

        if self._initialized:
            return

        # 简单初始化逻辑（保持向后兼容）
        # 实际项目应迁移到 DataAccessProxy
        for adapter_name in list(self._router._adapters.keys()):
            adapter = self._router.get_adapter(adapter_name)
            if adapter and hasattr(adapter, "initialize"):
                try:
                    await adapter.initialize()
                    logger.debug(f"已初始化适配器: {adapter_name}")
                except Exception as e:
                    logger.warning(f"适配器 {adapter_name} 初始化失败: {e}")

        self._initialized = True
        logger.info("UnifiedDataProxy 初始化完成（已废弃，建议迁移到 DataAccessProxy）")

    # ==================== K 线数据 ====================

    async def get_kline(
        self,
        symbol: str,
        period: str = "1d",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
        source: str = "auto",
    ) -> "pd.DataFrame":
        """获取 K 线数据

        Args:
            symbol: 股票代码 (如 "000001")
            period: 周期 ("1m", "5m", "15m", "30m", "60m", "1d", "1w", "1M")
            start_date: 开始日期 (YYYYMMDD)
            end_date: 结束日期 (YYYYMMDD)
            limit: 返回数量限制
            source: 数据源 ("auto" | "miniqmt" | "akshare" | "amazingdata")

        Returns:
            包含 OHLCV 数据的 DataFrame

        Raises:
            RuntimeError: 所有数据源都失败
        """

        # 选择数据源
        if source == "auto":
            source_name = await self._router.select_source(
                CAPABILITY_KLINE, preference=self._default_preference
            )
        else:
            source_name = source

        if not source_name:
            raise RuntimeError("没有可用的数据源支持 K 线查询")

        # 获取适配器并执行
        adapter = self._router.get_adapter(source_name)
        if adapter is None or not isinstance(adapter, KlineCapable):
            raise RuntimeError(f"数据源 {source_name} 不支持 K 线查询")

        start_time = time.perf_counter()
        try:
            result = await adapter.get_kline(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._router.record_latency(source_name, latency_ms)
            logger.debug(
                "K 线查询完成: {} {} from {} ({:.1f}ms)",
                symbol,
                period,
                source_name,
                latency_ms,
            )
            return result
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._router.record_latency(source_name, latency_ms + 1000)  # 惩罚延迟
            logger.warning("K 线查询失败 ({} {}): {}", source_name, symbol, e)
            # 尝试降级
            if source == "auto":
                return await self.get_kline(
                    symbol=symbol,
                    period=period,
                    start_date=start_date,
                    end_date=end_date,
                    limit=limit,
                    source=await self._router.select_source(CAPABILITY_KLINE, exclude=[source_name])
                    or "",
                )
            raise

    # ==================== 实时行情 ====================

    async def get_realtime_quotes(
        self,
        symbols: Sequence[str],
        source: str = "auto",
    ) -> Sequence["MarketSnapshot"]:
        """获取实时行情

        Args:
            symbols: 股票代码列表
            source: 数据源 ("auto" | "miniqmt" | "amazingdata")

        Returns:
            MarketSnapshot 列表
        """
        if source == "auto":
            source_name = await self._router.select_source(
                CAPABILITY_REALTIME, preference=self._default_preference
            )
        else:
            source_name = source

        if not source_name:
            raise RuntimeError("没有可用的数据源支持实时行情")

        adapter = self._router.get_adapter(source_name)
        if adapter is None or not isinstance(adapter, RealtimeCapable):
            raise RuntimeError(f"数据源 {source_name} 不支持实时行情")

        start_time = time.perf_counter()
        try:
            result = await adapter.get_realtime_quotes(symbols)
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._router.record_latency(source_name, latency_ms)
            return result
        except Exception as e:
            logger.warning("实时行情查询失败 ({}): {}", source_name, e)
            raise

    # ==================== 交易日历 ====================

    async def get_calendar(
        self,
        market: str = "SH",
        source: str = "auto",
    ) -> list[int]:
        """获取交易日历

        Args:
            market: 市场代码 ("SH", "SZ", "BJ")
            source: 数据源

        Returns:
            交易日列表 (格式: 20250102)
        """
        if source == "auto":
            source_name = await self._router.select_source(
                CAPABILITY_CALENDAR, preference=self._default_preference
            )
        else:
            source_name = source

        if not source_name:
            raise RuntimeError("没有可用的数据源支持交易日历")

        adapter = self._router.get_adapter(source_name)
        if adapter is None or not isinstance(adapter, CalendarCapable):
            raise RuntimeError(f"数据源 {source_name} 不支持交易日历")

        start_time = time.perf_counter()
        try:
            result = await adapter.get_calendar(market)
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._router.record_latency(source_name, latency_ms)
            return result
        except Exception as e:
            logger.warning("交易日历查询失败 ({}): {}", source_name, e)
            raise

    # ==================== 股票列表 ====================

    async def get_stock_list(
        self,
        market: str | None = None,
        board: str | None = None,
        source: str = "auto",
    ) -> Sequence[dict[str, Any]]:
        """获取股票列表

        Args:
            market: 市场过滤
            board: 板块过滤
            source: 数据源

        Returns:
            股票信息列表
        """
        if source == "auto":
            source_name = await self._router.select_source(
                CAPABILITY_STOCK_LIST, preference=self._default_preference
            )
        else:
            source_name = source

        if not source_name:
            raise RuntimeError("没有可用的数据源支持股票列表")

        adapter = self._router.get_adapter(source_name)
        if adapter is None or not isinstance(adapter, StockListCapable):
            raise RuntimeError(f"数据源 {source_name} 不支持股票列表")

        start_time = time.perf_counter()
        try:
            result = await adapter.get_stock_list(market, board)
            latency_ms = (time.perf_counter() - start_time) * 1000
            self._router.record_latency(source_name, latency_ms)
            return result
        except Exception as e:
            logger.warning("股票列表查询失败 ({}): {}", source_name, e)
            raise

    # ==================== 实时订阅 ====================

    async def subscribe(
        self,
        symbols: Sequence[str],
        callback_topic: str,
        source: str = "auto",
    ) -> None:
        """订阅实时行情

        Args:
            symbols: 股票代码列表
            callback_topic: 消息总线回调主题
            source: 数据源
        """
        if source == "auto":
            source_name = await self._router.select_source(
                CAPABILITY_SUBSCRIPTION, preference=self._default_preference
            )
        else:
            source_name = source

        if not source_name:
            raise RuntimeError("没有可用的数据源支持实时订阅")

        adapter = self._router.get_adapter(source_name)
        if adapter is None or not isinstance(adapter, SubscriptionCapable):
            raise RuntimeError(f"数据源 {source_name} 不支持实时订阅")

        await adapter.subscribe(symbols, callback_topic)
        logger.info("订阅成功: {} 个股票 via {}", len(symbols), source_name)

    # ==================== 管理接口 ====================

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "adapters": self._router.list_adapters(),
            "latency_stats": self._router.get_latency_stats(),
            "default_preference": self._default_preference,
        }


def get_data_proxy() -> UnifiedDataProxy:
    """获取全局数据代理单例

    Returns:
        UnifiedDataProxy 实例
    """
    global _global_proxy
    if _global_proxy is None:
        _global_proxy = UnifiedDataProxy()
    return _global_proxy


def set_data_proxy(proxy: UnifiedDataProxy) -> None:
    """设置全局数据代理

    Args:
        proxy: UnifiedDataProxy 实例
    """
    global _global_proxy
    _global_proxy = proxy
