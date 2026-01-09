"""
批量请求处理器

将零散请求合并为批量执行，提升吞吐效率
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import (
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Sequence,
    TypedDict,
    TypeVar,
    Union,
    cast,
)

from loguru import logger

T = TypeVar("T")
R = TypeVar("R")
ProcessorResult = Union[Sequence[R], R]
BatchProcessor = Callable[[List[T]], Awaitable[ProcessorResult]]


class BatchStats(TypedDict):
    total_requests: int
    total_batches: int
    successful_batches: int
    failed_batches: int
    average_batch_size: float
    total_processing_time: float


class BatchReport(BatchStats):
    pending_requests: int
    success_rate: float
    average_processing_time: float


class MultiKeyBatchReport(TypedDict):
    total_requests: int
    total_batches: int
    successful_batches: int
    failed_batches: int
    by_key: Dict[str, BatchReport]


class BatchStatus(Enum):
    """批处理状态"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BatchRequest(Generic[T, R]):
    """批处理单元"""

    id: str
    data: T
    future: asyncio.Future[R]
    timestamp: Optional[float] = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = time.time()


def _create_stats() -> BatchStats:
    return {
        "total_requests": 0,
        "total_batches": 0,
        "successful_batches": 0,
        "failed_batches": 0,
        "average_batch_size": 0.0,
        "total_processing_time": 0.0,
    }


