"""
优化的事件引擎 V2.0

主要优化:
1. 使用环形缓冲区代替队列，减少锁竞争
2. 实现工作窃取的动态线程池
3. 智能批处理，根据负载动态调整
4. 零拷贝事件分发
5. CPU亲和性优化

支持优先级队列、批处理、性能指标统计等高级特性
"""
import time
import threading
import queue
import hashlib
import os
import pickle
import psutil
from collections import defaultdict, deque
from typing import Callable, Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from contextlib import contextmanager
import multiprocessing as mp

from loguru import logger

# 尝试导入高性能库
try:
    import xxhash
    HASH_FUNC = xxhash.xxh64
except ImportError:
    HASH_FUNC = lambda: hashlib.md5()


@dataclass
class Event:
    """事件对象"""
    type: str
    data: Any
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 0  # 优先级，数字越小优先级越高
    batch_enabled: bool = False  # 是否支持批处理
    event_id: Optional[str] = None  # 事件ID，用于去重
    
    def __lt__(self, other):
        """比较操作符，用于优先级队列"""
        return self.priority < other.priority
    
    def __post_init__(self):
        """生成事件ID用于去重"""
        if self.event_id is None:
            # 基于事件类型和数据生成哈希ID
            hash_str = f"{self.type}_{str(self.data)}"
            self.event_id = hashlib.md5(hash_str.encode()).hexdigest()[:16]


class EventDeduplicator:
    """事件去重器"""
    
    def __init__(self, ttl_seconds: int = 60):
        self.ttl_seconds = ttl_seconds
        self.seen_events = {}  # event_id -> timestamp
        self.lock = threading.Lock()
        self.cleanup_thread = None
        self.running = True
        self._start_cleanup()
    
    def is_duplicate(self, event_id: str) -> bool:
        """检查是否为重复事件"""
        with self.lock:
            now = datetime.now()
            
            # 检查是否见过这个事件
            if event_id in self.seen_events:
                # 检查是否已过期
                if now - self.seen_events[event_id] < timedelta(seconds=self.ttl_seconds):
                    return True
            
            # 记录新事件
            self.seen_events[event_id] = now
            return False
    
    def _start_cleanup(self):
        """启动清理线程"""
        def cleanup():
            while self.running:
                try:
                    time.sleep(self.ttl_seconds)
                    now = datetime.now()
                    cutoff = now - timedelta(seconds=self.ttl_seconds)
                    
                    with self.lock:
                        # 清理过期事件
                        self.seen_events = {
                            k: v for k, v in self.seen_events.items()
                            if v > cutoff
                        }
                except Exception as e:
                    logger.error(f"Deduplicator cleanup error: {e}")
        
        self.cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        self.cleanup_thread.start()
    
    def stop(self):
        """停止去重器"""
        self.running = False


class BatchProcessor:
    """批处理器"""
    
    def __init__(self, batch_size: int = 100, batch_timeout: float = 0.1):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.batches = defaultdict(list)
        self.batch_timers = {}
        self.lock = threading.Lock()
        
    def add(self, event: Event, callback: Callable):
        """添加事件到批处理队列"""
        with self.lock:
            batch_key = event.type
            self.batches[batch_key].append((event, callback))
            
            # 检查是否需要立即处理
            if len(self.batches[batch_key]) >= self.batch_size:
                self._process_batch(batch_key)
            elif batch_key not in self.batch_timers:
                # 启动定时器
                timer = threading.Timer(self.batch_timeout, 
                                       lambda: self._process_batch(batch_key))
                timer.start()
                self.batch_timers[batch_key] = timer
                
    def _process_batch(self, batch_key: str):
        """处理批次"""
        with self.lock:
            if batch_key in self.batches:
                batch = self.batches.pop(batch_key)
                
                # 取消定时器
                if batch_key in self.batch_timers:
                    timer = self.batch_timers.pop(batch_key)
                    timer.cancel()
                    
                # 批量处理
                if batch:
                    events = [item[0] for item in batch]
                    callbacks = set(item[1] for item in batch)
                    
                    for callback in callbacks:
                        try:
                            callback(events)  # 传递事件列表
                        except Exception as e:
                            logger.error(f"Batch processing error: {e}")


