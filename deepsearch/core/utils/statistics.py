"""
统计收集系统

基于观察者模式的统计数据收集和聚合系统。
提供松耦合的统计数据收集机制，不影响核心业务逻辑。
"""

import threading
import time
from abc import abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional, Protocol, TypedDict, cast

from loguru import logger

ProvidersMap = Dict[str, Dict[str, Any]]


class CollectorSnapshot(TypedDict):
    """缓存的全量统计结构"""

    timestamp: str
    providers: ProvidersMap


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
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._logger = logger.bind(name=self.__class__.__name__)
        self._providers: Dict[str, StatisticsProvider] = {}
        self._cache: Optional[CollectorSnapshot] = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 1.0  # 默认1秒
        self._lock = threading.RLock()
        self._provider_timeout: float = 10.0

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

    def collect_all(self, use_cache: bool = True) -> CollectorSnapshot:
        """
        收集所有统计数据

        Args:
            use_cache: 是否使用缓存

        Returns:
            聚合的统计结果
        """
        with self._lock:
            cached_snapshot = self._cache
            if use_cache and cached_snapshot is not None and self._is_cache_valid():
                return cast(
                    CollectorSnapshot,
                    {
                        "timestamp": cached_snapshot["timestamp"],
                        "providers": dict(cached_snapshot["providers"]),
                    },
                )

            providers: ProvidersMap = {}

            for name, provider in self._providers.items():
                try:
                    providers[name] = self._collect_provider_data(provider)
                except Exception as exc:  # noqa: BLE001
                    self._logger.error(f"Error collecting statistics from {name}: {exc}")
                    providers[name] = {"error": str(exc), "status": "error"}

            snapshot: CollectorSnapshot = {
                "timestamp": datetime.now().isoformat(),
                "providers": providers,
            }
            self._cache = cast(
                CollectorSnapshot,
                {"timestamp": snapshot["timestamp"], "providers": dict(providers)},
            )
            self._cache_timestamp = time.time()
            return snapshot

    def _collect_provider_data(self, provider: StatisticsProvider) -> Dict[str, Any]:
        """ִ���ṩ��ͳ�Ʒ���������Э�̷���ֵ"""
        import asyncio
        import concurrent.futures
        import inspect

        def _invoke_provider() -> Any:
            return provider.get_statistics()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_invoke_provider)
            try:
                result = future.result(timeout=self._provider_timeout)
            except concurrent.futures.TimeoutError as exc:  # pragma: no cover - best effort
                raise TimeoutError(
                    f"Statistics provider timed out after {self._provider_timeout:.1f}s"
                ) from exc

        if inspect.iscoroutine(result):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is None:
                return cast(
                    Dict[str, Any],
                    asyncio.run(asyncio.wait_for(result, timeout=self._provider_timeout)),
                )

            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        asyncio.wait_for(result, timeout=self._provider_timeout),
                    )
                    return cast(Dict[str, Any], future.result(timeout=self._provider_timeout))

            return cast(
                Dict[str, Any],
                loop.run_until_complete(asyncio.wait_for(result, timeout=self._provider_timeout)),
            )

        return cast(Dict[str, Any], result)

    def get_provider_statistics(self, name: str) -> Optional[Dict[str, Any]]:
        """
        获取指定提供者的统计数据

        Args:
            name: 提供者名称

        Returns:
            统计结果或 None
        """
        with self._lock:
            provider = self._providers.get(name)

        if provider is None:
            return None

        try:
            return self._collect_provider_data(provider)
        except Exception as exc:  # noqa: BLE001
            self._logger.error(f"Error getting statistics from {name}: {exc}")
            return {"error": str(exc), "status": "error"}

    def get_summary(self) -> Dict[str, Any]:
        """
        获取系统统计摘要

        Returns:
            统计摘要
        """
        all_stats = self.collect_all()
        providers = all_stats["providers"]

        summary: Dict[str, Any] = {
            "timestamp": all_stats["timestamp"],
            "total_providers": len(self._providers),
            "healthy_providers": 0,
            "error_providers": 0,
            "key_metrics": {},
        }
        key_metrics = cast(Dict[str, Any], summary["key_metrics"])

        # 计算健康和错误的提供者数量
        for name, stats in providers.items():
            if "error" in stats:
                summary["error_providers"] += 1
            else:
                summary["healthy_providers"] += 1

        # 提取关键指标
        # 事件引擎指标
        if "event_engine" in providers:
            event_stats = providers["event_engine"]
            if "queue_size" in event_stats:
                key_metrics["event_queue_size"] = event_stats["queue_size"]
            if "total_processed" in event_stats:
                key_metrics["total_events"] = event_stats["total_processed"]

        # 数据库指标
        if "database" in providers:
            db_stats = providers["database"]
            key_metrics["database_connected"] = db_stats.get("connected", False)

        # 缓存指标
        if "cache" in providers:
            cache_stats = providers["cache"]
            key_metrics["cache_connected"] = cache_stats.get("connected", False)

        return summary

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if self._cache is None:
            return False
        return (time.time() - self._cache_timestamp) < self._cache_ttl

    def clear_cache(self) -> None:
        """清除缓存"""
        with self._lock:
            self._cache = None
            self._cache_timestamp = 0.0


# 全局统计收集器实例
statistics_collector = StatisticsCollector()


def get_statistics_collector() -> StatisticsCollector:
    """获取全局统计收集器实例"""
    return statistics_collector
