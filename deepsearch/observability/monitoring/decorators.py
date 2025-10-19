"""
数据源监控装饰器

提供统一的装饰器和上下文管理器用于收集监控指标。
"""

from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    TypedDict,
    TypeVar,
    Literal,
    cast,
    ParamSpec,
)

from deepsearch.observability.monitoring.data_source_monitor import (
    DataAccessType,
    DataSourceMonitor,
    DataSourceType,
    get_monitor,
)

P = ParamSpec("P")
T = TypeVar("T")
R = TypeVar("R")

SymbolExtractor = Callable[[Tuple[Any, ...], Dict[str, Any]], Optional[str]]


class MonitorMetadata(TypedDict, total=False):
    """监控埋点额外信息结构。"""

    function: str
    module: str
    symbol: Optional[str]
    has_result: bool
    record_count: int
    args_count: int
    kwargs_keys: List[str]
    data_size: int


@dataclass
class MonitorContext:
    """
    监控上下文管理器。

    Example:
        async with MonitorContext(
            source_type=DataSourceType.QMT,
            access_type=DataAccessType.TICK_DATA,
            symbol="000001.SZ"
        ) as ctx:
            result = await fetch_data()
            ctx.set_data_size(len(result))
    """

    source_type: DataSourceType
    access_type: DataAccessType
    symbol: Optional[str] = None
    module: str = "unknown"
    metadata: MonitorMetadata = field(default_factory=lambda: cast(MonitorMetadata, {}))
    monitor: DataSourceMonitor = field(init=False)
    start_time: float = field(init=False, default=0.0)
    data_size: int = 0
    success: bool = False
    error_message: Optional[str] = None

    def __post_init__(self) -> None:
        self.monitor = get_monitor()
        if not self.module:
            self.module = "unknown"

    def set_data_size(self, size: int) -> None:
        """记录返回数据大小。"""
        self.data_size = max(0, size)

    def __enter__(self) -> MonitorContext:
        self.start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> Literal[False]:
        self.success = exc_type is None
        if exc_val is not None:
            self.error_message = str(exc_val)

        latency_ms = (time.time() - self.start_time) * 1000.0
        metadata_payload: Optional[Dict[str, Any]] = dict(self.metadata) if self.metadata else None

        self.monitor.record_access(
            source=self.source_type,
            access_type=self.access_type,
            success=self.success,
            latency_ms=latency_ms,
            symbol=self.symbol,
            module=self.module,
            error_message=self.error_message,
            data_size=self.data_size,
            metadata=metadata_payload,
        )
        return False

    async def __aenter__(self) -> MonitorContext:
        self.start_time = time.time()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> Literal[False]:
        self.success = exc_type is None
        if exc_val is not None:
            self.error_message = str(exc_val)

        latency_ms = (time.time() - self.start_time) * 1000.0
        metadata_payload: Optional[Dict[str, Any]] = dict(self.metadata) if self.metadata else None

        self.monitor.record_access(
            source=self.source_type,
            access_type=self.access_type,
            success=self.success,
            latency_ms=latency_ms,
            symbol=self.symbol,
            module=self.module,
            error_message=self.error_message,
            data_size=self.data_size,
            metadata=metadata_payload,
        )
        return False


