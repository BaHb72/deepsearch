"""
AKShare 数据提供者适配器。

该模块将现有的 AkShareProxyProvider 包装为新的能力接口。
实现 IKlineProvider, IStockListProvider 接口。

特点：
- 仅支持日线及以上周期
- 历史数据深度大（10年+）
- 无实时能力
"""

from __future__ import annotations

import time
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from loguru import logger

from deepsearch.config.models.capability_routing import (
    KlineCapabilitySpec,
    ProviderCapabilitiesSpec,
    StockListCapabilitySpec,
)
from deepsearch.ports.data.requests import KlineRequest, StockListRequest
from deepsearch.ports.data.responses import KlineBar, KlineResponse, StockInfo, StockListResponse
from deepsearch.ports.data.semantic_types import AdjustType, AssetSpec, Exchange, Timeframe
from deepsearch.ports.data_sources import DataSourceType

from .base import (
    BaseProviderAdapter,
    CapabilityNotSupportedError,
    IKlineProvider,
    IStockListProvider,
)

if TYPE_CHECKING:
    from deepsearch.infrastructure.providers.implementations.akshare.akshare_refactored import (
        AkShareProxyProvider,
    )


class AKShareRequestMapper:
    """
    AKShare 请求参数映射器。

    AKShare 使用不同的周期和复权命名。
    """

    # Timeframe 映射表（AKShare 只支持日线及以上）
    TIMEFRAME_MAP: Dict[Timeframe, str] = {
        Timeframe.D1: "daily",
        Timeframe.W1: "weekly",
        Timeframe.MO1: "monthly",
    }

    # 复权类型映射
    ADJUST_MAP: Dict[AdjustType, str] = {
        AdjustType.NONE: "",
        AdjustType.FORWARD: "qfq",
        AdjustType.BACKWARD: "hfq",
    }

    def map_kline_request(self, request: KlineRequest) -> Dict[str, Any]:
        """将语义请求转换为 AKShare 参数"""
        # AKShare 使用纯数字股票代码
        symbol = request.asset.symbol

        params: Dict[str, Any] = {
            "symbol": symbol,
            "period": self.TIMEFRAME_MAP.get(request.timeframe, "daily"),
            "adjust": self.ADJUST_MAP.get(request.adjust, ""),
        }

        # 时间范围
        if request.range.start:
            params["start_date"] = request.range.start.strftime("%Y%m%d")
        if request.range.end:
            params["end_date"] = request.range.end.strftime("%Y%m%d")

        return params

    def supports_timeframe(self, timeframe: Timeframe) -> bool:
        """检查是否支持该周期"""
        return timeframe in self.TIMEFRAME_MAP


