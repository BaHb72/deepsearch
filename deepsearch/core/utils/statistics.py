"""
统计收集系统

基于观察者模式的统计数据收集和聚合系统。
提供松耦合的统计数据收集机制，不影响核心业务逻辑。
"""
import threading
import time
from abc import abstractmethod
from datetime import datetime
from typing import Dict, Any, Protocol, Optional

from loguru import logger


class StatisticsProvider(Protocol):
    """统计数据提供者协议"""

    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计数据"""
        ...


class StatisticsCollector:
    """
    统计收集器 - 全局单例
    
    负责：
    1. 注册和管理统计提供者
    2. 收集和聚合统计数据
    3. 提供缓存机制避免频繁收集
    4. 线程安全的数据访问
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # 只初始化一次
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self._logger = logger.bind(name=self.__class__.__name__)
        self._providers: Dict[str, StatisticsProvider] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_timestamp = 0
        self._cache_ttl = 1.0  # 缓存1秒
        self._lock = threading.RLock()

        self._logger.info("StatisticsCollector initialized")

    def register_provider(self, name: str, provider: StatisticsProvider) -> None:
        """
        注册统计提供者
        
        Args:
            name: 提供者名称
            provider: 统计提供者实例
        """
        with self._lock:
            self._providers[name] = provider
            self._logger.debug(f"Registered statistics provider: {name}")

    def unregister_provider(self, name: str) -> None:
        """
        注销统计提供者
        
        Args:
            name: 提供者名称
        """
        with self._lock:
            if name in self._providers:
                del self._providers[name]
                self._logger.debug(f"Unregistered statistics provider: {name}")

    def collect_all(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        收集所有统计数据
        
        Args:
            use_cache: 是否使用缓存
            
        Returns:
            聚合的统计数据
        """
        with self._lock:
            # 检查缓存
            if use_cache and self._is_cache_valid():
                return self._cache.copy()

            # 收集新数据
            stats = {
                "timestamp": datetime.now().isoformat(),
                "providers": {}
            }

            for name, provider in self._providers.items():
                try:
                    stats["providers"][name] = provider.get_statistics()
                except Exception as e:
                    self._logger.error(f"Error collecting statistics from {name}: {e}")
                    stats["providers"][name] = {
                        "error": str(e),
                        "status": "error"
                    }

            # 更新缓存
            self._cache = stats
            self._cache_timestamp = time.time()

            return stats

    def get_provider_statistics(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取特定提供者的统计数据
        
        Args:
            name: 提供者名称
            
        Returns:
            统计数据或None
        """
        with self._lock:
            provider = self._providers.get(name)
            if provider:
                try:
                    return provider.get_statistics()
                except Exception as e:
                    self._logger.error(f"Error getting statistics from {name}: {e}")
                    return {"error": str(e), "status": "error"}
            return None

    def get_summary(self) -> Dict[str, Any]:
        """
        获取系统统计摘要
        
        Returns:
            统计摘要
        """
        all_stats = self.collect_all()

        summary = {
            "timestamp": all_stats["timestamp"],
            "total_providers": len(self._providers),
            "healthy_providers": 0,
            "error_providers": 0,
            "key_metrics": {}
        }

        # 计算健康和错误的提供者数量
        for name, stats in all_stats["providers"].items():
            if "error" in stats:
                summary["error_providers"] += 1
            else:
                summary["healthy_providers"] += 1

        # 提取关键指标
        # 事件引擎指标
        if "event_engine" in all_stats["providers"]:
            event_stats = all_stats["providers"]["event_engine"]
            if "queue_size" in event_stats:
                summary["key_metrics"]["event_queue_size"] = event_stats["queue_size"]
            if "total_processed" in event_stats:
                summary["key_metrics"]["total_events"] = event_stats["total_processed"]

        # 数据库指标
        if "database" in all_stats["providers"]:
            db_stats = all_stats["providers"]["database"]
            summary["key_metrics"]["database_connected"] = db_stats.get("connected", False)

        # 缓存指标
        if "cache" in all_stats["providers"]:
            cache_stats = all_stats["providers"]["cache"]
            summary["key_metrics"]["cache_connected"] = cache_stats.get("connected", False)

        return summary

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        return (time.time() - self._cache_timestamp) < self._cache_ttl

    def clear_cache(self) -> None:
        """清除缓存"""
        with self._lock:
            self._cache.clear()
            self._cache_timestamp = 0


# 全局统计收集器实例
statistics_collector = StatisticsCollector()


def get_statistics_collector() -> StatisticsCollector:
    """获取全局统计收集器实例"""
    return statistics_collector
