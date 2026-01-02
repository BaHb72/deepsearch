"""
聚合调度引擎。

负责管理聚合任务的生命周期：启动、停止、刷新。
支持两种执行模式：
- local: 使用 asyncio 在本地执行
- dask: 分发到 Dask 集群执行
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

from loguru import logger

from .cache import get_cache
from .registry import get_registry

if TYPE_CHECKING:
    from deepsearch.compute import DaskTaskClient
    from deepsearch.infrastructure.providers.binder import UnifiedDataFeed


class ExecutionMode(str, Enum):
    """聚合执行模式。"""

    LOCAL = "local"  # 本地 asyncio 执行
    DASK = "dask"  # Dask 分布式执行


def _run_aggregation_on_worker(
    aggregation_class_name: str,
    aggregation_module: str,
) -> Any:
    """
    在 Dask Worker 中执行聚合计算。

    此函数在 Worker 进程中运行，需要动态导入聚合类。

    Args:
        aggregation_class_name: 聚合类名
        aggregation_module: 聚合类所在模块

    Returns:
        聚合计算结果
    """
    import asyncio
    import importlib

    # 动态导入聚合类
    module = importlib.import_module(aggregation_module)
    agg_class = getattr(module, aggregation_class_name)
    agg = agg_class()

    # 运行异步 compute 方法
    async def run_compute():
        # Worker 端目前无 feed，传入 None
        # 聚合实现应处理 feed=None 的情况
        return await agg.compute(None)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_compute())
    finally:
        loop.close()


class AggregationEngine:
    """
    聚合调度引擎（单例）。

    职责：
    - 管理聚合任务的生命周期
    - 定时调用各聚合的 compute 方法
    - 将结果写入 AggregationCache

    执行模式：
    - LOCAL: 使用 asyncio 在本地执行（默认）
    - DASK: 分发到 Dask 集群执行

    用法：
        engine = get_engine()
        engine.set_feed(feed)
        engine.start(mode=ExecutionMode.DASK)  # 或 ExecutionMode.LOCAL
    """

    _instance: Optional["AggregationEngine"] = None

    def __new__(cls) -> "AggregationEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._feed: Optional["UnifiedDataFeed"] = None
        self._mode: ExecutionMode = ExecutionMode.LOCAL
        self._running = False

        # Local mode: asyncio tasks
        self._tasks: Dict[str, asyncio.Task] = {}

        # Dask mode: client and futures
        self._dask_client: Optional["DaskTaskClient"] = None
        self._dask_futures: Dict[str, Any] = {}
        self._scheduler_task: Optional[asyncio.Task] = None

    def set_feed(self, feed: "UnifiedDataFeed") -> None:
        """设置 UnifiedDataFeed 实例。"""
        self._feed = feed

    @property
    def is_running(self) -> bool:
        """检查引擎是否正在运行。"""
        return self._running

    @property
    def mode(self) -> ExecutionMode:
        """获取当前执行模式。"""
        return self._mode

    def start(
        self,
        mode: ExecutionMode = ExecutionMode.LOCAL,
        dask_scheduler: str = "tcp://localhost:8786",
    ) -> None:
        """
        启动所有已注册的聚合任务。

        Args:
            mode: 执行模式 (LOCAL 或 DASK)
            dask_scheduler: Dask Scheduler 地址 (仅 DASK 模式需要)
        """
        if self._running:
            logger.warning("AggregationEngine 已在运行")
            return

        self._mode = mode

        if mode == ExecutionMode.DASK:
            self._start_dask_mode(dask_scheduler)
        else:
            self._start_local_mode()

    def _start_local_mode(self) -> None:
        """启动本地 asyncio 模式。"""
        if self._feed is None:
            raise RuntimeError("AggregationEngine 未设置 feed，请先调用 set_feed()")

        registry = get_registry()
        if not registry:
            logger.warning("没有已注册的聚合，引擎启动但无任务")
            self._running = True
            return

        self._running = True
        for name, agg_cls in registry.items():
            task = asyncio.create_task(self._run_local_aggregation(name, agg_cls))
            self._tasks[name] = task
            logger.info(f"启动本地聚合任务: {name} (间隔 {agg_cls.interval}s)")

        logger.info(f"AggregationEngine 启动完成 [LOCAL], 共 {len(self._tasks)} 个任务")

    def _start_dask_mode(self, scheduler_address: str) -> None:
        """启动 Dask 分布式模式。"""
        try:
            from deepsearch.compute import DaskTaskClient

            self._dask_client = DaskTaskClient(scheduler_address=scheduler_address)
            info = self._dask_client.get_cluster_info()
            logger.info(
                f"连接到 Dask 集群: {info.get('n_workers', 0)} workers, "
                f"{info.get('total_threads', 0)} threads"
            )
        except Exception as e:
            logger.error(f"连接 Dask 集群失败: {e}")
            raise

        self._running = True
        self._scheduler_task = asyncio.create_task(self._run_dask_scheduler())
        logger.info("AggregationEngine 启动完成 [DASK]")

    def stop(self) -> None:
        """停止所有聚合任务。"""
        if not self._running:
            return

        if self._mode == ExecutionMode.DASK:
            self._stop_dask_mode()
        else:
            self._stop_local_mode()

        self._running = False
        logger.info(f"AggregationEngine 已停止 [{self._mode.value.upper()}]")

    def _stop_local_mode(self) -> None:
        """停止本地模式。"""
        for name, task in self._tasks.items():
            task.cancel()
            logger.info(f"停止聚合任务: {name}")
        self._tasks.clear()

    def _stop_dask_mode(self) -> None:
        """停止 Dask 模式。"""
        if self._scheduler_task:
            self._scheduler_task.cancel()
            self._scheduler_task = None

        for name, future in self._dask_futures.items():
            try:
                future.cancel()
            except Exception:
                pass
        self._dask_futures.clear()

        if self._dask_client:
            self._dask_client.close()
            self._dask_client = None

    async def refresh(self, name: str) -> None:
        """
        立即刷新指定聚合。

        Args:
            name: 聚合名称
        """
        registry = get_registry()
        agg_cls = registry.get(name)
        if agg_cls is None:
            logger.warning(f"未找到聚合: {name}")
            return

        if self._mode == ExecutionMode.DASK and self._dask_client:
            await self._refresh_via_dask(name, agg_cls)
        else:
            await self._refresh_local(name, agg_cls)

    async def _refresh_local(self, name: str, agg_cls: type) -> None:
        """本地刷新聚合。"""
        if self._feed is None:
            logger.error("feed 未设置，无法刷新")
            return

        agg = agg_cls()
        try:
            result = await agg.compute(self._feed)
            get_cache().set(name, result)
            logger.info(f"手动刷新聚合完成: {name}")
        except Exception as e:
            logger.error(f"刷新聚合失败 {name}: {e}")

    async def _refresh_via_dask(self, name: str, agg_cls: type) -> None:
        """通过 Dask 刷新聚合。"""
        try:
            future = self._dask_client.submit_task(
                _run_aggregation_on_worker,
                agg_cls.__name__,
                agg_cls.__module__,
                key=f"refresh-{name}",
            )
            result = self._dask_client.get_result(future, timeout=30)
            get_cache().set(name, result)
            logger.info(f"手动刷新聚合完成 (Dask): {name}")
        except Exception as e:
            logger.error(f"刷新聚合失败 {name}: {e}")

    async def _run_local_aggregation(self, name: str, agg_cls: type) -> None:
        """单个聚合的本地调度循环。"""
        agg = agg_cls()
        cache = get_cache()

        while True:
            try:
                result = await agg.compute(self._feed)
                cache.set(name, result)
                logger.debug(f"聚合 {name} 计算完成，结果已缓存")
            except asyncio.CancelledError:
                logger.debug(f"聚合任务 {name} 被取消")
                break
            except Exception as e:
                logger.error(f"聚合 {name} 计算失败: {e}")

            await asyncio.sleep(agg.interval)

    async def _run_dask_scheduler(self) -> None:
        """Dask 模式的调度循环。"""
        import time

        registry = get_registry()
        if not registry:
            logger.warning("没有已注册的聚合")
            return

        cache = get_cache()
        next_run: Dict[str, float] = {name: time.time() for name in registry}

        while self._running:
            try:
                current_time = time.time()

                for name, agg_cls in registry.items():
                    # 收集已完成的任务
                    if name in self._dask_futures:
                        future = self._dask_futures[name]
                        if future.done():
                            try:
                                result = future.result()
                                cache.set(name, result)
                                logger.debug(f"Dask 聚合 {name} 完成")
                            except Exception as e:
                                logger.error(f"Dask 聚合 {name} 失败: {e}")
                            del self._dask_futures[name]
                        else:
                            continue  # 任务还在运行

                    # 检查是否到执行时间
                    if current_time >= next_run.get(name, 0):
                        self._submit_dask_aggregation(name, agg_cls)
                        next_run[name] = current_time + agg_cls.interval

                await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Dask 调度循环错误: {e}")
                await asyncio.sleep(5)

    def _submit_dask_aggregation(self, name: str, agg_cls: type) -> None:
        """提交聚合任务到 Dask。"""
        if not self._dask_client:
            return

        try:
            future = self._dask_client.submit_task(
                _run_aggregation_on_worker,
                agg_cls.__name__,
                agg_cls.__module__,
                key=f"aggregation-{name}",
            )
            self._dask_futures[name] = future
            logger.debug(f"提交 Dask 聚合任务: {name}")
        except Exception as e:
            logger.error(f"提交 Dask 任务失败 {name}: {e}")

    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态。"""
        status = {
            "running": self._running,
            "mode": self._mode.value,
        }

        if self._mode == ExecutionMode.LOCAL:
            status["tasks"] = list(self._tasks.keys())
        else:
            status["pending_tasks"] = list(self._dask_futures.keys())
            if self._dask_client:
                try:
                    info = self._dask_client.get_cluster_info()
                    status["cluster"] = {
                        "n_workers": info.get("n_workers", 0),
                        "total_threads": info.get("total_threads", 0),
                    }
                except Exception:
                    status["cluster"] = {"error": "Failed to get cluster info"}

        return status


def get_engine() -> AggregationEngine:
    """获取全局引擎实例。"""
    return AggregationEngine()


__all__ = ["AggregationEngine", "ExecutionMode", "get_engine"]
