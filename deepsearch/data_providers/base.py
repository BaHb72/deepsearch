"""
数据提供者基类

定义数据源接入的统一接口和基础功能，特别强化代理池支持。
"""
import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

# 可选导入
try:
    import aiohttp

    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

from loguru import logger

from deepsearch.core.async_component import AsyncComponent
from deepsearch.core.interfaces import ComponentType


class DataSourceType(Enum):
    """数据源类型"""
    AKSHARE = "akshare"
    TUSHARE = "tushare"
    EASTMONEY = "eastmoney"
    SINA = "sina"
    CUSTOM = "custom"


class RequestMethod(Enum):
    """请求方法"""
    GET = "GET"
    POST = "POST"


@dataclass
class ProxyConfig:
    """代理配置"""
    enabled: bool = False
    pool_size: int = 10
    rotation_strategy: str = "round-robin"  # round-robin, random, weighted, least-used
    health_check_interval: int = 60  # 健康检查间隔（秒）
    max_retries: int = 3
    timeout: int = 10
    proxy_list: List[str] = field(default_factory=list)
    proxy_api_url: Optional[str] = None  # 动态获取代理的API
    proxy_api_key: Optional[str] = None
    blacklist_threshold: int = 5  # 失败多少次后加入黑名单
    blacklist_duration: int = 300  # 黑名单持续时间（秒）


@dataclass
class DataProviderConfig:
    """数据提供者配置"""
    name: str
    source_type: DataSourceType
    enabled: bool = True
    max_concurrent: int = 5  # 最大并发请求数
    rate_limit: float = 0  # 请求速率限制（请求/秒），0表示不限制
    retry_times: int = 3
    retry_delay: float = 1.0
    timeout: int = 30
    cache_enabled: bool = True
    cache_ttl: int = 300  # 缓存过期时间（秒）
    proxy_config: Optional[ProxyConfig] = None
    custom_headers: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if self.proxy_config is None:
            self.proxy_config = ProxyConfig()


@dataclass
class DataRequest:
    """数据请求"""
    symbol: Optional[str] = None
    symbols: Optional[List[str]] = None
    start_date: Optional[Union[str, datetime]] = None
    end_date: Optional[Union[str, datetime]] = None
    period: str = "1d"  # 1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M
    adjust: str = "qfq"  # qfq-前复权, hfq-后复权, None-不复权
    fields: Optional[List[str]] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DataResponse:
    """数据响应"""
    success: bool
    data: Optional[pd.DataFrame] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    request_time: float = 0  # 请求耗时（秒）
    proxy_used: Optional[str] = None  # 使用的代理


class DataProviderError(Exception):
    """数据提供者异常"""
    pass


class RateLimiter:
    """速率限制器"""

    def __init__(self, rate: float):
        """
        Args:
            rate: 每秒允许的请求数，0表示不限制
        """
        self.rate = rate
        self.tokens = rate
        self.updated_at = time.time()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """获取令牌"""
        if self.rate <= 0:
            return

        async with self.lock:
            now = time.time()
            elapsed = now - self.updated_at
            self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
            self.updated_at = now

            if self.tokens < 1:
                sleep_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(sleep_time)
                self.tokens = 0
            else:
                self.tokens -= 1


