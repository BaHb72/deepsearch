"""
健康检查接口定义

定义健康检查的核心接口和数据结构
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List


class HealthStatus(Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"  # 健康
    DEGRADED = "degraded"  # 降级（部分功能不可用）
    UNHEALTHY = "unhealthy"  # 不健康
    UNKNOWN = "unknown"  # 未知


@dataclass
class HealthMetrics:
    """健康指标"""
    response_time_ms: Optional[float] = None  # 响应时间（毫秒）
    memory_usage_mb: Optional[float] = None  # 内存使用（MB）
    cpu_usage_percent: Optional[float] = None  # CPU使用率（%）
    connection_count: Optional[int] = None  # 连接数
    error_rate: Optional[float] = None  # 错误率
    queue_size: Optional[int] = None  # 队列大小
    custom_metrics: Dict[str, Any] = field(default_factory=dict)  # 自定义指标


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    status: HealthStatus  # 健康状态
    message: str = ""  # 状态消息
    details: Dict[str, Any] = field(default_factory=dict)  # 详细信息
    metrics: Optional[HealthMetrics] = None  # 健康指标
    errors: List[str] = field(default_factory=list)  # 错误列表
    timestamp: datetime = field(default_factory=datetime.now)  # 检查时间
    duration_ms: Optional[float] = None  # 检查耗时（毫秒）

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "errors": self.errors
        }

        if self.metrics:
            result["metrics"] = {
                k: v for k, v in {
                    "response_time_ms": self.metrics.response_time_ms,
                    "memory_usage_mb": self.metrics.memory_usage_mb,
                    "cpu_usage_percent": self.metrics.cpu_usage_percent,
                    "connection_count": self.metrics.connection_count,
                    "error_rate": self.metrics.error_rate,
                    "queue_size": self.metrics.queue_size,
                    **self.metrics.custom_metrics
                }.items() if v is not None
            }

        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms

        return result


class HealthChecker(ABC):
    """健康检查器抽象基类"""

    def __init__(self, name: str, component: Any = None):
        """
        初始化健康检查器
        
        Args:
            name: 检查器名称
            component: 要检查的组件实例（可选）
        """
        self._name = name
        self._component = component
        self._last_check_result: Optional[HealthCheckResult] = None
        self._check_count = 0
        self._failure_count = 0

    @property
    def name(self) -> str:
        """获取检查器名称"""
        return self._name

    @property
    def component(self) -> Any:
        """获取组件实例"""
        return self._component

    @component.setter
    def component(self, value: Any) -> None:
        """设置组件实例"""
        self._component = value

    @property
    def last_result(self) -> Optional[HealthCheckResult]:
        """获取最后一次检查结果"""
        return self._last_check_result

    @property
    def check_count(self) -> int:
        """获取检查次数"""
        return self._check_count

    @property
    def failure_count(self) -> int:
        """获取失败次数"""
        return self._failure_count

    @property
    def failure_rate(self) -> float:
        """获取失败率"""
        if self._check_count == 0:
            return 0.0
        return self._failure_count / self._check_count

    @abstractmethod
    async def check(self) -> HealthCheckResult:
        """
        执行健康检查
        
        Returns:
            健康检查结果
        """
        pass

    async def perform_check(self) -> HealthCheckResult:
        """
        执行健康检查并记录统计信息
        
        Returns:
            健康检查结果
        """
        import time

        start_time = time.perf_counter()
        self._check_count += 1

        try:
            result = await self.check()

            # 记录检查耗时
            result.duration_ms = (time.perf_counter() - start_time) * 1000

            # 更新失败计数
            if result.status in [HealthStatus.UNHEALTHY, HealthStatus.UNKNOWN]:
                self._failure_count += 1

            # 保存结果
            self._last_check_result = result

            return result

        except Exception as e:
            # 检查过程中出现异常
            self._failure_count += 1

            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                errors=[str(e)],
                duration_ms=(time.perf_counter() - start_time) * 1000
            )

            self._last_check_result = result
            return result

    def reset_stats(self) -> None:
        """重置统计信息"""
        self._check_count = 0
        self._failure_count = 0
        self._last_check_result = None


class CompositeHealthChecker(HealthChecker):
    """
    组合健康检查器
    
    可以包含多个子检查器，聚合它们的结果
    """

    def __init__(self, name: str):
        super().__init__(name)
        self._checkers: List[HealthChecker] = []

    def add_checker(self, checker: HealthChecker) -> None:
        """添加子检查器"""
        self._checkers.append(checker)

    def remove_checker(self, checker: HealthChecker) -> None:
        """移除子检查器"""
        self._checkers.remove(checker)

    async def check(self) -> HealthCheckResult:
        """执行所有子检查器并聚合结果"""
        import asyncio

        if not self._checkers:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                message="No sub-checkers configured"
            )

        # 并发执行所有子检查
        tasks = [checker.perform_check() for checker in self._checkers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 聚合结果
        all_healthy = True
        any_unhealthy = False
        errors = []
        details = {}
        metrics = HealthMetrics()

        for checker, result in zip(self._checkers, results):
            if isinstance(result, Exception):
                # 检查器执行出错
                any_unhealthy = True
                errors.append(f"{checker.name}: {str(result)}")
                details[checker.name] = {
                    "status": HealthStatus.UNHEALTHY.value,
                    "error": str(result)
                }
            else:
                # 正常结果
                details[checker.name] = result.to_dict()

                if result.status == HealthStatus.UNHEALTHY:
                    any_unhealthy = True
                    all_healthy = False
                elif result.status == HealthStatus.DEGRADED:
                    all_healthy = False

                errors.extend(result.errors)

        # 确定总体状态
        if any_unhealthy:
            status = HealthStatus.UNHEALTHY
            message = "One or more components are unhealthy"
        elif all_healthy:
            status = HealthStatus.HEALTHY
            message = "All components are healthy"
        else:
            status = HealthStatus.DEGRADED
            message = "Some components are degraded"

        return HealthCheckResult(
            status=status,
            message=message,
            details=details,
            errors=errors,
            metrics=metrics
        )
