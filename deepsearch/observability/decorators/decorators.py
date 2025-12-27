"""
观测性装饰器

提供数据源/缓存相关的监控装饰器。
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Optional,
    ParamSpec,
    TypedDict,
    TypeVar,
    Union,
    cast,
)

from loguru import logger

from deepsearch.infrastructure.providers.interfaces.base import (
    DataSourceType as ProviderDataSourceType,
)
from deepsearch.ports.data_sources import DataAccessType, DataSourceType

from ..monitoring.data_source_monitor import get_monitor
from ..monitoring.decorators import SymbolExtractor, monitor_access

P = ParamSpec("P")
R = TypeVar("R")


class CacheAccessMetadata(TypedDict, total=False):
    cache_name: str
    cache_hit: bool
    function: str


SourceTypeLike = Union[DataSourceType, ProviderDataSourceType, str]


def _wrap_symbol_extractor(
    resolver: Optional[Callable[..., Any]],
) -> Optional[SymbolExtractor]:
    if resolver is None:
        return None

    def wrapped(args: tuple[Any, ...], kwargs: Dict[str, Any]) -> Optional[str]:
        try:
            value = resolver(*args, **kwargs)
        except Exception:
            return None
        if value is None:
            return None
        return str(value)

    return wrapped


def _normalize_source_type(source: SourceTypeLike) -> DataSourceType:
    if isinstance(source, DataSourceType):
        return source
    if isinstance(source, ProviderDataSourceType):
        try:
            return DataSourceType(source.value)
        except ValueError:
            return DataSourceType.CUSTOM

    normalized = str(source).strip().lower()
    for candidate in DataSourceType:
        if candidate.value == normalized or candidate.name.lower() == normalized:
            return candidate
    return DataSourceType.CUSTOM


def monitor_data_source(
    source: SourceTypeLike,
    access_type: DataAccessType,
    extract_symbol: Optional[Callable[..., Any]] = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    数据源访问监控装饰器

    委托给 `monitor_access` 统一上报访问指标，并捕获失败日志。
    """

    normalized_source = _normalize_source_type(source)
    core_decorator = monitor_access(
        source_type=normalized_source,
        access_type=access_type,
        extract_symbol=_wrap_symbol_extractor(extract_symbol),
    )

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        monitored = core_decorator(func)

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                try:
                    async_func = cast(Callable[P, Awaitable[R]], monitored)
                    return await async_func(*args, **kwargs)
                except Exception as exc:
                    logger.error(f"{normalized_source.value}.{func.__name__} 失败: {exc}")
                    raise

            return cast(Callable[P, R], async_wrapper)

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                sync_func = cast(Callable[P, R], monitored)
                return sync_func(*args, **kwargs)
            except Exception as exc:
                logger.error(f"{normalized_source.value}.{func.__name__} 失败: {exc}")
                raise

        return cast(Callable[P, R], sync_wrapper)

    return decorator


def monitor_cache_access(cache_name: str = "default") -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    缓存访问监控装饰器

    访问缓存时通过 DataSourceMonitor 统一上报。
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            monitor = get_monitor()
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                cache_hit = result is not None
                latency_ms = (time.time() - start_time) * 1000

                success_metadata: CacheAccessMetadata = {
                    "cache_name": cache_name,
                    "cache_hit": cache_hit,
                    "function": func.__name__,
                }
                monitor.record_access(
                    source=DataSourceType.DATABASE,
                    access_type=DataAccessType.REALTIME_QUOTE,
                    success=True,
                    latency_ms=latency_ms,
                    module=getattr(func, "__module__", "unknown"),
                    metadata=dict(success_metadata),
                )
                return result

            except Exception as exc:
                latency_ms = (time.time() - start_time) * 1000
                failure_metadata: CacheAccessMetadata = {
                    "cache_name": cache_name,
                    "function": func.__name__,
                }
                monitor.record_access(
                    source=DataSourceType.DATABASE,
                    access_type=DataAccessType.REALTIME_QUOTE,
                    success=False,
                    latency_ms=latency_ms,
                    error_message=str(exc),
                    module=getattr(func, "__module__", "unknown"),
                    metadata=dict(failure_metadata),
                )
                raise

        return cast(Callable[P, R], wrapper)

    return decorator


monitor_akshare_hist = functools.partial(
    monitor_data_source,
    source=DataSourceType.AKSHARE,
    access_type=DataAccessType.HISTORICAL_KLINE,
    extract_symbol=lambda *args, **kwargs: kwargs.get("symbol", args[0] if args else None),
)

monitor_akshare_realtime = functools.partial(
    monitor_data_source,
    source=DataSourceType.AKSHARE,
    access_type=DataAccessType.REALTIME_QUOTE,
    extract_symbol=lambda *args, **kwargs: kwargs.get("symbol", args[0] if args else None),
)

monitor_qmt_hist = functools.partial(
    monitor_data_source,
    source=DataSourceType.QMT,
    access_type=DataAccessType.HISTORICAL_KLINE,
    extract_symbol=lambda *args, **kwargs: kwargs.get("symbol", args[0] if args else None),
)

monitor_qmt_realtime = functools.partial(
    monitor_data_source,
    source=DataSourceType.QMT,
    access_type=DataAccessType.REALTIME_QUOTE,
    extract_symbol=lambda *args, **kwargs: kwargs.get("symbols", args[0] if args else None),
)

monitor_cloudflare = functools.partial(
    monitor_data_source,
    source=DataSourceType.CLOUDFLARE,
    extract_symbol=lambda *args, **kwargs: kwargs.get("symbol", args[0] if args else None),
)

monitor_amazingdata = functools.partial(
    monitor_data_source,
    source=DataSourceType.AMAZINGDATA,
    extract_symbol=lambda *args, **kwargs: kwargs.get("symbol", args[0] if args else None),
)
