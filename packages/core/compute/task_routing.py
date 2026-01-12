# encoding:utf-8
"""
Dask 任务路由模块

提供统一的任务提交接口，根据任务类型自动路由到正确的 Worker 环境：
- WIN=1 资源: Windows Workers (数据获取任务)
- LINUX=1 资源: Docker Workers (适合 Docker 环境的任务)

使用示例:
    from core.compute.task_routing import submit_windows_task, submit_linux_task

    # 数据获取任务 → Windows Worker
    data = await submit_windows_task(fetch_market_data, symbol)

    # 计算任务 → Docker Worker
    result = await submit_linux_task(heavy_computation, data)
"""
from __future__ import annotations

import asyncio
import fnmatch
from enum import Enum
from typing import Any, Callable, TypeVar, cast

from loguru import logger

T = TypeVar("T")


class TaskEnvironment(Enum):
    """任务执行环境"""

    WINDOWS = "WIN"  # Windows Workers (数据访问)
    LINUX = "LINUX"  # Docker Workers (适合 Docker 的任务)
    ANY = None  # 无约束


# 默认的任务类型映射
_DEFAULT_WINDOWS_PATTERNS = [
    "data_fetch",
    "amazingdata_*",
    "miniqmt_*",
    "akshare_*",
    "realtime_quote",
    "fetch_*",
    "get_kline",
    "get_quote",
]

_DEFAULT_LINUX_PATTERNS = [
    "compute_*",
    "backtest_*",
    "train_*",
    "factor_*",
    "model_*",
]


def _match_task_type(task_type: str, patterns: list[str]) -> bool:
    """检查任务类型是否匹配模式列表"""
    for pattern in patterns:
        if fnmatch.fnmatch(task_type, pattern):
            return True
    return False


def infer_environment(task_type: str) -> TaskEnvironment:
    """根据任务类型推断执行环境"""
    # 优先检查 Windows 任务
    if _match_task_type(task_type, _DEFAULT_WINDOWS_PATTERNS):
        return TaskEnvironment.WINDOWS
    # 然后检查 Linux 任务
    if _match_task_type(task_type, _DEFAULT_LINUX_PATTERNS):
        return TaskEnvironment.LINUX
    # 默认无约束
    return TaskEnvironment.ANY


def get_resource_constraints(env: TaskEnvironment) -> dict[str, int] | None:
    """获取资源约束字典"""
    if env == TaskEnvironment.ANY or env.value is None:
        return None
    return {env.value: 1}


def requires_windows(func: Callable[..., T]) -> Callable[..., T]:
    """装饰器：标记函数需要 Windows 环境执行

    使用示例:
        @requires_windows
        def fetch_amazingdata(symbol: str) -> pd.DataFrame:
            ...
    """
    setattr(func, "_dask_environment", TaskEnvironment.WINDOWS)
    return func


def requires_linux(func: Callable[..., T]) -> Callable[..., T]:
    """装饰器：标记函数需要 Linux/Docker 环境执行

    使用示例:
        @requires_linux
        def train_model(data: pd.DataFrame) -> Model:
            ...
    """
    setattr(func, "_dask_environment", TaskEnvironment.LINUX)
    return func


def get_function_environment(func: Callable[..., Any]) -> TaskEnvironment:
    """获取函数标记的执行环境"""
    return getattr(func, "_dask_environment", TaskEnvironment.ANY)


