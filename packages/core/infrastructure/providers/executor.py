"""数据源执行器，负责统一的回退与监控打点。"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Mapping, MutableMapping, Sequence

from core.observability.monitoring.data_source_monitor import DataSourceMonitor, get_monitor
from core.ports.data_sources import DataAccessType, DataSourceType
from loguru import logger


class DataSourceExecutor:
    """封装数据源调用的 fallback、异常处理与监控逻辑。"""

    def __init__(self, monitor: DataSourceMonitor | None = None) -> None:
        self._monitor = monitor or get_monitor()

    async def execute(
        self,
        providers: Mapping[DataSourceType, Any],
        source_order: Sequence[DataSourceType],
        method_name: str,
        *,
        args: Sequence[Any] = (),
        kwargs: MutableMapping[str, Any] | None = None,
        access_type: DataAccessType = DataAccessType.REALTIME_QUOTE,
        monitor_symbol: str | None = None,
        monitor_module: str | None = None,
        validator: Callable[[Any], bool] | None = None,
        require_result: bool = False,
    ) -> tuple[Any | None, DataSourceType | None]:
        for source in source_order:
            call_kwargs = dict(kwargs or {})
            provider = providers.get(source)
            if provider is None:
                continue

            method = getattr(provider, method_name, None)
            if method is None:
                continue

            start = time.perf_counter()
            try:
                result = method(*args, **call_kwargs)
                if asyncio.iscoroutine(result):
                    result = await result
            except Exception as exc:  # pragma: no cover - 调用失败日志
                latency = (time.perf_counter() - start) * 1000
                self._record_metrics(
                    source=source,
                    access_type=access_type,
                    success=False,
                    latency_ms=latency,
                    symbol=monitor_symbol,
                    module=monitor_module,
                    error=str(exc),
                )
                logger.error(f"通过 {source.value} 执行 {method_name} 失败: {exc}")
                continue

            latency = (time.perf_counter() - start) * 1000
            success = self._is_successful(result, validator, require_result)
            self._record_metrics(
                source=source,
                access_type=access_type,
                success=success,
                latency_ms=latency,
                symbol=monitor_symbol,
                module=monitor_module,
                error=None if success else "invalid_result",
            )
            if success:
                return result, source

        logger.error(f"所有数据源均无法执行 {method_name}")
        return None, None

    def _record_metrics(
        self,
        *,
        source: DataSourceType,
        access_type: DataAccessType,
        success: bool,
        latency_ms: float,
        symbol: str | None,
        module: str | None,
        error: str | None,
    ) -> None:
        if not self._monitor:
            return
        try:
            self._monitor.record_access(
                source=source,
                access_type=access_type,
                success=success,
                latency_ms=latency_ms,
                symbol=symbol,
                module=module,
                error_message=error,
            )
        except Exception:  # pragma: no cover - 避免监控异常影响主流程
            logger.debug("记录监控指标失败", exc_info=True)

    @staticmethod
    def _is_successful(
        result: Any,
        validator: Callable[[Any], bool] | None,
        require_result: bool,
    ) -> bool:
        if result is None:
            return not require_result

        if validator and not validator(result):
            return False

        if isinstance(result, dict):
            if result.get("error"):
                return False
            if result.get("success") is False:
                return False
            code_value = result.get("code")
            if isinstance(code_value, int) and code_value not in (0, None):
                return False
        return True


__all__ = ["DataSourceExecutor"]
