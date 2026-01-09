"""
标准化错误处理装饰器

提供统一的错误处理、重试、超时和性能监控装饰器
"""

import asyncio
import functools
import logging
import time
import traceback
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional, Type, TypeVar, cast

from core.core.errors import (
    DatabaseConnectionError,
    DataProviderError,
    NetworkError,
    ValidationError,
)
from core.observability import get_logger

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class ErrorLevel(Enum):
    """错误级别"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """错误上下文信息"""

    function_name: str
    module_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    error_type: Optional[Type[Exception]] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    retry_count: int = 0
    execution_time: float = 0.0
    additional_info: Dict[str, Any] = field(default_factory=dict)


class ErrorHandler:
    """错误处理器基类"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        初始化错误处理器

        Args:
            logger: 日志记录器
        """
        self.logger = logger or get_logger(__name__)
        self._error_stats: Dict[str, int] = {}
        self._last_errors: Dict[str, ErrorContext] = {}

    def handle_error(self, context: ErrorContext, level: ErrorLevel = ErrorLevel.ERROR) -> None:
        """
        处理错误

        Args:
            context: 错误上下文
            level: 错误级别
        """
        # 更新错误统计
        error_key = f"{context.module_name}.{context.function_name}"
        self._error_stats[error_key] = self._error_stats.get(error_key, 0) + 1
        self._last_errors[error_key] = context

        # 记录日志
        log_message = self._format_error_message(context)
        log_method = getattr(self.logger, level.value)
        log_method(log_message)

        # 如果是严重错误，可以发送告警
        if level == ErrorLevel.CRITICAL:
            self._send_alert(context)

    def _format_error_message(self, context: ErrorContext) -> str:
        """格式化错误消息"""
        parts = [
            f"[{context.module_name}.{context.function_name}]",
            f"错误类型: {context.error_type.__name__ if context.error_type else 'Unknown'}",
            f"错误消息: {context.error_message}",
            f"重试次数: {context.retry_count}",
            f"执行时间: {context.execution_time:.3f}秒",
        ]

        if context.additional_info:
            parts.append(f"附加信息: {context.additional_info}")

        return " | ".join(parts)

    def _send_alert(self, context: ErrorContext) -> None:
        """发送告警（可以扩展实现）"""
        pass

    def get_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        return {
            "error_counts": dict(self._error_stats),
            "total_errors": sum(self._error_stats.values()),
            "last_errors": {
                key: {
                    "timestamp": ctx.timestamp.isoformat(),
                    "error_type": ctx.error_type.__name__ if ctx.error_type else None,
                    "message": ctx.error_message,
                }
                for key, ctx in self._last_errors.items()
            },
        }


# 全局错误处理器
_global_error_handler = ErrorHandler()


def with_error_handling(
    *,
    exceptions: tuple = (Exception,),
    default_return: Any = None,
    reraise: bool = True,
    level: ErrorLevel = ErrorLevel.ERROR,
    context_info: Optional[Dict[str, Any]] = None,
) -> Callable[[F], F]:
    """
    错误处理装饰器

    Args:
        exceptions: 要捕获的异常类型
        default_return: 发生异常时的默认返回值
        reraise: 是否重新抛出异常
        level: 错误级别
        context_info: 额外的上下文信息

    Example:
        @with_error_handling(
            exceptions=(DatabaseConnectionError,),
            default_return=[],
            reraise=False
        )
        def fetch_data():
            # 数据库操作
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            context = ErrorContext(
                function_name=func.__name__,
                module_name=func.__module__,
                args=args,
                kwargs=kwargs,
                additional_info=context_info or {},
            )

            try:
                return func(*args, **kwargs)
            except exceptions as e:
                context.error_type = type(e)
                context.error_message = str(e)
                context.stack_trace = traceback.format_exc()
                context.execution_time = time.time() - start_time

                _global_error_handler.handle_error(context, level)

                if reraise:
                    raise
                return default_return

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            context = ErrorContext(
                function_name=func.__name__,
                module_name=func.__module__,
                args=args,
                kwargs=kwargs,
                additional_info=context_info or {},
            )

            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                context.error_type = type(e)
                context.error_message = str(e)
                context.stack_trace = traceback.format_exc()
                context.execution_time = time.time() - start_time

                _global_error_handler.handle_error(context, level)

                if reraise:
                    raise
                return default_return

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def with_retry(
    *,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Callable[[F], F]:
    """
    重试装饰器

    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 退避因子
        exceptions: 要重试的异常类型
        on_retry: 重试时的回调函数

    Example:
        @with_retry(
            max_attempts=3,
            delay=1.0,
            exceptions=(NetworkError,)
        )
        async def fetch_from_api():
            # API调用
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        if on_retry:
                            on_retry(attempt + 1, e)

                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        # 最后一次尝试失败，抛出异常
                        raise

            # 不应该到达这里
            if last_exception:
                raise last_exception

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        if on_retry:
                            on_retry(attempt + 1, e)

                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        # 最后一次尝试失败，抛出异常
                        raise

            # 不应该到达这里
            if last_exception:
                raise last_exception

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def with_timeout(seconds: float, error_message: str = "Operation timed out") -> Callable[[F], F]:
    """
    超时装饰器

    Args:
        seconds: 超时时间（秒）
        error_message: 超时错误消息

    Example:
        @with_timeout(30.0)
        async def long_running_task():
            # 长时间运行的任务
            pass
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                raise TimeoutError(error_message)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 对于同步函数，使用线程超时（需要额外实现）
            # 这里简化处理，直接调用
            return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def with_performance_monitoring(
    *, threshold_seconds: float = 1.0, log_slow: bool = True
) -> Callable[[F], F]:
    """
    性能监控装饰器

    Args:
        threshold_seconds: 慢操作阈值（秒）
        log_slow: 是否记录慢操作

    Example:
        @with_performance_monitoring(threshold_seconds=0.5)
        def process_data(data):
            # 数据处理
            pass
    """

    def decorator(func: F) -> F:
        logger = get_logger(func.__module__)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.perf_counter()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                execution_time = time.perf_counter() - start_time

                if log_slow and execution_time > threshold_seconds:
                    logger.warning(
                        f"慢操作检测: {func.__name__} "
                        f"执行时间 {execution_time:.3f}秒 "
                        f"(阈值: {threshold_seconds}秒)"
                    )

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.perf_counter()

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                execution_time = time.perf_counter() - start_time

                if log_slow and execution_time > threshold_seconds:
                    logger.warning(
                        f"慢操作检测: {func.__name__} "
                        f"执行时间 {execution_time:.3f}秒 "
                        f"(阈值: {threshold_seconds}秒)"
                    )

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


def with_circuit_breaker(
    *,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    expected_exception: Type[Exception] = Exception,
) -> Callable[[F], F]:
    """
    熔断器装饰器

    Args:
        failure_threshold: 失败阈值
        recovery_timeout: 恢复超时（秒）
        expected_exception: 预期的异常类型

    Example:
        @with_circuit_breaker(
            failure_threshold=3,
            recovery_timeout=30.0
        )
        def external_api_call():
            # 外部API调用
            pass
    """

    def decorator(func: F) -> F:
        state = {"failure_count": 0, "last_failure_time": None, "is_open": False}

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 检查熔断器状态
            if state["is_open"]:
                if state["last_failure_time"]:
                    elapsed = time.time() - state["last_failure_time"]
                    if elapsed < recovery_timeout:
                        raise RuntimeError(
                            f"熔断器开启中，请在 {recovery_timeout - elapsed:.1f} 秒后重试"
                        )
                    else:
                        # 尝试恢复
                        state["is_open"] = False
                        state["failure_count"] = 0

            try:
                result = func(*args, **kwargs)
                # 成功，重置失败计数
                state["failure_count"] = 0
                return result
            except expected_exception:
                state["failure_count"] += 1
                state["last_failure_time"] = time.time()

                if state["failure_count"] >= failure_threshold:
                    state["is_open"] = True

                raise

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 检查熔断器状态
            if state["is_open"]:
                if state["last_failure_time"]:
                    elapsed = time.time() - state["last_failure_time"]
                    if elapsed < recovery_timeout:
                        raise RuntimeError(
                            f"熔断器开启中，请在 {recovery_timeout - elapsed:.1f} 秒后重试"
                        )
                    else:
                        # 尝试恢复
                        state["is_open"] = False
                        state["failure_count"] = 0

            try:
                result = await func(*args, **kwargs)
                # 成功，重置失败计数
                state["failure_count"] = 0
                return result
            except expected_exception:
                state["failure_count"] += 1
                state["last_failure_time"] = time.time()

                if state["failure_count"] >= failure_threshold:
                    state["is_open"] = True

                raise

        if asyncio.iscoroutinefunction(func):
            return cast(F, async_wrapper)
        return cast(F, sync_wrapper)

    return decorator


@asynccontextmanager
async def error_context(
    name: str, suppress: bool = False, on_error: Optional[Callable[[Exception], None]] = None
):
    """
    错误处理上下文管理器

    Args:
        name: 上下文名称
        suppress: 是否抑制异常
        on_error: 错误回调

    Example:
        async with error_context("database_operation"):
            # 数据库操作
            pass
    """
    try:
        yield
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"错误发生在 {name}: {e}")

        if on_error:
            on_error(e)

        if not suppress:
            raise


