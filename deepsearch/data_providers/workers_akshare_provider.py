"""
通过 Cloudflare Workers 代理的 AkShare 数据提供器

支持通过 Workers 代理或直连方式获取股票数据
"""
from datetime import datetime
from typing import Optional, Dict, Any, List

import pandas as pd
from loguru import logger

from deepsearch.cloudflare_workers import WorkersProxyManager, WorkersConfig
from deepsearch.data_providers.base import DataProvider, DataProviderConfig, DataSourceType


class WorkersAkShareProvider(DataProvider):
    """
    通过 Cloudflare Workers 代理的 AkShare 数据提供器
    
    特点：
    1. 支持通过 Workers 代理避免 IP 限制
    2. 自动故障转移到直连
    3. 内置缓存机制
    4. 实时切换代理模式
    """

    def __init__(self, config: Optional[DataProviderConfig] = None):
        """
        初始化提供器
        
        Args:
            config: 数据提供器配置
        """
        super().__init__(config or DataProviderConfig(
            name="workers_akshare",
            source_type=DataSourceType.AKSHARE,
            enabled=True
        ))

        # 创建 Workers 代理管理器
        workers_config = self._load_workers_config()
        self.proxy_manager = WorkersProxyManager(workers_config)

        self.logger = logger.bind(provider="WorkersAkShare")

    def _load_workers_config(self) -> WorkersConfig:
        """加载 Workers 配置"""
        try:
            from deepsearch.config import settings

            if hasattr(settings, 'cloudflare_workers'):
                return WorkersConfig(**settings.cloudflare_workers)
            else:
                # 使用默认配置
                return WorkersConfig(
                    enabled=False,
                    url="wandering-sea-d394.934073514.workers.dev"
                )
        except:
            # 使用默认配置
            return WorkersConfig(
                enabled=False,
                url="wandering-sea-d394.934073514.workers.dev"
            )

    async def _initialize_source(self) -> None:
        """初始化数据源特定配置"""
        # 初始化代理管理器
        await self.proxy_manager.initialize()

        # 测试连接（如果启用）
        if self.proxy_manager.config.enabled:
            test_result = await self.proxy_manager.test_connection()
            if test_result.success:
                self.logger.info(f"Workers proxy connected (time={test_result.response_time:.2f}ms)")
            else:
                self.logger.warning(f"Workers proxy test failed: {test_result.error}")

    async def _start_source(self) -> None:
        """启动数据源特定服务"""
        # Workers proxy manager 不需要特别的启动过程
        pass

    async def _stop_source(self) -> None:
        """停止数据源特定服务"""
        # 关闭代理管理器
        await self.proxy_manager.shutdown()

    async def _fetch_data(self, request) -> pd.DataFrame:
        """
        获取数据的具体实现
        
        Args:
            request: 数据请求对象
            
        Returns:
            数据 DataFrame
        """
        # 根据请求类型调用不同的方法
        if hasattr(request, 'symbols') and request.symbols:
            return await self.fetch_realtime_quotes(request.symbols)
        elif hasattr(request, 'symbol') and request.symbol:
            if hasattr(request, 'start_date'):
                return await self.fetch_historical_data(
                    symbol=request.symbol,
                    start_date=request.start_date,
                    end_date=request.end_date,
                    period=getattr(request, 'period', 'daily'),
                    adjust=getattr(request, 'adjust', 'qfq')
                )
            else:
                return await self.fetch_minute_data(
                    symbol=request.symbol,
                    period=getattr(request, 'period', 1)
                )
        else:
            # 默认获取全部实时行情
            return await self.fetch_realtime_quotes()

    async def fetch_realtime_quotes(
            self,
            symbols: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        获取实时行情
        
        Args:
            symbols: 股票代码列表（None 表示获取全部）
            
        Returns:
            行情数据 DataFrame
        """
        try:
            # 通过代理管理器请求
            response = await self.proxy_manager.request_akshare(
                function="stock_zh_a_spot_em",
                params={}
            )

            if response.success:
                # 转换为 DataFrame
                df = pd.DataFrame(response.data)

                # 如果指定了股票代码，进行过滤
                if symbols:
                    df = df[df['代码'].isin(symbols)]

                self._update_statistics(success=True)
                return df
            else:
                self.logger.error(f"Failed to fetch realtime quotes: {response.error}")
                self._update_statistics(success=False, error=response.error)
                raise Exception(response.error)

        except Exception as e:
            self.logger.error(f"Error fetching realtime quotes: {e}")
            self._update_statistics(success=False, error=str(e))
            raise

    async def fetch_historical_data(
            self,
            symbol: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            period: str = "daily",
            adjust: str = "qfq"
    ) -> pd.DataFrame:
        """
        获取历史K线数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 周期（daily/weekly/monthly）
            adjust: 复权类型（qfq/hfq/不复权）
            
        Returns:
            K线数据 DataFrame
        """
        try:
            # 通过代理管理器请求
            response = await self.proxy_manager.request_akshare(
                function="stock_zh_a_hist",
                params={
                    "symbol": symbol,
                    "period": period,
                    "start_date": start_date,
                    "end_date": end_date,
                    "adjust": adjust
                }
            )

            if response.success:
                df = pd.DataFrame(response.data)
                self._update_statistics(success=True)
                return df
            else:
                self.logger.error(f"Failed to fetch historical data: {response.error}")
                self._update_statistics(success=False, error=response.error)
                raise Exception(response.error)

        except Exception as e:
            self.logger.error(f"Error fetching historical data: {e}")
            self._update_statistics(success=False, error=str(e))
            raise

    async def fetch_stock_info(self, symbol: str) -> Dict[str, Any]:
        """
        获取个股信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            个股信息字典
        """
        try:
            response = await self.proxy_manager.request_akshare(
                function="stock_individual_info_em",
                params={"symbol": symbol}
            )

            if response.success:
                self._update_statistics(success=True)
                return response.data
            else:
                self.logger.error(f"Failed to fetch stock info: {response.error}")
                self._update_statistics(success=False, error=response.error)
                raise Exception(response.error)

        except Exception as e:
            self.logger.error(f"Error fetching stock info: {e}")
            self._update_statistics(success=False, error=str(e))
            raise

    async def fetch_minute_data(
            self,
            symbol: str,
            period: int = 1
    ) -> pd.DataFrame:
        """
        获取分钟K线数据
        
        Args:
            symbol: 股票代码
            period: 分钟周期（1/5/15/30/60）
            
        Returns:
            分钟K线 DataFrame
        """
        try:
            response = await self.proxy_manager.request_akshare(
                function="stock_zh_a_minute",
                params={
                    "symbol": symbol,
                    "period": str(period)
                }
            )

            if response.success:
                df = pd.DataFrame(response.data)
                self._update_statistics(success=True)
                return df
            else:
                self.logger.error(f"Failed to fetch minute data: {response.error}")
                self._update_statistics(success=False, error=response.error)
                raise Exception(response.error)

        except Exception as e:
            self.logger.error(f"Error fetching minute data: {e}")
            self._update_statistics(success=False, error=str(e))
            raise

    def enable_proxy(self) -> None:
        """启用 Workers 代理"""
        self.proxy_manager.enable()
        self.logger.info("Workers proxy enabled")

    def disable_proxy(self) -> None:
        """禁用 Workers 代理"""
        self.proxy_manager.disable()
        self.logger.info("Workers proxy disabled")

    def toggle_proxy(self) -> bool:
        """切换代理状态"""
        enabled = self.proxy_manager.toggle()
        self.logger.info(f"Workers proxy {'enabled' if enabled else 'disabled'}")
        return enabled

    async def test_proxy(self) -> Dict[str, Any]:
        """测试代理连接"""
        result = await self.proxy_manager.test_connection()
        return {
            "success": result.success,
            "response_time": result.response_time,
            "message": result.message,
            "error": result.error,
            "workers_version": result.workers_version
        }

    def get_proxy_status(self) -> Dict[str, Any]:
        """获取代理状态"""
        return self.proxy_manager.get_status()

    def clear_cache(self) -> None:
        """清空缓存"""
        self.proxy_manager.clear_cache()
        self.logger.info("Cache cleared")

    def get_status(self) -> Dict[str, Any]:
        """获取提供器状态"""
        status = super().get_status()

        # 添加代理信息
        proxy_status = self.proxy_manager.get_status()
        status.update({
            "proxy_enabled": proxy_status["enabled"],
            "proxy_status": proxy_status["status"],
            "proxy_url": proxy_status["url"],
            "proxy_statistics": proxy_status["statistics"],
            "cache_size": proxy_status["cache_size"]
        })

        return status

    def _update_statistics(self, success: bool, error: Optional[str] = None):
        """更新统计信息"""
        if success:
            self.statistics["successful_requests"] = \
                self.statistics.get("successful_requests", 0) + 1
        else:
            self.statistics["failed_requests"] = \
                self.statistics.get("failed_requests", 0) + 1
            if error:
                self.statistics["last_error"] = error
                self.statistics["last_error_time"] = datetime.now().isoformat()


# 导出全局实例
_provider_instance: Optional[WorkersAkShareProvider] = None


async def get_provider() -> WorkersAkShareProvider:
    """获取全局提供器实例"""
    global _provider_instance

    if _provider_instance is None:
        _provider_instance = WorkersAkShareProvider()
        await _provider_instance.initialize_async()

    return _provider_instance


async def close_provider() -> None:
    """关闭全局提供器实例"""
    global _provider_instance

    if _provider_instance:
        await _provider_instance.stop_async()
        _provider_instance = None