class DataProvider(AsyncComponent, ABC):
    """
    数据提供者基类
    
    提供数据源接入的统一接口，包括：
    - 代理池管理
    - 请求重试
    - 速率限制
    - 数据缓存
    - 性能监控
    """

    def __init__(self, config: DataProviderConfig):
        """
        初始化数据提供者
        
        Args:
            config: 数据提供者配置
        """
        super().__init__(
            name=f"data_provider_{config.name}",
            component_type=ComponentType.BUSINESS,
            display_name=f"数据提供者-{config.name}"
        )

        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = RateLimiter(config.rate_limit)
        self._cache: Dict[str, DataResponse] = {}
        self._proxy_manager = None

        # 性能统计
        self._request_count = 0
        self._success_count = 0
        self._error_count = 0
        self._total_request_time = 0

    async def _initialize(self) -> None:
        """初始化组件"""
        # 创建HTTP会话
        connector = aiohttp.TCPConnector(
            limit=self.config.max_concurrent,
            limit_per_host=self.config.max_concurrent
        )

        timeout = aiohttp.ClientTimeout(total=self.config.timeout)

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self.config.custom_headers
        )

        # 初始化代理管理器
        if self.config.proxy_config.enabled:
            from .proxy.manager import ProxyManager
            self._proxy_manager = ProxyManager(self.config.proxy_config)
            await self._proxy_manager.initialize()

        # 初始化数据源特定配置
        await self._initialize_source()

        self._instance = self
        logger.info(f"数据提供者 {self.config.name} 初始化完成")

    async def _start(self) -> None:
        """启动组件"""
        if self._proxy_manager:
            await self._proxy_manager.start()
        await self._start_source()
        logger.info(f"数据提供者 {self.config.name} 已启动")

    async def _stop(self) -> None:
        """停止组件"""
        await self._stop_source()

        if self._proxy_manager:
            await self._proxy_manager.stop()

        if self._session:
            await self._session.close()

        logger.info(f"数据提供者 {self.config.name} 已停止")

    @abstractmethod
    async def _initialize_source(self) -> None:
        """初始化数据源特定配置"""
        pass

    @abstractmethod
    async def _start_source(self) -> None:
        """启动数据源特定服务"""
        pass

    @abstractmethod
    async def _stop_source(self) -> None:
        """停止数据源特定服务"""
        pass

    @abstractmethod
    async def _fetch_data(self, request: DataRequest) -> pd.DataFrame:
        """
        获取数据的具体实现
        
        Args:
            request: 数据请求
            
        Returns:
            数据DataFrame
        """
        pass

    async def get_data(self, request: DataRequest) -> DataResponse:
        """
        获取数据（公共接口）
        
        Args:
            request: 数据请求
            
        Returns:
            数据响应
        """
        start_time = time.time()

        # 检查缓存
        cache_key = self._get_cache_key(request)
        if self.config.cache_enabled and cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.now() - cached.timestamp).seconds < self.config.cache_ttl:
                logger.debug(f"使用缓存数据: {cache_key}")
                return cached

        # 速率限制
        await self._rate_limiter.acquire()

        # 重试逻辑
        last_error = None
        for attempt in range(self.config.retry_times):
            try:
                # 获取数据
                data = await self._fetch_with_proxy(request)

                # 创建响应
                response = DataResponse(
                    success=True,
                    data=data,
                    source=self.config.source_type.value,
                    request_time=time.time() - start_time,
                    proxy_used=getattr(self, '_last_proxy_used', None)
                )

                # 更新缓存
                if self.config.cache_enabled:
                    self._cache[cache_key] = response

                # 更新统计
                self._request_count += 1
                self._success_count += 1
                self._total_request_time += response.request_time

                return response

            except Exception as e:
                last_error = e
                logger.warning(f"请求失败 (尝试 {attempt + 1}/{self.config.retry_times}): {e}")

                if attempt < self.config.retry_times - 1:
                    await asyncio.sleep(self.config.retry_delay * (attempt + 1))

        # 所有重试都失败
        self._request_count += 1
        self._error_count += 1

        return DataResponse(
            success=False,
            error=str(last_error),
            source=self.config.source_type.value,
            request_time=time.time() - start_time
        )

    async def _fetch_with_proxy(self, request: DataRequest) -> pd.DataFrame:
        """
        使用代理获取数据
        
        Args:
            request: 数据请求
            
        Returns:
            数据DataFrame
        """
        if self._proxy_manager:
            # 获取可用代理
            proxy = await self._proxy_manager.get_proxy()
            self._last_proxy_used = proxy

            try:
                # 设置代理并获取数据
                original_proxy = self._session.connector._proxy
                self._session.connector._proxy = proxy

                data = await self._fetch_data(request)

                # 标记代理成功
                await self._proxy_manager.mark_success(proxy)

                return data

            except Exception as e:
                # 标记代理失败
                await self._proxy_manager.mark_failure(proxy)
                raise
            finally:
                # 恢复原始代理设置
                self._session.connector._proxy = original_proxy
        else:
            # 直接获取数据
            return await self._fetch_data(request)

    async def make_request(
            self,
            url: str,
            method: RequestMethod = RequestMethod.GET,
            params: Optional[Dict] = None,
            data: Optional[Dict] = None,
            headers: Optional[Dict] = None
    ) -> Dict:
        """
        发起HTTP请求（供子类使用）
        
        Args:
            url: 请求URL
            method: 请求方法
            params: 查询参数
            data: 请求体数据
            headers: 请求头
            
        Returns:
            响应数据
        """
        if not self._session:
            raise DataProviderError("HTTP session not initialized")

        request_headers = self.config.custom_headers.copy()
        if headers:
            request_headers.update(headers)

        async with self._session.request(
                method.value,
                url,
                params=params,
                json=data if method == RequestMethod.POST else None,
                headers=request_headers
        ) as response:
            response.raise_for_status()
            return await response.json()

    def _get_cache_key(self, request: DataRequest) -> str:
        """生成缓存键"""
        parts = [
            self.config.name,
            request.symbol or "",
            str(request.start_date) if request.start_date else "",
            str(request.end_date) if request.end_date else "",
            request.period,
            request.adjust
        ]
        return "_".join(parts)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "provider": self.config.name,
            "source_type": self.config.source_type.value,
            "enabled": self.config.enabled,
            "request_count": self._request_count,
            "success_count": self._success_count,
            "error_count": self._error_count,
            "success_rate": self._success_count / self._request_count if self._request_count > 0 else 0,
            "avg_request_time": self._total_request_time / self._request_count if self._request_count > 0 else 0,
            "cache_size": len(self._cache),
            "proxy_enabled": self.config.proxy_config.enabled
        }

        if self._proxy_manager:
            stats["proxy_stats"] = self._proxy_manager.get_statistics()

        return stats

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.info(f"已清空数据提供者 {self.config.name} 的缓存")
