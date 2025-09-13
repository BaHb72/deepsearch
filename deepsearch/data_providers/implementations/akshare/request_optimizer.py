"""
请求优化器
实现请求批处理、并发控制和智能调度
"""
import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Callable, Set
from enum import Enum
import hashlib
import json
from loguru import logger


class RequestPriority(Enum):
    """请求优先级"""
    URGENT = 0      # 紧急请求（实时数据）
    HIGH = 1        # 高优先级（用户交互）
    NORMAL = 2      # 正常优先级
    LOW = 3         # 低优先级（后台任务）
    BATCH = 4       # 批量请求（可延迟）


@dataclass
class RequestTask:
    """请求任务"""
    api_name: str
    params: Dict[str, Any]
    priority: RequestPriority = RequestPriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    future: asyncio.Future = field(default_factory=asyncio.Future)
    retry_count: int = 0
    request_id: str = field(default="")
    
    def __post_init__(self):
        if not self.request_id:
            # 生成唯一请求ID
            content = f"{self.api_name}:{json.dumps(self.params, sort_keys=True)}"
            self.request_id = hashlib.md5(content.encode()).hexdigest()[:8]
    
    def __lt__(self, other):
        """比较优先级（用于优先队列）"""
        if self.priority != other.priority:
            return self.priority.value < other.priority.value
        return self.timestamp < other.timestamp


