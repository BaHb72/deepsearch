# encoding:utf-8
"""
Enhanced Data Provider Manager
增强版数据提供者管理器 - 统一管理AmazingData、QMT、MiniQMT和AkShare
Author: DeepSearch Team
Version: 4.0.0
"""

import asyncio
from enum import Enum
from typing import Dict, List, Optional, Any

import pandas as pd
from loguru import logger

from .akshare import AkShareProxyProvider
from .amazingdata import AmazingDataProvider, AmazingDataConfig
from .base import (
    DataProvider,
    DataProviderError
)
from .capabilities import (
    DataCapability
)
from .unified_qmt_provider import UnifiedQMTProvider, QMTMode, SmartCacheManager


class DataSourcePriority(Enum):
    """数据源优先级"""
    AMAZINGDATA = 1  # 最高优先级：AmazingData
    QMT = 2  # 次优先级：QMT（标准版或MiniQMT）
    AKSHARE = 3  # 第三优先级：AkShare
    FALLBACK = 4  # 兜底方案


class EnhancedDataProviderManager:
    """
    增强版数据提供者管理器
    
    特性：
    1. 统一管理QMT/MiniQMT/AkShare
    2. 智能路由和自动故障转移
    3. 多级缓存系统
    4. 性能监控和统计
    """

    def __init__(self):
        """初始化管理器"""
        self._providers: Dict[str, DataProvider] = {}
        self._initialized = False

        # 数据提供者实例
        self._amazingdata_provider: Optional[AmazingDataProvider] = None
        self._qmt_provider: Optional[UnifiedQMTProvider] = None
        self._akshare_provider: Optional[AkShareProxyProvider] = None

        # 全局缓存管理器
        self.global_cache = SmartCacheManager(max_memory_size=2000)

        # 性能统计
        self.stats = {
            'requests': 0,
            'successes': 0,
            'failures': 0,
            'cache_hits': 0,
            'provider_usage': {}
        }

        # 提供者健康状态
        self.provider_health = {}

    async def initialize(self) -> None:
        """初始化所有数据提供者"""
        if self._initialized:
            return

        logger.info("=" * 60)
        logger.info("初始化增强版数据提供者管理器 v4.0")
        logger.info("=" * 60)

        # 1. 初始化AmazingData提供者（最高优先级）
        await self._init_amazingdata_provider()

        # 2. 初始化统一QMT提供者（自动检测QMT或MiniQMT）
        await self._init_qmt_provider()

        # 3. 初始化AkShare提供者
        await self._init_akshare_provider()

        # 4. 健康检查
        await self._health_check_all()

        self._initialized = True

        # 打印初始化结果
        self._print_init_summary()

    async def _init_amazingdata_provider(self):
        """初始化AmazingData提供者"""
        try:
            # 从配置获取AmazingData设置
            from deepsearch.config import get_config
            config = get_config()

            # 检查是否启用
            if hasattr(config, 'amazingdata') and config.amazingdata.enabled:
                logger.info("正在初始化AmazingData数据源...")

                # 创建配置
                ad_config = AmazingDataConfig(
                    username=config.amazingdata.connection.username,
                    password=config.amazingdata.connection.password,
                    host=config.amazingdata.connection.host,
                    port=config.amazingdata.connection.port,
                    enabled=True,
                    cache_enabled=config.amazingdata.cache.enabled,
                    cache_ttl=config.amazingdata.cache.ttl,
                    heartbeat_interval=config.amazingdata.connection.heartbeat_interval,
                    auto_reconnect=config.amazingdata.connection.auto_reconnect,
                    subscription_enabled=config.amazingdata.subscription.enabled,
                    subscription_batch_size=config.amazingdata.subscription.batch_size,
                    max_subscriptions=config.amazingdata.subscription.max_symbols
                )

                # 创建提供者
                self._amazingdata_provider = AmazingDataProvider(ad_config)
                await self._amazingdata_provider.initialize()

                # 注册到提供者列表
                self._providers["amazingdata"] = self._amazingdata_provider

                logger.info("✅ AmazingData初始化成功")
                self.provider_health["amazingdata"] = {"status": "healthy", "priority": 1}
            else:
                logger.info("⚠️ AmazingData未启用")
                self.provider_health["amazingdata"] = {"status": "disabled"}

        except ImportError as e:
            logger.warning(f"⚠️ AmazingData SDK未安装: {e}")
            self.provider_health["amazingdata"] = {"status": "not_installed"}
        except Exception as e:
            logger.error(f"❌ AmazingData初始化失败: {e}")
            self.provider_health["amazingdata"] = {"status": "unhealthy", "error": str(e)}

    async def _init_qmt_provider(self):
        """初始化QMT提供者"""
        try:
            logger.info("正在初始化QMT数据源...")

            # 创建统一QMT提供者（自动检测模式）
            self._qmt_provider = UnifiedQMTProvider(mode=QMTMode.AUTO)
            await self._qmt_provider.initialize_async()

            # 注册到提供者列表
            self._providers["qmt"] = self._qmt_provider

            # 记录实际模式
            actual_mode = self._qmt_provider.actual_mode
            if actual_mode == QMTMode.MINI:
                logger.info("✅ MiniQMT初始化成功")
                self.provider_health["qmt"] = {"status": "healthy", "mode": "MiniQMT"}
            else:
                logger.info("✅ QMT标准版初始化成功")
                self.provider_health["qmt"] = {"status": "healthy", "mode": "Standard QMT"}

        except Exception as e:
            logger.error(f"❌ QMT初始化失败: {e}")
            self.provider_health["qmt"] = {"status": "unhealthy", "error": str(e)}

    async def _init_akshare_provider(self):
        """初始化AkShare提供者"""
        try:
            logger.info("正在初始化AkShare数据源...")

            self._akshare_provider = AkShareProxyProvider()
            await self._akshare_provider.initialize()

            # 注册到提供者列表
            self._providers["akshare"] = self._akshare_provider

            logger.info("✅ AkShare初始化成功")
            self.provider_health["akshare"] = {"status": "healthy"}

        except Exception as e:
            logger.error(f"❌ AkShare初始化失败: {e}")
            self.provider_health["akshare"] = {"status": "unhealthy", "error": str(e)}

    async def _health_check_all(self):
        """健康检查所有提供者"""
        logger.info("\n执行健康检查...")

        for name, provider in self._providers.items():
            try:
                # 简单测试获取一个股票的数据
                if name == "amazingdata":
                    # AmazingData测试 - 获取交易日历
                    from datetime import datetime
                    today = datetime.now().strftime('%Y%m%d')
                    if hasattr(provider, 'is_connected'):
                        healthy = provider.is_connected()
                    else:
                        healthy = True
                elif name == "qmt":
                    df = await provider.get_kline('000001', count=1)
                    healthy = not df.empty if isinstance(df, pd.DataFrame) else False
                else:
                    # AkShare - 跳过实时数据测试（太慢），假设健康
                    healthy = True  # 跳过缓慢的实时数据测试

                if healthy:
                    self.provider_health[name]["test"] = "passed"
                    logger.info(f"  ✅ {name}: 健康")
                else:
                    self.provider_health[name]["test"] = "failed"
                    logger.warning(f"  ⚠️ {name}: 无数据")

            except Exception as e:
                self.provider_health[name]["test"] = "error"
                logger.error(f"  ❌ {name}: 测试失败 - {e}")

    def _print_init_summary(self):
        """打印初始化摘要"""
        logger.info("\n" + "=" * 60)
        logger.info("初始化完成 - 数据源状态")
        logger.info("=" * 60)

        for name, health in self.provider_health.items():
            status = health.get("status", "unknown")
            mode = health.get("mode", "")
            test = health.get("test", "")

            status_icon = "✅" if status == "healthy" else "❌"
            test_icon = "✅" if test == "passed" else "⚠️" if test == "failed" else "❌"

            info = f"{status_icon} {name.upper()}"
            if mode:
                info += f" ({mode})"
            if test:
                info += f" - 测试: {test_icon}"

            logger.info(info)

        # 可用功能总结
        logger.info("\n可用功能:")
        available_features = self._get_available_features()
        for feature, providers in available_features.items():
            if providers:
                logger.info(f"  ✅ {feature}: {', '.join(providers)}")
            else:
                logger.info(f"  ❌ {feature}: 无可用数据源")

    def _get_available_features(self) -> Dict[str, List[str]]:
        """获取可用功能列表"""
        features = {
            "历史K线": [],
            "实时行情": [],
            "订阅推送": [],
            "财务数据": [],
            "Level2数据": []
        }

        # 检查AmazingData（最高优先级）
        if self.provider_health.get("amazingdata", {}).get("status") == "healthy":
            features["历史K线"].append("AmazingData")
            features["实时行情"].append("AmazingData")
            features["订阅推送"].append("AmazingData")
            features["财务数据"].append("AmazingData")
            features["Level2数据"].append("AmazingData")

        # 检查QMT
        if self.provider_health.get("qmt", {}).get("status") == "healthy":
            features["历史K线"].append("QMT")
            features["实时行情"].append("QMT")
            features["订阅推送"].append("QMT")

            # 标准QMT可能有Level2
            if self.provider_health["qmt"].get("mode") == "Standard QMT":
                features["Level2数据"].append("QMT")

        # 检查AkShare
        if self.provider_health.get("akshare", {}).get("status") == "healthy":
            features["历史K线"].append("AkShare")
            features["实时行情"].append("AkShare")
            features["财务数据"].append("AkShare")

        return features

    # ==================== 统一数据接口 ====================

    async def get_stock_daily(
            self,
            symbol: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            source: str = "auto",
            adjust: str = "qfq",
            use_cache: bool = True
    ) -> pd.DataFrame:
        """
        获取股票日线数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            source: 数据源（auto/qmt/akshare）
            adjust: 复权类型
            use_cache: 是否使用缓存
            
        Returns:
            日线数据DataFrame
        """
        self.stats['requests'] += 1

        # 检查缓存
        if use_cache:
            cache_key = f"daily_{symbol}_{start_date}_{end_date}_{adjust}"
            cached_data = self.global_cache.get(cache_key)
            if cached_data is not None:
                self.stats['cache_hits'] += 1
                logger.debug(f"📦 缓存命中: {symbol} 日线数据")
                return cached_data

        # 选择数据源
        if source == "auto":
            provider = await self._select_best_provider(DataCapability.KLINE_DATA)
        else:
            provider = self._providers.get(source)

        if not provider:
            raise DataProviderError("无可用的数据提供者")

        try:
            # 获取数据
            if hasattr(provider, 'get_kline'):
                df = await provider.get_kline(
                    symbol=symbol,
                    period='1d',
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust
                )
            else:
                # AkShare接口
                df = await self._get_akshare_daily(
                    symbol, start_date, end_date, adjust
                )

            if not df.empty:
                # 缓存数据
                if use_cache:
                    self.global_cache.set(cache_key, df, ttl=300)

                self.stats['successes'] += 1
                # 更新统计，记录实际使用的提供者
                actual_provider = source if source != "auto" else (
                    "amazingdata" if self._amazingdata_provider and provider == self._amazingdata_provider else
                    "qmt" if provider == self._qmt_provider else "akshare"
                )
                self._update_provider_stats(actual_provider)

            return df

        except Exception as e:
            self.stats['failures'] += 1
            logger.error(f"获取日线数据失败: {e}")

            # 尝试降级到下一个优先级
            if source == "auto":
                return await self._fallback_get_daily(symbol, start_date, end_date, adjust)

            raise DataProviderError(f"获取数据失败: {e}")

    async def get_realtime_quotes(
            self,
            symbols: List[str],
            source: str = "auto",
            use_cache: bool = True
    ) -> Dict[str, Dict]:
        """
        获取实时行情
        
        Args:
            symbols: 股票代码列表
            source: 数据源
            use_cache: 是否使用缓存（短缓存）
            
        Returns:
            {symbol: quote_data}
        """
        self.stats['requests'] += 1

        # 检查短缓存（10秒）
        if use_cache:
            cache_key = f"quotes_{','.join(sorted(symbols))}"
            cached_data = self.global_cache.get(cache_key, max_age=10)
            if cached_data is not None:
                self.stats['cache_hits'] += 1
                return cached_data

        # 选择数据源
        if source == "auto":
            provider = await self._select_best_provider(DataCapability.REALTIME_QUOTES)
        else:
            provider = self._providers.get(source)

        if not provider:
            raise DataProviderError("无可用的数据提供者")

        try:
            # 获取数据
            if hasattr(provider, 'get_realtime_quote'):
                quotes = await provider.get_realtime_quote(symbols)
            else:
                # AkShare接口
                quotes = await provider.get_realtime_data(symbols)

            if quotes:
                # 短缓存
                if use_cache:
                    self.global_cache.set(cache_key, quotes, ttl=10)

                self.stats['successes'] += 1
                # 更新统计，记录实际使用的提供者
                actual_provider = source if source != "auto" else (
                    "amazingdata" if self._amazingdata_provider and provider == self._amazingdata_provider else
                    "qmt" if provider == self._qmt_provider else "akshare"
                )
                self._update_provider_stats(actual_provider)

            return quotes

        except Exception as e:
            self.stats['failures'] += 1
            logger.error(f"获取实时行情失败: {e}")

            # 尝试降级
            if source == "auto":
                return await self._fallback_get_quotes(symbols)

            return {}

    async def subscribe_quotes(
            self,
            symbols: List[str],
            callback: callable,
            source: str = "auto"
    ) -> bool:
        """
        订阅实时行情
        
        Args:
            symbols: 股票代码列表
            callback: 回调函数
            source: 数据源
            
        Returns:
            是否订阅成功
        """
        # 只有QMT支持订阅
        if source == "auto":
            provider = self._providers.get("qmt")
        else:
            provider = self._providers.get(source)

        if not provider:
            logger.warning("无支持订阅的数据源")
            return False

        try:
            if hasattr(provider, 'subscribe_quote'):
                return await provider.subscribe_quote(symbols, callback)
            else:
                logger.warning(f"{source} 不支持订阅功能")
                return False

        except Exception as e:
            logger.error(f"订阅失败: {e}")
            return False

    # ==================== 辅助方法 ====================

    async def _select_best_provider(self, capability: DataCapability) -> Optional[DataProvider]:
        """选择最佳数据提供者"""
        # 按优先级顺序检查提供者
        priority_order = ['amazingdata', 'qmt', 'akshare']

        for provider_name in priority_order:
            if provider_name in self._providers:
                health = self.provider_health.get(provider_name, {})
                if health.get("status") == "healthy":
                    # 检查是否支持该能力
                    provider = self._providers[provider_name]
                    if self._provider_supports_capability(provider, capability):
                        logger.debug(f"选择数据源: {provider_name} for {capability}")
                        return provider

        return None

    def _provider_supports_capability(self, provider: DataProvider, capability: DataCapability) -> bool:
        """检查提供者是否支持指定能力"""
        # AmazingData支持所有能力
        if isinstance(provider, AmazingDataProvider):
            return True

        # QMT支持大部分能力
        if isinstance(provider, UnifiedQMTProvider):
            return capability in [
                DataCapability.KLINE_DATA,
                DataCapability.REALTIME_QUOTES,
                DataCapability.SUBSCRIPTION,
                DataCapability.LEVEL2_DATA
            ]

        # AkShare支持基础能力
        if isinstance(provider, AkShareProxyProvider):
            return capability in [
                DataCapability.KLINE_DATA,
                DataCapability.REALTIME_QUOTES,
                DataCapability.FINANCIAL_DATA
            ]

        return False

    async def _get_akshare_daily(
            self,
            symbol: str,
            start_date: str,
            end_date: str,
            adjust: str
    ) -> pd.DataFrame:
        """通过AkShare获取日线数据"""
        if not self._akshare_provider:
            return pd.DataFrame()

        try:
            # AkShare 的 get_history_data 不支持 adjust 参数
            df = await self._akshare_provider.get_history_data(
                symbol=symbol,
                period='daily',
                start_date=start_date,
                end_date=end_date
            )

            if df is not None and not df.empty:
                return df

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"AkShare获取日线失败: {e}")
            return pd.DataFrame()

    async def _fallback_get_daily(
            self,
            symbol: str,
            start_date: str,
            end_date: str,
            adjust: str
    ) -> pd.DataFrame:
        """降级获取日线数据"""
        # 按优先级尝试其他数据源
        fallback_order = []

        # 如果AmazingData失败，尝试QMT
        if self._qmt_provider and self.provider_health.get("qmt", {}).get("status") == "healthy":
            logger.info("尝试降级到QMT...")
            try:
                df = await self._qmt_provider.get_kline(
                    symbol=symbol,
                    period='1d',
                    start_date=start_date,
                    end_date=end_date,
                    adjust=adjust
                )
                if not df.empty:
                    return df
            except Exception as e:
                logger.error(f"QMT降级失败: {e}")

        # 最后尝试AkShare
        if self._akshare_provider:
            logger.info("尝试降级到AkShare...")
            return await self._get_akshare_daily(symbol, start_date, end_date, adjust)

        return pd.DataFrame()

    async def _fallback_get_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """降级获取实时行情"""
        # 按优先级尝试其他数据源

        # 如果AmazingData失败，尝试QMT
        if self._qmt_provider and self.provider_health.get("qmt", {}).get("status") == "healthy":
            logger.info("尝试降级到QMT...")
            try:
                quotes = await self._qmt_provider.get_realtime_quote(symbols)
                if quotes:
                    return quotes
            except Exception as e:
                logger.error(f"QMT降级失败: {e}")

        # 最后尝试AkShare
        if self._akshare_provider:
            logger.info("尝试降级到AkShare...")
            try:
                return await self._akshare_provider.get_realtime_data(symbols)
            except:
                pass

        return {}

    def _update_provider_stats(self, provider_name: str):
        """更新提供者使用统计"""
        if provider_name not in self.stats['provider_usage']:
            self.stats['provider_usage'][provider_name] = 0
        self.stats['provider_usage'][provider_name] += 1

    # ==================== 管理接口 ====================

    def get_status(self) -> Dict[str, Any]:
        """获取管理器状态"""
        return {
            'initialized': self._initialized,
            'providers': list(self._providers.keys()),
            'health': self.provider_health,
            'stats': self.stats,
            'cache_stats': self.global_cache.get_stats()
        }

    def clear_cache(self):
        """清空所有缓存"""
        self.global_cache.clear()
        logger.info("全局缓存已清空")

    async def refresh_providers(self):
        """刷新所有提供者"""
        logger.info("刷新数据提供者...")
        await self._health_check_all()

    async def close(self):
        """关闭管理器"""
        for name, provider in self._providers.items():
            try:
                if hasattr(provider, 'close'):
                    await provider.close()
                logger.info(f"关闭提供者: {name}")
            except Exception as e:
                logger.error(f"关闭提供者 {name} 失败: {e}")

        self._initialized = False


