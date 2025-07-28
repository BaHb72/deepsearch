"""
Event System Monitoring Module

This module provides comprehensive monitoring and observability features for the event system,
including metrics collection, performance tracking, and health monitoring.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Deque

from deepsearch.core.interfaces import MonitoringHook
from deepsearch.event.engine import Event, EventEngine
from deepsearch.messaging.bus import MessageBus as AbstractMessageBus

# ==============================================================================
# Constants
# ==============================================================================

DEFAULT_METRICS_WINDOW = 300  # 5 minutes
DEFAULT_HISTOGRAM_BUCKETS = [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
MAX_SLOW_EVENTS = 100
HEALTH_CHECK_INTERVAL = 60  # 1 minute
METRICS_EXPORT_INTERVAL = 60  # 1 minute

# ==============================================================================
# Type Definitions and Logger
# ==============================================================================

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class HealthStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# ==============================================================================
# Metric Data Structures
# ==============================================================================


@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class EventMetrics:
    """Metrics for a specific event type"""
    event_type: str
    total_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_processing_time: float = 0.0
    min_processing_time: float = float('inf')
    max_processing_time: float = 0.0
    last_event_time: Optional[float] = None

    @property
    def average_processing_time(self) -> float:
        """Calculate average processing time"""
        if self.total_count == 0:
            return 0.0
        return self.total_processing_time / self.total_count

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_count == 0:
            return 1.0
        return self.success_count / self.total_count

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate"""
        if self.total_count == 0:
            return 0.0
        return self.failure_count / self.total_count


@dataclass
class SlowEventRecord:
    """Record of a slow event"""
    event_type: str
    processing_time: float
    timestamp: float
    handler_name: str
    event_data: Optional[Dict[str, Any]] = None


# ==============================================================================
# Metrics Collector
# ==============================================================================


