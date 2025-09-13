"""
统一的数据源管理器 - 重构版本
配置驱动、策略模式、依赖注入
"""
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, List, Type

from loguru import logger

from deepsearch.config import get_config
from ..interfaces.base import DataSourceType


@dataclass
class DataSourceConfig:
    """数据源配置"""
    enabled: bool
    priority: int = 100
    timeout: float = 10.0
    retry_count: int = 3
    fallback_enabled: bool = False
    fallback_sources: List[str] = None
    config: Dict[str, Any] = None

    def __post_init__(self):
        if self.config is None:
            self.config = {}
        if self.fallback_sources is None:
            self.fallback_sources = []


class DataSourceRegistry:
    """数据源注册表 - 单例模式"""
    _instance = None
    _providers: Dict[DataSourceType, Any] = {}
    _configs: Dict[DataSourceType, DataSourceConfig] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register_provider(self, source_type: DataSourceType, provider_class: Type):
        """注册数据提供者类"""
        self._providers[source_type] = provider_class
        logger.info(f"注册数据提供者: {source_type.value} -> {provider_class.__name__}")

    def get_provider_class(self, source_type: DataSourceType) -> Optional[Type]:
        """获取数据提供者类"""
        return self._providers.get(source_type)

    def set_config(self, source_type: DataSourceType, config: DataSourceConfig):
        """设置数据源配置"""
        self._configs[source_type] = config

    def get_config(self, source_type: DataSourceType) -> Optional[DataSourceConfig]:
        """获取数据源配置"""
        return self._configs.get(source_type)