def compose_decorators(*decorators) -> Callable[[F], F]:
    """
    组合多个装饰器

    Args:
        *decorators: 装饰器列表

    Example:
        @compose_decorators(
            with_retry(max_attempts=3),
            with_timeout(30),
            with_error_handling()
        )
        async def complex_operation():
            pass
    """

    def decorator(func: F) -> F:
        result = func
        for dec in reversed(decorators):
            result = dec(result)
        return result

    return decorator


# 导出便捷函数
def get_error_statistics() -> Dict[str, Any]:
    """获取全局错误统计"""
    return _global_error_handler.get_statistics()


def reset_error_statistics() -> None:
    """重置错误统计"""
    global _global_error_handler
    _global_error_handler = ErrorHandler()


# 预定义的装饰器组合
safe_database_operation = compose_decorators(
    with_retry(max_attempts=3, delay=0.5, exceptions=(DatabaseConnectionError,)),
    with_timeout(30.0),
    with_error_handling(
        exceptions=(DatabaseConnectionError, ValidationError), reraise=False, default_return=None
    ),
    with_performance_monitoring(threshold_seconds=1.0),
)

safe_api_call = compose_decorators(
    with_circuit_breaker(
        failure_threshold=5, recovery_timeout=60.0, expected_exception=NetworkError
    ),
    with_retry(max_attempts=3, delay=1.0, exceptions=(NetworkError, DataProviderError)),
    with_timeout(10.0),
    with_error_handling(exceptions=(NetworkError, DataProviderError), level=ErrorLevel.WARNING),
)


# 使用示例
if __name__ == "__main__":
    # 示例1：基本错误处理
    @with_error_handling(exceptions=(ValueError,), default_return=0, reraise=False)
    def divide(a: int, b: int) -> float:
        if b == 0:
            raise ValueError("除数不能为0")
        return a / b

    # 示例2：组合装饰器
    @safe_database_operation
    async def fetch_user_data(user_id: int):
        # 模拟数据库查询
        await asyncio.sleep(0.1)
        return {"id": user_id, "name": "Test User"}

    # 示例3：熔断器
    @with_circuit_breaker(failure_threshold=3)
    def unstable_service():
        import random

        if random.random() < 0.7:
            raise Exception("Service unavailable")
        return "Success"