def _resolve_symbol(
    extractor: Optional[SymbolExtractor],
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> Optional[str]:
    if extractor is not None:
        try:
            return extractor(args, kwargs)
        except Exception:
            return None
    if "symbol" in kwargs:
        value = kwargs["symbol"]
        if value is not None:
            return str(value)
    if args:
        primary = args[0]
        if isinstance(primary, str):
            return primary
        if len(args) > 1 and isinstance(args[1], str):
            return args[1]
    return None


def _resolve_module(func: Callable[..., Any]) -> str:
    module_name = getattr(func, "__module__", None)
    if isinstance(module_name, str) and module_name:
        return module_name
    return "unknown"


def estimate_data_size(result: Any) -> int:
    """估算返回数据的大小，优先使用对象自身的统计方法。"""
    if result is None:
        return 0

    # Pandas DataFrame / Series
    memory_usage = getattr(result, "memory_usage", None)
    empty = getattr(result, "empty", None)
    if callable(memory_usage):
        try:
            if empty is False:
                usage = memory_usage(deep=True)
                total = usage.sum() if hasattr(usage, "sum") else usage
                if isinstance(total, (int, float)):
                    return int(total)
        except Exception:
            pass

    if isinstance(result, (bytes, bytearray)):
        return len(result)
    if isinstance(result, str):
        return len(result)

    if isinstance(result, Mapping):
        try:
            return len(str(result))
        except Exception:
            return 0

    if isinstance(result, Collection) and not isinstance(result, (str, bytes, bytearray)):
        try:
            return len(result)
        except Exception:
            pass

    sizeof = getattr(result, "__sizeof__", None)
    if callable(sizeof):
        try:
            return int(sizeof())
        except Exception:
            pass

    try:
        return len(str(result))
    except Exception:
        return 0


def count_records(result: Any) -> int:
    """尝试统计记录数量，用于批量指标。"""
    if result is None:
        return 0
    if isinstance(result, (list, tuple, set, frozenset)):
        return len(result)
    if isinstance(result, Mapping):
        data = result.get("data")
        if isinstance(data, (list, tuple, set, frozenset)):
            return len(data)
    if isinstance(result, Collection) and not isinstance(result, (str, bytes, bytearray)):
        try:
            return len(result)
        except Exception:
            return 0
    return 0


def analyze_result(result: Any) -> MonitorMetadata:
    """根据返回值推导监控元数据。"""
    metadata: MonitorMetadata = MonitorMetadata()
    if result is None:
        metadata["has_result"] = False
        return metadata

    metadata["has_result"] = True
    records = count_records(result)
    if records:
        metadata["record_count"] = records
    return metadata


def _prepare_context(
    func: Callable[P, Any],
    source_type: DataSourceType,
    access_type: DataAccessType,
    extract_symbol: Optional[SymbolExtractor],
    args: Tuple[Any, ...],
    kwargs: Dict[str, Any],
) -> MonitorContext:
    symbol = _resolve_symbol(extract_symbol, args, kwargs)
    module_name = _resolve_module(func)

    context = MonitorContext(
        source_type=source_type,
        access_type=access_type,
        symbol=symbol,
        module=module_name,
    )
    context.metadata["function"] = func.__name__
    context.metadata["module"] = module_name
    if symbol is not None:
        context.metadata["symbol"] = symbol
    context.metadata["args_count"] = len(args)
    context.metadata["kwargs_keys"] = [str(key) for key in kwargs.keys()]
    return context


def _update_context_with_result(context: MonitorContext, result: Any) -> None:
    context.set_data_size(estimate_data_size(result))
    context.metadata["data_size"] = context.data_size
    result_metadata = analyze_result(result)
    if "has_result" in result_metadata:
        context.metadata["has_result"] = result_metadata["has_result"]
    if "record_count" in result_metadata:
        context.metadata["record_count"] = result_metadata["record_count"]


def monitor_access(
    source_type: DataSourceType,
    access_type: DataAccessType,
    extract_symbol: Optional[SymbolExtractor] = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    数据访问监控装饰器。

    会自动统计耗时、成功率、数据体积等指标，并写入 DataSourceMonitor。
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                context = _prepare_context(func, source_type, access_type, extract_symbol, args, kwargs)
                async_func = cast(Callable[P, Awaitable[Any]], func)
                try:
                    async with context:
                        result = await async_func(*args, **kwargs)
                        _update_context_with_result(context, result)
                    return cast(T, result)
                except Exception:
                    raise

            return cast(Callable[P, T], async_wrapper)

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            context = _prepare_context(func, source_type, access_type, extract_symbol, args, kwargs)
            sync_func = cast(Callable[P, T], func)
            try:
                with context:
                    result = sync_func(*args, **kwargs)
                    _update_context_with_result(context, result)
                return result
            except Exception:
                raise

        return cast(Callable[P, T], sync_wrapper)

    return decorator


def with_monitoring(
    source_type: DataSourceType,
    access_type: DataAccessType,
    extract_symbol: Optional[SymbolExtractor] = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """
    `monitor_access` 的语义化别名，便于阅读场景化代码。
    """

    return monitor_access(source_type, access_type, extract_symbol)


def monitor_async(
    source_type: DataSourceType,
    access_type: DataAccessType,
    extract_symbol: Optional[SymbolExtractor] = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """
    专用于 `async def` 函数的监控装饰器，统一异步函数签名。
    """

    decorator = monitor_access(source_type, access_type, extract_symbol)

    def wrapper(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        wrapped = decorator(func)
        return cast(Callable[P, Awaitable[R]], wrapped)

    return wrapper


def batch_monitor_access(
    source_type: DataSourceType,
    access_type: DataAccessType,
    extract_symbol: Optional[SymbolExtractor] = None,
) -> Callable[[Callable[P, Any]], Callable[P, Any]]:
    """
    批量数据访问监控装饰器。

    相比 `monitor_access`，会额外统计 `record_count` 字段，适合批量 API。
    """

    def decorator(func: Callable[P, Any]) -> Callable[P, Any]:
        base_wrapper = monitor_access(source_type, access_type, extract_symbol)(func)

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
                result = await cast(Callable[P, Awaitable[Any]], base_wrapper)(*args, **kwargs)
                return result

            return cast(Callable[P, Any], async_wrapper)

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Any:
            return cast(Callable[P, Any], base_wrapper)(*args, **kwargs)

        return cast(Callable[P, Any], sync_wrapper)

    return decorator


__all__ = [
    "MonitorContext",
    "MonitorMetadata",
    "SymbolExtractor",
    "monitor_access",
    "monitor_async",
    "with_monitoring",
    "batch_monitor_access",
    "estimate_data_size",
    "count_records",
    "analyze_result",
]