class AKShareAdapter(BaseProviderAdapter, IKlineProvider, IStockListProvider):
    """
    AKShare 适配器。

    实现 K线（日线及以上）和股票列表能力。
    """

    def __init__(
        self,
        provider: "AkShareProxyProvider",
        capabilities: Optional[ProviderCapabilitiesSpec] = None,
    ):
        """
        初始化 AKShare 适配器。

        Args:
            provider: 底层 AkShareProxyProvider 实例
            capabilities: 能力声明，可选
        """
        if capabilities is None:
            capabilities = self._default_capabilities()

        super().__init__(name="akshare", capabilities=capabilities)
        self._provider = provider
        self._mapper = AKShareRequestMapper()

    @staticmethod
    def _default_capabilities() -> ProviderCapabilitiesSpec:
        """默认能力声明"""
        return ProviderCapabilitiesSpec(
            kline=KlineCapabilitySpec(
                supported=True,
                min_timeframe=Timeframe.D1,
                max_timeframe=Timeframe.MO1,
                history_days=3650,  # 10年历史
                adjust_types=[AdjustType.NONE, AdjustType.FORWARD, AdjustType.BACKWARD],
                realtime_capable=False,
            ),
            stock_list=StockListCapabilitySpec(
                supported=True,
                cache_ttl=86400,
            ),
        )

    async def initialize(self) -> bool:
        """初始化适配器"""
        return await self._provider.initialize()

    # ========================================================================
    # IKlineProvider 实现
    # ========================================================================

    async def query_kline(self, request: KlineRequest) -> KlineResponse:
        """
        查询 K 线数据。

        注意：AKShare 仅支持日线及以上周期。

        Args:
            request: K 线请求

        Returns:
            标准化的 K 线响应
        """
        start_time = time.perf_counter()

        # 检查能力支持
        if not self._can_handle_kline(request):
            raise CapabilityNotSupportedError(
                capability="kline",
                provider=self.name,
                reason=f"AKShare only supports daily, weekly, monthly. Got: {request.timeframe}",
            )

        # 转换请求参数
        params = self._mapper.map_kline_request(request)

        # 调用底层 Provider
        df = await self._provider.get_history_data(**params)

        # 计算延迟
        self._last_latency_ms = int((time.perf_counter() - start_time) * 1000)

        # 标准化响应
        return self._normalize_kline_response(df, request)

    def _can_handle_kline(self, request: KlineRequest) -> bool:
        """检查是否能处理该 K 线请求"""
        # AKShare 只支持日线及以上
        if not self._mapper.supports_timeframe(request.timeframe):
            return False

        spec = self._capabilities.kline
        if spec is None:
            return False

        # 检查复权类型
        if request.adjust not in spec.adjust_types:
            return False

        return True

    def _normalize_kline_response(
        self,
        df: Any,  # pandas DataFrame
        request: KlineRequest,
    ) -> KlineResponse:
        """标准化 K 线响应"""
        bars: List[KlineBar] = []

        if df is not None and hasattr(df, "empty") and not df.empty:
            for idx, row in df.iterrows():
                try:
                    timestamp = self._parse_timestamp(idx, row)

                    bars.append(
                        KlineBar(
                            timestamp=timestamp,
                            open=Decimal(str(row.get("open", row.get("开盘", 0)))),
                            high=Decimal(str(row.get("high", row.get("最高", 0)))),
                            low=Decimal(str(row.get("low", row.get("最低", 0)))),
                            close=Decimal(str(row.get("close", row.get("收盘", 0)))),
                            volume=int(row.get("volume", row.get("成交量", 0)) or 0),
                            amount=Decimal(str(row.get("amount", row.get("成交额", 0)) or 0)),
                        )
                    )
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"解析 AKShare K 线数据失败: {e}")
                    continue

        return KlineResponse(
            asset=request.asset,
            timeframe=request.timeframe,
            bars=bars,
            source=DataSourceType.AKSHARE,
            latency_ms=self._last_latency_ms,
        )

    def _parse_timestamp(self, idx: Any, row: Any) -> datetime:
        """解析时间戳"""
        if isinstance(idx, datetime):
            return idx

        # 尝试从 row 获取
        ts = row.get("date") or row.get("日期") or row.get("datetime")
        if isinstance(ts, datetime):
            return ts
        if hasattr(ts, "to_pydatetime"):
            return ts.to_pydatetime()
        if isinstance(ts, str):
            for fmt in ["%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"]:
                try:
                    return datetime.strptime(ts, fmt)
                except ValueError:
                    continue

        return datetime.now()

    # ========================================================================
    # IStockListProvider 实现
    # ========================================================================

    async def query_stock_list(self, request: StockListRequest) -> StockListResponse:
        """
        查询股票列表。

        Args:
            request: 股票列表请求

        Returns:
            标准化的股票列表响应
        """
        start_time = time.perf_counter()

        # 调用底层 Provider 获取实时行情（包含股票列表信息）
        raw_data = await self._provider.fetch_all_realtime_quotes()

        self._last_latency_ms = int((time.perf_counter() - start_time) * 1000)

        stocks: List[StockInfo] = []

        if raw_data is not None and hasattr(raw_data, "iterrows"):
            for _, row in raw_data.iterrows():
                try:
                    code = str(row.get("代码", row.get("code", "")))
                    name = str(row.get("名称", row.get("name", "")))

                    # 推断交易所
                    if code.startswith("6"):
                        exchange = Exchange.SH
                    elif code.startswith(("0", "3")):
                        exchange = Exchange.SZ
                    elif code.startswith(("4", "8")):
                        exchange = Exchange.BJ
                    else:
                        continue

                    stocks.append(
                        StockInfo(
                            asset=AssetSpec(symbol=code, exchange=exchange),
                            name=name,
                            is_st="ST" in name or "*ST" in name,
                        )
                    )
                except Exception as e:
                    logger.debug(f"解析股票信息失败: {e}")
                    continue

        # 应用市场筛选
        if request.market:
            market_exchange = Exchange(request.market)
            stocks = [s for s in stocks if s.asset.exchange == market_exchange]

        # 应用数量限制
        if request.limit and request.limit > 0:
            stocks = stocks[: request.limit]

        return StockListResponse(
            stocks=stocks,
            source=DataSourceType.AKSHARE,
            latency_ms=self._last_latency_ms,
        )


__all__ = [
    "AKShareAdapter",
    "AKShareRequestMapper",
]