# ==================== 全局实例 ====================
_manager_instance: Optional[EnhancedDataProviderManager] = None


async def get_data_manager() -> EnhancedDataProviderManager:
    """获取全局数据管理器实例"""
    global _manager_instance

    if _manager_instance is None:
        _manager_instance = EnhancedDataProviderManager()
        await _manager_instance.initialize()

    return _manager_instance


# ==================== 使用示例 ====================
async def example():
    """使用示例"""

    # 获取管理器
    manager = await get_data_manager()

    # 查看状态
    status = manager.get_status()
    print("管理器状态:", status)

    # 获取日线数据（自动选择最佳数据源）
    df = await manager.get_stock_daily(
        symbol='000001.SZ',
        start_date='20240101',
        end_date='20240131',
        source='auto',  # 自动选择
        use_cache=True  # 使用缓存
    )
    print(f"获取到 {len(df)} 条日线数据")

    # 获取实时行情
    quotes = await manager.get_realtime_quotes(
        symbols=['000001.SZ', '600000.SH'],
        source='auto',
        use_cache=True
    )
    for symbol, quote in quotes.items():
        print(f"{symbol}: {quote}")

    # 查看缓存统计
    cache_stats = manager.global_cache.get_stats()
    print(f"缓存统计: {cache_stats}")


if __name__ == '__main__':
    asyncio.run(example())
