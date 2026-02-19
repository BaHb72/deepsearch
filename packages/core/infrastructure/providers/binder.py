"""
数据访问层装配器（Binder）。

提供 UnifiedDataFeed 统一入口，封装路由和降级逻辑。
"""

from __future__ import annotations

import asyncio
import time
from enum import StrEnum
from typing import TYPE_CHECKING, Dict

from core.ports.data.requests import (
    DataRequest,
    KlineRequest,
    RealtimeQuoteRequest,
    StockListRequest,
    TickRequest,
)
from core.ports.data.responses import (
    DataResponse,
    KlineResponse,
    RealtimeQuoteResponse,
    StockListResponse,
    TickResponse,
)
from core.ports.data.routing_result import (
    FallbackReasonCode,
    RouteAttempt,
    RoutedResponseMeta,
)
from loguru import logger

from .adapters.base import (
    BaseProviderAdapter,
    CapabilityNotSupportedError,
    IKlineProvider,
    IRealtimeProvider,
    ITickProvider,
)
from .capability_router import CapabilityRouter, NoProviderAvailableError

if TYPE_CHECKING:
    pass


class FallbackStrategy(StrEnum):
    """降级策略"""

    NONE = "none"  # 不降级，直接报错
    SEQUENTIAL = "sequential"  # 按优先级顺序尝试
    PARALLEL = "parallel"  # 并行请求，取最快响应（未实现）


class AllProvidersFailedError(Exception):
    """所有 Provider 都失败"""

    def __init__(
        self,
        request: DataRequest,
        errors: Dict[str, Exception],
        attempts: tuple[RouteAttempt, ...] = (),
    ):
        self.request = request
        self.errors = errors
        self.attempts = attempts
        providers = ", ".join(errors.keys())
        super().__init__(f"All providers failed: {providers}")


class UnifiedDataFeed:
    """
    统一数据入口（Facade）。

    应用层通过该类访问所有数据，无需关心底层数据源。
    使用组合模式委派不同能力层。
    """

    def __init__(
        self,
        router: CapabilityRouter,
        reference: "ReferenceDataCapability | None" = None,
    ):
        """
        初始化 UnifiedDataFeed。

        Args:
            router: 能力路由器（行情数据）
            reference: 参考数据能力层（可选）
        """
        self._router = router
        self._reference = reference

    @property
    def router(self) -> CapabilityRouter:
        """获取路由器"""
        return self._router

    async def query(self, request: DataRequest) -> DataResponse:
        """
        查询数据。

        根据请求类型自动路由到合适的 Provider。

        Args:
            request: 数据请求

        Returns:
            DataResponse: 响应数据

        Raises:
            NoProviderAvailableError: 无可用 Provider
            CapabilityNotSupportedError: 能力不支持
        """
        adapter = self._router.resolve(request)
        return await self._dispatch(adapter, request)

    async def query_with_trace(
        self,
        request: DataRequest,
    ) -> tuple[DataResponse, RoutedResponseMeta]:
        """
        查询数据并返回路由元信息（无降级）。
        """
        response = await self.query(request)
        source_name = getattr(getattr(response, "source", None), "value", None) or "unknown"
        meta = RoutedResponseMeta(
            source=source_name,
            fallback_reason=None,
            attempts=(
                RouteAttempt(
                    provider=source_name,
                    success=True,
                    reason_code=None,
                    reason_detail=None,
                    latency_ms=getattr(response, "latency_ms", None),
                ),
            ),
        )
        return response, meta

    async def query_with_fallback(
        self,
        request: DataRequest,
        strategy: FallbackStrategy = FallbackStrategy.SEQUENTIAL,
    ) -> DataResponse:
        """
        带降级的查询。

        Args:
            request: 数据请求
            strategy: 降级策略

        Returns:
            DataResponse: 响应数据

        Raises:
            AllProvidersFailedError: 所有 Provider 都失败
        """
        response, _ = await self.query_with_fallback_trace(request=request, strategy=strategy)
        return response

    async def query_with_fallback_trace(
        self,
        request: DataRequest,
        strategy: FallbackStrategy = FallbackStrategy.SEQUENTIAL,
    ) -> tuple[DataResponse, RoutedResponseMeta]:
        """
        带降级的查询，并返回路由轨迹。
        """
        if strategy == FallbackStrategy.NONE:
            return await self.query_with_trace(request)

        adapters = self._router.resolve_all(request)
        if not adapters:
            raise NoProviderAvailableError(
                self._router._infer_capability(request),
                request,
            )

        errors: Dict[str, Exception] = {}
        attempts: list[RouteAttempt] = []

        for adapter in adapters:
            started = time.perf_counter()
            try:
                response = await self._dispatch(adapter, request)
                latency_ms = int((time.perf_counter() - started) * 1000)
                attempts.append(
                    RouteAttempt(
                        provider=adapter.name,
                        success=True,
                        reason_code=None,
                        reason_detail=None,
                        latency_ms=latency_ms,
                    )
                )
                fallback_reason = None
                if len(attempts) > 1:
                    fallback_reason = attempts[-2].reason_code or FallbackReasonCode.PROVIDER_ERROR
                return response, RoutedResponseMeta(
                    source=adapter.name,
                    fallback_reason=fallback_reason,
                    attempts=tuple(attempts),
                )
            except Exception as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                reason_code = self._classify_exception(exc)
                attempts.append(
                    RouteAttempt(
                        provider=adapter.name,
                        success=False,
                        reason_code=reason_code,
                        reason_detail=str(exc),
                        latency_ms=latency_ms,
                    )
                )
                logger.warning(f"Provider {adapter.name} 失败: {exc}, 尝试下一个")
                errors[adapter.name] = exc
                continue

        raise AllProvidersFailedError(request, errors, attempts=tuple(attempts))

    async def _dispatch(
        self,
        adapter: BaseProviderAdapter,
        request: DataRequest,
    ) -> DataResponse:
        """分发请求到适配器"""
        if isinstance(request, KlineRequest):
            if not isinstance(adapter, IKlineProvider):
                raise CapabilityNotSupportedError(
                    capability="kline",
                    provider=adapter.name,
                    reason="Adapter does not implement IKlineProvider",
                )
            return await adapter.query_kline(request)

        elif isinstance(request, RealtimeQuoteRequest):
            if not isinstance(adapter, IRealtimeProvider):
                raise CapabilityNotSupportedError(
                    capability="realtime_quote",
                    provider=adapter.name,
                    reason="Adapter does not implement IRealtimeProvider",
                )
            return await adapter.query_realtime(request)

        elif isinstance(request, TickRequest):
            if not isinstance(adapter, ITickProvider):
                raise CapabilityNotSupportedError(
                    capability="tick",
                    provider=adapter.name,
                    reason="Adapter does not implement ITickProvider",
                )
            return await adapter.query_tick(request)

        else:
            raise ValueError(f"Unknown request type: {type(request)}")

    @staticmethod
    def _classify_exception(exc: Exception) -> FallbackReasonCode:
        """异常映射到统一降级原因。"""
        if isinstance(exc, CapabilityNotSupportedError):
            return FallbackReasonCode.CAPABILITY_NOT_SUPPORTED
        if isinstance(exc, asyncio.TimeoutError):
            return FallbackReasonCode.PROVIDER_TIMEOUT
        message = str(exc).lower()
        if any(keyword in message for keyword in ("not initialized", "unavailable", "connection")):
            return FallbackReasonCode.PROVIDER_UNAVAILABLE
        return FallbackReasonCode.PROVIDER_ERROR

    # ========================================================================
    # 便捷方法
    # ========================================================================

    async def get_kline(self, request: KlineRequest) -> KlineResponse:
        """获取 K 线数据（类型安全）"""
        response = await self.query(request)
        if not isinstance(response, KlineResponse):
            raise TypeError(f"Expected KlineResponse, got {type(response)}")
        return response

    async def get_realtime(self, request: RealtimeQuoteRequest) -> RealtimeQuoteResponse:
        """获取实时行情（类型安全）"""
        response = await self.query(request)
        if not isinstance(response, RealtimeQuoteResponse):
            raise TypeError(f"Expected RealtimeQuoteResponse, got {type(response)}")
        return response

    async def get_tick(self, request: TickRequest) -> TickResponse:
        """获取 Tick 数据（类型安全）"""
        response = await self.query(request)
        if not isinstance(response, TickResponse):
            raise TypeError(f"Expected TickResponse, got {type(response)}")
        return response

    # ========================================================================
    # 参考数据方法 (ReferenceDataCapability)
    # ========================================================================

    async def list_instruments(self, request: StockListRequest) -> StockListResponse:
        """获取股票列表（带强缓存）"""
        if self._reference is None:
            raise RuntimeError("ReferenceDataCapability 未配置")
        return await self._reference.list_instruments(request)

    async def refresh_metadata(self) -> None:
        """显式刷新参考数据缓存"""
        if self._reference is not None:
            await self._reference.refresh()

    @property
    def reference(self) -> "ReferenceDataCapability | None":
        """获取参考数据能力层"""
        return self._reference


# 延迟导入避免循环依赖
from core.infrastructure.providers.reference_capability import ReferenceDataCapability  # noqa: E402

__all__ = [
    "FallbackStrategy",
    "AllProvidersFailedError",
    "UnifiedDataFeed",
    "ReferenceDataCapability",
]
