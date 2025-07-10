# deepsearch/trader/core/event/persist.py
"""
PersistBus：单协程批量写缓存/持久化。
特点
- 非阻塞 Core/Aux 线程
- 可 async with 使用
- stop() 保证数据不丢
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, List, Optional

LOGGER = logging.getLogger(__name__)


class PersistBus:
    """
    持久化总线类

    提供一个异步队列，支持批量数据刷新的功能。该类适合于需要高频次写入
    但希望以批量刷新的方式提高效率的场景。

    :ivar _flush_size: 刷新时的批处理大小，决定每次写入的最大数据量。
    :type _flush_size: int
    :ivar _flush_interval: 刷新间隔时间（秒），即任务检查队列的时间间隔。
    :type _flush_interval: int
    :ivar _active: 控制类是否继续运行的开关。
    :type _active: bool
    :ivar _workers: 刷新任务的协程列表。
    :type _workers: list[asyncio.Task]
    """

    def __init__(self, flush_size: int = 1000, flush_interval: int = 50, max_q=None, flusher_worker=1) -> None:
        self._queue: asyncio.Queue[Any] = asyncio.Queue(maxsize=max_q or flush_size * 10)
        self._flush_size = int(flush_size)
        self._flush_interval = flush_interval
        self._active = True
        self._task: Optional[asyncio.Task[None]] = asyncio.create_task(self._flusher())
        self._task.add_done_callback(self._on_task_done)
        self._workers = [asyncio.create_task(self._flusher()) for _ in range(flusher_worker)]

    # ---------------- 公共接口 ----------------
    async def put(self, obj: Any, block=True) -> None:
        if not self._active:
            raise RuntimeError("PersistBus 已停止，无法再写入")
        try:
            await asyncio.wait_for(self._queue.put(obj), timeout=0.1 if not block else None)
        except asyncio.QueueFull:
            LOGGER.warning("queue full, drop=1")
            raise
        await self._queue.put(obj)

    async def stop(self) -> None:
        """优雅停止：等待队列清空 & 任务结束（5 s 超时）"""
        if not self._active:
            return
        self._active = False
        # 若队列还有残留，让 flusher 再跑一次
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except asyncio.TimeoutError:
                LOGGER.warning("Flusher 停止超时，强制取消")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

    # --------- 上下文管理 (async with) ----------
    async def __aenter__(self):  # noqa: D401
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()

    # ---------------- 内部实现 ----------------
    async def _flush_impl(self, batch: List[Any]) -> None:
        """
        执行内部刷新操作，将批处理中的数据写入目标。

        :param batch: 类型为 ``List[Any]``，表示需要刷新的数据列表。
        :return: 无返回值
        """
        LOGGER.debug("Flushed %d items", len(batch))

    async def _flusher(self) -> None:
        batch: List[Any] = []
        try:
            while self._active or not self._queue.empty():
                try:
                    item = await asyncio.wait_for(self._queue.get(), timeout=self._flush_interval)
                    batch.append(item)
                    if len(batch) >= self._flush_size:
                        await self._flush_impl(batch.copy())
                        LOGGER.debug("flush %d, batch=%d", self._flush_size, batch)
                        batch.clear()
                except asyncio.TimeoutError:
                    if batch:
                        await self._flush_impl(batch.copy())
                        batch.clear()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.error("Flusher 处理异常: %s", exc, exc_info=True)
        except asyncio.CancelledError:
            LOGGER.info("Flusher 任务被取消")
        finally:
            # 结束前把剩余批次写完
            if batch:
                try:
                    await self._flush_impl(batch.copy())
                except Exception as exc:  # noqa: BLE001
                    LOGGER.error("关闭时 flush 剩余批次失败: %s", exc, exc_info=True)

    @staticmethod
    def _on_task_done(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        if (exc := task.exception()) is not None:  # noqa: BLE001
            LOGGER.error("Flusher 退出异常: %s", exc, exc_info=True)