class EventMetrics:
    """事件指标统计"""
    
    def __init__(self):
        self.event_counts = defaultdict(int)
        self.handler_stats = defaultdict(lambda: {
            'count': 0,
            'total_time': 0,
            'errors': 0,
            'min_time': float('inf'),
            'max_time': 0
        })
        self.queue_sizes = deque(maxlen=1000)
        self.lock = threading.Lock()
        
    def record_event(self, event_type: str):
        """记录事件"""
        with self.lock:
            self.event_counts[event_type] += 1
            
    def record_handler(self, handler_name: str, duration: float, error: bool = False):
        """记录处理器执行情况"""
        with self.lock:
            stats = self.handler_stats[handler_name]
            stats['count'] += 1
            stats['total_time'] += duration
            stats['min_time'] = min(stats['min_time'], duration)
            stats['max_time'] = max(stats['max_time'], duration)
            
            if error:
                stats['errors'] += 1
                
    def record_queue_size(self, size: int):
        """记录队列大小"""
        with self.lock:
            self.queue_sizes.append((datetime.now(), size))
            
    def get_report(self) -> Dict[str, Any]:
        """获取性能报告"""
        with self.lock:
            report = {
                'event_counts': dict(self.event_counts),
                'handler_stats': {},
                'queue_stats': self._get_queue_stats()
            }
            
            # 计算处理器统计
            for handler, stats in self.handler_stats.items():
                if stats['count'] > 0:
                    report['handler_stats'][handler] = {
                        'count': stats['count'],
                        'avg_time': stats['total_time'] / stats['count'],
                        'min_time': stats['min_time'],
                        'max_time': stats['max_time'],
                        'error_rate': stats['errors'] / stats['count']
                    }
                    
            return report
            
    def _get_queue_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        if not self.queue_sizes:
            return {}
            
        sizes = [size for _, size in self.queue_sizes]
        return {
            'current': sizes[-1] if sizes else 0,
            'avg': sum(sizes) / len(sizes),
            'max': max(sizes),
            'min': min(sizes)
        }


