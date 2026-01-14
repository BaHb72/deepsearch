"""
实时数据流模块。

基于 AsyncIO + Pub/Sub 模式的实时数据流抽象层。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Set

from loguru import logger

if TYPE_CHECKING:
    from core.infrastructure.providers.interfaces.base import DataProvider


class RealtimeDataStream:
    """
    实时数据流抽象（基于 AsyncIO + Pub/Sub）。

    核心特性：
    - Producer-Consumer 模式：生产者从数据源拉取，消费者分发到订阅者
    - asyncio.Queue：解耦生产和消费，缓冲区最多10000条
    - Pub/Sub：支持多个订阅者订阅不同股票
    - 协程链式处理：所有回调都是异步的
    """

    def __init__(self, provider: "DataProvider | None" = None, queue_size: int = 10000):
        """
        初始化实时数据流。

        Args:
            provider: 数据提供者（可选，用于从真实数据源拉取）
            queue_size: 队列大小，默认10000
        """
        self.provider = provider
        self.queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=queue_size)
        self.subscriptions: Dict[str, Set[Callable]] = {}
        self._running = False
        self._tasks: List[asyncio.Task[Any]] = []

    async def subscribe(self, symbols: List[str], callback: Callable) -> None:
        """
        订阅实时数据（Pub/Sub 模式）。

        Args:
            symbols: 股票代码列表
            callback: 回调函数（async def callback(tick: Dict) -> None）
        """
        for symbol in symbols:
            if symbol not in self.subscriptions:
                self.subscriptions[symbol] = set()
                # 如果有 provider，通知其订阅该股票
                if self.provider and hasattr(self.provider, "subscribe_realtime"):
                    try:
                        await self.provider.subscribe_realtime(symbol)  # type: ignore[attr-defined]
                        logger.debug(f"订阅实时数据: {symbol}")
                    except Exception as e:
                        logger.warning(f"订阅 {symbol} 失败: {e}")

            self.subscriptions[symbol].add(callback)
            logger.debug(f"添加订阅者: {symbol} -> {callback.__name__}")

    async def unsubscribe(self, symbols: List[str], callback: Callable) -> None:
        """
        取消订阅。

        Args:
            symbols: 股票代码列表
            callback: 回调函数
        """
        for symbol in symbols:
            if symbol in self.subscriptions:
                self.subscriptions[symbol].discard(callback)
                if not self.subscriptions[symbol]:
                    # 没有订阅者了，清理
                    del self.subscriptions[symbol]
                    logger.debug(f"清理订阅: {symbol}")

    async def start(self) -> None:
        """
        启动数据流消费者。

        创建两个后台任务：
        - 生产者：从数据源拉取数据到队列
        - 消费者：从队列消费数据并分发
        """
        if self._running:
            logger.warning("数据流已经在运行")
            return

        self._running = True
        logger.info("启动实时数据流")

        # 创建后台任务
        producer_task = asyncio.create_task(self._produce(), name="realtime-producer")
        consumer_task = asyncio.create_task(self._consume(), name="realtime-consumer")

        self._tasks = [producer_task, consumer_task]

    async def stop(self) -> None:
        """停止数据流"""
        if not self._running:
            return

        logger.info("停止实时数据流")
        self._running = False

        # 取消所有后台任务
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # 等待任务完成
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        logger.info("实时数据流已停止")

    async def push(self, tick: Dict[str, Any]) -> None:
        """
        推送数据到队列（供外部调用）。

        Args:
            tick: Tick 数据字典（必须包含 'symbol' 键）
        """
        try:
            await self.queue.put(tick)
        except asyncio.QueueFull:
            logger.warning("队列已满，丢弃数据")

    async def _produce(self) -> None:
        """
        生产者：从数据源拉取数据到队列。

        如果没有 provider 或 provider 不支持 stream()，则只是等待外部 push()。
        """
        if not self.provider or not hasattr(self.provider, "stream"):
            logger.debug("无数据源，等待外部 push()")
            # 保持运行但不做任何事
            while self._running:
                await asyncio.sleep(1)
            return

        try:
            async for tick in self.provider.stream():  # type: ignore[attr-defined]
                if not self._running:
                    break
                await self.queue.put(tick)
        except Exception as e:
            logger.error(f"生产者错误: {e}")

    async def _consume(self) -> None:
        """
        消费者：从队列消费数据并分发到订阅者。

        使用协程链式处理，所有回调都是异步执行。
        """
        while self._running:
            try:
                # 带超时的等待，避免永久阻塞
                tick = await asyncio.wait_for(self.queue.get(), timeout=1.0)

                symbol = tick.get("symbol")
                if not symbol:
                    logger.warning("Tick 数据缺少 symbol 字段")
                    continue

                # 分发到订阅者
                callbacks = self.subscriptions.get(symbol, set())
                if callbacks:
                    # 并发调用所有回调
                    await asyncio.gather(
                        *[callback(tick) for callback in callbacks],
                        return_exceptions=True,
                    )

            except asyncio.TimeoutError:
                # 超时正常，继续等待
                continue
            except Exception as e:
                logger.error(f"消费者错误: {e}")

    def is_running(self) -> bool:
        """检查数据流是否在运行"""
        return self._running

    def get_subscribed_symbols(self) -> List[str]:
        """获取所有已订阅的股票代码"""
        return list(self.subscriptions.keys())


__all__ = ["RealtimeDataStream"]
