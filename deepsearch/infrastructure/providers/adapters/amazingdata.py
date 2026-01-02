"""
AmazingData 数据提供者适配器。

该模块将现有的 AmazingDataProvider 包装为新的能力接口。
实现 IKlineProvider, IRealtimeProvider 接口。
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
)
from deepsearch.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from deepsearch.ports.data.responses import KlineBar, KlineResponse, Quote, RealtimeQuoteResponse
from deepsearch.ports.data.semantic_types import AdjustType, AssetSpec, Timeframe
from deepsearch.ports.data_sources import DataSourceType

from .base import (
    BaseProviderAdapter,
    CapabilityNotSupportedError,
    IKlineProvider,
    IRealtimeProvider,
)

if TYPE_CHECKING:
    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
        AmazingDataProvider,
    )


class AmazingDataRequestMapper:
    """
    AmazingData 请求参数映射器。

    负责将语义请求转换为 AmazingData Provider 的参数格式。
    """

    # Timeframe 映射表
    TIMEFRAME_MAP: Dict[Timeframe, str] = {
        Timeframe.M1: "1m",
        Timeframe.M5: "5m",
        Timeframe.M15: "15m",
        Timeframe.M30: "30m",
        Timeframe.H1: "60m",
        Timeframe.D1: "1d",
        Timeframe.W1: "1w",
        Timeframe.MO1: "1M",
    }

    # 复权类型映射
    ADJUST_MAP: Dict[AdjustType, str] = {
        AdjustType.NONE: "none",
        AdjustType.FORWARD: "qfq",
        AdjustType.BACKWARD: "hfq",
    }

    def map_kline_request(self, request: KlineRequest) -> Dict[str, Any]:
        """将语义请求转换为 AmazingData 参数"""
        params: Dict[str, Any] = {
            "symbol": request.asset.to_standard(),  # 000001.SZ
            "period": self.TIMEFRAME_MAP.get(request.timeframe, "1d"),
            "adjust": self.ADJUST_MAP.get(request.adjust, "none"),
        }

        # 时间范围
        if request.range.start:
            params["start_date"] = request.range.start.strftime("%Y-%m-%d")
        if request.range.end:
            params["end_date"] = request.range.end.strftime("%Y-%m-%d")
        if request.range.limit:
            params["count"] = request.range.limit

        return params


class AmazingDataAdapter(BaseProviderAdapter, IKlineProvider, IRealtimeProvider):
    """
    AmazingData 适配器。

    实现 K线、实时行情能力。
    """

    def __init__(
        self,
        provider: "AmazingDataProvider",
        capabilities: Optional[ProviderCapabilitiesSpec] = None,
    ):
        """
        初始化 AmazingData 适配器。

        Args:
            provider: 底层 AmazingDataProvider 实例
            capabilities: 能力声明，可选（默认使用标准配置）
        """
        if capabilities is None:
            capabilities = self._default_capabilities()

        super().__init__(name="amazingdata", capabilities=capabilities)
        self._provider = provider
        self._mapper = AmazingDataRequestMapper()

    @staticmethod
    def _default_capabilities() -> ProviderCapabilitiesSpec:
        """默认能力声明"""
        return ProviderCapabilitiesSpec(
            kline=KlineCapabilitySpec(
                supported=True,
                min_timeframe=Timeframe.M1,
                max_timeframe=Timeframe.MO1,
                history_days=365,
                adjust_types=[AdjustType.NONE, AdjustType.FORWARD, AdjustType.BACKWARD],
                realtime_capable=True,
            ),
            realtime_quote=RealtimeQuoteCapabilitySpec(
                supported=True,
                max_symbols=1000,
                latency_ms=200,
                premarket=True,
                afterhours=True,
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
                reason=f"Timeframe {request.timeframe} or adjust {request.adjust} not supported",
            )

        # 转换请求参数
        params = self._mapper.map_kline_request(request)

        # 调用底层 Provider
        df = await self._provider.get_kline(**params)

        # 计算延迟
        self._last_latency_ms = int((time.perf_counter() - start_time) * 1000)

        # 标准化响应
        return self._normalize_kline_response(df, request)

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
        df: Any,  # pandas DataFrame
        request: KlineRequest,
    ) -> KlineResponse:
        """标准化 K 线响应"""
        bars: List[KlineBar] = []

        if df is not None and not df.empty:
            for idx, row in df.iterrows():
                try:
                    # 解析时间戳
                    timestamp = self._parse_timestamp(idx, row)

                    bars.append(
                        KlineBar(
                            timestamp=timestamp,
                            open=Decimal(str(row.get("open", 0))),
                            high=Decimal(str(row.get("high", 0))),
                            low=Decimal(str(row.get("low", 0))),
                            close=Decimal(str(row.get("close", 0))),
                            volume=int(row.get("volume", 0) or 0),
                            amount=Decimal(str(row.get("amount", 0) or 0)),
                        )
                    )
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"解析 K 线数据失败: {e}")
                    continue

        return KlineResponse(
            asset=request.asset,
            timeframe=request.timeframe,
            bars=bars,
            source=DataSourceType.AMAZINGDATA,
            latency_ms=self._last_latency_ms,
        )

    def _parse_timestamp(self, idx: Any, row: Any) -> datetime:
        """解析时间戳"""
        # DataFrame index 可能是 datetime
        if isinstance(idx, datetime):
            return idx

        # 尝试从 row 获取
        ts = row.get("datetime") or row.get("time") or row.get("timestamp")
        if isinstance(ts, datetime):
            return ts
        if hasattr(ts, "to_pydatetime"):
            return ts.to_pydatetime()
        if isinstance(ts, str):
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y%m%d"]:
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
        symbols = [asset.to_standard() for asset in request.assets]

        # 调用底层 Provider
        raw_data = await self._provider.get_realtime_quotes(symbols)

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
                    symbol = row.get("symbol", row.get("code", ""))
                    asset = AssetSpec.from_code(symbol)

                    quotes.append(
                        Quote(
                            asset=asset,
                            timestamp=self._parse_row_timestamp(row),
                            last_price=Decimal(str(row.get("price", row.get("lastPrice", 0)))),
                            open=Decimal(str(row.get("open", 0))),
                            high=Decimal(str(row.get("high", 0))),
                            low=Decimal(str(row.get("low", 0))),
                            pre_close=Decimal(str(row.get("prev_close", row.get("preClose", 0)))),
                            volume=int(row.get("volume", 0) or 0),
                            amount=Decimal(str(row.get("amount", 0) or 0)),
                        )
                    )
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"解析实时行情失败: {e}")
                    continue

        return RealtimeQuoteResponse(
            quotes=quotes,
            source=DataSourceType.AMAZINGDATA,
            latency_ms=self._last_latency_ms,
        )

    def _parse_row_timestamp(self, row: Dict[str, Any]) -> datetime:
        """解析行情时间戳"""
        ts = row.get("timestamp") or row.get("time") or row.get("datetime")
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, (int, float)):
            if ts > 1e12:
                return datetime.fromtimestamp(ts / 1000)
            return datetime.fromtimestamp(ts)
        if isinstance(ts, str):
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y%m%d%H%M%S"]:
                try:
                    return datetime.strptime(ts, fmt)
                except ValueError:
                    continue
        return datetime.now()


__all__ = [
    "AmazingDataAdapter",
    "AmazingDataRequestMapper",
]
