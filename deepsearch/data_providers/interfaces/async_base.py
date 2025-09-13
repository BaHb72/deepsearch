"""
异步数据提供者基类

提供统一的异步数据访问接口，支持高性能并发访问
"""
import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from datetime import datetime

import aiohttp
from loguru import logger
from pydantic import BaseModel, Field


class DataFormat(Enum):
    """数据格式枚举"""
    JSON = "json"
    PROTOBUF = "protobuf"
    MSGPACK = "msgpack"
    PARQUET = "parquet"


class RequestPriority(Enum):
    """请求优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class DataRequest:
    """统一的数据请求格式"""
    request_id: str
    api_name: str
    params: Dict[str, Any]
    priority: RequestPriority = RequestPriority.NORMAL
    timeout: float = 30.0
    max_retries: int = 3
    cache_enabled: bool = True
    cache_ttl: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


@dataclass
class DataResponse:
    """统一的数据响应格式"""
    request_id: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    source: Optional[str] = None
    latency_ms: float = 0
    cached: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


class AsyncDataProvider(ABC):
    """异步数据提供者基类"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        初始化异步数据提供者
        
        Args:
            name: 提供者名称
            config: 配置参数
        """
        self.name = name
        self.config = config or {}
        
        # 连接池配置
        self.max_connections = self.config.get('max_connections', 100)
        self.max_connections_per_host = self.config.get('max_connections_per_host', 30)
        self.keepalive_timeout = self.config.get('keepalive_timeout', 30)
        
        # 性能配置
        self.batch_size = self.config.get('batch_size', 50)
        self.batch_timeout = self.config.get('batch_timeout', 0.1)
        self.concurrent_limit = self.config.get('concurrent_limit', 20)
        
        # 内部状态
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._batch_queue: List[DataRequest] = []
        self._batch_task: Optional[asyncio.Task] = None
        self._initialized = False
        
        # 统计信息
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'cache_hits': 0,
            'total_latency_ms': 0,
            'active_connections': 0
        }
    
    async def initialize(self) -> None:
        """初始化提供者"""
        if self._initialized:
            return
        
        logger.info(f"初始化异步数据提供者: {self.name}")
        
        # 创建连接器
        self._connector = aiohttp.TCPConnector(
            limit=self.max_connections,
            limit_per_host=self.max_connections_per_host,
            keepalive_timeout=self.keepalive_timeout,
            force_close=False,
            enable_cleanup_closed=True
        )
        
        # 创建会话
        timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=30)
        self._session = aiohttp.ClientSession(
            connector=self._connector,
            timeout=timeout,
            headers={'User-Agent': f'DeepSearch/{self.name}'}
        )
        
        # 创建并发控制
        self._semaphore = asyncio.Semaphore(self.concurrent_limit)
        
        # 启动批处理任务
        if self.batch_size > 1:
            self._batch_task = asyncio.create_task(self._batch_processor())
        
        # 执行子类特定初始化
        await self._initialize_provider()
        
        self._initialized = True
        logger.info(f"异步数据提供者初始化完成: {self.name}")
    
    @abstractmethod
    async def _initialize_provider(self) -> None:
        """子类特定的初始化逻辑"""
        pass
    
    async def fetch(self, request: DataRequest) -> DataResponse:
        """
        获取数据（统一入口）
        
        Args:
            request: 数据请求
            
        Returns:
            数据响应
        """
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        
        try:
            # 检查是否有相同的请求正在处理（请求去重）
            request_key = self._get_request_key(request)
            if request_key in self._pending_requests:
                logger.debug(f"请求去重命中: {request_key}")
                future = self._pending_requests[request_key]
                return await future
            
            # 创建Future用于请求去重
            future = asyncio.get_event_loop().create_future()
            self._pending_requests[request_key] = future
            
            try:
                # 根据优先级决定是否立即执行
                if request.priority == RequestPriority.CRITICAL:
                    response = await self._fetch_immediate(request)
                else:
                    response = await self._fetch_with_batch(request)
                
                # 设置Future结果
                future.set_result(response)
                
            except Exception as e:
                # 设置Future异常
                future.set_exception(e)
                raise
            finally:
                # 清理pending请求
                self._pending_requests.pop(request_key, None)
            
            # 更新统计
            latency_ms = (time.time() - start_time) * 1000
            response.latency_ms = latency_ms
            self._update_stats(response)
            
            return response
            
        except Exception as e:
            logger.error(f"数据获取失败: {e}")
            return DataResponse(
                request_id=request.request_id,
                success=False,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000
            )
    
    async def _fetch_immediate(self, request: DataRequest) -> DataResponse:
        """立即执行请求（高优先级）"""
        async with self._semaphore:
            return await self._execute_request(request)
    
    async def _fetch_with_batch(self, request: DataRequest) -> DataResponse:
        """批量执行请求（普通优先级）"""
        # 如果批处理未启用，直接执行
        if self.batch_size <= 1:
            return await self._fetch_immediate(request)
        
        # 加入批处理队列
        self._batch_queue.append(request)
        
        # 等待批处理完成
        # 这里简化处理，实际应该使用更复杂的等待机制
        await asyncio.sleep(self.batch_timeout)
        
        return await self._fetch_immediate(request)
    
    async def _batch_processor(self) -> None:
        """批处理任务"""
        while True:
            try:
                # 等待超时或队列满
                await asyncio.sleep(self.batch_timeout)
                
                if not self._batch_queue:
                    continue
                
                # 取出待处理请求
                batch = self._batch_queue[:self.batch_size]
                self._batch_queue = self._batch_queue[self.batch_size:]
                
                # 并发执行批量请求
                tasks = [self._fetch_immediate(req) for req in batch]
                await asyncio.gather(*tasks, return_exceptions=True)
                
            except Exception as e:
                logger.error(f"批处理任务异常: {e}")
                await asyncio.sleep(1)
    
    @abstractmethod
    async def _execute_request(self, request: DataRequest) -> DataResponse:
        """
        执行实际的数据请求（子类实现）
        
        Args:
            request: 数据请求
            
        Returns:
            数据响应
        """
        pass
    
    def _get_request_key(self, request: DataRequest) -> str:
        """生成请求唯一键（用于去重）"""
        import hashlib
        import json
        
        key_data = {
            'api': request.api_name,
            'params': request.params
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _update_stats(self, response: DataResponse) -> None:
        """更新统计信息"""
        self.stats['total_requests'] += 1
        
        if response.success:
            self.stats['successful_requests'] += 1
        else:
            self.stats['failed_requests'] += 1
        
        if response.cached:
            self.stats['cache_hits'] += 1
        
        self.stats['total_latency_ms'] += response.latency_ms
    
    async def batch_fetch(self, requests: List[DataRequest]) -> List[DataResponse]:
        """
        批量获取数据
        
        Args:
            requests: 数据请求列表
            
        Returns:
            数据响应列表
        """
        tasks = [self.fetch(req) for req in requests]
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    async def close(self) -> None:
        """关闭提供者"""
        logger.info(f"关闭异步数据提供者: {self.name}")
        
        # 取消批处理任务
        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass
        
        # 关闭会话
        if self._session:
            await self._session.close()
        
        # 关闭连接器
        if self._connector:
            await self._connector.close()
        
        self._initialized = False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.stats.copy()
        
        # 计算平均延迟
        if stats['successful_requests'] > 0:
            stats['avg_latency_ms'] = stats['total_latency_ms'] / stats['successful_requests']
        else:
            stats['avg_latency_ms'] = 0
        
        # 计算成功率
        if stats['total_requests'] > 0:
            stats['success_rate'] = stats['successful_requests'] / stats['total_requests']
        else:
            stats['success_rate'] = 0
        
        # 计算缓存命中率
        if stats['total_requests'] > 0:
            stats['cache_hit_rate'] = stats['cache_hits'] / stats['total_requests']
        else:
            stats['cache_hit_rate'] = 0
        
        return stats
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            # 执行一个简单的测试请求
            test_request = DataRequest(
                request_id="health_check",
                api_name="ping",
                params={},
                priority=RequestPriority.CRITICAL,
                timeout=5.0
            )
            
            response = await self.fetch(test_request)
            return response.success
            
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False


class RequestDeduplicator:
    """请求去重器"""
    
    def __init__(self, ttl: int = 60):
        """
        初始化去重器
        
        Args:
            ttl: 去重记录保留时间（秒）
        """
        self.ttl = ttl
        self._cache: Dict[str, asyncio.Future] = {}
        self._timestamps: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    async def deduplicate(
        self,
        key: str,
        func: Any,
        *args,
        **kwargs
    ) -> Any:
        """
        去重执行函数
        
        Args:
            key: 请求唯一键
            func: 要执行的异步函数
            *args, **kwargs: 函数参数
            
        Returns:
            函数执行结果
        """
        async with self._lock:
            # 清理过期记录
            await self._cleanup_expired()
            
            # 检查是否有相同请求正在处理
            if key in self._cache:
                logger.debug(f"请求去重命中: {key}")
                return await self._cache[key]
            
            # 创建Future并缓存
            future = asyncio.create_task(func(*args, **kwargs))
            self._cache[key] = future
            self._timestamps[key] = time.time()
        
        try:
            result = await future
            return result
        finally:
            # 执行完成后清理
            async with self._lock:
                self._cache.pop(key, None)
                self._timestamps.pop(key, None)
    
    async def _cleanup_expired(self) -> None:
        """清理过期记录"""
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self._timestamps.items()
            if current_time - timestamp > self.ttl
        ]
        
        for key in expired_keys:
            self._cache.pop(key, None)
            self._timestamps.pop(key, None)