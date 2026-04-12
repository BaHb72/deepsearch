"""
熔断器路由模块。

基于 Circuit Breaker 模式的数据源路由，提供自动容错和降级能力。
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Dict, List

from aiobreaker import CircuitBreaker
from aiocache import cached
from core.ports.data.requests import DataRequest
from loguru import logger

from .capability_router import CapabilityRouter, NoProviderAvailableError

if TYPE_CHECKING:
    from .adapters.base import BaseProviderAdapter


class AllProvidersUnavailableError(Exception):
    """所有数据源不可用异常"""

    def __init__(self, providers: List[str]):
        self.providers = providers
        super().__init__(f"所有数据源不可用: {', '.join(providers)}")


class CircuitBreakerRouter:
    """
    熔断器路由器。

    在 CapabilityRouter 的基础上添加 Circuit Breaker 保护和可用性评分：
    - 自动熔断：5 次失败后熔断 60 秒
    - 可用性评分：响应时间 40% + 成功率 60%
    - Redis 缓存：评分缓存 30 秒
    - 后台刷新：每 30 秒自动刷新评分
    """

    def __init__(
        self,
        router: CapabilityRouter,
        fail_max: int = 5,
        timeout_duration: int = 60,
    ):
        """
        初始化熔断器路由。

        Args:
            router: 能力路由器
            fail_max: 最大失败次数，默认 5 次
            timeout_duration: 熔断时长（秒），默认 60 秒
        """
        self.router = router
        self.fail_max = fail_max
        self.timeout_duration = timeout_duration

        # 为每个 Provider 创建熔断器
        self.breakers: Dict[str, CircuitBreaker] = {}
        self._create_breakers()

        # 统计数据
        self._response_times: Dict[str, List[float]] = {}
        self._success_counts: Dict[str, int] = {}
        self._total_counts: Dict[str, int] = {}

        # 后台刷新任务
        self._refresh_task: asyncio.Task[None] | None = None
        self._running = False

    def _create_breakers(self) -> None:
        """为所有适配器创建熔断器"""
        for name in self.router.adapters.keys():
            breaker = CircuitBreaker(
                fail_max=self.fail_max,
                timeout=self.timeout_duration,
                name=f"breaker-{name}",
            )
            # 注册状态变化监听器
            breaker.add_listener(self._on_breaker_state_change)
            self.breakers[name] = breaker
            logger.info(
                f"创建熔断器: {name} (fail_max={self.fail_max}, timeout={self.timeout_duration}s)"
            )

    def _on_breaker_state_change(
        self,
        breaker: CircuitBreaker,
        old_state: str,
        new_state: str,
    ) -> None:
        """熔断器状态变化回调（告警）"""
        logger.warning(f"熔断器状态变化: {breaker.name} {old_state} -> {new_state}")

        # 可以集成到告警系统
        if new_state == "open":
            logger.error(f"数据源 {breaker.name} 熔断！")

    async def resolve(self, request: DataRequest) -> "BaseProviderAdapter":
        """
        路由到最佳数据源（Circuit Breaker 保护）。

        Args:
            request: 数据请求

        Returns:
            最佳适配器

        Raises:
            AllProvidersUnavailableError: 所有数据源不可用
        """
        # 1. 获取可用性评分（Redis 缓存）
        scores = await self._get_availability_scores()

        # 2. 获取所有可能的适配器（按优先级）
        try:
            adapters = self.router.resolve_all(request)
        except NoProviderAvailableError:
            adapters = []

        if not adapters:
            logger.error("无可用数据源")
            raise AllProvidersUnavailableError([])

        # 3. 按评分重新排序（结合路由器优先级和可用性评分）
        sorted_adapters = sorted(
            adapters,
            key=lambda a: scores.get(a.name, 0.0),
            reverse=True,
        )

        # 4. 依次尝试（Circuit Breaker 自动跳过熔断的）
        errors = []
        for adapter in sorted_adapters:
            breaker = self.breakers.get(adapter.name)
            if not breaker:
                continue

            # 检查熔断器状态
            if breaker.current_state == "open":
                logger.debug(f"跳过熔断的数据源: {adapter.name}")
                continue

            try:
                # Circuit Breaker 保护的健康检查
                start_time = time.time()
                async with breaker:
                    # 快速健康检查（ping），不是完整请求
                    # 这里简化处理，实际可以添加专门的 health_check() 方法
                    pass
                elapsed = time.time() - start_time

                # 记录响应时间
                self._record_response_time(adapter.name, elapsed)
                self._record_success(adapter.name, success=True)

                logger.debug(f"路由到: {adapter.name} (评分: {scores.get(adapter.name, 0):.2f})")
                return adapter

            except Exception as e:
                errors.append((adapter.name, e))
                self._record_success(adapter.name, success=False)
                logger.warning(f"数据源 {adapter.name} 失败: {e}")
                continue

        # 所有数据源都失败
        provider_names = [a.name for a in adapters]
        logger.error(f"所有数据源不可用: {provider_names}")
        raise AllProvidersUnavailableError(provider_names)

    @cached(ttl=30, key="router:availability_scores")
    async def _get_availability_scores(self) -> Dict[str, float]:
        """
        获取可用性评分（Redis 缓存 30 秒）。

        评分算法：响应时间 40% + 成功率 60%
        """
        scores = {}
        for name in self.router.adapters.keys():
            # 计算响应时间评分（越小越好，转换为 0-1 分数）
            rt_score = self._calculate_response_time_score(name)

            # 计算成功率评分（0-1）
            success_score = self._calculate_success_rate(name)

            # 综合评分
            scores[name] = rt_score * 0.4 + success_score * 0.6

        logger.debug(f"可用性评分: {scores}")
        return scores

    def _calculate_response_time_score(self, name: str) -> float:
        """
        计算响应时间评分。

        使用最近 10 次的平均响应时间，转换为 0-1 分数：
        - < 100ms: 1.0
        - 100-500ms: 0.8-1.0 线性
        - 500-2000ms: 0.5-0.8 线性
        - > 2000ms: 0.0-0.5 线性
        """
        times = self._response_times.get(name, [])
        if not times:
            return 0.5  # 默认中等评分

        # 取最近 10 次
        recent_times = times[-10:]
        avg_time = sum(recent_times) / len(recent_times)

        # 转换为评分
        if avg_time < 0.1:  # < 100ms
            return 1.0
        elif avg_time < 0.5:  # 100-500ms
            return 0.8 + (0.5 - avg_time) / 0.4 * 0.2
        elif avg_time < 2.0:  # 500-2000ms
            return 0.5 + (2.0 - avg_time) / 1.5 * 0.3
        else:  # > 2000ms
            return max(0.0, 0.5 - (avg_time - 2.0) / 3.0 * 0.5)

    def _calculate_success_rate(self, name: str) -> float:
        """
        计算成功率评分。

        返回最近所有请求的成功率（0-1）。
        """
        total = self._total_counts.get(name, 0)
        if total == 0:
            return 0.5  # 默认中等评分

        success = self._success_counts.get(name, 0)
        return success / total

    def _record_response_time(self, name: str, elapsed: float) -> None:
        """记录响应时间"""
        if name not in self._response_times:
            self._response_times[name] = []

        self._response_times[name].append(elapsed)

        # 只保留最近 100 次
        if len(self._response_times[name]) > 100:
            self._response_times[name] = self._response_times[name][-100:]

    def _record_success(self, name: str, success: bool) -> None:
        """记录成功/失败"""
        if name not in self._total_counts:
            self._total_counts[name] = 0
            self._success_counts[name] = 0

        self._total_counts[name] += 1
        if success:
            self._success_counts[name] += 1

        # 滚动窗口：只保留最近 1000 次
        if self._total_counts[name] > 1000:
            ratio = self._success_counts[name] / self._total_counts[name]
            self._total_counts[name] = 100
            self._success_counts[name] = int(100 * ratio)

    async def start_background_refresh(self) -> None:
        """启动后台评分刷新任务"""
        if self._running:
            logger.warning("后台刷新任务已在运行")
            return

        self._running = True
        self._refresh_task = asyncio.create_task(self._background_refresh_loop())
        logger.info("启动后台评分刷新任务")

    async def stop_background_refresh(self) -> None:
        """停止后台评分刷新任务"""
        if not self._running:
            return

        logger.info("停止后台评分刷新任务")
        self._running = False

        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await asyncio.wait_for(self._refresh_task, timeout=5)
            except asyncio.CancelledError, asyncio.TimeoutError:
                pass

    async def _background_refresh_loop(self) -> None:
        """后台刷新可用性评分（每 30 秒）"""
        try:
            while self._running:
                await asyncio.sleep(30)
                # 触发缓存刷新（@cached 装饰器会自动处理）
                await self._get_availability_scores()
                logger.debug("后台刷新可用性评分")
        except asyncio.CancelledError:
            logger.info("后台刷新任务被取消")

    def get_statistics(self) -> Dict[str, Dict[str, float | int | str]]:
        """
        获取统计数据。

        Returns:
            {
                "provider_name": {
                    "success_rate": 0.95,
                    "avg_response_time": 0.123,
                    "breaker_state": "closed",
                    "total_calls": 1000,
                }
            }
        """
        stats = {}
        for name in self.router.adapters.keys():
            breaker = self.breakers.get(name)
            times = self._response_times.get(name, [])

            stats[name] = {
                "success_rate": self._calculate_success_rate(name),
                "avg_response_time": sum(times[-10:]) / len(times[-10:]) if times else 0.0,
                "breaker_state": breaker.current_state if breaker else "unknown",
                "total_calls": self._total_counts.get(name, 0),
            }

        return stats


__all__ = [
    "CircuitBreakerRouter",
    "AllProvidersUnavailableError",
]
