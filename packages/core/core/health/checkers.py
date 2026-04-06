"""
具体的健康检查器实现

为各个系统组件提供专门的健康检查器
"""

import time

import psutil
from loguru import logger
from sqlalchemy import text

from ..interfaces import ComponentStatus
from .interfaces import HealthChecker, HealthCheckResult, HealthMetrics, HealthStatus


class DatabaseHealthChecker(HealthChecker):
    """数据库健康检查器"""

    # 默认配置
    DEFAULT_LATENCY_THRESHOLD_MS = 1000.0

    def __init__(self, latency_threshold_ms: float = DEFAULT_LATENCY_THRESHOLD_MS):
        """
        初始化数据库健康检查器

        Args:
            latency_threshold_ms: 查询延迟阈值（毫秒），超过此值触发 DEGRADED
        """
        super().__init__("database")
        self._latency_threshold_ms = latency_threshold_ms

    def configure(self, latency_threshold_ms: float | None = None) -> None:
        """
        动态配置检查器参数

        Args:
            latency_threshold_ms: 查询延迟阈值（毫秒）
        """
        if latency_threshold_ms is not None:
            self._latency_threshold_ms = latency_threshold_ms

    async def check(self) -> HealthCheckResult:
        """执行数据库健康检查"""
        try:
            # 检查组件是否存在
            if not self._component:
                return HealthCheckResult(
                    status=HealthStatus.UNKNOWN, message="Database component not available"
                )

            # 检查连接状态
            if not self._component.is_connected():
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="Database not connected",
                    details={
                        "connected": False,
                        "status": (
                            self._component.status.value
                            if hasattr(self._component, "status")
                            else "unknown"
                        ),
                    },
                )

            # 执行查询测试（仅计量查询时间，不含连接获取开销）
            try:
                async with self._component._engine.begin() as conn:
                    start_time = time.perf_counter()
                    await conn.execute(text("SELECT 1"))
                    query_time = (time.perf_counter() - start_time) * 1000
            except Exception as e:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Database query failed: {str(e)}",
                    errors=[str(e)],
                )

            # 获取连接池状态
            pool_stats = {}
            try:
                pool = self._component._engine.pool
                pool_stats = {
                    "size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "overflow": pool.overflow(),
                    "total": pool.size() + pool.overflow(),
                }
                pool_utilization = (
                    (pool_stats["total"] - pool_stats["checked_in"]) / pool_stats["total"]
                    if pool_stats["total"] > 0
                    else 0
                )
            except Exception as e:
                logger.debug(f"Failed to get pool stats: {e}")
                pool_utilization = 0

            # 检查 TimescaleDB
            timescale_info = {}
            if (
                hasattr(self._component, "_is_timescale_enabled")
                and self._component._is_timescale_enabled
            ):
                try:
                    async with self._component._engine.begin() as conn:
                        result = await conn.execute(
                            text("SELECT COUNT(*) FROM timescaledb_information.hypertables")
                        )
                        hypertable_count = result.scalar()
                        timescale_info = {"enabled": True, "hypertable_count": hypertable_count}
                except Exception as e:
                    timescale_info = {"enabled": True, "error": str(e)}

            # 构建健康指标
            metrics = HealthMetrics(
                response_time_ms=query_time,
                connection_count=pool_stats.get("total", 0),
                custom_metrics={
                    "pool_utilization": pool_utilization,
                    "pool_checked_in": pool_stats.get("checked_in", 0),
                },
            )

            # 确定健康状态
            if query_time > self._latency_threshold_ms:
                status = HealthStatus.DEGRADED
                message = f"Database response time is high ({query_time:.1f}ms > {self._latency_threshold_ms}ms)"
            elif pool_utilization > 0.8:  # 连接池使用率超过80%
                status = HealthStatus.DEGRADED
                message = "Database connection pool utilization is high"
            else:
                status = HealthStatus.HEALTHY
                message = "Database is healthy"

            return HealthCheckResult(
                status=status,
                message=message,
                details={
                    "connected": True,
                    "pool_stats": pool_stats,
                    "timescaledb": timescale_info,
                },
                metrics=metrics,
            )

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                errors=[str(e)],
            )