class TaskRouter:
    """任务路由器

    管理 Dask Client 连接，提供环境感知的任务提交接口。
    """

    _instance: "TaskRouter | None" = None
    _lock = asyncio.Lock()

    def __init__(self, scheduler_address: str = "localhost:8786") -> None:
        self._scheduler_address = scheduler_address
        self._client: Any = None
        self._connected = False

    @classmethod
    async def get_instance(cls, scheduler_address: str = "localhost:8786") -> "TaskRouter":
        """获取单例实例"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(scheduler_address)
            return cls._instance

    async def connect(self) -> bool:
        """连接到 Dask Scheduler"""
        if self._connected and self._client is not None:
            return True

        try:
            from distributed import Client

            self._client = await Client(
                self._scheduler_address,
                asynchronous=True,
                timeout="10s",
            )
            self._connected = True
            logger.info(f"Connected to Dask scheduler: {self._scheduler_address}")
            return True
        except Exception as exc:
            logger.warning(f"Failed to connect to Dask scheduler: {exc}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """断开连接"""
        if self._client is not None:
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def submit(
        self,
        func: Callable[..., T],
        *args: Any,
        env: TaskEnvironment | None = None,
        task_type: str | None = None,
        **kwargs: Any,
    ) -> T:
        """提交任务到指定环境

        Args:
            func: 要执行的函数
            *args: 位置参数
            env: 执行环境 (如果为 None，则自动推断)
            task_type: 任务类型 (用于自动推断环境)
            **kwargs: 关键字参数

        Returns:
            任务结果
        """
        if not self._connected:
            await self.connect()

        if self._client is None:
            raise RuntimeError("Dask client not connected")

        # 确定执行环境
        if env is None:
            # 优先检查函数装饰器
            env = get_function_environment(func)
            # 其次根据任务类型推断
            if env == TaskEnvironment.ANY and task_type:
                env = infer_environment(task_type)

        # 获取资源约束
        resources = get_resource_constraints(env)

        # 提交任务
        future = self._client.submit(func, *args, resources=resources, **kwargs)
        result = await future
        return cast(T, result)

    async def map(
        self,
        func: Callable[..., T],
        *iterables: Any,
        env: TaskEnvironment | None = None,
        **kwargs: Any,
    ) -> list[T]:
        """并行 map 操作

        Args:
            func: 要执行的函数
            *iterables: 可迭代对象
            env: 执行环境
            **kwargs: 传递给 client.map 的参数

        Returns:
            结果列表
        """
        if not self._connected:
            await self.connect()

        if self._client is None:
            raise RuntimeError("Dask client not connected")

        if env is None:
            env = get_function_environment(func)

        resources = get_resource_constraints(env)

        futures = self._client.map(func, *iterables, resources=resources, **kwargs)
        results = await self._client.gather(futures)
        return list(results)

    async def get_worker_status(self) -> dict[str, Any]:
        """获取 Worker 状态统计"""
        if not self._connected or self._client is None:
            return {"connected": False, "workers": {}}

        try:
            scheduler_info = self._client.scheduler_info()
            workers = scheduler_info.get("workers", {})

            status: dict[str, Any] = {
                "connected": True,
                "scheduler": self._scheduler_address,
                "total_workers": len(workers),
                "windows_workers": 0,
                "linux_workers": 0,
                "workers": {},
            }

            for addr, info in workers.items():
                resources = info.get("resources", {})
                name = info.get("name", addr)
                worker_info = {
                    "name": name,
                    "address": addr,
                    "memory": info.get("memory_limit", 0),
                    "nthreads": info.get("nthreads", 0),
                    "resources": resources,
                }
                status["workers"][addr] = worker_info

                if resources.get("WIN"):
                    status["windows_workers"] = int(status["windows_workers"]) + 1
                elif resources.get("LINUX"):
                    status["linux_workers"] = int(status["linux_workers"]) + 1

            return status
        except Exception as exc:
            logger.warning(f"Failed to get worker status: {exc}")
            return {"connected": False, "error": str(exc)}


# 便捷函数
async def submit_windows_task(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """提交任务到 Windows Worker"""
    router = await TaskRouter.get_instance()
    return await router.submit(func, *args, env=TaskEnvironment.WINDOWS, **kwargs)


async def submit_linux_task(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """提交任务到 Docker/Linux Worker"""
    router = await TaskRouter.get_instance()
    return await router.submit(func, *args, env=TaskEnvironment.LINUX, **kwargs)


async def submit_task(
    func: Callable[..., T],
    *args: Any,
    task_type: str | None = None,
    **kwargs: Any,
) -> T:
    """提交任务，自动推断环境"""
    router = await TaskRouter.get_instance()
    return await router.submit(func, *args, task_type=task_type, **kwargs)
