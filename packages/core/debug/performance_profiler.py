"""
性能分析器模块

提供性能监控、分析和优化建议
"""

import asyncio
import statistics
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Awaitable,
    Callable,
    DefaultDict,
    Deque,
    Dict,
    List,
    ParamSpec,
    Sequence,
    TypedDict,
    TypeVar,
    cast,
)

import psutil
from core.observability.logger import logger_manager
from loguru import logger


class Measurement(TypedDict):
    duration_ms: float
    memory_delta: int
    timestamp: datetime


class SlowOperation(TypedDict):
    operation: str
    duration_ms: float
    memory_delta: int
    timestamp: datetime
    thread_id: int


P = ParamSpec("P")
R = TypeVar("R")


class PerformanceMetrics:
    """性能指标"""

    def __init__(self, operation: str):
        self.operation = operation
        self.measurements: Deque[Measurement] = deque(maxlen=1000)
        self.slow_threshold_ms: float = 100.0

    def add_measurement(self, duration_ms: float, memory_delta: int):
        """添加测量数据"""
        measurement: Measurement = {
            "duration_ms": duration_ms,
            "memory_delta": memory_delta,
            "timestamp": datetime.now(),
        }
        self.measurements.append(measurement)

    def _percentile(self, data: Sequence[float], percentile: float) -> float:
        """计算百分位数"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = (len(sorted_data) - 1) * percentile / 100
        lower = int(index)
        upper = lower + 1
        if upper >= len(sorted_data):
            return sorted_data[lower]
        weight = index - lower
        return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.measurements:
            return {}

        durations = [m["duration_ms"] for m in self.measurements]
        memory_deltas = [m["memory_delta"] for m in self.measurements]

        return {
            "count": len(self.measurements),
            "duration": {
                "total_ms": sum(durations),
                "avg_ms": statistics.mean(durations),
                "min_ms": min(durations),
                "max_ms": max(durations),
                "median_ms": statistics.median(durations),
                "stdev_ms": statistics.stdev(durations) if len(durations) > 1 else 0,
                "p95_ms": self._percentile(durations, 95) if durations else 0,
                "p99_ms": self._percentile(durations, 99) if durations else 0,
            },
            "memory": {
                "avg_delta": statistics.mean(memory_deltas) if memory_deltas else 0,
                "max_delta": max(memory_deltas) if memory_deltas else 0,
                "total_delta": sum(memory_deltas),
            },
            "slow_operations": sum(1 for d in durations if d > self.slow_threshold_ms),
        }


class PerformanceProfiler:
    """性能分析器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self.metrics: DefaultDict[str, PerformanceMetrics] = defaultdict(
                lambda: PerformanceMetrics("unknown")
            )
            self.slow_operations: Deque[SlowOperation] = deque(maxlen=100)
            self.threshold_ms = 100
            # 延迟导入配置
            try:
                from core.config import get_config

                config = get_config()
                self.enabled = getattr(config.app, "env", "prod") == "dev"
            except ImportError:
                self.enabled = True  # 默认启用
            except Exception:
                self.enabled = True
            self.auto_suggestions: List[Dict[str, Any]] = []
            self._lock = threading.Lock()
            self._initialized = True

    @contextmanager
    def profile(self, operation: str, auto_log: bool = True):
        """性能分析上下文管理器"""
        if not self.enabled:
            yield
            return

        start_time = time.perf_counter()
        start_memory = psutil.Process().memory_info().rss

        try:
            yield
        finally:
            duration = (time.perf_counter() - start_time) * 1000  # ms
            memory_delta = psutil.Process().memory_info().rss - start_memory

            with self._lock:
                # 记录性能数据
                metrics = self.metrics[operation]
                metrics.add_measurement(duration, memory_delta)

                # 检测慢操作
                if duration > self.threshold_ms:
                    slow_op: SlowOperation = {
                        "operation": operation,
                        "duration_ms": duration,
                        "memory_delta": memory_delta,
                        "timestamp": datetime.now(),
                        "thread_id": threading.get_ident(),
                    }
                    self.slow_operations.append(slow_op)

                    if auto_log:
                        logger.warning(
                            f"慢操作检测: {operation} 耗时 {duration:.2f}ms "
                            f"(阈值: {self.threshold_ms}ms)"
                        )

    def profile_function(self, func: Callable[P, R]) -> Callable[P, R]:
        """函数性能分析装饰器"""

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            operation = f"{func.__module__}.{func.__name__}"
            with self.profile(operation):
                return func(*args, **kwargs)

        return wrapper

    def profile_async_function(self, func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        """异步函数性能分析装饰器"""

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            operation = f"{func.__module__}.{func.__name__}"
            with self.profile(operation):
                return await func(*args, **kwargs)

        return wrapper

    def get_report(self, top_n: int = 20) -> Dict[str, Any]:
        """生成性能报告"""
        operations: Dict[str, Dict[str, Any]] = {}
        slow_operations: List[Dict[str, Any]] = []
        report: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "operations": operations,
            "slow_operations": slow_operations,
            "summary": {},
        }

        # 操作统计
        for operation, metrics in self.metrics.items():
            stats = metrics.get_statistics()
            if stats:
                operations[operation] = stats

        # 慢操作列表
        for op in list(self.slow_operations)[-top_n:]:
            slow_operations.append(
                {
                    "operation": op["operation"],
                    "duration_ms": op["duration_ms"],
                    "timestamp": op["timestamp"].isoformat(),
                }
            )

        # 汇总信息
        if operations:
            total_ops = sum(cast(int, op.get("count", 0)) for op in operations.values())
            total_time = sum(
                cast(float, op.get("duration", {}).get("total_ms", 0.0))
                for op in operations.values()
            )

            report["summary"] = {
                "total_operations": total_ops,
                "total_time_ms": total_time,
                "avg_time_ms": total_time / total_ops if total_ops > 0 else 0,
                "slow_operations_count": len(slow_operations),
            }

        return report

    def get_top_slow_operations(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """获取最慢的操作"""
        operations_by_time = []

        for operation, metrics in self.metrics.items():
            stats = metrics.get_statistics()
            if stats and stats.get("duration"):
                operations_by_time.append(
                    {
                        "operation": operation,
                        "avg_ms": stats["duration"]["avg_ms"],
                        "max_ms": stats["duration"]["max_ms"],
                        "count": stats["count"],
                    }
                )

        # 按平均时间排序
        operations_by_time.sort(key=lambda x: x["avg_ms"], reverse=True)

        return operations_by_time[:top_n]

    def get_memory_intensive_operations(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """获取内存密集型操作"""
        operations_by_memory = []

        for operation, metrics in self.metrics.items():
            stats = metrics.get_statistics()
            if stats and stats.get("memory"):
                operations_by_memory.append(
                    {
                        "operation": operation,
                        "avg_delta": stats["memory"]["avg_delta"],
                        "max_delta": stats["memory"]["max_delta"],
                        "total_delta": stats["memory"]["total_delta"],
                        "count": stats["count"],
                    }
                )

        # 按平均内存增量排序
        operations_by_memory.sort(key=lambda x: abs(x["avg_delta"]), reverse=True)

        return operations_by_memory[:top_n]

    def auto_optimize_suggestions(self) -> List[Dict[str, Any]]:
        """生成自动优化建议"""
        suggestions: List[Dict[str, Any]] = []

        # 分析每个操作
        for operation, metrics in self.metrics.items():
            stats = metrics.get_statistics()
            if not stats:
                continue

            duration_stats = cast(Dict[str, Any], stats.get("duration", {}))
            memory_stats = cast(Dict[str, Any], stats.get("memory", {}))

            # 检测需要优化的操作
            if duration_stats.get("avg_ms", 0) > 500:
                suggestions.append(
                    {
                        "operation": operation,
                        "issue": "平均耗时过长",
                        "current": f"{duration_stats['avg_ms']:.2f}ms",
                        "target": "<100ms",
                        "suggestion": "考虑使用缓存、异步处理或优化算法",
                        "priority": "HIGH",
                    }
                )

            # 检测性能不稳定的操作
            if duration_stats.get("stdev_ms", 0) > duration_stats.get("avg_ms", 1) * 0.5:
                suggestions.append(
                    {
                        "operation": operation,
                        "issue": "性能不稳定",
                        "current": f"标准差: {duration_stats['stdev_ms']:.2f}ms",
                        "target": "标准差 < 平均值的20%",
                        "suggestion": "检查是否有偶发的性能问题，如网络延迟、锁竞争等",
                        "priority": "MEDIUM",
                    }
                )

            # 检测内存问题
            if abs(memory_stats.get("avg_delta", 0)) > 10 * 1024 * 1024:  # 10MB
                suggestions.append(
                    {
                        "operation": operation,
                        "issue": "内存使用过多",
                        "current": f"{abs(memory_stats['avg_delta']) / 1024 / 1024:.2f}MB",
                        "target": "<1MB",
                        "suggestion": "优化数据结构、使用生成器或分批处理",
                        "priority": (
                            "HIGH"
                            if abs(memory_stats["avg_delta"]) > 50 * 1024 * 1024
                            else "MEDIUM"
                        ),
                    }
                )

            # 检测频繁的慢操作
            slow_ratio = float(stats.get("slow_operations", 0)) / max(1, int(stats.get("count", 1)))
            if slow_ratio > 0.1:  # 超过10%的操作是慢操作
                suggestions.append(
                    {
                        "operation": operation,
                        "issue": "频繁出现慢操作",
                        "current": f"{slow_ratio * 100:.1f}%的操作超过{self.threshold_ms}ms",
                        "target": "<5%",
                        "suggestion": "分析慢操作的具体原因，可能需要优化数据库查询或算法",
                        "priority": "HIGH" if slow_ratio > 0.3 else "MEDIUM",
                    }
                )

        # 按优先级排序
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        suggestions.sort(key=lambda x: priority_order.get(x.get("priority", "LOW"), 3))

        return suggestions

    def compare_operations(self, op1: str, op2: str) -> Dict[str, Any]:
        """比较两个操作的性能"""
        stats1 = self.metrics[op1].get_statistics() if op1 in self.metrics else None
        stats2 = self.metrics[op2].get_statistics() if op2 in self.metrics else None

        if not stats1 or not stats2:
            return {"error": "操作数据不足"}

        comparison = {
            "operation1": op1,
            "operation2": op2,
            "performance": {
                "avg_ms_diff": stats1["duration"]["avg_ms"] - stats2["duration"]["avg_ms"],
                "max_ms_diff": stats1["duration"]["max_ms"] - stats2["duration"]["max_ms"],
                "faster": (
                    op1 if stats1["duration"]["avg_ms"] < stats2["duration"]["avg_ms"] else op2
                ),
            },
            "memory": {
                "avg_delta_diff": stats1["memory"]["avg_delta"] - stats2["memory"]["avg_delta"],
                "more_efficient": (
                    op1
                    if abs(stats1["memory"]["avg_delta"]) < abs(stats2["memory"]["avg_delta"])
                    else op2
                ),
            },
            "stability": {
                "stdev_diff": stats1["duration"]["stdev_ms"] - stats2["duration"]["stdev_ms"],
                "more_stable": (
                    op1 if stats1["duration"]["stdev_ms"] < stats2["duration"]["stdev_ms"] else op2
                ),
            },
        }

        return comparison

    def reset(self):
        """重置所有性能数据"""
        with self._lock:
            self.metrics.clear()
            self.slow_operations.clear()
            self.auto_suggestions.clear()
            logger.info("性能分析器已重置")

    def set_threshold(self, threshold_ms: float):
        """设置慢操作阈值"""
        self.threshold_ms = threshold_ms
        for metrics in self.metrics.values():
            metrics.slow_threshold_ms = threshold_ms
        logger.info(f"慢操作阈值已设置为 {threshold_ms}ms")

    def enable(self):
        """启用性能分析"""
        self.enabled = True
        logger.info("性能分析已启用")

    def disable(self):
        """禁用性能分析"""
        self.enabled = False
        logger.info("性能分析已禁用")

    def export_report(self, filepath: str | None = None) -> str:
        """导出性能报告"""
        import json

        if not filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_dir = logger_manager.ensure_subdirectory("performance")
            file_path = target_dir / f"profile_{timestamp}.json"
        else:
            file_path = Path(filepath)
            file_path.parent.mkdir(parents=True, exist_ok=True)

        report = self.get_report()
        report["suggestions"] = self.auto_optimize_suggestions()

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"性能报告已导出: {file_path}")
        return str(file_path)


# 创建全局实例
profiler = PerformanceProfiler()


# 便捷装饰器
def profile_performance(operation: str | None = None):
    """性能分析装饰器"""

    def decorator(func):
        op_name = operation or f"{func.__module__}.{func.__name__}"

        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                with profiler.profile(op_name):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                with profiler.profile(op_name):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator
