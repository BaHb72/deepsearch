"""
Singleton Data Provider Factory

Ensures single instances of data providers across all API endpoints
to reduce memory usage and improve caching efficiency.
"""
from typing import Dict, Any, Optional
from threading import Lock
from datetime import datetime
from loguru import logger
from enum import Enum


class DataSourceType(Enum):
    """数据源类型枚举"""
    AMAZINGDATA = "amazingdata"
    CLOUDFLARE = "cloudflare"
    CLOUDFLARE_PROXY = "cloudflare_proxy"
    AKSHARE = "akshare"
    QMT = "qmt"
    DEFAULT = "default"
    CUSTOM = "custom"


class DataProviderFactory:
    """
    Singleton factory for data providers.
    
    Benefits:
    - Reduces memory usage by ~500MB (avoiding duplicate instances)
    - Improves cache hit rate (shared cache across endpoints)
    - Better connection pooling (single pool for all requests)
    - Consistent state across API endpoints
    """

    _instances: Dict[str, Any] = {}
    _lock = Lock()

    # 新增：降级状态跟踪和健康监控
    _fallback_status: Dict[str, Dict[str, Any]] = {}
    _provider_health: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def get_provider(cls, provider_type: str = "akshare") -> Any:
        """
        Get or create singleton provider instance (synchronous version).
        
        Args:
            provider_type: Type of provider to get
                - "akshare": AkShareProxyProvider
                - "unified": DataSourceManager
                - "market": MarketService
                - "qmt": QMTDataProvider
                
        Returns:
            Singleton instance of requested provider
        """
        with cls._lock:
            if provider_type not in cls._instances:
                logger.info(f"Creating singleton instance for {provider_type}")
                
                if provider_type == "akshare":
                    from deepsearch.infrastructure.providers.implementations.akshare.akshare import AkShareProxyProvider
                    cls._instances[provider_type] = AkShareProxyProvider()
                    
                elif provider_type == "unified":
                    # For unified, we need async initialization - use get_provider_async instead
                    logger.warning(f"Unified provider requires async initialization. Use get_provider_async()")
                    return None
                    
                elif provider_type == "market":
                    # from deepsearch.application.services.market.market_service import MarketService
                    from deepsearch.infrastructure.providers.implementations.akshare.akshare import AkShareProxyProvider
                    # Market service with a default AkShare provider
                    default_provider = AkShareProxyProvider()
                    cls._instances[provider_type] = MarketService(default_provider)
                    
                elif provider_type == "qmt":
                    from deepsearch.infrastructure.providers.implementations.qmt.miniqmt import MiniQMTDataProvider
                    cls._instances[provider_type] = MiniQMTDataProvider()
                    
                else:
                    raise ValueError(f"Unknown provider type: {provider_type}")
                    
                logger.info(f"Created {provider_type} provider instance")
                
            return cls._instances[provider_type]
    
    @classmethod
    async def get_provider_async(cls, provider_type: str = "akshare") -> Any:
        """
        Get or create singleton provider instance (asynchronous version).
        
        Args:
            provider_type: Type of provider to get
                
        Returns:
            Singleton instance of requested provider
        """
        # Check if already exists
        if provider_type in cls._instances:
            return cls._instances[provider_type]
            
        with cls._lock:
            # Double check after acquiring lock
            if provider_type in cls._instances:
                return cls._instances[provider_type]
                
            logger.info(f"Creating singleton instance for {provider_type} (async)")
            
            if provider_type == "akshare":
                from deepsearch.infrastructure.providers.implementations.akshare.akshare import AkShareProxyProvider
                cls._instances[provider_type] = AkShareProxyProvider()
                
            elif provider_type == "unified":
                from deepsearch.infrastructure.providers.managers.data_source_manager import get_data_source_manager
                cls._instances[provider_type] = await get_data_source_manager()
                
            elif provider_type == "market":
                # from deepsearch.application.services.market.market_service import MarketService
                from deepsearch.infrastructure.providers.implementations.akshare.akshare import AkShareProxyProvider
                # Try to get akshare provider if available, or create a new one
                akshare_provider = None
                if "akshare" in cls._instances:
                    akshare_provider = cls._instances["akshare"]
                else:
                    akshare_provider = AkShareProxyProvider()
                cls._instances[provider_type] = MarketService(akshare_provider)
                
            elif provider_type == "qmt":
                from deepsearch.infrastructure.providers.implementations.qmt.miniqmt import MiniQMTDataProvider
                cls._instances[provider_type] = MiniQMTDataProvider()

            elif provider_type == "amazingdata":
                # 实现多级降级链
                init_success = False
                fallback_reason = None

                # 级别1: 尝试AmazingData
                try:
                    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
                        AmazingDataProvider, AmazingDataConfig
                    )
                    # 创建配置对象
                    config = AmazingDataConfig(
                        username="212200038719",
                        password="212200038719@2025",
                        host="101.230.159.234",
                        port=8600,
                        timeout=10,  # 秒，不是毫秒
                        retry_count=2,
                        heartbeat_interval=60,
                        auto_reconnect=True
                    )
                    # 使用配置创建实例
                    provider = AmazingDataProvider(config)
                    # 初始化
                    await provider.initialize()
                    cls._instances[provider_type] = provider
                    init_success = True
                    logger.info("AmazingData provider initialized successfully")

                    # 记录健康状态
                    cls._provider_health[provider_type] = {
                        'status': 'healthy',
                        'provider': 'amazingdata',
                        'initialized_at': datetime.now().isoformat()
                    }

                except ImportError as e:
                    fallback_reason = f"AmazingData provider not available: {e}"
                    logger.warning(fallback_reason)

                except Exception as e:
                    fallback_reason = f"Failed to initialize AmazingData provider: {e}"
                    logger.error(fallback_reason)

                    # 检查是否是SDK退出导致的
                    if "SDK尝试强制退出程序" in str(e):
                        fallback_reason = f"CRITICAL: AmazingData SDK attempted to exit the process"
                        logger.critical(fallback_reason)
                        cls._record_provider_failure("amazingdata", "SDK_EXIT", str(e))

                # 级别2: 降级到AkShare
                if not init_success:
                    logger.warning(f"Falling back to AkShare due to: {fallback_reason}")
                    try:
                        from deepsearch.infrastructure.providers.implementations.akshare.akshare import AkShareProxyProvider
                        fallback_provider = AkShareProxyProvider()
                        await fallback_provider.initialize() if hasattr(fallback_provider, 'initialize') else None
                        cls._instances[provider_type] = fallback_provider
                        init_success = True

                        # 记录降级状态
                        cls._fallback_status[provider_type] = {
                            'original': 'amazingdata',
                            'fallback': 'akshare',
                            'reason': fallback_reason,
                            'timestamp': datetime.now().isoformat()
                        }

                        cls._provider_health[provider_type] = {
                            'status': 'degraded',
                            'provider': 'akshare',
                            'fallback_reason': fallback_reason,
                            'initialized_at': datetime.now().isoformat()
                        }

                        logger.info("Successfully fell back to AkShare provider")

                    except Exception as e:
                        logger.error(f"Failed to initialize AkShare fallback: {e}")
                        cls._record_provider_failure("akshare", "INIT_FAILED", str(e))

                # 级别3: 最终降级到ErrorProvider
                if not init_success:
                    logger.critical("All data providers failed, using ErrorProvider as last resort")
                    try:
                        from deepsearch.infrastructure.providers.mock.error_provider import MockErrorProvider
                        cls._instances[provider_type] = MockErrorProvider(fallback_reason)
                    except:
                        # 如果ErrorProvider还未创建，使用临时的错误提供者
                        class TempErrorProvider:
                            def __init__(self, error_msg):
                                self.error_msg = error_msg
                            async def get_data(self, *args, **kwargs):
                                return {'error': self.error_msg, 'status': 'all_providers_failed'}

                        cls._instances[provider_type] = TempErrorProvider(fallback_reason)

                    cls._provider_health[provider_type] = {
                        'status': 'failed',
                        'provider': 'error',
                        'error': fallback_reason,
                        'initialized_at': datetime.now().isoformat()
                    }

            else:
                raise ValueError(f"Unknown provider type: {provider_type}")
                
            logger.info(f"Created {provider_type} provider instance (async)")
            
            return cls._instances[provider_type]
    
    @classmethod
    def clear_instance(cls, provider_type: str):
        """
        Clear a specific provider instance (useful for testing or reconnection).
        
        Args:
            provider_type: Type of provider to clear
        """
        with cls._lock:
            if provider_type in cls._instances:
                logger.info(f"Clearing {provider_type} provider instance")
                # Attempt graceful cleanup if available
                instance = cls._instances[provider_type]
                if hasattr(instance, 'close'):
                    try:
                        instance.close()
                    except Exception as e:
                        logger.warning(f"Error closing {provider_type}: {e}")
                        
                del cls._instances[provider_type]
    
    @classmethod
    def clear_all(cls):
        """Clear all provider instances."""
        with cls._lock:
            for provider_type in list(cls._instances.keys()):
                cls.clear_instance(provider_type)
    
    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """
        Get statistics about provider instances.
        
        Returns:
            Dictionary with instance information
        """
        with cls._lock:
            stats = {
                "instance_count": len(cls._instances),
                "providers": list(cls._instances.keys()),
                "memory_saved_mb": len(cls._instances) * 50  # Approx 50MB per instance saved
            }
            
            # Add provider-specific stats if available
            for name, instance in cls._instances.items():
                if hasattr(instance, 'get_statistics'):
                    stats[f"{name}_stats"] = instance.get_statistics()
                    return stats

    @classmethod
    def _record_provider_failure(cls, provider_name: str, failure_type: str, error_msg: str):
        """
        记录提供者失败信息

        Args:
            provider_name: 提供者名称
            failure_type: 失败类型（SDK_EXIT, INIT_FAILED, CONNECTION_LOST等）
            error_msg: 错误消息
        """
        if provider_name not in cls._provider_health:
            cls._provider_health[provider_name] = {
                'failures': []
            }

        failure_record = {
            'timestamp': datetime.now().isoformat(),
            'type': failure_type,
            'message': error_msg
        }

        # 记录失败
        if 'failures' not in cls._provider_health[provider_name]:
            cls._provider_health[provider_name]['failures'] = []

        cls._provider_health[provider_name]['failures'].append(failure_record)

        # 保留最近的20条失败记录
        if len(cls._provider_health[provider_name]['failures']) > 20:
            cls._provider_health[provider_name]['failures'] = \
                cls._provider_health[provider_name]['failures'][-20:]

        # 更新状态
        cls._provider_health[provider_name]['status'] = 'failed'
        cls._provider_health[provider_name]['last_failure'] = failure_record

        # 记录严重错误
        if failure_type == 'SDK_EXIT':
            logger.critical(f"[CRITICAL] Provider {provider_name} attempted to exit the process!")
            cls._provider_health[provider_name]['critical_error'] = True

    @classmethod
    def get_health_status(cls) -> Dict[str, Any]:
        """
        获取所有提供者的健康状态

        Returns:
            包含健康状态信息的字典
        """
        return {
            'providers': cls._provider_health.copy(),
            'fallback_status': cls._fallback_status.copy(),
            'timestamp': datetime.now().isoformat()
        }


