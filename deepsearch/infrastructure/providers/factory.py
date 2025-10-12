"""
数据提供者工厂
基于策略模式和工厂模式，智能创建和管理数据提供者
"""

import asyncio
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from loguru import logger

from deepsearch.core.utils.async_timeout import run_with_timeout, with_timeout
from deepsearch.core.utils.timeout_config import TimeoutCategory

from .base.provider_base import BaseDataProvider
from .registry import ProviderType, get_registry


class SelectionStrategy(Enum):
    """数据源选择策略"""

    PRIORITY = "priority"  # 基于优先级
    ROUND_ROBIN = "round_robin"  # 轮询
    FAILOVER = "failover"  # 故障转移
    PERFORMANCE = "performance"  # 基于性能
    HYBRID = "hybrid"  # 混合策略


class CircuitBreakerState(Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 正常
    OPEN = "open"  # 熔断
    HALF_OPEN = "half_open"  # 半开


class CircuitBreaker:
    """
    熔断器实现

    用于防止对故障服务的持续调用
    """

    def __init__(
        self, failure_threshold: int = 5, recovery_timeout: int = 60, success_threshold: int = 2
    ):
        """
        初始化熔断器

        Args:
            failure_threshold: 失败阈值，达到后开启熔断
            recovery_timeout: 恢复超时（秒）
            success_threshold: 成功阈值，半开状态下达到后关闭熔断
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None

    def call_succeeded(self):
        """调用成功"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                logger.info("熔断器关闭")
        else:
            self.failure_count = 0

    def call_failed(self):
        """调用失败"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"熔断器开启，失败次数: {self.failure_count}")

    def can_attempt(self) -> bool:
        """是否可以尝试调用"""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).seconds
                if elapsed >= self.recovery_timeout:
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.success_count = 0
                    logger.info("熔断器进入半开状态")
                    return True
            return False

        # HALF_OPEN state
        return True


class DataProviderFactory:
    """
    数据提供者工厂

    负责创建、管理和智能选择数据提供者
    """

    def __init__(
        self,
        strategy: SelectionStrategy = SelectionStrategy.HYBRID,
        enable_circuit_breaker: bool = True,
    ):
        """
        初始化工厂

        Args:
            strategy: 选择策略
            enable_circuit_breaker: 是否启用熔断器
        """
        self.registry = get_registry()
        self.strategy = strategy
        self.enable_circuit_breaker = enable_circuit_breaker

        # 提供者实例缓存
        self._providers: Dict[str, BaseDataProvider] = {}

        # 熔断器
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}

        # 轮询索引
        self._round_robin_index = 0

        # 性能统计
        self._performance_stats: Dict[str, Dict[str, Any]] = {}

    async def get_provider(
        self, provider_type: Optional[ProviderType] = None, provider_name: Optional[str] = None
    ) -> Optional[BaseDataProvider]:
        """
        获取数据提供者

        Args:
            provider_type: 提供者类型
            provider_name: 提供者名称（优先使用）

        Returns:
            数据提供者实例
        """
        # 如果指定了名称，直接获取
        if provider_name:
            return await self._get_specific_provider(provider_name)

        # 根据策略选择提供者
        if self.strategy == SelectionStrategy.PRIORITY:
            return await self._get_by_priority(provider_type)
        elif self.strategy == SelectionStrategy.ROUND_ROBIN:
            return await self._get_by_round_robin(provider_type)
        elif self.strategy == SelectionStrategy.FAILOVER:
            return await self._get_by_failover(provider_type)
        elif self.strategy == SelectionStrategy.PERFORMANCE:
            return await self._get_by_performance(provider_type)
        else:  # HYBRID
            return await self._get_by_hybrid(provider_type)

    async def _get_specific_provider(self, name: str) -> Optional[BaseDataProvider]:
        """
        获取特定的提供者

        Args:
            name: 提供者名称

        Returns:
            提供者实例
        """
        # 检查缓存
        if name in self._providers:
            provider = self._providers[name]
            if await self._check_provider_health(name, provider):
                return provider

        # 创建新实例
        provider_obj = self.registry.get_provider_instance(name)
        if isinstance(provider_obj, BaseDataProvider):
            provider = provider_obj
            init_method = getattr(provider, "initialize", None)
            if callable(init_method):
                try:
                    from deepsearch.core.utils.timeout_config import get_timeout_manager

                    timeout_manager = get_timeout_manager()
                    timeout_value = timeout_manager.get_timeout(TimeoutCategory.COMPONENT_INIT)

                    if asyncio.iscoroutinefunction(init_method):
                        await with_timeout(init_method(), timeout=timeout_value)
                    else:
                        init_result = init_method()
                        if asyncio.iscoroutine(init_result):
                            await with_timeout(init_result, timeout=timeout_value)
                        else:
                            await run_with_timeout(init_method, timeout=timeout_value)

                    self._providers[name] = provider
                    return provider
                except Exception as e:
                    logger.error(f"初始化提供者 {name} 失败: {e}")
                    return None
            else:
                self._providers[name] = provider
                return provider

        return None

    async def _get_by_priority(
        self, provider_type: Optional[ProviderType] = None
    ) -> Optional[BaseDataProvider]:
        """
        基于优先级获取提供者

        Args:
            provider_type: 提供者类型

        Returns:
            提供者实例
        """
        providers = self.registry.get_providers_by_priority()

        for provider_info in providers:
            # 过滤类型
            if provider_type and provider_info.type != provider_type:
                continue

            # 检查是否启用
            if not provider_info.enabled:
                continue

            # 检查熔断器
            if not self._check_circuit_breaker(provider_info.name):
                continue

            # 尝试获取提供者
            provider = await self._get_specific_provider(provider_info.name)
            if provider is not None:
                return provider

        return None

    async def _get_by_round_robin(
        self, provider_type: Optional[ProviderType] = None
    ) -> Optional[BaseDataProvider]:
        """
        轮询方式获取提供者

        Args:
            provider_type: 提供者类型

        Returns:
            提供者实例
        """
        if provider_type:
            providers = self.registry.get_providers_by_type(provider_type)
        else:
            providers = self.registry.get_enabled_providers()

        if not providers:
            return None

        # 轮询选择
        for _ in range(len(providers)):
            provider_info = providers[self._round_robin_index % len(providers)]
            self._round_robin_index += 1

            # 检查熔断器
            if not self._check_circuit_breaker(provider_info.name):
                continue

            provider = await self._get_specific_provider(provider_info.name)
            if provider is not None:
                return provider

        return None

    async def _get_by_failover(
        self, provider_type: Optional[ProviderType] = None
    ) -> Optional[BaseDataProvider]:
        """
        故障转移方式获取提供者

        与优先级类似，但会记录故障并自动切换

        Args:
            provider_type: 提供者类型

        Returns:
            提供者实例
        """
        return await self._get_by_priority(provider_type)

    async def _get_by_performance(
        self, provider_type: Optional[ProviderType] = None
    ) -> Optional[BaseDataProvider]:
        """
        基于性能获取提供者

        选择响应时间最快的提供者

        Args:
            provider_type: 提供者类型

        Returns:
            提供者实例
        """
        if provider_type:
            providers = self.registry.get_providers_by_type(provider_type)
        else:
            providers = self.registry.get_enabled_providers()

        # 计算性能分数
        provider_scores = []
        for provider_info in providers:
            if provider_info.name in self._performance_stats:
                stats = self._performance_stats[provider_info.name]
                # 分数 = 成功率 * (1 / 平均延迟)
                score = stats.get("success_rate", 0) / max(stats.get("avg_latency", 1), 0.01)
            else:
                # 新提供者给予初始分数
                score = 50.0

            provider_scores.append((provider_info, score))

        # 按分数排序
        provider_scores.sort(key=lambda x: x[1], reverse=True)

        # 尝试获取
        for provider_info, _ in provider_scores:
            if not self._check_circuit_breaker(provider_info.name):
                continue

            provider = await self._get_specific_provider(provider_info.name)
            if provider is not None:
                return provider

        return None

    async def _get_by_hybrid(
        self, provider_type: Optional[ProviderType] = None
    ) -> Optional[BaseDataProvider]:
        """
        混合策略获取提供者

        结合优先级、性能和可用性

        Args:
            provider_type: 提供者类型

        Returns:
            提供者实例
        """
        if provider_type:
            providers = self.registry.get_providers_by_type(provider_type)
        else:
            providers = self.registry.get_enabled_providers()

        # 计算综合分数
        provider_scores = []
        for provider_info in providers:
            # 基础分数 = 优先级
            score = float(provider_info.priority)

            # 性能加成
            if provider_info.name in self._performance_stats:
                stats = self._performance_stats[provider_info.name]
                performance_bonus = stats.get("success_rate", 0) * 0.5
                score += performance_bonus

            # 熔断器惩罚
            if self.enable_circuit_breaker:
                breaker = self._circuit_breakers.get(provider_info.name)
                if breaker and breaker.state == CircuitBreakerState.OPEN:
                    score *= 0.1  # 大幅降低分数

            provider_scores.append((provider_info, score))

        # 按分数排序
        provider_scores.sort(key=lambda x: x[1], reverse=True)

        # 尝试获取
        for provider_info, _ in provider_scores:
            if not self._check_circuit_breaker(provider_info.name):
                continue

            provider = await self._get_specific_provider(provider_info.name)
            if provider is not None:
                return provider

        return None

    def _check_circuit_breaker(self, provider_name: str) -> bool:
        """
        检查熔断器状态

        Args:
            provider_name: 提供者名称

        Returns:
            是否可以尝试调用
        """
        if not self.enable_circuit_breaker:
            return True

        if provider_name not in self._circuit_breakers:
            self._circuit_breakers[provider_name] = CircuitBreaker()

        return self._circuit_breakers[provider_name].can_attempt()

    async def _check_provider_health(self, name: str, provider: BaseDataProvider) -> bool:
        """
        检查提供者健康状态

        Args:
            name: 提供者名称
            provider: 提供者实例

        Returns:
            是否健康
        """
        if hasattr(provider, "health_check"):
            try:
                from deepsearch.core.utils.timeout_config import get_timeout_manager

                timeout_manager = get_timeout_manager()
                timeout_value = timeout_manager.get_timeout(TimeoutCategory.COMPONENT_HEALTH)
                from deepsearch.core.utils.async_timeout import with_timeout

                health = await with_timeout(
                    provider.health_check(), timeout=timeout_value, default={"status": "timeout"}
                )
                if isinstance(health, dict):
                    return health.get("status") != "error"
                return bool(health)
            except Exception:
                return False
        return True

    def report_success(self, provider_name: str, latency: float):
        """
        报告成功调用

        Args:
            provider_name: 提供者名称
            latency: 延迟（秒）
        """
        # 更新熔断器
        if provider_name in self._circuit_breakers:
            self._circuit_breakers[provider_name].call_succeeded()

        # 更新性能统计
        if provider_name not in self._performance_stats:
            self._performance_stats[provider_name] = {
                "total_requests": 0,
                "failed_requests": 0,
                "total_latency": 0.0,
                "success_rate": 100.0,
                "avg_latency": 0.0,
            }

        stats = self._performance_stats[provider_name]
        stats["total_requests"] += 1
        stats["total_latency"] += latency
        stats["avg_latency"] = stats["total_latency"] / stats["total_requests"]
        stats["success_rate"] = (
            (stats["total_requests"] - stats["failed_requests"]) / stats["total_requests"] * 100
        )

    def report_failure(self, provider_name: str):
        """
        报告失败调用

        Args:
            provider_name: 提供者名称
        """
        # 更新熔断器
        if provider_name in self._circuit_breakers:
            self._circuit_breakers[provider_name].call_failed()

        # 更新性能统计
        if provider_name not in self._performance_stats:
            self._performance_stats[provider_name] = {
                "total_requests": 0,
                "failed_requests": 0,
                "total_latency": 0.0,
                "success_rate": 0.0,
                "avg_latency": 0.0,
            }

        stats = self._performance_stats[provider_name]
        stats["total_requests"] += 1
        stats["failed_requests"] += 1
        stats["success_rate"] = (
            (stats["total_requests"] - stats["failed_requests"]) / stats["total_requests"] * 100
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息
        """
        return {
            "providers": len(self._providers),
            "circuit_breakers": {
                name: breaker.state.value for name, breaker in self._circuit_breakers.items()
            },
            "performance": self._performance_stats,
        }


# 全局工厂实例
_factory = None


def get_factory(strategy: SelectionStrategy = SelectionStrategy.HYBRID) -> DataProviderFactory:
    """
    获取全局数据提供者工厂实例

    Args:
        strategy: 选择策略

    Returns:
        工厂实例
    """
    global _factory
    if _factory is None:
        _factory = DataProviderFactory(strategy)
    return _factory
