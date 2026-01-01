"""
MiniQMT 数据提供者适配器。

该模块将现有的 MiniQMTProvider 包装为新的能力接口。
实现 IKlineProvider, IRealtimeProvider, ITickProvider 接口。
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
    RealtimeQuoteCapabilitySpec,
    TickCapabilitySpec,
)
from deepsearch.ports.data.capabilities import DataCapability
from deepsearch.ports.data.requests import (
    KlineRequest,
    RealtimeQuoteRequest,
    TickRequest,
)
from deepsearch.ports.data.responses import (
    KlineBar,
    KlineResponse,
    Quote,
    RealtimeQuoteResponse,
    TickData,
    TickResponse,
)
from deepsearch.ports.data.semantic_types import (
    AdjustType,
    AssetSpec,
    Timeframe,
)
from deepsearch.ports.data_sources import DataSourceType

from .base import (
    BaseProviderAdapter,
    CapabilityNotSupportedError,
    IKlineProvider,
    IRealtimeProvider,
    ITickProvider,
)

if TYPE_CHECKING:
    from deepsearch.infrastructure.providers.implementations.qmt.miniqmt import (
        MiniQMTProvider,
    )


class MiniQMTRequestMapper:
    """
    MiniQMT 请求参数映射器。

    负责将语义请求转换为 MiniQMT Provider 的参数格式。
    """

    # Timeframe 映射表
    TIMEFRAME_MAP: Dict[Timeframe, str] = {
        Timeframe.M1: "1m",
        Timeframe.M5: "5m",
        Timeframe.M15: "15m",
        Timeframe.M30: "30m",
        Timeframe.H1: "1h",
        Timeframe.H4: "4h",
        Timeframe.D1: "1d",
        Timeframe.W1: "1w",
    }

    # 复权类型映射
    ADJUST_MAP: Dict[AdjustType, int] = {
        AdjustType.NONE: 0,
        AdjustType.FORWARD: 1,  # 前复权
        AdjustType.BACKWARD: 2,  # 后复权
    }

    def map_kline_request(self, request: KlineRequest) -> Dict[str, Any]:
        """将语义请求转换为 MiniQMT 参数"""
        params: Dict[str, Any] = {
            "symbol": request.asset.to_standard(),  # 000001.SZ
            "period": self.TIMEFRAME_MAP.get(request.timeframe, "1d"),
        }

        # 时间范围
        if request.range.start:
            params["start_date"] = request.range.start.strftime("%Y%m%d%H%M%S")
        if request.range.end:
            params["end_date"] = request.range.end.strftime("%Y%m%d%H%M%S")
        if request.range.limit:
            params["limit"] = request.range.limit

        return params

    def map_realtime_request(self, request: RealtimeQuoteRequest) -> Dict[str, Any]:
        """将实时行情请求转换为 MiniQMT 参数"""
        return {
            "symbols": [asset.to_standard() for asset in request.assets],
        }


class MiniQMTAdapter(BaseProviderAdapter, IKlineProvider, IRealtimeProvider, ITickProvider):
    """
    MiniQMT 适配器。

    实现 K线、实时行情、Tick 三种能力。
    """

    def __init__(
        self,
        provider: "MiniQMTProvider",
        capabilities: Optional[ProviderCapabilitiesSpec] = None,
    ):
        """
        初始化 MiniQMT 适配器。

        Args:
            provider: 底层 MiniQMTProvider 实例
            capabilities: 能力声明，可选（默认使用标准配置）
        """
        if capabilities is None:
            capabilities = self._default_capabilities()

        super().__init__(name="miniqmt", capabilities=capabilities)
        self._provider = provider
        self._mapper = MiniQMTRequestMapper()

    @staticmethod
    def _default_capabilities() -> ProviderCapabilitiesSpec:
        """默认能力声明"""
        return ProviderCapabilitiesSpec(
            kline=KlineCapabilitySpec(
                supported=True,
                min_timeframe=Timeframe.M1,
                max_timeframe=Timeframe.W1,
                history_days=90,
                adjust_types=[AdjustType.NONE, AdjustType.FORWARD],
                realtime_capable=True,
            ),
            realtime_quote=RealtimeQuoteCapabilitySpec(
                supported=True,
                max_symbols=500,
                latency_ms=100,
                premarket=False,
                afterhours=False,
            ),
            tick=TickCapabilitySpec(
                supported=True,
                max_symbols=50,
                include_depth=True,
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
                reason=f"Timeframe {request.timeframe} not supported",
            )

        # 转换请求参数
        params = self._mapper.map_kline_request(request)

        # 调用底层 Provider
        raw_data = await self._provider.get_kline_data(**params)

        # 计算延迟
        self._last_latency_ms = int((time.perf_counter() - start_time) * 1000)

        # 标准化响应
        return self._normalize_kline_response(raw_data, request)

    def _can_handle_kline(self, request: KlineRequest) -> bool:
        """检查是否能处理该 K 线请求"""
        spec = self._capabilities.kline
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

    def _normalize_kline_response(
        self,
        raw_data: Optional[List[Dict[str, Any]]],
        request: KlineRequest,
    ) -> KlineResponse:
        """标准化 K 线响应"""
        bars: List[KlineBar] = []

        if raw_data:
            for row in raw_data:
                try:
                    # 解析时间戳
                    timestamp = self._parse_timestamp(row)

                    bars.append(
                        KlineBar(
                            timestamp=timestamp,
                            open=Decimal(str(row.get("open", 0))),
                            high=Decimal(str(row.get("high", 0))),
                            low=Decimal(str(row.get("low", 0))),
                            close=Decimal(str(row.get("close", 0))),
                            volume=int(row.get("volume", 0) or 0),
                            amount=Decimal(str(row.get("amount", 0) or 0)),
                            turnover=Decimal(str(row["turnover"])) if row.get("turnover") else None,
                        )
                    )
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"解析 K 线数据失败: {e}, row={row}")
                    continue

        return KlineResponse(
            asset=request.asset,
            timeframe=request.timeframe,
            bars=bars,
            source=DataSourceType.MINIQMT,
            latency_ms=self._last_latency_ms,
        )

    def _parse_timestamp(self, row: Dict[str, Any]) -> datetime:
        """解析时间戳"""
        ts = row.get("time") or row.get("timestamp") or row.get("index")
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, (int, float)):
            # Unix 时间戳（毫秒或秒）
            if ts > 1e12:
                return datetime.fromtimestamp(ts / 1000)
            return datetime.fromtimestamp(ts)
        if isinstance(ts, str):
            # 尝试多种格式
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S", "%Y-%m-%d", "%Y%m%d"]:
                try:
                    return datetime.strptime(ts, fmt)
                except ValueError:
                    continue
        return datetime.now()

    # ========================================================================
    # IRealtimeProvider 实现
    # ========================================================================

    async def query_realtime(self, request: RealtimeQuoteRequest) -> RealtimeQuoteResponse:
        """
        查询实时行情。

        Args:
            request: 实时行情请求

        Returns:
            标准化的实时行情响应
        """
        start_time = time.perf_counter()

        # 转换请求参数
        params = self._mapper.map_realtime_request(request)

        # 调用底层 Provider
        raw_data = await self._provider.get_realtime_quotes(**params)

        # 计算延迟
        self._last_latency_ms = int((time.perf_counter() - start_time) * 1000)

        # 标准化响应
        return self._normalize_realtime_response(raw_data, request)

    def _normalize_realtime_response(
        self,
        raw_data: Optional[List[Dict[str, Any]]],
        request: RealtimeQuoteRequest,
    ) -> RealtimeQuoteResponse:
        """标准化实时行情响应"""
        quotes: List[Quote] = []

        if raw_data:
            for row in raw_data:
                try:
                    # 解析资产
                    symbol = row.get("symbol", row.get("code", ""))
                    asset = AssetSpec.from_code(symbol)

                    quotes.append(
                        Quote(
                            asset=asset,
                            timestamp=self._parse_timestamp(row),
                            last_price=Decimal(str(row.get("price", row.get("lastPrice", 0)))),
                            open=Decimal(str(row.get("open", 0))),
                            high=Decimal(str(row.get("high", 0))),
                            low=Decimal(str(row.get("low", 0))),
                            pre_close=Decimal(str(row.get("prev_close", row.get("lastClose", 0)))),
                            volume=int(row.get("volume", 0) or 0),
                            amount=Decimal(str(row.get("amount", 0) or 0)),
                            bid_prices=self._parse_prices(row, "bid"),
                            bid_volumes=self._parse_volumes(row, "bid"),
                            ask_prices=self._parse_prices(row, "ask"),
                            ask_volumes=self._parse_volumes(row, "ask"),
                        )
                    )
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"解析实时行情失败: {e}, row={row}")
                    continue

        return RealtimeQuoteResponse(
            quotes=quotes,
            source=DataSourceType.MINIQMT,
            latency_ms=self._last_latency_ms,
        )

    def _parse_prices(self, row: Dict[str, Any], side: str) -> tuple[Decimal, ...]:
        """解析买卖价格"""
        prices = []
        for i in range(1, 11):
            key = f"{side}Price{i}" if i > 1 else f"{side}Price"
            key_alt = f"{side}_price{i}" if i > 1 else f"{side}_price"
            val = row.get(key) or row.get(key_alt)
            if val is not None:
                prices.append(Decimal(str(val)))
        return tuple(prices)

    def _parse_volumes(self, row: Dict[str, Any], side: str) -> tuple[int, ...]:
        """解析买卖量"""
        volumes = []
        for i in range(1, 11):
            key = f"{side}Vol{i}" if i > 1 else f"{side}Vol"
            key_alt = f"{side}_vol{i}" if i > 1 else f"{side}_vol"
            val = row.get(key) or row.get(key_alt)
            if val is not None:
                volumes.append(int(val))
        return tuple(volumes)

    # ========================================================================
    # ITickProvider 实现
    # ========================================================================

    async def query_tick(self, request: TickRequest) -> TickResponse:
        """
        查询 Tick 数据。

        Args:
            request: Tick 请求

        Returns:
            标准化的 Tick 响应
        """
        start_time = time.perf_counter()

        # MiniQMT 通过订阅获取 Tick，这里返回空响应
        # 实际 Tick 数据通过回调获取
        logger.info(f"MiniQMT Tick 查询: {request.asset}")

        self._last_latency_ms = int((time.perf_counter() - start_time) * 1000)

        return TickResponse(
            asset=request.asset,
            ticks=[],
            source=DataSourceType.MINIQMT,
            latency_ms=self._last_latency_ms,
        )


__all__ = [
    "MiniQMTAdapter",
    "MiniQMTRequestMapper",
]