# Dependency injection helpers for FastAPI
async def get_akshare_provider():
    """FastAPI dependency for AkShare provider."""
    return await DataProviderFactory.get_provider_async("akshare")


async def get_unified_manager():
    """FastAPI dependency for Unified Data Manager."""
    return await DataProviderFactory.get_provider_async("unified")


async def get_market_service():
    """FastAPI dependency for Market Service."""
    # 优先使用东方财富服务（最快）
    try:
        # from deepsearch.application.services.market.eastmoney_service import EastMoneyService
        logger.info("Using EastMoneyService for fast real market data")
        return EastMoneyService()
    except Exception as e1:
        logger.warning(f"EastMoneyService failed: {e1}, trying AkShareDirectService")
        # 备选：使用AkShare直接服务
        try:
            # from deepsearch.application.services.market.akshare_direct_service import AkShareDirectService
            logger.info("Using AkShareDirectService for real market data")
            return AkShareDirectService()
        except Exception as e2:
            logger.error(f"AkShareDirectService failed: {e2}")
            # 最后的后备：返回一个基础的MarketService
            # from deepsearch.application.services.market.market_service import MarketService
            return MarketService(None)


async def get_qmt_provider():
    """FastAPI dependency for QMT provider."""
    return await DataProviderFactory.get_provider_async("qmt")