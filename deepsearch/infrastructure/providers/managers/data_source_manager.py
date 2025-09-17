"""
统一的数据源管理器 - 重构版本
配置驱动、策略模式、依赖注入
"""
import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, List, Type

from loguru import logger

from deepsearch.config import get_config
from deepsearch.infrastructure.providers.interfaces.base import DataSourceType
from deepsearch.infrastructure.providers.config.timeout_config import (
    get_timeout, adjust_timeout, RequestType as TimeoutRequestType
)


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
        # 获取类名，处理Mock对象
        class_name = getattr(provider_class, '__name__', str(provider_class))
        logger.info(f"注册数据提供者: {source_type.value} -> {class_name}")

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

    _instance = None  # 单例实例

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

    @classmethod
    def get_instance(cls, config=None):
        """
        获取数据源管理器单例实例

        Args:
            config: 配置对象，仅在第一次创建时使用

        Returns:
            DataSourceManager实例
        """
        if cls._instance is None:
            cls._instance = cls(config)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        """重置单例实例（用于测试）"""
        cls._instance = None

    def _load_configs(self):
        """从配置文件加载数据源配置"""
        # 优先读取新的data_sources配置
        if hasattr(self.config, 'data_sources') and self.config.data_sources:
            self._load_data_sources_config()
        # 兼容旧的配置格式
        elif hasattr(self.config, 'amazingdata') and self.config.amazingdata:
            amazing_config = self.config.amazingdata
            self.registry.set_config(
                DataSourceType.AMAZINGDATA,
                DataSourceConfig(
                    enabled=amazing_config.enabled,
                    priority=getattr(amazing_config, 'priority', 1),
                    timeout=getattr(amazing_config.connection, 'timeout', 10) if hasattr(amazing_config, 'connection') else 10,
                    config=amazing_config.model_dump() if hasattr(amazing_config, 'model_dump') else {}
                )
            )
        
        # QMT配置
        if hasattr(self.config, 'qmt') and self.config.qmt:
            self.registry.set_config(
                DataSourceType.QMT,
                DataSourceConfig(
                    enabled=self.config.qmt.enabled,
                    priority=2,  # 第二优先级
                    timeout=10,
                    config=self.config.qmt.model_dump() if hasattr(self.config.qmt, 'model_dump') else {}
                )
            )

        # 数据提供者配置
        if hasattr(self.config, 'data_providers') and self.config.data_providers:
            providers_config = self.config.data_providers
            
            # AmazingData配置 (从data_providers中)
            if hasattr(providers_config, 'amazingdata'):
                amazing_cfg = providers_config.amazingdata
                self.registry.set_config(
                    DataSourceType.AMAZINGDATA,
                    DataSourceConfig(
                        enabled=getattr(amazing_cfg, 'enabled', False) if hasattr(amazing_cfg, 'enabled') else amazing_cfg.get('enabled', False) if isinstance(amazing_cfg, dict) else False,
                        priority=getattr(amazing_cfg, 'priority', 1) if hasattr(amazing_cfg, 'priority') else amazing_cfg.get('priority', 1) if isinstance(amazing_cfg, dict) else 1,
                        timeout=getattr(amazing_cfg, 'timeout', 10) if hasattr(amazing_cfg, 'timeout') else amazing_cfg.get('timeout', 10) if isinstance(amazing_cfg, dict) else 10,
                        config=amazing_cfg.model_dump() if hasattr(amazing_cfg, 'model_dump') else amazing_cfg if isinstance(amazing_cfg, dict) else {}
                    )
                )

            # QMT配置 (从data_providers中)
            if hasattr(providers_config, 'qmt'):
                qmt_cfg = providers_config.qmt
                self.registry.set_config(
                    DataSourceType.QMT,
                    DataSourceConfig(
                        enabled=getattr(qmt_cfg, 'enabled', False) if hasattr(qmt_cfg, 'enabled') else qmt_cfg.get('enabled', False) if isinstance(qmt_cfg, dict) else False,
                        priority=getattr(qmt_cfg, 'priority', 2) if hasattr(qmt_cfg, 'priority') else qmt_cfg.get('priority', 2) if isinstance(qmt_cfg, dict) else 2,
                        timeout=getattr(qmt_cfg, 'timeout', 10) if hasattr(qmt_cfg, 'timeout') else qmt_cfg.get('timeout', 10) if isinstance(qmt_cfg, dict) else 10,
                        config=qmt_cfg.model_dump() if hasattr(qmt_cfg, 'model_dump') else qmt_cfg if isinstance(qmt_cfg, dict) else {}
                    )
                )

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

    def _load_data_sources_config(self):
        """加载新的data_sources配置格式"""
        data_sources = self.config.data_sources
        providers = data_sources.get('providers', {})

        # 映射配置到DataSourceType
        type_mapping = {
            'amazingdata': DataSourceType.AMAZINGDATA,
            'qmt': DataSourceType.QMT,
            'cloudflare': DataSourceType.CLOUDFLARE,
            'cloudflare_proxy': DataSourceType.CLOUDFLARE,  # 映射到CLOUDFLARE
            'akshare': DataSourceType.AKSHARE,
            'akshare_proxy': DataSourceType.AKSHARE,  # 映射到AKSHARE而不是AKSHARE_PROXY
            'miniqmt': DataSourceType.QMT,  # 映射到QMT而不是MINIQMT
        }

        for provider_name, provider_config in providers.items():
            if provider_name not in type_mapping:
                logger.warning(f"未知的数据源类型: {provider_name}")
                continue

            source_type = type_mapping[provider_name]

            # 创建DataSourceConfig
            config_obj = DataSourceConfig(
                enabled=provider_config.get('enabled', False),
                priority=provider_config.get('priority', 999),
                timeout=provider_config.get('config', {}).get('timeout', 30),
                config=provider_config.get('config', {})
            )

            self.registry.set_config(source_type, config_obj)
            logger.debug(f"加载数据源配置: {provider_name} -> {source_type.value}, enabled={config_obj.enabled}")

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
                    logger.info(f"[SUCCESS] 数据源 {source_type.value} 初始化成功")
                else:
                    self._source_status[source_type] = {
                        "available": False,
                        "reason": "initialization_failed"
                    }
                    logger.warning(f"[FAILED] 数据源 {source_type.value} 初始化失败")

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
        if source_type == DataSourceType.AMAZINGDATA:
            if not config.enabled:
                logger.info("AmazingData被配置禁用")
                return None
            try:
                from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
                    AmazingDataProvider, 
                    AmazingDataConfig
                )
                # 从配置字典创建 AmazingDataConfig 对象
                cfg_dict = config.config
                if hasattr(cfg_dict, 'model_dump'):
                    cfg_dict = cfg_dict.model_dump()
                elif not isinstance(cfg_dict, dict):
                    cfg_dict = {}
                
                # 从配置中提取连接参数
                connection = cfg_dict.get('connection', {})
                amazing_config = AmazingDataConfig(
                    username=connection.get('username', ''),
                    password=connection.get('password', ''),
                    host=connection.get('host', 'localhost'),
                    port=connection.get('port', 8600),
                    heartbeat_interval=connection.get('heartbeat_interval', 60),
                    timeout=connection.get('timeout', 10)
                )
                
                provider = AmazingDataProvider(amazing_config)
                if hasattr(provider, 'initialize'):
                    init_method = getattr(provider, 'initialize')
                    if callable(init_method):
                        result = init_method()
                        if asyncio.iscoroutine(result):
                            await result
                return provider
            except ImportError as e:
                logger.warning(f"AmazingData模块未安装: {e}")
                return None
            except Exception as e:
                logger.error(f"创建AmazingData提供者失败: {e}")
                return None
        
        elif source_type == DataSourceType.QMT:
            try:
                from deepsearch.infrastructure.providers.datafeed.qmt.provider import QMTDataProvider
                provider = QMTDataProvider()
                if hasattr(provider, 'initialize'):
                    init_method = getattr(provider, 'initialize')
                    if callable(init_method):
                        result = init_method()
                        if asyncio.iscoroutine(result):
                            await result
                return provider
            except ImportError as e:
                logger.warning(f"QMT模块未安装: {e}")
                return None

        elif source_type == DataSourceType.AKSHARE:
            if not config.enabled:
                logger.info("AKShare被配置禁用")
                return None
            try:
                from deepsearch.infrastructure.providers.implementations.akshare.akshare_direct import AKShareDirectProvider
                provider = AKShareDirectProvider()
                if hasattr(provider, 'initialize'):
                    init_method = getattr(provider, 'initialize')
                    if callable(init_method):
                        result = init_method()
                        if asyncio.iscoroutine(result):
                            await result
                return provider
            except ImportError as e:
                logger.warning(f"AKShare模块未安装: {e}")
                return None

        elif source_type == DataSourceType.CLOUDFLARE:
            if not config.enabled:
                logger.info("CloudFlare被配置禁用")
                return None
            try:
                from deepsearch.infrastructure.providers.implementations.cloudflare.cloudflare import ProxyDataProvider
                provider = ProxyDataProvider()
                if hasattr(provider, 'initialize'):
                    init_method = getattr(provider, 'initialize')
                    if callable(init_method):
                        result = init_method()
                        if asyncio.iscoroutine(result):
                            await result
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

    async def get_stock_list(self, limit: int = None, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """
        获取股票列表

        Args:
            limit: 限制返回数量
            **kwargs: 其他参数

        Returns:
            股票列表
        """
        if not self.initialized:
            await self.initialize()

        # 尝试每个可用的数据源
        for source_type in self.providers:
            try:
                provider = self.providers.get(source_type)
                if provider and hasattr(provider, 'get_stock_list'):
                    method = getattr(provider, 'get_stock_list')
                    if callable(method):
                        result = method(limit=limit, **kwargs)
                        if asyncio.iscoroutine(result):
                            result = await result
                        if result:
                            logger.info(f"从{source_type}获取股票列表成功")
                            return result
            except Exception as e:
                logger.error(f"从{source_type}获取股票列表失败: {e}")
                continue

        logger.error("所有数据源均无法获取股票列表")
        return None

    async def get_kline_data(
        self,
        symbol: str,
        period: str = '1d',
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取K线数据

        Args:
            symbol: 股票代码
            period: 周期 (1m, 5m, 15m, 30m, 60m, 1d, 1w, 1M)
            start_date: 开始日期
            end_date: 结束日期
            limit: 限制数量
            **kwargs: 其他参数

        Returns:
            K线数据列表
        """
        if not self.initialized:
            await self.initialize()

        # 尝试每个可用的数据源
        for source_type in self.providers:
            try:
                provider = self.providers.get(source_type)
                if provider and hasattr(provider, 'get_kline_data'):
                    method = getattr(provider, 'get_kline_data')
                    if callable(method):
                        result = method(
                            symbol=symbol,
                            period=period,
                            start_date=start_date,
                            end_date=end_date,
                            limit=limit,
                            **kwargs
                        )
                        if asyncio.iscoroutine(result):
                            result = await result
                        if result:
                            logger.info(f"从{source_type}获取K线数据成功: {symbol}")
                            return result
            except Exception as e:
                logger.error(f"从{source_type}获取K线数据失败: {e}")
                continue

        logger.error(f"所有数据源均无法获取K线数据: {symbol}")
        return None

    async def get_realtime_quotes(
        self,
        symbols: List[str],
        **kwargs
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        获取实时行情

        Args:
            symbols: 股票代码列表
            **kwargs: 其他参数

        Returns:
            实时行情字典 {symbol: quote_data}
        """
        if not self.initialized:
            await self.initialize()

        # 尝试每个可用的数据源
        for source_type in self.providers:
            try:
                provider = self.providers.get(source_type)
                if provider and hasattr(provider, 'get_realtime_quotes'):
                    method = getattr(provider, 'get_realtime_quotes')
                    if callable(method):
                        result = method(symbols=symbols, **kwargs)
                        if asyncio.iscoroutine(result):
                            result = await result
                        if result:
                            logger.info(f"从{source_type}获取实时行情成功")
                            return result
            except Exception as e:
                logger.error(f"从{source_type}获取实时行情失败: {e}")
                continue

        logger.error("所有数据源均无法获取实时行情")
        return None

    def _get_provider_for_request(self, request_type: str = None) -> Optional[Any]:
        """
        根据请求类型获取合适的数据提供者

        Args:
            request_type: 请求类型

        Returns:
            数据提供者实例
        """
        # 按优先级排序的可用数据源
        available_sources = self.get_available_sources()

        for source_type in available_sources:
            provider = self.providers.get(source_type)
            if provider:
                return provider

        return None

    def get_provider(self, source_type: DataSourceType = None) -> Optional[Any]:
        """
        获取指定的数据提供者

        Args:
            source_type: 数据源类型

        Returns:
            数据提供者实例
        """
        if source_type is None:
            # 返回优先级最高的可用提供者
            return self._get_provider_for_request()

        return self.providers.get(source_type)

    async def execute_with_fallback(self, method_name: str, *args, **kwargs) -> Optional[Any]:
        """
        执行方法，带故障转移

        Args:
            method_name: 方法名
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            执行结果
        """
        if not self.initialized:
            await self.initialize()

        # 尝试每个可用的数据源
        for source_type in self.get_available_sources():
            try:
                provider = self.providers.get(source_type)
                if provider and hasattr(provider, method_name):
                    method = getattr(provider, method_name)
                    if callable(method):
                        result = method(*args, **kwargs)
                        if asyncio.iscoroutine(result):
                            result = await result
                        if result is not None:
                            logger.info(f"通过{source_type}执行{method_name}成功")
                            return result
            except Exception as e:
                logger.error(f"通过{source_type}执行{method_name}失败: {e}")
                continue

        logger.error(f"所有数据源均无法执行{method_name}")
        return None

    async def health_check(self) -> Dict[str, Any]:
        """
        执行健康检查

        Returns:
            健康状态报告
        """
        health_status = {}

        for source_type, provider in self.providers.items():
            try:
                # 检查provider是否有health_check方法
                if hasattr(provider, 'health_check'):
                    status = await provider.health_check() if asyncio.iscoroutinefunction(provider.health_check) else provider.health_check()
                    health_status[source_type.value] = {
                        'status': 'healthy' if status else 'unhealthy',
                        'details': status
                    }
                else:
                    # 基础健康检查：检查provider是否可用
                    health_status[source_type.value] = {
                        'status': 'healthy' if provider else 'unhealthy',
                        'details': {'available': bool(provider)}
                    }
            except Exception as e:
                health_status[source_type.value] = {
                    'status': 'error',
                    'details': {'error': str(e)}
                }

        return {
            'overall': 'healthy' if any(s['status'] == 'healthy' for s in health_status.values()) else 'unhealthy',
            'sources': health_status,
            'available_count': len([s for s in health_status.values() if s['status'] == 'healthy'])
        }

    async def close(self):
        """
        关闭数据源管理器，释放资源
        """
        logger.info("正在关闭数据源管理器...")

        for source_type, provider in self.providers.items():
            try:
                if hasattr(provider, 'close'):
                    if asyncio.iscoroutinefunction(provider.close):
                        await provider.close()
                    else:
                        provider.close()
                    logger.info(f"已关闭数据源: {source_type}")
            except Exception as e:
                logger.error(f"关闭数据源{source_type}时出错: {e}")

        self.providers.clear()
        self.initialized = False
        logger.info("数据源管理器已关闭")

    async def subscribe_realtime(self, symbols: List[str], callback: callable) -> bool:
        """
        订阅实时数据

        Args:
            symbols: 股票代码列表
            callback: 回调函数

        Returns:
            订阅是否成功
        """
        if not self.initialized:
            await self.initialize()

        # 尝试每个可用的数据源
        for source_type in self.get_available_sources():
            try:
                provider = self.providers.get(source_type)
                if provider and hasattr(provider, 'subscribe_realtime'):
                    method = getattr(provider, 'subscribe_realtime')
                    if callable(method):
                        result = method(symbols, callback)
                        if asyncio.iscoroutine(result):
                            result = await result
                        if result:
                            logger.info(f"通过{source_type}订阅实时数据成功")
                            return True
            except Exception as e:
                logger.error(f"通过{source_type}订阅实时数据失败: {e}")
                continue

        logger.error("所有数据源均无法订阅实时数据")
        return False

    def set_primary_source(self, source_type: DataSourceType) -> bool:
        """
        设置主数据源

        Args:
            source_type: 数据源类型

        Returns:
            bool: 是否设置成功
        """
        # 检查数据源是否可用
        if not self.is_source_available(source_type):
            logger.error(f"数据源 {source_type.value} 不可用，无法设置为主数据源")
            return False

        # 更新配置优先级，将指定数据源设为最高优先级
        config = self.registry.get_config(source_type)
        if config:
            # 将所有其他数据源优先级降低
            for other_type in self.get_available_sources():
                if other_type != source_type:
                    other_config = self.registry.get_config(other_type)
                    if other_config and other_config.priority < 100:
                        other_config.priority += 10

            # 设置主数据源优先级为最高
            config.priority = 1
            logger.info(f"已设置 {source_type.value} 为主数据源")
            return True
        else:
            logger.error(f"无法获取数据源 {source_type.value} 的配置")
            return False

    def get_available_providers(self) -> List[DataSourceType]:
        """获取所有可用的数据提供者（别名方法）"""
        return self.get_available_sources()

    def get_providers_by_priority(self) -> List[DataSourceType]:
        """按优先级排序获取所有数据提供者"""
        available_sources = self.get_available_sources()

        # 按配置的优先级排序
        priorities = {}
        for source_type in available_sources:
            config = self.registry.get_config(source_type)
            if config:
                priorities[source_type] = config.priority
            else:
                priorities[source_type] = 999

        # 按优先级排序（数字越小优先级越高）
        sorted_sources = sorted(available_sources, key=lambda x: priorities[x])
        return sorted_sources


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
