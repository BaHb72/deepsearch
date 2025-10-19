"""
数据源监控装饰器

在统一的监控链路基础上补充结构化日志输出。
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, cast

from loguru import logger

from deepsearch.observability.monitoring.data_source_monitor import (
    DataAccessType,
    DataSourceType,
)
from deepsearch.observability.monitoring.decorators import (
    MonitorMetadata,
    SymbolExtractor,
    analyze_result,
    monitor_access as core_monitor_access,
)

__all__ = ["monitor_access", "batch_monitor_access", "MonitorMetadata"]


def _wrap_symbol_extractor(
    resolver: Optional[Callable[..., Any]]
) -> Optional[SymbolExtractor]:
    if resolver is None:
        return None

    def wrapped(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Optional[str]:
        try:
            value = resolver(*args, **kwargs)
        except Exception:
            return None
        if value is None:
            return None
        return str(value)

    return wrapped


def _resolve_symbol_for_log(
    resolver: Optional[Callable[..., Any]],
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> Optional[str]:
    if resolver is not None:
        try:
            value = resolver(*args, **kwargs)
        except Exception:
            value = None
        if value is not None:
            return str(value)
    if "symbol" in kwargs and kwargs["symbol"] is not None:
        return str(kwargs["symbol"])
    if len(args) > 1 and isinstance(args[1], str):
        return args[1]
    if args and isinstance(args[0], str):
        return args[0]
    return None


def monitor_access(
    source: DataSourceType,
    access_type: DataAccessType,
    extract_symbol: Optional[Callable[..., Any]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    为同步/异步函数提供监控采集与结构化日志。
    """

    symbol_extractor = _wrap_symbol_extractor(extract_symbol)
    core_decorator = core_monitor_access(
        source_type=source,
        access_type=access_type,
        extract_symbol=symbol_extractor,
    )

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        monitored = core_decorator(func)

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                symbol = _resolve_symbol_for_log(extract_symbol, args, kwargs)
                symbol_label = symbol or "-"
                try:
                    async_func = cast(Callable[..., Awaitable[Any]], monitored)
                    result = await async_func(*args, **kwargs)
                    latency_ms = (time.time() - start_time) * 1000.0
                    logger.debug(
                        f"[MONITOR] {source.value} -> {access_type.value} [{symbol_label}] "
                        f"{latency_ms:.1f}ms OK"
                    )
                    return result
                except Exception as exc:
                    latency_ms = (time.time() - start_time) * 1000.0
                    logger.warning(
                        f"[MONITOR] {source.value} -> {access_type.value} [{symbol_label}] FAILED: {exc}"
                    )
                    raise

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            symbol = _resolve_symbol_for_log(extract_symbol, args, kwargs)
            symbol_label = symbol or "-"
            try:
                sync_func = cast(Callable[..., Any], monitored)
                result = sync_func(*args, **kwargs)
                latency_ms = (time.time() - start_time) * 1000.0
                logger.debug(
                    f"[MONITOR] {source.value} -> {access_type.value} "
                    f"[{symbol_label}] {latency_ms:.1f}ms OK"
                )
                return result
            except Exception as exc:
                latency_ms = (time.time() - start_time) * 1000.0
                logger.warning(
                    f"[MONITOR] {source.value} -> {access_type.value} "
                    f"[{symbol_label}] FAILED: {exc}"
                )
                raise

        return sync_wrapper

    return decorator


def batch_monitor_access(
    source: DataSourceType,
    access_type: DataAccessType,
    extract_symbol: Optional[Callable[..., Any]] = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    针对批量返回结构增加记录数统计的装饰器。
    """

    symbol_extractor = _wrap_symbol_extractor(extract_symbol)
    core_decorator = core_monitor_access(
        source_type=source,
        access_type=access_type,
        extract_symbol=symbol_extractor,
    )

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        monitored = core_decorator(func)

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.time()
                symbol = _resolve_symbol_for_log(extract_symbol, args, kwargs)
                symbol_label = symbol or "-"
                try:
                    async_func = cast(Callable[..., Awaitable[Any]], monitored)
                    result = await async_func(*args, **kwargs)
                    metadata = analyze_result(result)
                    record_count = metadata.get("record_count", 0)
                    latency_ms = (time.time() - start_time) * 1000.0
                    logger.debug(
                        f"[MONITOR] {source.value} -> {access_type.value} {symbol_label} "
                        f"[{record_count} records] {latency_ms:.1f}ms OK"
                    )
                    return result
                except Exception as exc:
                    latency_ms = (time.time() - start_time) * 1000.0
                    logger.warning(
                        f"[MONITOR] {source.value} -> {access_type.value} {symbol_label} FAILED: {exc}"
                    )
                    raise

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                sync_func = cast(Callable[..., Any], monitored)
                result = sync_func(*args, **kwargs)
                metadata = analyze_result(result)
                record_count = metadata.get("record_count", 0)
                latency_ms = (time.time() - start_time) * 1000.0
                logger.debug(
                    f"[MONITOR] {source.value} -> {access_type.value} "
                    f"[{record_count} records] {latency_ms:.1f}ms OK"
                )
                return result
            except Exception as exc:
                latency_ms = (time.time() - start_time) * 1000.0
                logger.warning(
                    f"[MONITOR] {source.value} -> {access_type.value} FAILED: {exc}"
                )
                raise

        return sync_wrapper

    return decorator