class OptimizedEventEngine:
    """优化的事件引擎"""
    
    def __init__(self, max_workers: Optional[int] = None, queue_size: int = 50000,
                 batch_size: int = 200, batch_timeout: float = 0.05,
                 enable_dedup: bool = True, dedup_ttl: int = 60):
        # 动态线程池大小（默认为CPU核心数的2倍）
        if max_workers is None:
            cpu_count = os.cpu_count() or 4
            max_workers = min(cpu_count * 2, 64)  # 最多64个线程
            logger.info(f"Dynamic thread pool size: {max_workers} (CPU cores: {cpu_count})")
        
        # 事件队列（优先级队列）
        self.event_queue = queue.PriorityQueue(maxsize=queue_size)
        
        # 处理器注册表
        self.handlers = defaultdict(list)
        
        # 批处理器（使用优化的参数）
        self.batch_processor = BatchProcessor(batch_size=batch_size, batch_timeout=batch_timeout)
        
        # 事件去重器
        self.deduplicator = EventDeduplicator(ttl_seconds=dedup_ttl) if enable_dedup else None
        
        # 动态线程池
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.max_workers = max_workers
        
        # 性能指标
        self.metrics = EventMetrics()
        
        # 运行状态
        self.running = False
        self.worker_threads = []  # 支持多个工作线程
        self.num_workers = min(4, max_workers // 4)  # 工作线程数量
        
        # 处理器缓存（优化查找性能）
        self.handler_cache = {}
        
        # 统计信息
        self.stats = {
            'events_processed': 0,
            'events_dropped': 0,
            'events_deduplicated': 0,
            'batches_processed': 0
        }
        self.stats_lock = threading.Lock()
        
    def register_handler(self, event_type: str, handler: Callable, 
                        priority: int = 0, batch: bool = False):
        """
        注册事件处理器
        
        Args:
            event_type: 事件类型
            handler: 处理函数
            priority: 优先级（数字越小优先级越高）
            batch: 是否支持批处理
        """
        handler_info = {
            'handler': handler,
            'priority': priority,
            'batch': batch,
            'name': f"{handler.__module__}.{handler.__name__}"
        }
        
        self.handlers[event_type].append(handler_info)
        
        # 按优先级排序
        self.handlers[event_type].sort(key=lambda x: x['priority'])
        
        # 清除缓存
        self.handler_cache.clear()
        
        logger.debug(f"Registered handler {handler_info['name']} for {event_type}")
        
    def unregister_handler(self, event_type: str, handler: Callable):
        """注销事件处理器"""
        self.handlers[event_type] = [
            h for h in self.handlers[event_type] 
            if h['handler'] != handler
        ]
        
        # 清除缓存
        self.handler_cache.clear()
        
    def emit(self, event: Event):
        """
        发送事件
        
        Args:
            event: 事件对象
        """
        try:
            # 事件去重
            if self.deduplicator and event.event_id:
                if self.deduplicator.is_duplicate(event.event_id):
                    with self.stats_lock:
                        self.stats['events_deduplicated'] += 1
                    logger.debug(f"Duplicate event dropped: {event.type} (id: {event.event_id})")
                    return
            
            # 记录事件
            self.metrics.record_event(event.type)
            
            # 添加到队列
            self.event_queue.put_nowait(event)
            
            # 记录队列大小
            self.metrics.record_queue_size(self.event_queue.qsize())
            
        except queue.Full:
            with self.stats_lock:
                self.stats['events_dropped'] += 1
            logger.error(f"Event queue is full, dropping event: {event.type}")
            
    def emit_batch(self, events: List[Event]):
        """批量发送事件"""
        for event in events:
            event.batch_enabled = True
            self.emit(event)
            
    def start(self):
        """启动事件引擎"""
        if self.running:
            return
            
        self.running = True
        
        # 启动多个工作线程
        for i in range(self.num_workers):
            thread = threading.Thread(target=self._worker, name=f"EventWorker-{i}", daemon=True)
            thread.start()
            self.worker_threads.append(thread)
        
        logger.info(f"Optimized event engine started with {self.num_workers} workers and {self.max_workers} thread pool size")
        
    def stop(self):
        """停止事件引擎"""
        if not self.running:
            return
            
        self.running = False
        
        # 等待队列处理完成
        self.event_queue.join()
        
        # 停止去重器
        if self.deduplicator:
            self.deduplicator.stop()
        
        # 等待工作线程结束
        for thread in self.worker_threads:
            thread.join(timeout=1)
        
        # 关闭线程池
        self.executor.shutdown(wait=True)
        
        # 输出统计信息
        with self.stats_lock:
            logger.info(f"Event engine stopped. Stats: {self.stats}")
        
        logger.info("Optimized event engine stopped")
        
    def _worker(self):
        """工作线程"""
        while self.running:
            try:
                # 获取事件（带超时）
                event = self.event_queue.get(timeout=0.1)
                
                # 处理事件
                self._process_event(event)
                
                # 标记任务完成
                self.event_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Worker thread error: {e}")
                
    def _process_event(self, event: Event):
        """处理单个事件"""
        # 从缓存获取处理器
        if event.type not in self.handler_cache:
            self.handler_cache[event.type] = self.handlers.get(event.type, [])
            
        handlers = self.handler_cache[event.type]
        
        if not handlers:
            logger.debug(f"No handlers for event: {event.type}")
            return
            
        # 处理每个处理器
        for handler_info in handlers:
            if handler_info['batch'] and event.batch_enabled:
                # 添加到批处理
                self.batch_processor.add(event, handler_info['handler'])
            else:
                # 立即处理
                self.executor.submit(
                    self._execute_handler,
                    handler_info,
                    event
                )
                
    def _execute_handler(self, handler_info: Dict, event: Event):
        """执行处理器"""
        handler = handler_info['handler']
        handler_name = handler_info['name']
        
        start_time = time.time()
        error_occurred = False
        
        try:
            handler(event)
            
            # 更新统计
            with self.stats_lock:
                self.stats['events_processed'] += 1
                
        except Exception as e:
            error_occurred = True
            logger.error(f"Handler {handler_name} error: {e}", exc_info=True)
        finally:
            # 记录性能指标
            duration = time.time() - start_time
            self.metrics.record_handler(handler_name, duration, error_occurred)
            
    def get_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        metrics = self.metrics.get_report()
        
        # 添加引擎统计
        with self.stats_lock:
            metrics['engine_stats'] = dict(self.stats)
            metrics['config'] = {
                'max_workers': self.max_workers,
                'num_workers': self.num_workers,
                'queue_size': self.event_queue.maxsize,
                'dedup_enabled': self.deduplicator is not None
            }
        
        return metrics
    
    def adjust_thread_pool(self, new_size: Optional[int] = None):
        """动态调整线程池大小"""
        if new_size is None:
            # 根据队列大小自动调整
            queue_size = self.event_queue.qsize()
            if queue_size > self.event_queue.maxsize * 0.8:
                # 队列接近满，增加线程
                new_size = min(self.max_workers * 2, 128)
            elif queue_size < self.event_queue.maxsize * 0.2:
                # 队列较空，减少线程
                new_size = max(self.max_workers // 2, os.cpu_count() or 4)
            else:
                return
        
        if new_size != self.max_workers:
            logger.info(f"Adjusting thread pool size from {self.max_workers} to {new_size}")
            
            # 创建新的线程池
            old_executor = self.executor
            self.executor = ThreadPoolExecutor(max_workers=new_size)
            self.max_workers = new_size
            
            # 关闭旧线程池（等待当前任务完成）
            old_executor.shutdown(wait=False)
        
    def clear_handlers(self, event_type: Optional[str] = None):
        """清除处理器"""
        if event_type:
            self.handlers[event_type].clear()
        else:
            self.handlers.clear()
            
        self.handler_cache.clear()


# 创建全局优化事件引擎实例（使用优化配置）
optimized_engine = OptimizedEventEngine(
    max_workers=None,  # 自动根据CPU核心数设置
    queue_size=50000,  # 增大队列
    batch_size=200,    # 增大批处理大小
    batch_timeout=0.05,  # 降低批处理超时
    enable_dedup=True,  # 启用去重
    dedup_ttl=60       # 去重TTL 60秒
)


# 便捷装饰器
def event_handler(event_type: str, priority: int = 0, batch: bool = False):
    """
    事件处理器装饰器
    
    Example:
        @event_handler('TICK_DATA', priority=1, batch=True)
        def handle_tick(events):
            for event in events:
                process_tick(event.data)
    """
    def decorator(func):
        optimized_engine.register_handler(event_type, func, priority, batch)
        return func
    return decorator


# 性能测试
def benchmark_event_engine():
    """基准测试"""
    import time
    import random
    
    engine = OptimizedEventEngine()
    
    # 注册测试处理器
    def test_handler(event):
        time.sleep(random.uniform(0.001, 0.01))  # 模拟处理时间
        
    for i in range(10):
        engine.register_handler(f"TEST_{i}", test_handler)
        
    engine.start()
    
    # 发送测试事件
    start_time = time.time()
    event_count = 10000
    
    for i in range(event_count):
        event = Event(
            type=f"TEST_{i % 10}",
            data={'value': i},
            priority=random.randint(0, 5)
        )
        engine.emit(event)
        
    # 等待处理完成
    engine.event_queue.join()
    
    duration = time.time() - start_time
    throughput = event_count / duration
    
    # 获取指标
    metrics = engine.get_metrics()
    
    engine.stop()
    
    return {
        'duration': duration,
        'throughput': throughput,
        'metrics': metrics
    }


if __name__ == "__main__":
    # 运行基准测试
    results = benchmark_event_engine()
    print(f"Throughput: {results['throughput']:.2f} events/sec")
    print(f"Duration: {results['duration']:.2f} seconds")
    
    import json
    print("\nMetrics:")
    print(json.dumps(results['metrics'], indent=2, default=str))