class DataSourceManager:
    """
    数据源管理器 - 核心组件
    负责根据配置管理所有数据源
    """

    def __init__(self, config=None):
        """
        初始化数据源管理器
        
        Args:
            config: 配置对象，如果为None则从全局配置获取
        """
        self.config = config or get_config()
        self.registry = DataSourceRegistry()
        self.providers: Dict[DataSourceType, Any] = {}
        self.initialized = False

        # 数据源状态
        self._source_status: Dict[DataSourceType, Dict[str, Any]] = {}

        # 策略模式 - 数据源选择策略
        self._selection_strategy = None

        # 初始化配置
        self._load_configs()

    def _load_configs(self):
        """从配置文件加载数据源配置"""
        # QMT配置
        if hasattr(self.config, 'qmt') and self.config.qmt:
            self.registry.set_config(
                DataSourceType.QMT,
                DataSourceConfig(
                    enabled=self.config.qmt.enabled,
                    priority=1,
                    timeout=10,
                    config=self.config.qmt.model_dump() if hasattr(self.config.qmt, 'model_dump') else {}
                )
            )

        # 数据提供者配置
        if hasattr(self.config, 'data_providers') and self.config.data_providers:
            providers_config = self.config.data_providers

            # AKShare配置
            if hasattr(providers_config, 'akshare_proxy'):
                akshare_cfg = providers_config.akshare_proxy
                self.registry.set_config(
                    DataSourceType.AKSHARE,
                    DataSourceConfig(
                        enabled=akshare_cfg.get('enabled', False),
                        priority=akshare_cfg.get('priority', 3),
                        timeout=akshare_cfg.get('timeout', 30),
                        config=akshare_cfg
                    )
                )

            # CloudFlare配置
            if hasattr(providers_config, 'cloudflare_proxy'):
                cf_cfg = providers_config.cloudflare_proxy
                self.registry.set_config(
                    DataSourceType.CLOUDFLARE,
                    DataSourceConfig(
                        enabled=cf_cfg.get('enabled', False),
                        priority=cf_cfg.get('priority', 2),
                        timeout=cf_cfg.get('timeout', 30),
                        config=cf_cfg
                    )
                )

    async def initialize(self):
        """初始化所有启用的数据源"""
        logger.info("初始化数据源管理器...")

        # 只初始化配置中启用的数据源
        for source_type in DataSourceType:
            config = self.registry.get_config(source_type)

            if not config or not config.enabled:
                logger.info(f"数据源 {source_type.value} 未启用，跳过初始化")
                self._source_status[source_type] = {
                    "available": False,
                    "reason": "disabled_by_config"
                }
                continue

            # 尝试初始化数据源
            try:
                provider = await self._create_provider(source_type, config)
                if provider:
                    self.providers[source_type] = provider
                    self._source_status[source_type] = {
                        "available": True,
                        "initialized_at": time.time()
                    }
                    logger.info(f"✓ 数据源 {source_type.value} 初始化成功")
                else:
                    self._source_status[source_type] = {
                        "available": False,
                        "reason": "initialization_failed"
                    }
                    logger.warning(f"✗ 数据源 {source_type.value} 初始化失败")

            except Exception as e:
                logger.error(f"初始化数据源 {source_type.value} 时出错: {e}")
                self._source_status[source_type] = {
                    "available": False,
                    "reason": str(e)
                }

        self.initialized = True
        logger.info(f"数据源管理器初始化完成，可用数据源: {self.get_available_sources()}")

    async def _create_provider(self, source_type: DataSourceType, config: DataSourceConfig):
        """创建数据提供者实例"""
        # 动态导入，避免不必要的依赖
        if source_type == DataSourceType.QMT:
            try:
                from deepsearch.data_providers.datafeed.qmt.provider import QMTDataProvider
                provider = QMTDataProvider()
                if hasattr(provider, 'initialize'):
                    await provider.initialize()
                return provider
            except ImportError as e:
                logger.warning(f"QMT模块未安装: {e}")
                return None

        elif source_type == DataSourceType.AKSHARE:
            if not config.enabled:
                logger.info("AKShare被配置禁用")
                return None
            try:
                from deepsearch.data_providers.implementations.akshare.akshare_direct import AKShareDirectProvider
                provider = AKShareDirectProvider()
                if hasattr(provider, 'initialize'):
                    await provider.initialize()
                return provider
            except ImportError as e:
                logger.warning(f"AKShare模块未安装: {e}")
                return None

        elif source_type == DataSourceType.CLOUDFLARE:
            if not config.enabled:
                logger.info("CloudFlare被配置禁用")
                return None
            try:
                from deepsearch.data_providers.implementations.cloudflare.cloudflare import ProxyDataProvider
                provider = ProxyDataProvider()
                if hasattr(provider, 'initialize'):
                    await provider.initialize()
                return provider
            except ImportError as e:
                logger.warning(f"CloudFlare模块未安装: {e}")
                return None

        return None

    def get_available_sources(self) -> List[DataSourceType]:
        """获取所有可用的数据源"""
        return [
            source_type
            for source_type, status in self._source_status.items()
            if status.get("available", False)
        ]

    def is_source_available(self, source_type: DataSourceType) -> bool:
        """检查数据源是否可用"""
        return self._source_status.get(source_type, {}).get("available", False)

    async def get_data(
            self,
            data_type: str,
            symbol: str,
            preferred_source: Optional[DataSourceType] = None,
            **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        统一的数据获取接口
        
        Args:
            data_type: 数据类型 (realtime_quote, orderbook, kline等)
            symbol: 股票代码
            preferred_source: 首选数据源
            **kwargs: 其他参数
            
        Returns:
            数据字典，包含source字段标识来源
        """
        # 检查是否初始化
        if not self.initialized:
            await self.initialize()

        # 获取可用数据源
        available_sources = self.get_available_sources()
        if not available_sources:
            logger.error("没有可用的数据源")
            return None

        # 选择数据源
        sources_to_try = self._select_sources(available_sources, preferred_source)

        # 依次尝试数据源
        for source_type in sources_to_try:
            provider = self.providers.get(source_type)
            if not provider:
                continue

            try:
                # 根据数据类型调用相应方法
                if data_type == "realtime_quote":
                    data = await self._get_realtime_quote(provider, symbol)
                elif data_type == "orderbook":
                    data = await self._get_orderbook(provider, symbol)
                elif data_type == "kline":
                    data = await self._get_kline(provider, symbol, **kwargs)
                else:
                    logger.warning(f"不支持的数据类型: {data_type}")
                    continue

                if data:
                    # 添加数据源标识
                    data["source"] = source_type.value
                    data["timestamp"] = time.time()
                    return data

            except Exception as e:
                logger.error(f"从 {source_type.value} 获取数据失败: {e}")
                continue

        logger.warning(f"所有数据源都无法获取 {symbol} 的 {data_type} 数据")
        return None

    def _select_sources(
            self,
            available_sources: List[DataSourceType],
            preferred_source: Optional[DataSourceType] = None
    ) -> List[DataSourceType]:
        """
        选择数据源顺序
        
        Args:
            available_sources: 可用数据源列表
            preferred_source: 首选数据源
            
        Returns:
            按优先级排序的数据源列表
        """
        result = []

        # 如果有首选源且可用，放在第一位
        if preferred_source and preferred_source in available_sources:
            result.append(preferred_source)
            available_sources = [s for s in available_sources if s != preferred_source]

        # 按配置的优先级排序剩余数据源
        priorities = {}
        for source_type in available_sources:
            config = self.registry.get_config(source_type)
            if config:
                priorities[source_type] = config.priority
            else:
                priorities[source_type] = 999

        # 按优先级排序（数字越小优先级越高）
        sorted_sources = sorted(available_sources, key=lambda x: priorities[x])
        result.extend(sorted_sources)

        return result

    async def _get_realtime_quote(self, provider, symbol: str) -> Optional[Dict[str, Any]]:
        """获取实时行情"""
        if hasattr(provider, 'get_realtime_quote'):
            return await provider.get_realtime_quote(symbol)
        return None

    async def _get_orderbook(self, provider, symbol: str) -> Optional[Dict[str, Any]]:
        """获取盘口数据"""
        if hasattr(provider, 'get_orderbook'):
            return await provider.get_orderbook(symbol)
        elif hasattr(provider, 'get_latest_orderbook'):
            return provider.get_latest_orderbook(symbol)
        return None

    async def _get_kline(self, provider, symbol: str, **kwargs) -> Optional[Dict[str, Any]]:
        """获取K线数据"""
        if hasattr(provider, 'get_kline_data'):
            return await provider.get_kline_data(symbol, **kwargs)
        elif hasattr(provider, 'get_stock_hist'):
            return await provider.get_stock_hist(symbol, **kwargs)
        return None

    def get_status_report(self) -> Dict[str, Any]:
        """获取状态报告"""
        return {
            "initialized": self.initialized,
            "sources": {
                source_type.value: {
                    "available": status.get("available", False),
                    "reason": status.get("reason", ""),
                    "config": {
                        "enabled": config.enabled if (config := self.registry.get_config(source_type)) else False,
                        "priority": config.priority if (config := self.registry.get_config(source_type)) else 999
                    }
                }
                for source_type, status in self._source_status.items()
            },
            "available_count": len(self.get_available_sources())
        }


# 全局实例
_data_source_manager: Optional[DataSourceManager] = None


def get_data_source_manager() -> DataSourceManager:
    """获取全局数据源管理器实例"""
    global _data_source_manager
    if _data_source_manager is None:
        _data_source_manager = DataSourceManager()
    return _data_source_manager


async def initialize_data_sources():
    """初始化数据源系统"""
    manager = get_data_source_manager()
    await manager.initialize()
    return manager