class RequestOptimizer:
    """
    请求优化器
    - 请求批处理：将多个相似请求合并
    - 并发控制：限制同时执行的请求数
    - 智能调度：基于优先级和时间窗口
    - 去重缓存：避免重复请求
    """
    
    def __init__(self, max_concurrent: int = 10, batch_window: float = 0.1):
        """
        初始化请求优化器
        
        Args:
            max_concurrent: 最大并发请求数
            batch_window: 批处理时间窗口（秒）
        """
        self.max_concurrent = max_concurrent
        self.batch_window = batch_window
        
        # 请求队列（按优先级）
        self.request_queue: List[RequestTask] = []
        self.queue_lock = asyncio.Lock()
        
        # 执行中的请求
        self.executing: Dict[str, RequestTask] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # 批处理缓冲区
        self.batch_buffer: Dict[str, List[RequestTask]] = defaultdict(list)
        self.batch_timers: Dict[str, asyncio.Task] = {}
        
        # 请求去重缓存（request_id -> result）
        self.dedup_cache: Dict[str, Tuple[Any, float]] = {}
        self.cache_ttl = 60  # 缓存TTL（秒）
        
        # 统计信息
        self.stats = {
            "total_requests": 0,
            "batched_requests": 0,
            "cache_hits": 0,
            "concurrent_peak": 0,
            "failed_requests": 0,
            "avg_wait_time": 0,
            "avg_exec_time": 0
        }
        
        # 请求执行器（由外部设置）
        self.executor: Optional[Callable] = None
        
        # 后台清理任务
        self.cleanup_task = None
        self.running = False
    
    async def start(self):
        """启动优化器"""
        self.running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_cache())
        logger.info(f"请求优化器已启动: 最大并发={self.max_concurrent}, 批处理窗口={self.batch_window}秒")
    
    async def stop(self):
        """停止优化器"""
        self.running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 取消所有批处理定时器
        for timer in self.batch_timers.values():
            timer.cancel()
        
        logger.info(f"请求优化器已停止. 统计: {self.stats}")
    
    async def submit(
        self, 
        api_name: str, 
        params: Dict[str, Any],
        priority: RequestPriority = RequestPriority.NORMAL,
        use_cache: bool = True
    ) -> Any:
        """
        提交请求
        
        Args:
            api_name: API名称
            params: 请求参数
            priority: 优先级
            use_cache: 是否使用去重缓存
        
        Returns:
            API响应结果
        """
        self.stats["total_requests"] += 1
        
        # 创建请求任务
        task = RequestTask(
            api_name=api_name,
            params=params,
            priority=priority
        )
        
        # 检查去重缓存
        if use_cache and task.request_id in self.dedup_cache:
            result, cache_time = self.dedup_cache[task.request_id]
            if time.time() - cache_time < self.cache_ttl:
                self.stats["cache_hits"] += 1
                logger.debug(f"请求命中缓存: {api_name} [{task.request_id}]")
                return result
            else:
                # 缓存过期，删除
                del self.dedup_cache[task.request_id]
        
        # 根据优先级决定处理策略
        if priority == RequestPriority.URGENT:
            # 紧急请求直接执行
            return await self._execute_immediate(task)
        elif priority == RequestPriority.BATCH:
            # 批量请求进入批处理
            return await self._add_to_batch(task)
        else:
            # 普通请求进入队列
            return await self._add_to_queue(task)
    
    async def _execute_immediate(self, task: RequestTask) -> Any:
        """立即执行请求（用于紧急请求）"""
        async with self.semaphore:
            return await self._execute_task(task)
    
    async def _add_to_queue(self, task: RequestTask) -> Any:
        """添加到优先级队列"""
        async with self.queue_lock:
            # 插入到合适位置（保持优先级顺序）
            inserted = False
            for i, existing in enumerate(self.request_queue):
                if task < existing:
                    self.request_queue.insert(i, task)
                    inserted = True
                    break
            if not inserted:
                self.request_queue.append(task)
        
        # 触发处理
        asyncio.create_task(self._process_queue())
        
        # 等待结果
        return await task.future
    
    async def _add_to_batch(self, task: RequestTask) -> Any:
        """添加到批处理缓冲区"""
        api_name = task.api_name
        
        # 添加到缓冲区
        self.batch_buffer[api_name].append(task)
        self.stats["batched_requests"] += 1
        
        # 如果没有定时器，创建一个
        if api_name not in self.batch_timers:
            self.batch_timers[api_name] = asyncio.create_task(
                self._batch_timer(api_name)
            )
        
        # 等待结果
        return await task.future
    
    async def _batch_timer(self, api_name: str):
        """批处理定时器"""
        await asyncio.sleep(self.batch_window)
        
        # 时间到，执行批处理
        if api_name in self.batch_buffer:
            tasks = self.batch_buffer.pop(api_name)
            del self.batch_timers[api_name]
            
            if tasks:
                await self._execute_batch(api_name, tasks)
    
    async def _execute_batch(self, api_name: str, tasks: List[RequestTask]):
        """执行批处理请求"""
        if not tasks:
            return
        
        logger.debug(f"执行批处理: {api_name}, {len(tasks)}个请求")
        
        # 合并参数（这里需要根据具体API定制）
        merged_params = self._merge_params(api_name, [t.params for t in tasks])
        
        try:
            # 执行合并后的请求
            async with self.semaphore:
                if self.executor:
                    result = await self.executor(api_name, merged_params)
                else:
                    raise RuntimeError("未设置请求执行器")
            
            # 分发结果
            self._distribute_batch_results(tasks, result)
            
        except Exception as e:
            # 批处理失败，回退到单独执行
            logger.warning(f"批处理失败，回退到单独执行: {e}")
            for task in tasks:
                asyncio.create_task(self._execute_immediate(task))
    
    async def _process_queue(self):
        """处理请求队列"""
        while self.request_queue:
            # 检查并发限制
            if len(self.executing) >= self.max_concurrent:
                await asyncio.sleep(0.01)
                continue
            
            async with self.queue_lock:
                if not self.request_queue:
                    break
                task = self.request_queue.pop(0)
            
            # 异步执行
            asyncio.create_task(self._execute_with_semaphore(task))
        
        # 更新峰值并发数
        current_concurrent = len(self.executing)
        if current_concurrent > self.stats["concurrent_peak"]:
            self.stats["concurrent_peak"] = current_concurrent
    
    async def _execute_with_semaphore(self, task: RequestTask):
        """使用信号量控制的执行"""
        async with self.semaphore:
            await self._execute_task(task)
    
    async def _execute_task(self, task: RequestTask):
        """执行单个任务"""
        start_time = time.time()
        self.executing[task.request_id] = task
        
        try:
            if self.executor:
                result = await self.executor(task.api_name, task.params)
                
                # 更新缓存
                self.dedup_cache[task.request_id] = (result, time.time())
                
                # 设置结果
                if not task.future.done():
                    task.future.set_result(result)
                
                # 更新统计
                exec_time = time.time() - start_time
                self.stats["avg_exec_time"] = (
                    self.stats["avg_exec_time"] * 0.9 + exec_time * 0.1
                )
                
            else:
                raise RuntimeError("未设置请求执行器")
                
        except Exception as e:
            self.stats["failed_requests"] += 1
            logger.error(f"执行请求失败 {task.api_name}: {e}")
            if not task.future.done():
                task.future.set_exception(e)
        
        finally:
            if task.request_id in self.executing:
                del self.executing[task.request_id]
    
    def _merge_params(self, api_name: str, params_list: List[Dict]) -> Dict:
        """
        合并请求参数
        TODO: 根据不同API实现具体的合并逻辑
        """
        if not params_list:
            return {}
        
        # 对于股票列表类API，可以合并代码列表
        if "stock" in api_name and "codes" in params_list[0]:
            merged_codes = set()
            for params in params_list:
                if "codes" in params:
                    codes = params["codes"]
                    if isinstance(codes, list):
                        merged_codes.update(codes)
                    else:
                        merged_codes.add(codes)
            return {**params_list[0], "codes": list(merged_codes)}
        
        # 默认返回第一个参数
        return params_list[0]
    
    def _distribute_batch_results(self, tasks: List[RequestTask], result: Any):
        """
        分发批处理结果
        TODO: 根据不同API实现具体的分发逻辑
        """
        # 简单分发：所有任务获得相同结果
        for task in tasks:
            if not task.future.done():
                task.future.set_result(result)
    
    async def _cleanup_cache(self):
        """定期清理过期缓存"""
        while self.running:
            try:
                await asyncio.sleep(60)  # 每分钟清理一次
                
                now = time.time()
                expired = []
                
                for request_id, (_, cache_time) in self.dedup_cache.items():
                    if now - cache_time > self.cache_ttl:
                        expired.append(request_id)
                
                for request_id in expired:
                    del self.dedup_cache[request_id]
                
                if expired:
                    logger.debug(f"清理了 {len(expired)} 个过期缓存")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理缓存时出错: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "queue_length": len(self.request_queue),
            "executing": len(self.executing),
            "cache_size": len(self.dedup_cache),
            "batch_buffer_size": sum(len(tasks) for tasks in self.batch_buffer.values())
        }