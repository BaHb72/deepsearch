"""
聚合调度引擎。

负责管理聚合任务的生命周期：启动、停止、刷新。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Dict, Optional

from loguru import logger

from .cache import get_cache
from .registry import get_registry

if TYPE_CHECKING:
    from deepsearch.infrastructure.providers.binder import UnifiedDataFeed


class AggregationEngine:
    """
    聚合调度引擎（单例）。

    职责：
    - 管理聚合任务的生命周期
    - 定时调用各聚合的 compute 方法
    - 将结果写入 AggregationCache
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
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = False

    def set_feed(self, feed: "UnifiedDataFeed") -> None:
        """设置 UnifiedDataFeed 实例。"""
        self._feed = feed

    @property
    def is_running(self) -> bool:
        """检查引擎是否正在运行。"""
        return self._running

    def start(self) -> None:
        """
        启动所有已注册的聚合任务。

        注意：需要在 asyncio 事件循环中调用。
        """
        if self._running:
            logger.warning("AggregationEngine 已在运行")
            return

        if self._feed is None:
            raise RuntimeError("AggregationEngine 未设置 feed，请先调用 set_feed()")

        registry = get_registry()
        if not registry:
            logger.warning("没有已注册的聚合，引擎启动但无任务")
            self._running = True
            return

        self._running = True
        for name, agg_cls in registry.items():
            task = asyncio.create_task(self._run_aggregation(name, agg_cls))
            self._tasks[name] = task
            logger.info(f"启动聚合任务: {name} (间隔 {agg_cls.interval}s)")

        logger.info(f"AggregationEngine 启动完成，共 {len(self._tasks)} 个任务")

    def stop(self) -> None:
        """停止所有聚合任务。"""
        if not self._running:
            return

        for name, task in self._tasks.items():
            task.cancel()
            logger.info(f"停止聚合任务: {name}")

        self._tasks.clear()
        self._running = False
        logger.info("AggregationEngine 已停止")

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

    async def _run_aggregation(self, name: str, agg_cls: type) -> None:
        """单个聚合的调度循环。"""
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


def get_engine() -> AggregationEngine:
    """获取全局引擎实例。"""
    return AggregationEngine()


__all__ = ["AggregationEngine", "get_engine"]
