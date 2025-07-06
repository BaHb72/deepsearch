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

LOGGER = logging.getLogger("deepsearch.persist")


class PersistBus:
    def __init__(self, flush_size: int = 1000, flush_ms: int = 50) -> None:
        self._queue: asyncio.Queue[Any] = asyncio.Queue()
        self._flush_size = int(flush_size)
        self._flush_ms = flush_ms / 1000
        self._active = True
        self._task: Optional[asyncio.Task[None]] = asyncio.create_task(self._flusher())
        self._task.add_done_callback(self._on_task_done)

    # ---------------- 公共接口 ----------------
    async def put(self, obj: Any) -> None:
        if not self._active:
            raise RuntimeError("PersistBus 已停止，无法再写入")
        await self._queue.put(obj)

    async def stop(self) -> None:
        """优雅停止：等待队列清空 & 任务结束（5 s 超时）"""
        if not self._active:
            return
        self._active = False
        # 若队列还有残留，让 flusher 再跑一次
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
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
        真正写缓存 DB / 持久化 DB 的地方。
        子类可 override；此处仅示例打印。
        """
        LOGGER.debug("Flushed %d items", len(batch))

    async def _flusher(self) -> None:
        batch: List[Any] = []
        try:
            while self._active or not self._queue.empty():
                try:
                    item = await asyncio.wait_for(self._queue.get(), timeout=self._flush_ms)
                    batch.append(item)
                    if len(batch) >= self._flush_size:
                        await self._flush_impl(batch)
                        batch.clear()
                except asyncio.TimeoutError:
                    if batch:
                        await self._flush_impl(batch)
                        batch.clear()
                except Exception as exc:  # noqa: BLE001
                    LOGGER.error("Flusher 处理异常: %s", exc, exc_info=True)
        except asyncio.CancelledError:
            LOGGER.info("Flusher 任务被取消")
        finally:
            # 结束前把剩余批次写完
            if batch:
                try:
                    await self._flush_impl(batch)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.error("关闭时 flush 剩余批次失败: %s", exc, exc_info=True)

    @staticmethod
    def _on_task_done(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        if (exc := task.exception()) is not None:  # noqa: BLE001
            LOGGER.error("Flusher 退出异常: %s", exc, exc_info=True)
