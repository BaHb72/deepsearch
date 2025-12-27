# encoding:utf-8
"""
SDK对象的进程隔离代理

通过 __getattr__ 拦截所有SDK方法调用，自动将其转换为 ProcessCommand
在子进程中安全执行，防止SDK调用 sys.exit() 导致主进程崩溃。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from loguru import logger

if TYPE_CHECKING:
    from .process.runtime import ProcessIsolatedAmazingDataProvider

from deepsearch.ports.amazingdata_process import ProcessCommand


class ProcessIsolatedSDKProxy:
    """
    SDK对象的进程隔离代理类

    用法示例:
        # 原来的不安全方式
        self._info_data = sdk.InfoData()
        result = self._info_data.get_income(code_list)  # 可能调用 sys.exit()

        # 使用代理的安全方式
        self._info_data = ProcessIsolatedSDKProxy("InfoData", backend)
        result = await self._info_data.get_income(code_list)  # 在子进程安全执行
    """

    def __init__(self, class_name: str, backend: "ProcessIsolatedAmazingDataProvider"):
        """
        初始化SDK代理

        Args:
            class_name: SDK类名，如 "InfoData", "BaseData", "MarketData"
            backend: ProcessIsolatedAmazingDataProvider实例，用于执行命令
        """
        # 使用 object.__setattr__ 避免触发 __getattr__
        object.__setattr__(self, "_class_name", class_name)
        object.__setattr__(self, "_backend", backend)

    def __getattr__(self, method_name: str) -> Callable[..., Coroutine[Any, Any, Any]]:
        """
        拦截所有属性/方法访问，返回异步方法包装器

        Args:
            method_name: 被访问的方法名，如 "get_income"

        Returns:
            异步方法包装器，调用时在子进程执行对应的SDK方法
        """
        # 获取内部属性
        class_name = object.__getattribute__(self, "_class_name")
        backend = object.__getattribute__(self, "_backend")

        async def _method_wrapper(*args: Any, **kwargs: Any) -> Any:
            """
            异步方法包装器，将调用转换为 ProcessCommand 在子进程执行
            """
            full_method = f"{class_name}.{method_name}"

            logger.debug(
                "ProcessIsolatedSDKProxy calling method={} args_count={} kwargs_keys={}",
                full_method,
                len(args),
                list(kwargs.keys()),
            )

            command: ProcessCommand[Any] = ProcessCommand(
                method=full_method,
                args=args,
                kwargs=kwargs,
            )

            try:
                result = await backend._execute(command)
                logger.debug(
                    "ProcessIsolatedSDKProxy method={} completed result_type={}",
                    full_method,
                    type(result).__name__ if result is not None else "None",
                )
                return result
            except Exception as e:
                logger.error(
                    "ProcessIsolatedSDKProxy method={} failed error={}",
                    full_method,
                    str(e),
                )
                raise

        return _method_wrapper

    def __repr__(self) -> str:
        class_name = object.__getattribute__(self, "_class_name")
        return f"<ProcessIsolatedSDKProxy({class_name})>"


class ProcessIsolatedSDKProxySync:
    """
    同步方法的SDK代理（用于需要同步调用的场景）

    注意：此类会在调用时阻塞等待结果，适用于不在异步上下文中的场景。
    """

    def __init__(self, class_name: str, backend: "ProcessIsolatedAmazingDataProvider"):
        object.__setattr__(self, "_class_name", class_name)
        object.__setattr__(self, "_backend", backend)

    def __getattr__(self, method_name: str) -> Callable[..., Any]:
        class_name = object.__getattribute__(self, "_class_name")
        backend = object.__getattribute__(self, "_backend")

        def _sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            """同步包装器，通过 asyncio.run 执行异步调用"""
            full_method = f"{class_name}.{method_name}"

            command: ProcessCommand[Any] = ProcessCommand(
                method=full_method,
                args=args,
                kwargs=kwargs,
            )

            # 尝试获取当前事件循环
            try:
                loop = asyncio.get_running_loop()
                # 如果在异步上下文中，创建任务
                future = asyncio.run_coroutine_threadsafe(backend._execute(command), loop)
                return future.result(timeout=60)
            except RuntimeError:
                # 没有运行中的事件循环，创建新的
                return asyncio.run(backend._execute(command))

        return _sync_wrapper


__all__ = ["ProcessIsolatedSDKProxy", "ProcessIsolatedSDKProxySync"]
