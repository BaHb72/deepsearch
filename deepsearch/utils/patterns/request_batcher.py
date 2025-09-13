"""
请求批处理器

将多个请求合并为批量请求，提高处理效率
"""
import asyncio
import time
from typing import List, Dict, Any, Callable, Optional, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum
from loguru import logger

T = TypeVar('T')


class BatchStatus(Enum):
    """批处理状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class BatchRequest(Generic[T]):
    """批处理请求"""
    id: str
    data: T
    future: asyncio.Future
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class RequestBatcher(Generic[T]):
    """
    请求批处理器
    
    特性：
    - 自动合并相近时间的请求
    - 支持批量大小和超时控制
    - 异步处理和结果分发
    - 错误隔离和重试
    """
    
    def __init__(
        self,
        batch_processor: Callable[[List[T]], Any],
        batch_size: int = 20,
        batch_timeout: float = 0.1,
        max_queue_size: int = 1000
    ):
        """
        初始化批处理器
        
        Args:
            batch_processor: 批处理函数
            batch_size: 批量大小
            batch_timeout: 批处理超时（秒）
            max_queue_size: 最大队列大小
        """
        self.batch_processor = batch_processor
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_queue_size = max_queue_size
        
        # 请求队列
        self.pending_requests: List[BatchRequest] = []
        self._lock = asyncio.Lock()
        self._timer_task = None
        self._processing = False
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'total_batches': 0,
            'successful_batches': 0,
            'failed_batches': 0,
            'average_batch_size': 0,
            'total_processing_time': 0
        }
    
    async def add_request(self, request_data: T) -> Any:
        """
        添加请求到批处理队列
        
        Args:
            request_data: 请求数据
            
        Returns:
            处理结果
        """
        # 创建Future用于返回结果
        future = asyncio.Future()
        
        async with self._lock:
            # 检查队列大小
            if len(self.pending_requests) >= self.max_queue_size:
                raise RuntimeError(f"批处理队列已满 (max={self.max_queue_size})")
            
            # 创建批处理请求
            request = BatchRequest(
                id=f"{time.time()}_{len(self.pending_requests)}",
                data=request_data,
                future=future
            )
            
            self.pending_requests.append(request)
            self.stats['total_requests'] += 1
            
            # 检查是否需要立即处理
            if len(self.pending_requests) >= self.batch_size:
                # 达到批量大小，立即处理
                asyncio.create_task(self._flush_batch())
            elif not self._timer_task or self._timer_task.done():
                # 启动定时器
                self._timer_task = asyncio.create_task(self._timeout_flush())
        
        # 等待结果
        try:
            result = await future
            return result
        except Exception as e:
            logger.error(f"批处理请求失败: {e}")
            raise
    
    async def _timeout_flush(self):
        """超时刷新批处理"""
        await asyncio.sleep(self.batch_timeout)
        await self._flush_batch()
    
    async def _flush_batch(self):
        """刷新批处理队列"""
        async with self._lock:
            if not self.pending_requests or self._processing:
                return
            
            # 取出待处理的请求
            batch = self.pending_requests[:self.batch_size]
            self.pending_requests = self.pending_requests[self.batch_size:]
            
            # 标记为处理中
            self._processing = True
            
            # 取消定时器
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()
        
        # 执行批处理（在锁外执行，避免阻塞）
        await self._process_batch(batch)
        
        # 处理完成
        async with self._lock:
            self._processing = False
            
            # 如果还有待处理的请求，继续处理
            if self.pending_requests:
                asyncio.create_task(self._flush_batch())
    
    async def _process_batch(self, batch: List[BatchRequest]):
        """
        处理批量请求
        
        Args:
            batch: 批处理请求列表
        """
        if not batch:
            return
        
        start_time = time.time()
        batch_data = [req.data for req in batch]
        
        logger.debug(f"处理批量请求: {len(batch)} 个")
        
        try:
            # 调用批处理函数
            results = await self.batch_processor(batch_data)
            
            # 分发结果
            if isinstance(results, list) and len(results) == len(batch):
                # 结果是列表，按顺序分发
                for req, result in zip(batch, results):
                    if not req.future.done():
                        req.future.set_result(result)
            else:
                # 结果是单个值，分发给所有请求
                for req in batch:
                    if not req.future.done():
                        req.future.set_result(results)
            
            # 更新统计
            self.stats['successful_batches'] += 1
            
        except Exception as e:
            logger.error(f"批处理失败: {e}")
            
            # 将错误传递给所有请求
            for req in batch:
                if not req.future.done():
                    req.future.set_exception(e)
            
            self.stats['failed_batches'] += 1
        
        finally:
            # 更新统计
            elapsed = time.time() - start_time
            self.stats['total_batches'] += 1
            self.stats['total_processing_time'] += elapsed
            
            # 计算平均批量大小
            if self.stats['total_batches'] > 0:
                self.stats['average_batch_size'] = (
                    self.stats['total_requests'] / self.stats['total_batches']
                )
            
            logger.debug(f"批处理完成: {len(batch)} 个请求, 耗时: {elapsed:.3f}s")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        stats['pending_requests'] = len(self.pending_requests)
        stats['success_rate'] = (
            self.stats['successful_batches'] / max(self.stats['total_batches'], 1)
        ) * 100
        
        if self.stats['total_batches'] > 0:
            stats['average_processing_time'] = (
                self.stats['total_processing_time'] / self.stats['total_batches']
            )
        else:
            stats['average_processing_time'] = 0
        
        return stats
    
    async def flush_all(self):
        """强制刷新所有待处理的请求"""
        while self.pending_requests:
            await self._flush_batch()
    
    async def clear(self):
        """清空所有待处理的请求"""
        async with self._lock:
            # 取消所有待处理的请求
            for req in self.pending_requests:
                if not req.future.done():
                    req.future.cancel()
            
            self.pending_requests.clear()
            
            # 取消定时器
            if self._timer_task and not self._timer_task.done():
                self._timer_task.cancel()
        
        logger.info("批处理队列已清空")


class MultiKeyBatcher:
    """
    多键批处理器
    
    支持按不同的键分组批处理
    """
    
    def __init__(
        self,
        batch_processor: Callable[[str, List[Any]], Any],
        batch_size: int = 20,
        batch_timeout: float = 0.1
    ):
        """
        初始化多键批处理器
        
        Args:
            batch_processor: 批处理函数，接收键和数据列表
            batch_size: 批量大小
            batch_timeout: 批处理超时
        """
        self.batch_processor = batch_processor
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        
        # 每个键一个批处理器
        self.batchers: Dict[str, RequestBatcher] = {}
        self._lock = asyncio.Lock()
    
    async def add_request(self, key: str, request_data: Any) -> Any:
        """
        添加请求到指定键的批处理器
        
        Args:
            key: 批处理键
            request_data: 请求数据
            
        Returns:
            处理结果
        """
        async with self._lock:
            if key not in self.batchers:
                # 创建新的批处理器
                async def processor(data_list):
                    return await self.batch_processor(key, data_list)
                
                self.batchers[key] = RequestBatcher(
                    batch_processor=processor,
                    batch_size=self.batch_size,
                    batch_timeout=self.batch_timeout
                )
        
        # 添加到对应的批处理器
        return await self.batchers[key].add_request(request_data)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取所有批处理器的统计信息"""
        total_stats = {
            'total_requests': 0,
            'total_batches': 0,
            'successful_batches': 0,
            'failed_batches': 0,
            'by_key': {}
        }
        
        for key, batcher in self.batchers.items():
            stats = batcher.get_stats()
            total_stats['by_key'][key] = stats
            total_stats['total_requests'] += stats['total_requests']
            total_stats['total_batches'] += stats['total_batches']
            total_stats['successful_batches'] += stats['successful_batches']
            total_stats['failed_batches'] += stats['failed_batches']
        
        return total_stats
    
    async def flush_all(self):
        """刷新所有批处理器"""
        tasks = [batcher.flush_all() for batcher in self.batchers.values()]
        if tasks:
            await asyncio.gather(*tasks)
    
    async def clear_all(self):
        """清空所有批处理器"""
        tasks = [batcher.clear() for batcher in self.batchers.values()]
        if tasks:
            await asyncio.gather(*tasks)
        self.batchers.clear()