class MetricsCollector:
    """Collects and aggregates event system metrics"""

    def __init__(self, window_size: int = DEFAULT_METRICS_WINDOW):
        self._window_size = window_size
        self._metrics: Dict[str, EventMetrics] = {}
        self._time_series: Dict[str, Deque[MetricPoint]] = defaultdict(lambda: deque(maxlen=1000))
        self._slow_events: Deque[SlowEventRecord] = deque(maxlen=MAX_SLOW_EVENTS)
        self._handler_metrics: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._lock = threading.RLock()

    def record_event(
            self,
            event_type: str,
            processing_time: float,
            success: bool,
            handler_name: Optional[str] = None,
            labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record an event execution"""
        timestamp = time.time()

        with self._lock:
            # Update event metrics
            if event_type not in self._metrics:
                self._metrics[event_type] = EventMetrics(event_type)

            metrics = self._metrics[event_type]
            metrics.total_count += 1
            metrics.total_processing_time += processing_time
            metrics.last_event_time = timestamp

            if success:
                metrics.success_count += 1
            else:
                metrics.failure_count += 1

            # Update min/max
            metrics.min_processing_time = min(metrics.min_processing_time, processing_time)
            metrics.max_processing_time = max(metrics.max_processing_time, processing_time)

            # Record time series data
            point = MetricPoint(timestamp, processing_time, labels or {})
            self._time_series[f"{event_type}_processing_time"].append(point)

            # Track handler metrics
            if handler_name:
                self._handler_metrics[handler_name]["count"] += 1
                self._handler_metrics[handler_name]["total_time"] += processing_time

            # Track slow events
            if processing_time > 1.0:  # Events taking more than 1 second
                self._slow_events.append(SlowEventRecord(
                    event_type=event_type,
                    processing_time=processing_time,
                    timestamp=timestamp,
                    handler_name=handler_name or "unknown"
                ))

    def get_metrics(self, event_type: Optional[str] = None) -> Dict[str, EventMetrics]:
        """Get metrics for specific event type or all types"""
        with self._lock:
            if event_type:
                return {event_type: self._metrics.get(event_type, EventMetrics(event_type))}
            return self._metrics.copy()

    def get_handler_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get metrics grouped by handler"""
        with self._lock:
            result = {}
            for handler, metrics in self._handler_metrics.items():
                result[handler] = {
                    "count": metrics["count"],
                    "total_time": metrics["total_time"],
                    "average_time": metrics["total_time"] / metrics["count"] if metrics["count"] > 0 else 0
                }
            return result

    def get_slow_events(self, limit: Optional[int] = None) -> List[SlowEventRecord]:
        """Get slow event records"""
        with self._lock:
            events = list(self._slow_events)
            if limit:
                events = events[-limit:]
            return events

    def get_time_series(self, metric_name: str, start_time: Optional[float] = None) -> List[MetricPoint]:
        """Get time series data for a metric"""
        with self._lock:
            points = list(self._time_series.get(metric_name, []))
            if start_time:
                points = [p for p in points if p.timestamp >= start_time]
            return points

    def calculate_percentiles(self, event_type: str, percentiles: List[float]) -> Dict[float, float]:
        """Calculate percentiles for event processing times"""
        metric_name = f"{event_type}_processing_time"
        points = self.get_time_series(metric_name)

        if not points:
            return {p: 0.0 for p in percentiles}

        values = sorted([p.value for p in points])
        result = {}

        for percentile in percentiles:
            index = int(len(values) * percentile / 100)
            if index >= len(values):
                index = len(values) - 1
            result[percentile] = values[index]

        return result

    def reset_metrics(self) -> None:
        """Reset all metrics"""
        with self._lock:
            self._metrics.clear()
            self._time_series.clear()
            self._slow_events.clear()
            self._handler_metrics.clear()


# ==============================================================================
# Monitoring Hook Implementation
# ==============================================================================


class MetricsCollectorHook(MonitoringHook):
    """
    监控钩子实现，用于收集事件处理的性能指标
    """

    def __init__(self, collector: MetricsCollector):
        self._collector = collector

    def on_handler_start(self, handler_name: str, event_type: str) -> None:
        """处理器开始执行时的钩子"""
        # 可以在这里记录开始时间或其他预处理
        pass

    def on_handler_complete(self, handler_name: str, event_type: str, duration: float, error: Exception = None) -> None:
        """处理器执行完成时的钩子"""
        success = error is None

        # 记录事件处理的指标
        self._collector.record_event(
            event_type=event_type,
            processing_time=duration,
            success=success,
            handler_name=handler_name
        )

        # 如果有错误，记录错误信息
        if error:
            logger.error(f"Handler {handler_name} failed for event {event_type}: {error}")


# ==============================================================================
# Performance Monitor
# ==============================================================================


class PerformanceMonitor:
    """Monitors event system performance"""

    def __init__(self, engine: EventEngine, collector: MetricsCollector):
        self._engine = engine
        self._collector = collector
        self._monitoring = False
        self._monitoring_hook: Optional[MetricsCollectorHook] = None

    def start_monitoring(self) -> None:
        """Start monitoring event handlers"""
        if self._monitoring:
            return

        self._monitoring = True

        # 创建并添加监控钩子
        self._monitoring_hook = MetricsCollectorHook(self._collector)
        self._engine.add_monitoring_hook(self._monitoring_hook)

        logger.info("性能监控已启动")

    def stop_monitoring(self) -> None:
        """Stop monitoring event handlers"""
        if not self._monitoring:
            return

        self._monitoring = False

        # 移除监控钩子
        if self._monitoring_hook:
            self._engine.remove_monitoring_hook(self._monitoring_hook)
            self._monitoring_hook = None

        logger.info("性能监控已停止")

    def get_statistics(self) -> Dict[str, Any]:
        """获取性能监控统计信息"""
        return {
            "monitoring": self._monitoring,
            "collector_stats": self._collector.get_metrics() if self._collector else {},
            "handler_metrics": self._collector.get_handler_metrics() if self._collector else {}
        }


# ==============================================================================
# Health Monitor
# ==============================================================================


@dataclass
class HealthCheck:
    """Health check configuration"""
    name: str
    check_func: Callable[[], Tuple[bool, Optional[str]]]
    critical: bool = False
    timeout: float = 5.0


class HealthMonitor:
    """Monitors event system health"""

    def __init__(self):
        self._checks: List[HealthCheck] = []
        self._last_results: Dict[str, Tuple[bool, Optional[str], float]] = {}
        self._monitoring = False
        self._thread: Optional[threading.Thread] = None

    def add_check(self, check: HealthCheck) -> None:
        """Add a health check"""
        self._checks.append(check)

    def remove_check(self, name: str) -> None:
        """Remove a health check by name"""
        self._checks = [c for c in self._checks if c.name != name]

    def start_monitoring(self) -> None:
        """Start health monitoring"""
        if self._monitoring:
            return

        self._monitoring = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("健康监控已启动")

    def stop_monitoring(self) -> None:
        """Stop health monitoring"""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("健康监控已停止")

    def _monitor_loop(self) -> None:
        """Main monitoring loop"""
        while self._monitoring:
            self._run_checks()
            time.sleep(HEALTH_CHECK_INTERVAL)

    def _run_checks(self) -> None:
        """Run all health checks"""
        for check in self._checks:
            start_time = time.time()

            try:
                success, message = check.check_func()
                duration = time.time() - start_time
                self._last_results[check.name] = (success, message, duration)

                if not success:
                    logger.warning(f"Health check '{check.name}' failed: {message}")

            except Exception as e:
                duration = time.time() - start_time
                self._last_results[check.name] = (False, str(e), duration)
                logger.error(f"Health check '{check.name}' error: {e}")

    def get_status(self) -> Tuple[HealthStatus, Dict[str, Any]]:
        """Get overall health status"""
        if not self._last_results:
            return HealthStatus.HEALTHY, {"message": "No checks configured"}

        critical_failed = False
        any_failed = False
        details = {}

        for check in self._checks:
            if check.name in self._last_results:
                success, message, duration = self._last_results[check.name]
                details[check.name] = {
                    "success": success,
                    "message": message,
                    "duration": duration,
                    "critical": check.critical
                }

                if not success:
                    any_failed = True
                    if check.critical:
                        critical_failed = True

        if critical_failed:
            status = HealthStatus.UNHEALTHY
        elif any_failed:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY

        return status, details


# ==============================================================================
# Event System Monitor
# ==============================================================================


class EventSystemMonitor:
    """Comprehensive monitoring for the event system"""

    def __init__(self, engine: EventEngine, bus: Optional[AbstractMessageBus] = None):
        self._engine = engine
        self._bus = bus
        self._collector = MetricsCollector()
        self._performance_monitor = PerformanceMonitor(engine, self._collector)
        self._health_monitor = HealthMonitor()
        self._export_thread: Optional[threading.Thread] = None
        self._monitoring = False

        # Setup default health checks
        self._setup_default_health_checks()

    def _setup_default_health_checks(self) -> None:
        """Setup default health checks"""
        # Engine health check
        self._health_monitor.add_check(HealthCheck(
            name="engine_running",
            check_func=self._check_engine_health,
            critical=True
        ))

        # Message bus health check (if available)
        if self._bus:
            self._health_monitor.add_check(HealthCheck(
                name="message_bus",
                check_func=self._check_bus_health,
                critical=True
            ))

        # Queue size check
        self._health_monitor.add_check(HealthCheck(
            name="queue_size",
            check_func=self._check_queue_size,
            critical=False
        ))

        # Processing latency check
        self._health_monitor.add_check(HealthCheck(
            name="processing_latency",
            check_func=self._check_processing_latency,
            critical=False
        ))

    def _check_engine_health(self) -> Tuple[bool, Optional[str]]:
        """Check if engine is running"""
        if self._engine._running:
            return True, None
        return False, "Engine is not running"

    def _check_bus_health(self) -> Tuple[bool, Optional[str]]:
        """Check message bus health"""
        if not self._bus:
            return True, None

        try:
            # 简单的连通性检查 - 不发布事件，只检查总线状态
            # 检查是否有可用的总线实例
            if hasattr(self._bus, '_buses'):
                if self._bus._buses:
                    return True, None
                else:
                    # 没有配置的消息总线也是正常的
                    return True, "没有启用的消息总线"
            else:
                return False, "消息总线状态异常"
        except Exception as e:
            return False, f"总线错误: {str(e)}"

    def _check_queue_size(self) -> Tuple[bool, Optional[str]]:
        """Check event queue size"""
        queue_size = self._engine._queue.qsize()
        if queue_size > 1000:
            return False, f"Queue size too large: {queue_size}"
        return True, None

    def _check_processing_latency(self) -> Tuple[bool, Optional[str]]:
        """Check average processing latency"""
        metrics = self._collector.get_metrics()
        if not metrics:
            return True, None

        total_events = sum(m.total_count for m in metrics.values())
        if total_events == 0:
            return True, None

        avg_latency = sum(m.average_processing_time for m in metrics.values()) / len(metrics)
        if avg_latency > 1.0:  # 1 second threshold
            return False, f"High average latency: {avg_latency:.3f}s"
        return True, None

    def start(self) -> None:
        """Start all monitoring"""
        if self._monitoring:
            return

        self._monitoring = True
        self._performance_monitor.start_monitoring()
        self._health_monitor.start_monitoring()

        # Start metrics export thread
        self._export_thread = threading.Thread(target=self._export_loop, daemon=True)
        self._export_thread.start()

        logger.info("事件系统监控已启动")

    def stop(self) -> None:
        """Stop all monitoring"""
        if not self._monitoring:
            return

        self._monitoring = False
        self._performance_monitor.stop_monitoring()
        self._health_monitor.stop_monitoring()

        if self._export_thread:
            self._export_thread.join(timeout=10)

        logger.info("事件系统监控已停止")

    def _export_loop(self) -> None:
        """Export metrics periodically"""
        while self._monitoring:
            self._export_metrics()
            time.sleep(METRICS_EXPORT_INTERVAL)

    def _export_metrics(self) -> None:
        """Export metrics (placeholder for actual export)"""
        try:
            metrics = self.get_summary()
            # 这里可以添加导出逻辑，比如写入文件或发送到监控系统
            logger.debug(f"Exported metrics: {json.dumps(metrics, indent=2)}")
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """Get monitoring summary"""
        health_status, health_details = self._health_monitor.get_status()
        event_metrics = self._collector.get_metrics()
        handler_metrics = self._collector.get_handler_metrics()
        slow_events = self._collector.get_slow_events(limit=10)

        return {
            "timestamp": datetime.now().isoformat(),
            "health": {
                "status": health_status.value,
                "checks": health_details
            },
            "events": {
                event_type: {
                    "total": metrics.total_count,
                    "success_rate": metrics.success_rate,
                    "avg_processing_time": metrics.average_processing_time,
                    "min_processing_time": metrics.min_processing_time,
                    "max_processing_time": metrics.max_processing_time
                }
                for event_type, metrics in event_metrics.items()
            },
            "handlers": handler_metrics,
            "slow_events": [
                {
                    "event_type": e.event_type,
                    "processing_time": e.processing_time,
                    "handler": e.handler_name,
                    "timestamp": datetime.fromtimestamp(e.timestamp).isoformat()
                }
                for e in slow_events
            ]
        }

    def get_metrics_collector(self) -> MetricsCollector:
        """Get the metrics collector instance"""
        return self._collector

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取事件系统监控的统计信息
        
        :return: 包含所有监控子系统统计信息的字典
        """
        stats = {
            "monitoring": self._monitoring,
            "performance": {},
            "health": {},
            "metrics": {}
        }

        # 获取性能监控统计
        if self._performance_monitor:
            perf_stats = self._performance_monitor.get_statistics()
            stats["performance"] = perf_stats

        # 获取健康监控统计
        if self._health_monitor:
            health_status, health_details = self._health_monitor.get_status()
            health_stats = {
                "monitoring": self._health_monitor._monitoring,
                "status": health_status.value,
                "checks": health_details
            }
            stats["health"] = health_stats

        # 获取度量收集器统计
        if self._collector:
            metrics_summary = {
                "event_metrics": self._collector.get_metrics(),
                "handler_metrics": self._collector.get_handler_metrics(),
                "slow_events_count": len(self._collector.get_slow_events())
            }
            stats["metrics"] = metrics_summary

        return stats


# ==============================================================================
# Monitoring Decorators
# ==============================================================================


def monitored_handler(event_type: str, monitor: EventSystemMonitor):
    """Decorator to automatically monitor event handlers"""

    def decorator(func):
        def wrapper(event: Event):
            collector = monitor.get_metrics_collector()
            start_time = time.time()
            success = True

            try:
                result = func(event)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                processing_time = time.time() - start_time
                collector.record_event(
                    event_type=event_type,
                    processing_time=processing_time,
                    success=success,
                    handler_name=func.__name__
                )

        return wrapper

    return decorator


# ==============================================================================
# Module Summary
# ==============================================================================
"""
Event System Monitoring Module

This module provides comprehensive monitoring capabilities:

1. Metrics Collection:
   - Event counts and processing times
   - Success/failure rates
   - Handler-level metrics
   - Time series data
   - Slow event tracking

2. Performance Monitoring:
   - Automatic handler wrapping
   - Processing time measurement
   - Percentile calculations

3. Health Monitoring:
   - Configurable health checks
   - Critical vs non-critical checks
   - Automatic status aggregation

4. Event System Monitor:
   - Unified monitoring interface
   - Default health checks
   - Metrics export capability
   - Summary generation

Usage Example:
    from deepsearch.event.monitoring import EventSystemMonitor
    
    # Create monitor
    monitor = EventSystemMonitor(engine, bus)
    
    # Start monitoring
    monitor.start()
    
    # Get monitoring summary
    summary = monitor.get_summary()
    
    # Use decorator for automatic monitoring
    @monitored_handler("TICK", monitor)
    def handle_tick(event: Event):
        process_tick(event.data)
"""