class RedisHealthChecker(HealthChecker):
    """Redis缓存健康检查器"""

    # 默认配置
    DEFAULT_LATENCY_THRESHOLD_MS = 50.0
    DEFAULT_LATENCY_SAMPLES = 3
    DEFAULT_CONSECUTIVE_DEGRADED = 2

    def __init__(
        self,
        latency_threshold_ms: float = DEFAULT_LATENCY_THRESHOLD_MS,
        latency_samples: int = DEFAULT_LATENCY_SAMPLES,
        consecutive_degraded: int = DEFAULT_CONSECUTIVE_DEGRADED,
    ):
        """
        初始化 Redis 健康检查器

        Args:
            latency_threshold_ms: 响应延迟阈值（毫秒），超过此值触发 DEGRADED
            latency_samples: 延迟测量采样次数，取中位数以避免偶发毛刺
            consecutive_degraded: 连续高延迟次数阈值，达到后才判定 DEGRADED
        """
        super().__init__("redis")
        self._latency_threshold_ms = latency_threshold_ms
        self._latency_samples = max(1, min(latency_samples, 10))  # 限制范围 1-10
        self._consecutive_degraded = max(1, consecutive_degraded)
        self._high_latency_streak = 0

    def configure(
        self,
        latency_threshold_ms: float | None = None,
        latency_samples: int | None = None,
        consecutive_degraded: int | None = None,
    ) -> None:
        """
        动态配置检查器参数

        Args:
            latency_threshold_ms: 响应延迟阈值（毫秒）
            latency_samples: 延迟测量采样次数
            consecutive_degraded: 连续高延迟次数阈值
        """
        if latency_threshold_ms is not None:
            self._latency_threshold_ms = latency_threshold_ms
        if latency_samples is not None:
            self._latency_samples = max(1, min(latency_samples, 10))
        if consecutive_degraded is not None:
            self._consecutive_degraded = max(1, consecutive_degraded)

    async def _measure_ping_latency(self) -> float:
        """
        测量 Redis ping 延迟，使用多次采样取中位数

        Returns:
            中位数延迟（毫秒）
        """
        latencies = []
        for _ in range(self._latency_samples):
            start_time = time.perf_counter()
            await self._component._redis_client.ping()
            latency = (time.perf_counter() - start_time) * 1000
            latencies.append(latency)

        # 返回中位数
        latencies.sort()
        mid = len(latencies) // 2
        if len(latencies) % 2 == 0:
            return (latencies[mid - 1] + latencies[mid]) / 2
        return latencies[mid]

    async def check(self) -> HealthCheckResult:
        """执行Redis健康检查"""
        try:
            # 检查组件是否存在
            if not self._component:
                return HealthCheckResult(
                    status=HealthStatus.UNKNOWN, message="Redis component not available"
                )

            # 检查连接状态
            if not self._component.is_connected():
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="Redis not connected",
                    details={
                        "connected": False,
                        "disconnect_reason": getattr(self._component, "_connection_error", None),
                    },
                )

            # Ping测试（多次采样取中位数）
            try:
                ping_time = await self._measure_ping_latency()
            except Exception as e:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Redis ping failed: {str(e)}",
                    errors=[str(e)],
                )

            # 获取Redis信息
            try:
                info = await self._component._redis_client.info()
                redis_version = info.get("redis_version", "unknown")
                connected_clients = info.get("connected_clients", 0)
                used_memory = info.get("used_memory", 0)
                used_memory_human = info.get("used_memory_human", "unknown")
                maxmemory = info.get("maxmemory", 0)

                # 计算内存使用率
                memory_usage_percent = 0
                if maxmemory > 0:
                    memory_usage_percent = (used_memory / maxmemory) * 100

            except Exception as e:
                logger.debug(f"Failed to get Redis info: {e}")
                redis_version = "unknown"
                connected_clients = 0
                used_memory = 0
                used_memory_human = "unknown"
                memory_usage_percent = 0

            # 确定健康状态
            if ping_time > self._latency_threshold_ms:
                self._high_latency_streak += 1
                if self._high_latency_streak >= self._consecutive_degraded:
                    status = HealthStatus.DEGRADED
                    message = (
                        "Redis response time is high "
                        f"({ping_time:.1f}ms > {self._latency_threshold_ms}ms, "
                        f"streak={self._high_latency_streak})"
                    )
                else:
                    status = HealthStatus.HEALTHY
                    message = (
                        "Redis latency spike observed "
                        f"({ping_time:.1f}ms > {self._latency_threshold_ms}ms, "
                        f"streak={self._high_latency_streak}/{self._consecutive_degraded})"
                    )
            elif memory_usage_percent > 90:  # 内存使用率超过90%
                self._high_latency_streak = 0
                status = HealthStatus.DEGRADED
                message = "Redis memory usage is high"
            else:
                self._high_latency_streak = 0
                status = HealthStatus.HEALTHY
                message = "Redis is healthy"

            # 构建健康指标（使用已更新后的 streak）
            metrics = HealthMetrics(
                response_time_ms=ping_time,
                memory_usage_mb=used_memory / 1024 / 1024 if used_memory else None,
                connection_count=connected_clients,
                custom_metrics={
                    "memory_usage_percent": memory_usage_percent,
                    "version": redis_version,
                    "high_latency_streak": self._high_latency_streak,
                },
            )

            return HealthCheckResult(
                status=status,
                message=message,
                details={
                    "connected": True,
                    "version": redis_version,
                    "connected_clients": connected_clients,
                    "used_memory": used_memory_human,
                },
                metrics=metrics,
            )

        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                errors=[str(e)],
            )


class EventEngineHealthChecker(HealthChecker):
    """事件引擎健康检查器"""

    def __init__(self):
        super().__init__("event_engine")

    async def check(self) -> HealthCheckResult:
        """执行事件引擎健康检查"""
        try:
            # 检查组件是否存在
            if not self._component:
                return HealthCheckResult(
                    status=HealthStatus.UNKNOWN, message="EventEngine component not available"
                )

            # 检查引擎状态
            engine = getattr(self._component, "resource", None)
            if not engine:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY, message="EventEngine not initialized"
                )

            # 检查运行状态
            is_running = getattr(engine, "_running", False)
            if not is_running:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY, message="EventEngine is not running"
                )

            # 获取队列状态
            queue_size = 0
            max_queue_size = 0
            try:
                if hasattr(engine, "_queue"):
                    queue_size = engine._queue.qsize()
                    max_queue_size = engine._queue.maxsize
            except Exception as e:
                logger.debug(f"Failed to get queue size: {e}")

            # 获取处理统计
            processed_count = getattr(engine, "_processed_count", 0)
            error_count = getattr(engine, "_error_count", 0)

            # 计算错误率
            error_rate: float = 0.0
            if processed_count > 0:
                error_rate = float(error_count) / float(processed_count)

            # 获取系统资源使用
            process = psutil.Process()
            cpu_percent = process.cpu_percent(interval=0.1)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            # 构建健康指标
            metrics = HealthMetrics(
                cpu_usage_percent=cpu_percent,
                memory_usage_mb=memory_mb,
                queue_size=queue_size,
                error_rate=error_rate,
                custom_metrics={"processed_count": processed_count, "error_count": error_count},
            )

            # 确定健康状态
            if queue_size > max_queue_size * 0.8:  # 队列使用率超过80%
                status = HealthStatus.DEGRADED
                message = "Event queue is nearly full"
            elif error_rate > 0.1:  # 错误率超过10%
                status = HealthStatus.DEGRADED
                message = "High error rate in event processing"
            else:
                status = HealthStatus.HEALTHY
                message = "EventEngine is healthy"

            return HealthCheckResult(
                status=status,
                message=message,
                details={
                    "running": is_running,
                    "queue_size": queue_size,
                    "max_queue_size": max_queue_size,
                    "processed_count": processed_count,
                    "error_count": error_count,
                },
                metrics=metrics,
            )

        except Exception as e:
            logger.error(f"EventEngine health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                errors=[str(e)],
            )


class MessageBusHealthChecker(HealthChecker):
    """消息总线健康检查器"""

    def __init__(self):
        super().__init__("message_bus")

    async def check(self) -> HealthCheckResult:
        """执行消息总线健康检查"""
        try:
            # 检查组件是否存在
            if not self._component:
                return HealthCheckResult(
                    status=HealthStatus.UNKNOWN, message="MessageBus component not available"
                )

            # 检查组件状态
            status = getattr(self._component, "status", ComponentStatus.UNKNOWN)
            if status != ComponentStatus.RUNNING:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"MessageBus is not running (status: {status.value})",
                )

            # 获取消息总线实例
            bus = getattr(self._component, "resource", None)
            if not bus:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY, message="MessageBus instance not found"
                )

            # 检查各个总线后端状态
            bus_statuses = {}
            all_healthy = True

            if hasattr(bus, "_buses"):
                for bus_name, bus_instance in bus._buses.items():
                    try:
                        # 检查连接状态
                        is_connected = True
                        if hasattr(bus_instance, "is_connected"):
                            is_connected = bus_instance.is_connected()
                        elif hasattr(bus_instance, "_connected"):
                            is_connected = bus_instance._connected

                        bus_statuses[bus_name] = {
                            "connected": is_connected,
                            "type": type(bus_instance).__name__,
                        }

                        if not is_connected:
                            all_healthy = False

                    except Exception as e:
                        bus_statuses[bus_name] = {"connected": False, "error": str(e)}
                        all_healthy = False

            # 确定健康状态
            if not bus_statuses:
                status = HealthStatus.UNKNOWN
                message = "No message buses configured"
            elif all_healthy:
                status = HealthStatus.HEALTHY
                message = "All message buses are healthy"
            else:
                status = HealthStatus.DEGRADED
                message = "Some message buses are not connected"

            return HealthCheckResult(
                status=status,
                message=message,
                details={
                    "buses": bus_statuses,
                    "component_status": (
                        self._component.status.value
                        if hasattr(self._component, "status")
                        else "unknown"
                    ),
                },
            )

        except Exception as e:
            logger.error(f"MessageBus health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                errors=[str(e)],
            )


class MonitorHealthChecker(HealthChecker):
    """监控组件健康检查器"""

    def __init__(self):
        super().__init__("monitor")

    async def check(self) -> HealthCheckResult:
        """执行监控组件健康检查"""
        try:
            # 检查组件是否存在
            if not self._component:
                return HealthCheckResult(
                    status=HealthStatus.UNKNOWN, message="Monitor component not available"
                )

            # 检查监控器实例
            monitor = getattr(self._component, "monitor", None)
            if not monitor:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY, message="Monitor instance not found"
                )

            # 检查监控状态
            is_monitoring = getattr(monitor, "_monitoring", False)
            if not is_monitoring:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY, message="Monitor is not active"
                )

            # 获取监控统计
            stats = {}
            if hasattr(monitor, "get_statistics"):
                stats = monitor.get_statistics()

            # 获取系统指标
            metrics = HealthMetrics()
            if stats:
                metrics.custom_metrics = {
                    "total_events": stats.get("total_events", 0),
                    "event_types": len(stats.get("event_types", {})),
                    "handler_count": stats.get("handler_count", 0),
                }

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Monitor is healthy",
                details={"monitoring": is_monitoring, "statistics": stats},
                metrics=metrics,
            )

        except Exception as e:
            logger.error(f"Monitor health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                errors=[str(e)],
            )


class GatewayHealthChecker(HealthChecker):
    """网关组件健康检查器"""

    def __init__(self):
        super().__init__("gateway")

    async def check(self) -> HealthCheckResult:
        """执行网关健康检查"""
        try:
            # 检查组件是否存在
            if not self._component:
                return HealthCheckResult(
                    status=HealthStatus.UNKNOWN, message="Gateway component not available"
                )

            # 检查网关实例
            gateway = getattr(self._component, "gateway", None)
            if not gateway:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY, message="Gateway instance not found"
                )

            # 检查连接状态
            is_connected = False
            if hasattr(gateway, "_connected"):
                is_connected = gateway._connected

            # 检查关闭状态
            is_shutdown = False
            if hasattr(gateway, "_shutdown"):
                is_shutdown = gateway._shutdown

            # 确定健康状态
            if is_shutdown:
                status = HealthStatus.UNHEALTHY
                message = "Gateway is shutdown"
            elif not is_connected:
                status = HealthStatus.UNHEALTHY
                message = "Gateway is not connected"
            else:
                status = HealthStatus.HEALTHY
                message = "Gateway is healthy"

            return HealthCheckResult(
                status=status,
                message=message,
                details={"connected": is_connected, "shutdown": is_shutdown},
            )

        except Exception as e:
            logger.error(f"Gateway health check failed: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                errors=[str(e)],
            )
