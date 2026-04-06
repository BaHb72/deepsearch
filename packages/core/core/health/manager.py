"""
健康检查管理器

统一管理所有健康检查器，提供并发执行、超时保护等功能
"""

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set

from loguru import logger

from ...config.models.health import HealthCheckConfig
from .checkers import (
    DatabaseHealthChecker,
    EventEngineHealthChecker,
    GatewayHealthChecker,
    MessageBusHealthChecker,
    MonitorHealthChecker,
    RedisHealthChecker,
)
from .interfaces import HealthChecker, HealthCheckResult, HealthStatus


class HealthCheckManager:
    """
    健康检查管理器

    负责：
    - 注册和管理健康检查器
    - 定期执行健康检查
    - 提供健康状态查询
    - 支持并发执行和超时保护
    """

    def __init__(
        self,
        check_interval: float = 30.0,
        check_timeout: float = 5.0,
        config: HealthCheckConfig | None = None,
    ):
        """
        初始化健康检查管理器

        Args:
            check_interval: 健康检查间隔（秒）
            check_timeout: 单个健康检查超时时间（秒）
            config: 健康检查配置（可选，优先于单独的参数）
        """
        # 如果提供了配置，使用配置中的值
        if config:
            check_interval = config.interval
            check_timeout = config.timeout

        self._checkers: Dict[str, HealthChecker] = {}
        self._check_interval = check_interval
        self._check_timeout = check_timeout
        self._config = config or HealthCheckConfig()
        self._last_results: Dict[str, HealthCheckResult] = {}
        self._check_task: Optional[asyncio.Task] = None
        self._running = False
        self._enabled_checkers: Set[str] = set()

        # 健康检查历史记录
        self._history_size = self._config.history_size
        self._check_history: List[Dict[str, Any]] = []

        logger.info(f"健康检查管理器初始化: interval={check_interval}s, timeout={check_timeout}s")

    def register_checker(self, checker: HealthChecker, enabled: bool = True) -> None:
        """
        注册健康检查器

        Args:
            checker: 健康检查器实例
            enabled: 是否启用
        """
        name = checker.name
        self._checkers[name] = checker

        if enabled:
            self._enabled_checkers.add(name)

        logger.info(f"注册健康检查器: {name} (enabled={enabled})")

    def unregister_checker(self, name: str) -> None:
        """移除健康检查器"""
        if name in self._checkers:
            del self._checkers[name]
            self._enabled_checkers.discard(name)
            self._last_results.pop(name, None)
            logger.info(f"移除健康检查器: {name}")

    def enable_checker(self, name: str) -> None:
        """启用健康检查器"""
        if name in self._checkers:
            self._enabled_checkers.add(name)
            logger.info(f"启用健康检查器: {name}")

    def disable_checker(self, name: str) -> None:
        """禁用健康检查器"""
        self._enabled_checkers.discard(name)
        logger.info(f"禁用健康检查器: {name}")

    def auto_register_checkers(self, components: Dict[str, Any]) -> None:
        """
        自动注册组件的健康检查器

        Args:
            components: 组件字典 {name: component}
        """

        def create_database_checker() -> HealthChecker:
            return DatabaseHealthChecker(
                latency_threshold_ms=self._config.database_latency_threshold_ms
            )

        def create_redis_checker() -> HealthChecker:
            return RedisHealthChecker(
                latency_threshold_ms=self._config.redis_latency_threshold_ms,
                latency_samples=self._config.redis_latency_samples,
                consecutive_degraded=self._config.redis_latency_consecutive_degraded,
            )

        checker_factories: Dict[str, Callable[[], HealthChecker]] = {
            "database": create_database_checker,
            "cache": create_redis_checker,
            "event_engine": EventEngineHealthChecker,
            "message_bus": MessageBusHealthChecker,
            "monitor": MonitorHealthChecker,
            "gateway": GatewayHealthChecker,
        }
        for name, component in components.items():
            if name in checker_factories:
                try:
                    # 只为运行中的组件注册健康检查器
                    if hasattr(component, "status") and component.status.value in [
                        "initialized",
                        "running",
                    ]:
                        checker_factory = checker_factories[name]
                        checker = checker_factory()
                        checker.component = component
                        self.register_checker(checker)
                        logger.debug(f"自动注册健康检查器: {name}")
                except Exception as e:
                    logger.warning(f"自动注册健康检查器失败 {name}: {e}")

    async def check_all(self, timeout: Optional[float] = None) -> Dict[str, HealthCheckResult]:
        """
        执行所有启用的健康检查

        Args:
            timeout: 超时时间（秒），None表示使用默认值

        Returns:
            检查结果字典
        """
        if not self._enabled_checkers:
            logger.warning("没有启用的健康检查器")
            return {}

        timeout = timeout or self._check_timeout
        results = {}

        # 创建检查任务
        tasks = {}
        for name in self._enabled_checkers:
            if name in self._checkers:
                checker = self._checkers[name]
                tasks[name] = asyncio.create_task(checker.perform_check())

        # 并发执行，带超时保护
        for name, task in tasks.items():
            try:
                result = await asyncio.wait_for(task, timeout=timeout)
                results[name] = result
            except asyncio.TimeoutError:
                results[name] = HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check timed out after {timeout}s",
                )
                logger.warning(f"健康检查超时: {name}")
            except Exception as e:
                results[name] = HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {str(e)}",
                    errors=[str(e)],
                )
                logger.error(f"健康检查失败 {name}: {e}")

        # 更新结果缓存
        self._last_results = results

        # 记录历史
        self._record_history(results)

        return results

    async def check_component(
        self, name: str, timeout: Optional[float] = None
    ) -> HealthCheckResult:
        """
        检查特定组件

        Args:
            name: 组件名称
            timeout: 超时时间（秒）

        Returns:
            健康检查结果
        """
        if name not in self._checkers:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN, message=f"No health checker registered for {name}"
            )

        if name not in self._enabled_checkers:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN, message=f"Health checker for {name} is disabled"
            )

        checker = self._checkers[name]
        timeout = timeout or self._check_timeout

        try:
            result = await asyncio.wait_for(checker.perform_check(), timeout=timeout)
            self._last_results[name] = result
            return result
        except asyncio.TimeoutError:
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY, message=f"Health check timed out after {timeout}s"
            )
            self._last_results[name] = result
            return result
        except Exception as e:
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                errors=[str(e)],
            )
            self._last_results[name] = result
            return result

    def get_overall_status(self) -> HealthStatus:
        """获取系统整体健康状态"""
        if not self._last_results:
            return HealthStatus.UNKNOWN

        statuses = [result.status for result in self._last_results.values()]

        # 如果有任何组件不健康，整体不健康
        if any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY

        # 如果有组件降级，整体降级
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED

        # 如果有未知状态，整体未知
        elif any(s == HealthStatus.UNKNOWN for s in statuses):
            return HealthStatus.UNKNOWN

        # 否则健康
        else:
            return HealthStatus.HEALTHY

    def get_last_results(self) -> Dict[str, HealthCheckResult]:
        """获取最后一次检查结果"""
        return self._last_results.copy()

    def get_component_status(self, name: str) -> Optional[HealthCheckResult]:
        """获取特定组件的最后检查结果"""
        return self._last_results.get(name)

    def get_latest_result(self, component_name: str) -> Optional[HealthCheckResult]:
        """获取指定组件的最新健康检查结果（不执行新的检查）"""
        return self._last_results.get(component_name)

    async def start(self) -> None:
        """启动定期健康检查"""
        if self._running:
            logger.warning("健康检查管理器已在运行")
            return

        self._running = True
        self._check_task = asyncio.create_task(self._check_loop())
        logger.info("健康检查管理器已启动")

    async def stop(self) -> None:
        """停止定期健康检查"""
        self._running = False

        if self._check_task and not self._check_task.done():
            self._check_task.cancel()
            try:
                await self._check_task
            except asyncio.CancelledError:
                pass

        logger.info("健康检查管理器已停止")

    async def _check_loop(self) -> None:
        """健康检查循环"""
        while self._running:
            try:
                # 执行健康检查
                await self.check_all()

                # 检查是否需要告警
                overall_status = self.get_overall_status()
                if overall_status in [HealthStatus.UNHEALTHY, HealthStatus.DEGRADED]:
                    # 收集所有非健康组件的详情
                    unhealthy_components = []
                    for name, result in self._last_results.items():
                        if result.status != HealthStatus.HEALTHY:
                            detail = f"{name}={result.status.value}"
                            if result.message:
                                detail += f"({result.message})"
                            unhealthy_components.append(detail)

                    details = ", ".join(unhealthy_components) if unhealthy_components else "unknown"
                    logger.warning(
                        f"系统健康状态异常: {overall_status.value} | 问题组件: {details}"
                    )

                # 等待下次检查
                await asyncio.sleep(self._check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"健康检查循环异常: {e}")
                await asyncio.sleep(self._check_interval)

    def _record_history(self, results: Dict[str, HealthCheckResult]) -> None:
        """记录健康检查历史"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": self.get_overall_status().value,
            "components": {
                name: {"status": result.status.value, "message": result.message}
                for name, result in results.items()
            },
        }

        self._check_history.append(record)

        # 限制历史记录大小
        if len(self._check_history) > self._history_size:
            self._check_history = self._check_history[-self._history_size :]

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取健康检查历史

        Args:
            limit: 限制返回的记录数

        Returns:
            历史记录列表
        """
        if limit:
            return self._check_history[-limit:]
        return self._check_history.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """获取健康检查管理器的统计信息"""
        stats: Dict[str, Any] = {
            "total_checkers": len(self._checkers),
            "enabled_checkers": len(self._enabled_checkers),
            "overall_status": self.get_overall_status().value,
        }
        checker_details: Dict[str, Dict[str, Any]] = {}

        # 每个健康检查器的统计
        for name, checker in self._checkers.items():
            checker_stats: Dict[str, Any] = {
                "enabled": name in self._enabled_checkers,
                "check_count": checker.check_count,
                "failure_count": checker.failure_count,
                "failure_rate": checker.failure_rate,
                "last_status": None,
                "last_check": None,
            }

            # 最近状态
            if name in self._last_results:
                result = self._last_results[name]
                checker_stats["last_status"] = result.status.value
                checker_stats["last_check"] = result.timestamp.isoformat()

            checker_details[name] = checker_stats

        stats["checkers"] = checker_details
        return stats

    async def get_health_report(self) -> Dict[str, Any]:
        """获取完整的健康检查报告"""
        # 执行一次健康检查以获取最新数据
        results = await self.check_all()

        components_report: Dict[str, Dict[str, Any]] = {}
        report: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "overall_status": self.get_overall_status().value,
            "summary": self._generate_summary(),
            "components": components_report,
            "statistics": self.get_statistics(),
        }

        # 追加详细组件信息
        for name, result in results.items():
            components_report[name] = result.to_dict()

        return report

    def _generate_summary(self) -> str:
        """生成健康状态摘要"""
        overall = self.get_overall_status()

        if overall == HealthStatus.HEALTHY:
            return "All systems are operational"
        elif overall == HealthStatus.DEGRADED:
            degraded = [
                name
                for name, result in self._last_results.items()
                if result.status == HealthStatus.DEGRADED
            ]
            return f"System degraded: {', '.join(degraded)}"
        elif overall == HealthStatus.UNHEALTHY:
            unhealthy = [
                name
                for name, result in self._last_results.items()
                if result.status == HealthStatus.UNHEALTHY
            ]
            return f"System unhealthy: {', '.join(unhealthy)}"
        else:
            return "System status unknown"
