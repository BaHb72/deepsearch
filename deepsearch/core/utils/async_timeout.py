"""
异步超时管理模块

提供异步操作的超时控制功能
"""
import asyncio
import functools
from typing import TypeVar, Callable, Any, Optional, Coroutine
from contextlib import asynccontextmanager

from loguru import logger


T = TypeVar('T')


async def with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout: float,
    default: Optional[T] = None
) -> T:
    """
    为协程添加超时控制

    Args:
        coro: 要执行的协程
        timeout: 超时时间（秒）
        default: 超时后返回的默认值

    Returns:
        协程的返回值，或超时后的默认值
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning(f"Coroutine timed out after {timeout} seconds")
        return default


async def run_with_timeout(
    func: Callable[..., T],
    *args,
    timeout: float,
    default: Optional[T] = None,
    **kwargs
) -> T:
    """
    在超时控制下运行同步函数

    Args:
        func: 要执行的同步函数
        *args: 函数参数
        timeout: 超时时间（秒）
        default: 超时后返回的默认值
        **kwargs: 函数关键字参数

    Returns:
        函数的返回值，或超时后的默认值
    """
    loop = asyncio.get_event_loop()
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(None, func, *args, **kwargs),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning(f"Function {func.__name__} timed out after {timeout} seconds")
        return default


def timeout_decorator(seconds: float, default: Any = None):
    """
    超时装饰器

    Args:
        seconds: 超时时间（秒）
        default: 超时后返回的默认值

    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            if asyncio.iscoroutinefunction(func):
                return await with_timeout(
                    func(*args, **kwargs),
                    timeout=seconds,
                    default=default
                )
            else:
                return await run_with_timeout(
                    func,
                    *args,
                    timeout=seconds,
                    default=default,
                    **kwargs
                )
        return wrapper
    return decorator


@asynccontextmanager
async def timeout_context(seconds: float):
    """
    超时上下文管理器

    Args:
        seconds: 超时时间（秒）

    Usage:
        async with timeout_context(10):
            await some_long_operation()
    """
    task = asyncio.current_task()
    if task is None:
        raise RuntimeError("No current task in timeout_context")

    # 创建一个取消任务的回调
    def timeout_callback():
        task.cancel()

    # 设置超时
    handle = asyncio.get_event_loop().call_later(seconds, timeout_callback)

    try:
        yield
    finally:
        handle.cancel()


class TimeoutError(Exception):
    """超时异常"""

    def __init__(self, message: str = "Operation timed out"):
        super().__init__(message)
        self.message = message


# 为了兼容性，提供一些别名函数
async def wait_for(coro: Coroutine[Any, Any, T], timeout: float) -> T:
    """
    等待协程完成，带超时控制（asyncio.wait_for的包装）

    Args:
        coro: 要执行的协程
        timeout: 超时时间（秒）

    Returns:
        协程的返回值

    Raises:
        asyncio.TimeoutError: 超时时抛出
    """
    return await asyncio.wait_for(coro, timeout=timeout)


# 导出timeout函数作为别名
timeout = timeout_context