class RequestBatcher(Generic[T, R]):
    """
    批量请求调度器

    能力：
    - 自动合并短时间内的请求
    - 支持最大批次与超时控制
    - 兼容异步处理器
    - 持续输出统计指标
    """

    def __init__(
        self,
        batch_processor: BatchProcessor,
        batch_size: int = 20,
        batch_timeout: float = 0.1,
        max_queue_size: int = 1000,
    ) -> None:
        self.batch_processor = batch_processor
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_queue_size = max_queue_size

        self.pending_requests: List[BatchRequest[T, R]] = []
        self._lock = asyncio.Lock()
        self._timer_task: Optional[asyncio.Task[None]] = None
        self._processing = False

        self.stats: BatchStats = _create_stats()

    async def add_request(self, request_data: T) -> R:
        """提交单个请求并等待结果"""

        loop = asyncio.get_running_loop()
        future = cast(asyncio.Future[R], loop.create_future())

        async with self._lock:
            if len(self.pending_requests) >= self.max_queue_size:
                raise RuntimeError(f"请求数量超过限制 (max={self.max_queue_size})")

            request = BatchRequest(
                id=f"{time.time()}_{len(self.pending_requests)}",
                data=request_data,
                future=future,
            )
            self.pending_requests.append(request)
            self.stats["total_requests"] += 1

            if len(self.pending_requests) >= self.batch_size:
                asyncio.create_task(self._flush_batch())
            elif not self._timer_task or self._timer_task.done():
                self._timer_task = cast(
                    asyncio.Task[None], asyncio.create_task(self._schedule_flush())
                )

        try:
            result = await future
            return result
        except asyncio.CancelledError:
            if not future.cancelled():
                future.cancel()
            raise

    async def _schedule_flush(self) -> None:
        await asyncio.sleep(self.batch_timeout)
        await self._flush_batch()

    async def _flush_batch(self) -> None:
        async with self._lock:
            if self._processing or not self.pending_requests:
                return
            self._processing = True
            batch = self.pending_requests[: self.batch_size]
            self.pending_requests = self.pending_requests[self.batch_size :]
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()

        try:
            await self._process_batch(batch)
        finally:
            async with self._lock:
                self._processing = False
                if self.pending_requests and (not self._timer_task or self._timer_task.done()):
                    self._timer_task = cast(
                        asyncio.Task[None], asyncio.create_task(self._schedule_flush())
                    )

    async def _process_batch(self, batch: List[BatchRequest[T, R]]) -> None:
        start_time = time.time()
        batch_data = [req.data for req in batch]

        logger.debug(f"开始处理批量请求: {len(batch)} 条")

        try:
            results = await self.batch_processor(batch_data)
            self._resolve_results(batch, results)
            self.stats["successful_batches"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.error(f"批处理失败: {exc}")
            for req in batch:
                if not req.future.done():
                    req.future.set_exception(exc)
            self.stats["failed_batches"] += 1
        finally:
            elapsed = time.time() - start_time
            self.stats["total_batches"] += 1
            self.stats["total_processing_time"] += elapsed
            if self.stats["total_batches"] > 0:
                self.stats["average_batch_size"] = (
                    self.stats["total_requests"] / self.stats["total_batches"]
                )
            logger.debug(f"批量处理完成: {len(batch)} 条, 耗时: {elapsed:.3f}s")

    def _resolve_results(self, batch: List[BatchRequest[T, R]], results: ProcessorResult) -> None:
        if isinstance(results, Sequence) and not isinstance(results, (str, bytes, bytearray)):
            if len(results) == len(batch):
                for req, result in zip(batch, results):
                    if not req.future.done():
                        req.future.set_result(cast(R, result))
                return
        for req in batch:
            if not req.future.done():
                req.future.set_result(cast(R, results))

    def get_stats(self) -> BatchReport:
        report: BatchReport = {
            "total_requests": self.stats["total_requests"],
            "total_batches": self.stats["total_batches"],
            "successful_batches": self.stats["successful_batches"],
            "failed_batches": self.stats["failed_batches"],
            "average_batch_size": self.stats["average_batch_size"],
            "total_processing_time": self.stats["total_processing_time"],
            "pending_requests": len(self.pending_requests),
            "success_rate": (
                (self.stats["successful_batches"] / self.stats["total_batches"]) * 100
                if self.stats["total_batches"]
                else 0.0
            ),
            "average_processing_time": (
                self.stats["total_processing_time"] / self.stats["total_batches"]
                if self.stats["total_batches"]
                else 0.0
            ),
        }
        return report

    async def flush_all(self) -> None:
        while self.pending_requests:
            await self._flush_batch()

    async def clear(self) -> None:
        async with self._lock:
            for req in self.pending_requests:
                if not req.future.done():
                    req.future.cancel()
            self.pending_requests.clear()
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()
        logger.info("批量缓冲已清空")


class MultiKeyBatcher(Generic[T, R]):
    """多键批处理器，支持按 key 维度构建独立批次"""

    def __init__(
        self,
        batch_processor: Callable[[str, List[T]], Awaitable[ProcessorResult]],
        batch_size: int = 20,
        batch_timeout: float = 0.1,
    ) -> None:
        self.batch_processor = batch_processor
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.batchers: Dict[str, RequestBatcher[T, R]] = {}
        self._lock = asyncio.Lock()

    async def add_request(self, key: str, request_data: T) -> R:
        async with self._lock:
            if key not in self.batchers:

                async def processor(payload: List[T]) -> ProcessorResult:
                    return await self.batch_processor(key, payload)

                self.batchers[key] = RequestBatcher[T, R](
                    batch_processor=processor,
                    batch_size=self.batch_size,
                    batch_timeout=self.batch_timeout,
                )
        return await self.batchers[key].add_request(request_data)

    def get_stats(self) -> MultiKeyBatchReport:
        aggregated: MultiKeyBatchReport = {
            "total_requests": 0,
            "total_batches": 0,
            "successful_batches": 0,
            "failed_batches": 0,
            "by_key": cast(Dict[str, BatchReport], {}),
        }
        for key, batcher in self.batchers.items():
            report = batcher.get_stats()
            aggregated["by_key"][key] = report
            aggregated["total_requests"] += report["total_requests"]
            aggregated["total_batches"] += report["total_batches"]
            aggregated["successful_batches"] += report["successful_batches"]
            aggregated["failed_batches"] += report["failed_batches"]
        return aggregated

    async def flush_all(self) -> None:
        tasks = [batcher.flush_all() for batcher in self.batchers.values()]
        if tasks:
            await asyncio.gather(*tasks)

    async def clear_all(self) -> None:
        tasks = [batcher.clear() for batcher in self.batchers.values()]
        if tasks:
            await asyncio.gather(*tasks)
        self.batchers.clear()
