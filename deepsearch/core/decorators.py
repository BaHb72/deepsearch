"""
核心装饰器

提供通用的装饰器来减少代码重复。
"""
import asyncio
import functools
import logging
import time
from typing import Callable, Any, Optional, TypeVar

from .interfaces import ComponentLifecycleError

# 类型变量
F = TypeVar('F', bound=Callable[..., Any])


def with_error_handling(
        error_message: str = "操作失败",
        raise_on_error: bool = True,
        log_level: int = logging.ERROR
) -> Callable[[F], F]:
    """
    错误处理装饰器
    
    Args:
        error_message: 错误消息前缀
        raise_on_error: 是否重新抛出异常
        log_level: 日志级别
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 尝试从第一个参数（可能是self）获取logger
                if args and hasattr(args[0], '_logger'):
                    logger = args[0]._logger
                else:
                    logger = logging.getLogger(func.__module__)
                logger.log(log_level, f"{error_message}: {e}")
                if raise_on_error:
                    raise
                return None

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # 尝试从第一个参数（可能是self）获取logger
                if args and hasattr(args[0], '_logger'):
                    logger = args[0]._logger
                else:
                    logger = logging.getLogger(func.__module__)
                logger.log(log_level, f"{error_message}: {e}")
                if raise_on_error:
                    raise
                return None

        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def with_retry(
        max_attempts: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: tuple = (Exception,)
) -> Callable[[F], F]:
    """
    重试装饰器
    
    Args:
        max_attempts: 最大重试次数
        delay: 初始延迟（秒）
        backoff: 延迟增长因子
        exceptions: 需要重试的异常类型
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
                        # 尝试从第一个参数（可能是self）获取logger
                        if args and hasattr(args[0], '_logger'):
                            logger = args[0]._logger
                        else:
                            logger = logging.getLogger(func.__module__)
                        logger.warning(
                            f"{func.__name__} 失败（尝试 {attempt + 1}/{max_attempts}）: {e}"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff

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
                        # 尝试从第一个参数（可能是self）获取logger
                        if args and hasattr(args[0], '_logger'):
                            logger = args[0]._logger
                        else:
                            logger = logging.getLogger(func.__module__)
                        logger.warning(
                            f"{func.__name__} 失败（尝试 {attempt + 1}/{max_attempts}）: {e}"
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff

            if last_exception:
                raise last_exception

        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def with_timeout(timeout: float) -> Callable[[F], F]:
    """
    超时装饰器（仅用于异步函数）
    
    Args:
        timeout: 超时时间（秒）
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            try:
                return await asyncio.wait_for(func(self, *args, **kwargs), timeout=timeout)
            except asyncio.TimeoutError:
                # 尝试从第一个参数（可能是self）获取logger
                if args and hasattr(args[0], '_logger'):
                    logger = args[0]._logger
                else:
                    logger = logging.getLogger(func.__module__)
                logger.error(f"{func.__name__} 执行超时（{timeout}秒）")
                raise

        if not asyncio.iscoroutinefunction(func):
            raise TypeError(f"@with_timeout 只能用于异步函数，{func.__name__} 不是异步函数")

        return wrapper

    return decorator


def measure_performance(
        log_slow_threshold: Optional[float] = None
) -> Callable[[F], F]:
    """
    性能测量装饰器
    
    Args:
        log_slow_threshold: 慢操作阈值（秒），超过则记录警告日志
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(self, *args, **kwargs)
                return result
            finally:
                elapsed = time.time() - start_time
                # 尝试从第一个参数（可能是self）获取logger
                if args and hasattr(args[0], '_logger'):
                    logger = args[0]._logger
                else:
                    logger = logging.getLogger(func.__module__)

                if log_slow_threshold and elapsed > log_slow_threshold:
                    logger.warning(
                        f"{func.__name__} 执行时间过长: {elapsed:.3f}秒"
                    )
                else:
                    logger.debug(
                        f"{func.__name__} 执行时间: {elapsed:.3f}秒"
                    )

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(self, *args, **kwargs)
                return result
            finally:
                elapsed = time.time() - start_time
                # 尝试从第一个参数（可能是self）获取logger
                if args and hasattr(args[0], '_logger'):
                    logger = args[0]._logger
                else:
                    logger = logging.getLogger(func.__module__)

                if log_slow_threshold and elapsed > log_slow_threshold:
                    logger.warning(
                        f"{func.__name__} 执行时间过长: {elapsed:.3f}秒"
                    )
                else:
                    logger.debug(
                        f"{func.__name__} 执行时间: {elapsed:.3f}秒"
                    )

        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def ensure_initialized(func: F) -> F:
    """
    确保组件已初始化的装饰器
    
    用于组件的公共方法，确保在调用前组件已经初始化
    """

    @functools.wraps(func)
    def sync_wrapper(self, *args, **kwargs):
        if hasattr(self, '_status'):
            from .interfaces import ComponentStatus
            if self._status == ComponentStatus.UNINITIALIZED:
                raise ComponentLifecycleError(
                    f"组件 {getattr(self, '_name', 'unknown')} 尚未初始化"
                )
        return func(self, *args, **kwargs)

    @functools.wraps(func)
    async def async_wrapper(self, *args, **kwargs):
        if hasattr(self, '_status'):
            from .interfaces import ComponentStatus
            if self._status == ComponentStatus.UNINITIALIZED:
                raise ComponentLifecycleError(
                    f"组件 {getattr(self, '_name', 'unknown')} 尚未初始化"
                )
        return await func(self, *args, **kwargs)

    # 根据函数类型返回相应的包装器
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


def singleton(cls):
    """
    单例装饰器
    
    确保类只有一个实例
    """
    instances = {}
    lock = asyncio.Lock() if asyncio else None

    @functools.wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in instances:
            if lock and asyncio.get_event_loop().is_running():
                # 异步环境下使用锁
                async def create_instance():
                    async with lock:
                        if cls not in instances:
                            instances[cls] = cls(*args, **kwargs)
                    return instances[cls]

                return asyncio.create_task(create_instance())
            else:
                # 同步环境下直接创建
                instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance
