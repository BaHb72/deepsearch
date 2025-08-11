"""
数据提供者管理器

统一管理多个数据源，提供智能路由和容错机制。
"""
import asyncio
from typing import Dict, List, Optional, Any

import pandas as pd
from loguru import logger

from .base import (
    DataProvider,
    DataRequest,
    DataResponse,
    DataProviderError
)
from .cloudflare_proxy import CloudflareProxyProvider, CloudflareConfig


class DataProviderManager:
    """
    数据提供者管理器
    
    功能：
    - 管理多个数据提供者
    - 智能选择最优数据源
    - 失败自动切换
    - 负载均衡
    - 统一的数据接口
    """

    def __init__(self):
        """初始化管理器"""
        self._providers: Dict[str, DataProvider] = {}
        self._provider_priority: Dict[str, int] = {
            "cloudflare_proxy": 1,  # Cloudflare Worker 优先级最高
            "tushare": 2,
            "akshare": 3,
            "eastmoney": 4,
            "sina": 5,
            "custom": 6
        }
        self._initialized = False
        self._cloudflare_provider = None

    async def initialize(self) -> None:
        """初始化所有数据提供者"""
        if self._initialized:
            return

        logger.info("初始化数据提供者管理器...")

        # 初始化 Cloudflare Worker 提供者
        try:
            from deepsearch.config import settings
            cloudflare_config = settings.data_providers.get("cloudflare_proxy", {})

            if cloudflare_config.get("enabled", False):
                config = CloudflareConfig(
                    worker_url=cloudflare_config.get("worker_url"),
                    timeout=cloudflare_config.get("timeout", 30),
                    retry_count=cloudflare_config.get("retry_count", 3),
                    cache_ttl=cloudflare_config.get("cache_ttl", 60)
                )
                self._cloudflare_provider = CloudflareProxyProvider(config)
                await self._cloudflare_provider.initialize()
                self._providers["cloudflare_proxy"] = self._cloudflare_provider
                logger.info("Cloudflare Worker 提供者初始化成功")
        except Exception as e:
            logger.error(f"Cloudflare Worker 提供者初始化失败: {e}")

        # 初始化其他已注册的提供者
        init_tasks = []
        for name, provider in self._providers.items():
            if name != "cloudflare_proxy" and hasattr(provider, 'config') and provider.config.enabled:
                init_tasks.append(self._init_provider(name, provider))

        if init_tasks:
            results = await asyncio.gather(*init_tasks, return_exceptions=True)

            # 检查初始化结果
            for name, result in zip(self._providers.keys(), results):
                if isinstance(result, Exception):
                    logger.error(f"数据提供者 {name} 初始化失败: {result}")
                else:
                    logger.info(f"数据提供者 {name} 初始化成功")

        self._initialized = True
        logger.info(f"数据提供者管理器初始化完成，可用提供者: {self.get_available_providers()}")

    async def _init_provider(self, name: str, provider: DataProvider) -> None:
        """初始化单个提供者"""
        try:
            await provider.initialize_async()
            await provider.start_async()
        except Exception as e:
            logger.error(f"初始化提供者 {name} 失败: {e}")
            raise

    def register_provider(self, provider: DataProvider) -> None:
        """
        注册数据提供者
        
        Args:
            provider: 数据提供者实例
        """
        name = provider.config.name
        if name in self._providers:
            logger.warning(f"数据提供者 {name} 已存在，将被覆盖")

        self._providers[name] = provider
        logger.info(f"注册数据提供者: {name} ({provider.config.source_type.value})")

    def unregister_provider(self, name: str) -> None:
        """
        注销数据提供者
        
        Args:
            name: 提供者名称
        """
        if name in self._providers:
            del self._providers[name]
            logger.info(f"注销数据提供者: {name}")

    def get_provider(self, name: str) -> Optional[DataProvider]:
        """
        获取指定的数据提供者
        
        Args:
            name: 提供者名称
            
        Returns:
            数据提供者实例
        """
        return self._providers.get(name)

    def get_available_providers(self) -> List[str]:
        """获取所有可用的提供者名称"""
        return [
            name for name, provider in self._providers.items()
            if provider.config.enabled and provider.status.value == "running"
        ]

    async def get_stock_daily(
            self,
            symbol: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            source: str = "auto",
            adjust: str = "qfq"
    ) -> pd.DataFrame:
        """
        获取股票日线数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            source: 数据源 ("auto" 表示自动选择)
            adjust: 复权类型
            
        Returns:
            日线数据DataFrame
        """
        request = DataRequest(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            period="1d",
            adjust=adjust
        )

        response = await self._get_data(request, source)

        if response.success:
            return response.data
        else:
            raise DataProviderError(f"获取数据失败: {response.error}")

    async def get_stock_minute(
            self,
            symbol: str,
            date: Optional[str] = None,
            period: str = "1m",
            source: str = "auto"
    ) -> pd.DataFrame:
        """
        获取股票分钟数据
        
        Args:
            symbol: 股票代码
            date: 日期
            period: 周期 (1m, 5m, 15m, 30m, 60m)
            source: 数据源
            
        Returns:
            分钟数据DataFrame
        """
        request = DataRequest(
            symbol=symbol,
            start_date=date,
            end_date=date,
            period=period
        )

        response = await self._get_data(request, source)

        if response.success:
            return response.data
        else:
            raise DataProviderError(f"获取数据失败: {response.error}")

    async def get_realtime_quotes(
            self,
            symbols: List[str],
            source: str = "auto"
    ) -> pd.DataFrame:
        """
        获取实时行情
        
        Args:
            symbols: 股票代码列表
            source: 数据源
            
        Returns:
            实时行情DataFrame
        """
        request = DataRequest(
            symbols=symbols,
            period="tick"
        )

        response = await self._get_data(request, source)

        if response.success:
            return response.data
        else:
            raise DataProviderError(f"获取数据失败: {response.error}")

    async def _get_data(
            self,
            request: DataRequest,
            source: str = "auto"
    ) -> DataResponse:
        """
        获取数据（内部方法）
        
        Args:
            request: 数据请求
            source: 数据源
            
        Returns:
            数据响应
        """
        if not self._initialized:
            await self.initialize()

        # 确定使用的提供者
        if source == "auto":
            providers = self._select_providers(request)
        else:
            provider = self._providers.get(source)
            if not provider:
                return DataResponse(
                    success=False,
                    error=f"数据提供者 {source} 不存在"
                )
            providers = [provider]

        if not providers:
            return DataResponse(
                success=False,
                error="没有可用的数据提供者"
            )

        # 尝试从各个提供者获取数据
        last_error = None
        for provider in providers:
            try:
                logger.debug(f"尝试从 {provider.config.name} 获取数据")
                response = await provider.get_data(request)

                if response.success:
                    return response
                else:
                    last_error = response.error
                    logger.debug(f"提供者 {provider.config.name} 失败: {response.error}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"提供者 {provider.config.name} 异常: {e}")

        # 所有提供者都失败
        return DataResponse(
            success=False,
            error=f"所有数据源都失败: {last_error}"
        )

    def _select_providers(self, request: DataRequest) -> List[DataProvider]:
        """
        根据请求选择合适的提供者
        
        Args:
            request: 数据请求
            
        Returns:
            按优先级排序的提供者列表
        """
        available = []

        for name, provider in self._providers.items():
            if not provider.config.enabled:
                continue

            if provider.status.value != "running":
                continue

            # 根据数据类型检查提供者是否支持
            available.append(provider)

        # 按优先级排序
        available.sort(
            key=lambda p: self._provider_priority.get(
                p.config.source_type,
                999
            )
        )

        return available

    async def stop(self) -> None:
        """停止所有数据提供者"""
        logger.info("停止数据提供者管理器...")

        stop_tasks = []
        for provider in self._providers.values():
            if provider.status.value == "running":
                stop_tasks.append(provider.stop_async())

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        self._initialized = False
        logger.info("数据提供者管理器已停止")

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "total_providers": len(self._providers),
            "available_providers": len(self.get_available_providers()),
            "providers": {}
        }

        for name, provider in self._providers.items():
            stats["providers"][name] = provider.get_statistics()

        return stats
