"""
综合性能监控系统

提供全面的系统性能监控，包括：
- 系统资源监控（CPU、内存、磁盘）
- 数据库性能跟踪
- API端点性能分析
- 实时指标聚合
"""

import json
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, DefaultDict, Deque, Dict, List, Optional, Protocol, TypedDict, cast

import psutil
from loguru import logger


class DiskIOSnapshot(Protocol):
    read_bytes: int
    write_bytes: int
    read_count: int
    write_count: int


class NetworkIOSnapshot(Protocol):
    bytes_sent: int
    bytes_recv: int


class MetricLevel(Enum):
    """指标级别"""

    SYSTEM = "system"
    APPLICATION = "application"
    DATABASE = "database"
    NETWORK = "network"
    CUSTOM = "custom"


class AlertSeverity(Enum):
    """告警严重程度"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class SystemMetrics:
    """系统资源指标"""

    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_available: int
    memory_used: int
    disk_io_read_bytes: int
    disk_io_write_bytes: int
    network_sent_bytes: int
    network_recv_bytes: int
    process_count: int
    thread_count: int
    open_files: int

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "cpu": {"percent": round(self.cpu_percent, 2)},
            "memory": {
                "percent": round(self.memory_percent, 2),
                "available_mb": round(self.memory_available / 1024 / 1024, 2),
                "used_mb": round(self.memory_used / 1024 / 1024, 2),
            },
            "disk_io": {
                "read_mb": round(self.disk_io_read_bytes / 1024 / 1024, 2),
                "write_mb": round(self.disk_io_write_bytes / 1024 / 1024, 2),
            },
            "network": {
                "sent_mb": round(self.network_sent_bytes / 1024 / 1024, 2),
                "recv_mb": round(self.network_recv_bytes / 1024 / 1024, 2),
            },
            "process": {
                "count": self.process_count,
                "threads": self.thread_count,
                "open_files": self.open_files,
            },
        }


@dataclass
class DatabaseMetrics:
    """数据库性能指标"""

    timestamp: float
    active_connections: int = 0
    idle_connections: int = 0
    total_queries: int = 0
    slow_queries: int = 0
    failed_queries: int = 0
    avg_query_time: float = 0.0
    max_query_time: float = 0.0
    cache_hit_ratio: float = 0.0
    deadlocks: int = 0
    lock_waits: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "connections": {
                "active": self.active_connections,
                "idle": self.idle_connections,
                "total": self.active_connections + self.idle_connections,
            },
            "queries": {
                "total": self.total_queries,
                "slow": self.slow_queries,
                "failed": self.failed_queries,
                "error_rate": round(self.failed_queries / max(self.total_queries, 1) * 100, 2),
            },
            "performance": {
                "avg_query_time_ms": round(self.avg_query_time * 1000, 2),
                "max_query_time_ms": round(self.max_query_time * 1000, 2),
                "cache_hit_ratio": round(self.cache_hit_ratio * 100, 2),
            },
            "locks": {"deadlocks": self.deadlocks, "lock_waits": self.lock_waits},
        }


@dataclass
class ApplicationMetrics:
    """应用层指标"""

    timestamp: float
    request_count: int = 0
    request_rate: float = 0.0
    error_count: int = 0
    error_rate: float = 0.0
    avg_response_time: float = 0.0
    p50_response_time: float = 0.0
    p90_response_time: float = 0.0
    p99_response_time: float = 0.0
    active_sessions: int = 0
    cache_hit_rate: float = 0.0
    event_queue_size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "requests": {
                "count": self.request_count,
                "rate_per_sec": round(self.request_rate, 2),
                "error_count": self.error_count,
                "error_rate": round(self.error_rate * 100, 2),
            },
            "response_time": {
                "avg_ms": round(self.avg_response_time * 1000, 2),
                "p50_ms": round(self.p50_response_time * 1000, 2),
                "p90_ms": round(self.p90_response_time * 1000, 2),
                "p99_ms": round(self.p99_response_time * 1000, 2),
            },
            "application": {
                "active_sessions": self.active_sessions,
                "cache_hit_rate": round(self.cache_hit_rate * 100, 2),
                "event_queue_size": self.event_queue_size,
            },
        }


class CustomMetric(TypedDict):
    """自定义指标结构"""

    timestamp: float
    value: float
    tags: Dict[str, str]


@dataclass
class Alert:
    """性能告警"""

    id: str
    severity: AlertSeverity
    metric_level: MetricLevel
    message: str
    details: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "severity": self.severity.value,
            "level": self.metric_level.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class PerformanceTracker:
    """综合性能跟踪器"""

    def __init__(
        self, collect_interval: float = 1.0, history_size: int = 3600, enable_alerts: bool = True
    ):
        """
        初始化性能跟踪器

        Args:
            collect_interval: 采集间隔（秒）
            history_size: 历史数据保留数量
            enable_alerts: 是否启用告警
        """
        self.collect_interval = collect_interval
        self._history_size = history_size
        self.enable_alerts = enable_alerts

        # 指标历史
        self.system_metrics: Deque[SystemMetrics] = deque(maxlen=history_size)
        self.database_metrics: Deque[DatabaseMetrics] = deque(maxlen=history_size)
        self.application_metrics: Deque[ApplicationMetrics] = deque(maxlen=history_size)

        # 自定义指标
        self.custom_metrics: DefaultDict[str, Deque[CustomMetric]] = self._create_custom_metric_store(history_size)

        # 告警
        self.alerts: Dict[str, Alert] = {}
        self.alert_rules: List[Dict[str, Any]] = []

        # 回调函数
        self.metric_callbacks: List[Callable] = []
        self.alert_callbacks: List[Callable] = []

        # 状态
        self._running = False
        self._collect_thread = None
        self._last_disk_io: DiskIOSnapshot | None = None
        self._last_network_io: NetworkIOSnapshot | None = None
        self._process: psutil.Process = psutil.Process()

        # 初始化默认告警规则
        self._init_default_alert_rules()

    @property
    def history_size(self) -> int:
        """Return current history limit"""
        return self._history_size

    @history_size.setter
    def history_size(self, value: int):
        """Update history limit and trim existing buffers"""
        if value <= 0:
            raise ValueError("history_size must be positive")
        if value == self._history_size:
            return

        self._history_size = value

        self.system_metrics = deque(list(self.system_metrics)[-value:], maxlen=value)
        self.database_metrics = deque(list(self.database_metrics)[-value:], maxlen=value)
        self.application_metrics = deque(list(self.application_metrics)[-value:], maxlen=value)

        updated_custom = self._create_custom_metric_store(value)
        for name, metrics in self.custom_metrics.items():
            updated_custom[name].extend(list(metrics)[-value:])
        self.custom_metrics = updated_custom

    def _create_custom_metric_store(self, maxlen: int) -> DefaultDict[str, Deque[CustomMetric]]:
        """构造自定义指标缓冲区"""

        def _factory() -> Deque[CustomMetric]:
            return cast(Deque[CustomMetric], deque(maxlen=maxlen))

        return defaultdict(_factory)

    def _init_default_alert_rules(self):
        """初始化默认告警规则"""
        self.alert_rules = [
            {
                "name": "high_cpu",
                "level": MetricLevel.SYSTEM,
                "severity": AlertSeverity.WARNING,
                "condition": lambda m: m.cpu_percent > 80,
                "message": "CPU使用率过高: {cpu_percent:.1f}%",
            },
            {
                "name": "high_memory",
                "level": MetricLevel.SYSTEM,
                "severity": AlertSeverity.WARNING,
                "condition": lambda m: m.memory_percent > 85,
                "message": "内存使用率过高: {memory_percent:.1f}%",
            },
            {
                "name": "critical_memory",
                "level": MetricLevel.SYSTEM,
                "severity": AlertSeverity.CRITICAL,
                "condition": lambda m: m.memory_percent > 95,
                "message": "内存使用率危急: {memory_percent:.1f}%",
            },
            {
                "name": "high_error_rate",
                "level": MetricLevel.APPLICATION,
                "severity": AlertSeverity.ERROR,
                "condition": lambda m: m.error_rate > 0.1,
                "message": "错误率过高: {error_rate:.1%}",
            },
            {
                "name": "slow_response",
                "level": MetricLevel.APPLICATION,
                "severity": AlertSeverity.WARNING,
                "condition": lambda m: m.p99_response_time > 5.0,
                "message": "响应时间过慢: P99={p99_response_time:.2f}s",
            },
            {
                "name": "db_connection_leak",
                "level": MetricLevel.DATABASE,
                "severity": AlertSeverity.ERROR,
                "condition": lambda m: m.active_connections > 100,
                "message": "数据库连接数过多: {active_connections}",
            },
            {
                "name": "db_deadlock",
                "level": MetricLevel.DATABASE,
                "severity": AlertSeverity.CRITICAL,
                "condition": lambda m: m.deadlocks > 0,
                "message": "检测到数据库死锁: {deadlocks}个",
            },
        ]

    def start(self):
        """启动性能监控"""
        if self._running:
            logger.warning("性能监控器已经在运行")
            return

        self._running = True
        self._collect_thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._collect_thread.start()
        logger.info("性能监控器已启动")

    def stop(self):
        """停止性能监控"""
        self._running = False
        if self._collect_thread:
            self._collect_thread.join(timeout=5)
        logger.info("性能监控器已停止")

    def _collect_loop(self):
        """采集循环"""
        while self._running:
            try:
                # 采集系统指标
                system_metrics = self._collect_system_metrics()
                self.system_metrics.append(system_metrics)

                # 检查告警
                if self.enable_alerts:
                    self._check_alerts(MetricLevel.SYSTEM, system_metrics)

                # 触发回调
                for callback in self.metric_callbacks:
                    try:
                        callback(MetricLevel.SYSTEM, system_metrics)
                    except Exception as e:
                        logger.error(f"指标回调失败: {e}")

                time.sleep(self.collect_interval)

            except Exception as e:
                logger.error(f"指标采集失败: {e}")
                time.sleep(self.collect_interval)

    def _collect_system_metrics(self) -> SystemMetrics:
        """采集系统指标"""
        # CPU使用率
        cpu_percent_raw = psutil.cpu_percent(interval=None)
        if isinstance(cpu_percent_raw, list):
            cpu_percent = float(sum(cpu_percent_raw) / len(cpu_percent_raw)) if cpu_percent_raw else 0.0
        else:
            cpu_percent = float(cpu_percent_raw)

        # 内存使用
        memory = psutil.virtual_memory()

        # 磁盘IO
        disk_io = psutil.disk_io_counters()
        if self._last_disk_io:
            disk_read = disk_io.read_bytes - self._last_disk_io.read_bytes
            disk_write = disk_io.write_bytes - self._last_disk_io.write_bytes
        else:
            disk_read = disk_write = 0
        self._last_disk_io = disk_io

        # 网络IO
        net_io = psutil.net_io_counters()
        if self._last_network_io:
            net_sent = net_io.bytes_sent - self._last_network_io.bytes_sent
            net_recv = net_io.bytes_recv - self._last_network_io.bytes_recv
        else:
            net_sent = net_recv = 0
        self._last_network_io = net_io

        # 进程信息
        try:
            process_info: dict[str, object] = {}
            as_dict = getattr(self._process, "as_dict", None)
            if callable(as_dict):
                process_info = cast(dict[str, object], as_dict(attrs=["num_threads", "num_fds"]))
            raw_thread = process_info.get("num_threads", 0) if process_info else 0
            raw_fds = process_info.get("num_fds", 0) if process_info else 0
            thread_count = int(raw_thread) if isinstance(raw_thread, (int, float)) else 0
            open_files = int(raw_fds) if isinstance(raw_fds, (int, float)) else 0
        except Exception:
            thread_count = open_files = 0

        return SystemMetrics(
            timestamp=time.time(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_available=memory.available,
            memory_used=memory.used,
            disk_io_read_bytes=disk_read,
            disk_io_write_bytes=disk_write,
            network_sent_bytes=net_sent,
            network_recv_bytes=net_recv,
            process_count=len(psutil.pids()),
            thread_count=thread_count,
            open_files=open_files,
        )

    def record_database_metrics(self, metrics: DatabaseMetrics):
        """记录数据库指标"""
        self.database_metrics.append(metrics)

        if self.enable_alerts:
            self._check_alerts(MetricLevel.DATABASE, metrics)

        for callback in self.metric_callbacks:
            try:
                callback(MetricLevel.DATABASE, metrics)
            except Exception as e:
                logger.error(f"数据库指标回调失败: {e}")

    def record_application_metrics(self, metrics: ApplicationMetrics):
        """记录应用层指标"""
        self.application_metrics.append(metrics)

        if self.enable_alerts:
            self._check_alerts(MetricLevel.APPLICATION, metrics)

        for callback in self.metric_callbacks:
            try:
                callback(MetricLevel.APPLICATION, metrics)
            except Exception as e:
                logger.error(f"应用指标回调失败: {e}")

    def record_custom_metric(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """记录自定义指标"""
        metric_tags: Dict[str, str] = tags if tags is not None else {}
        metric: CustomMetric = {"timestamp": time.time(), "value": value, "tags": metric_tags}
        self.custom_metrics[name].append(metric)

    def _check_alerts(self, level: MetricLevel, metrics: Any):
        """检查告警规则"""
        for rule in self.alert_rules:
            if rule["level"] != level:
                continue

            try:
                # 检查条件
                if rule["condition"](metrics):
                    # 生成告警ID
                    alert_id = f"{rule['name']}_{int(time.time())}"

                    # 检查是否已存在未解决的同类告警
                    existing_alert = None
                    for aid, alert in self.alerts.items():
                        if alert.id.startswith(rule["name"]) and not alert.resolved:
                            existing_alert = alert
                            break

                    if not existing_alert:
                        # 创建新告警
                        message = rule["message"].format(**metrics.__dict__)
                        alert = Alert(
                            id=alert_id,
                            severity=rule["severity"],
                            metric_level=level,
                            message=message,
                            details=metrics.to_dict() if hasattr(metrics, "to_dict") else {},
                        )

                        self.alerts[alert_id] = alert
                        logger.warning(f"[性能告警] {alert.severity.value.upper()}: {message}")

                        # 触发告警回调
                        for callback in self.alert_callbacks:
                            try:
                                callback(alert)
                            except Exception as e:
                                logger.error(f"告警回调失败: {e}")

                else:
                    # 检查是否有需要解决的告警
                    for alert in self.alerts.values():
                        if alert.id.startswith(rule["name"]) and not alert.resolved:
                            alert.resolved = True
                            alert.resolved_at = datetime.now()
                            logger.info(f"[告警解除] {alert.message}")

            except Exception as e:
                logger.error(f"检查告警规则失败: {rule['name']} - {e}")

    def get_current_metrics(self) -> Dict[str, Any]:
        """获取当前指标"""
        result = {}

        if self.system_metrics:
            result["system"] = self.system_metrics[-1].to_dict()

        if self.database_metrics:
            result["database"] = self.database_metrics[-1].to_dict()

        if self.application_metrics:
            result["application"] = self.application_metrics[-1].to_dict()

        # 自定义指标
        custom = {}
        for name, values in self.custom_metrics.items():
            if values:
                custom[name] = values[-1]
        if custom:
            result["custom"] = custom

        return result

    def get_metrics_history(
        self, level: MetricLevel, duration: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取指标历史

        Args:
            level: 指标级别
            duration: 时长（秒），None表示全部

        Returns:
            指标历史列表
        """
        metrics: Deque[Any]
        if level == MetricLevel.SYSTEM:
            metrics = cast(Deque[Any], self.system_metrics)
        elif level == MetricLevel.DATABASE:
            metrics = cast(Deque[Any], self.database_metrics)
        elif level == MetricLevel.APPLICATION:
            metrics = cast(Deque[Any], self.application_metrics)
        else:
            return []

        if not metrics:
            return []

        if duration:
            cutoff_time = time.time() - duration
            filtered = [m for m in metrics if m.timestamp >= cutoff_time]
        else:
            filtered = list(metrics)

        return [m.to_dict() for m in filtered]

    def get_statistics(self, duration: Optional[int] = None) -> Dict[str, Any]:
        """
        获取统计信息

        Args:
            duration: 统计时长（秒）

        Returns:
            统计信息
        """
        stats: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "duration": duration,
            "metrics_count": {
                "system": len(self.system_metrics),
                "database": len(self.database_metrics),
                "application": len(self.application_metrics),
                "custom": sum(len(v) for v in self.custom_metrics.values()),
            },
        }

        # 系统统计
        if self.system_metrics:
            system_data = self.get_metrics_history(MetricLevel.SYSTEM, duration)
            if system_data:
                cpu_values = [m["cpu"]["percent"] for m in system_data]
                memory_values = [m["memory"]["percent"] for m in system_data]

                stats["system"] = {
                    "cpu": {
                        "avg": round(sum(cpu_values) / len(cpu_values), 2),
                        "max": round(max(cpu_values), 2),
                        "min": round(min(cpu_values), 2),
                    },
                    "memory": {
                        "avg": round(sum(memory_values) / len(memory_values), 2),
                        "max": round(max(memory_values), 2),
                        "min": round(min(memory_values), 2),
                    },
                }

        # 应用统计
        if self.application_metrics:
            app_data = self.get_metrics_history(MetricLevel.APPLICATION, duration)
            if app_data:
                response_times = []
                error_rates = []
                for m in app_data:
                    response_times.append(m["response_time"]["avg_ms"])
                    error_rates.append(m["requests"]["error_rate"])

                stats["application"] = {
                    "response_time_ms": {
                        "avg": round(sum(response_times) / len(response_times), 2),
                        "max": round(max(response_times), 2),
                        "min": round(min(response_times), 2),
                    },
                    "error_rate": {
                        "avg": round(sum(error_rates) / len(error_rates), 2),
                        "max": round(max(error_rates), 2),
                    },
                }

        # 告警统计
        active_alerts = [a for a in self.alerts.values() if not a.resolved]
        resolved_alerts = [a for a in self.alerts.values() if a.resolved]

        stats["alerts"] = {
            "total": len(self.alerts),
            "active": len(active_alerts),
            "resolved": len(resolved_alerts),
            "by_severity": {
                "critical": len([a for a in active_alerts if a.severity == AlertSeverity.CRITICAL]),
                "error": len([a for a in active_alerts if a.severity == AlertSeverity.ERROR]),
                "warning": len([a for a in active_alerts if a.severity == AlertSeverity.WARNING]),
                "info": len([a for a in active_alerts if a.severity == AlertSeverity.INFO]),
            },
        }

        return stats

    def get_alerts(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        获取告警列表

        Args:
            active_only: 只返回活跃告警

        Returns:
            告警列表
        """
        if active_only:
            alerts = [a for a in self.alerts.values() if not a.resolved]
        else:
            alerts = list(self.alerts.values())

        # 按时间排序
        alerts.sort(key=lambda a: a.timestamp, reverse=True)

        return [a.to_dict() for a in alerts]

    def add_metric_callback(self, callback: Callable):
        """添加指标回调"""
        self.metric_callbacks.append(callback)

    def add_alert_callback(self, callback: Callable):
        """添加告警回调"""
        self.alert_callbacks.append(callback)

    def add_alert_rule(self, rule: Dict[str, Any]):
        """添加告警规则"""
        self.alert_rules.append(rule)

    def export_metrics(self, filepath: str, format: str = "json"):
        """
        导出指标数据

        Args:
            filepath: 文件路径
            format: 导出格式（json/csv）
        """
        data: Dict[str, Any] = {
            "exported_at": datetime.now().isoformat(),
            "system": [m.to_dict() for m in self.system_metrics],
            "database": [m.to_dict() for m in self.database_metrics],
            "application": [m.to_dict() for m in self.application_metrics],
            "custom": {},
        }

        for name, values in self.custom_metrics.items():
            data["custom"][name] = list(values)

        if format == "json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            logger.warning(f"不支持的导出格式: {format}")

    def generate_report(self) -> str:
        """生成性能报告"""
        lines = []
        lines.append("# 性能监控报告")
        lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 当前指标
        current = self.get_current_metrics()

        if "system" in current:
            lines.append("\n## 系统资源")
            sys = current["system"]
            lines.append(f"- CPU使用率: {sys['cpu']['percent']}%")
            lines.append(f"- 内存使用率: {sys['memory']['percent']}%")
            lines.append(f"- 可用内存: {sys['memory']['available_mb']} MB")
            lines.append(f"- 磁盘读取: {sys['disk_io']['read_mb']} MB")
            lines.append(f"- 磁盘写入: {sys['disk_io']['write_mb']} MB")
            lines.append(f"- 网络发送: {sys['network']['sent_mb']} MB")
            lines.append(f"- 网络接收: {sys['network']['recv_mb']} MB")

        if "database" in current:
            lines.append("\n## 数据库性能")
            db = current["database"]
            lines.append(f"- 活跃连接: {db['connections']['active']}")
            lines.append(f"- 空闲连接: {db['connections']['idle']}")
            lines.append(f"- 总查询数: {db['queries']['total']}")
            lines.append(f"- 慢查询数: {db['queries']['slow']}")
            lines.append(f"- 错误率: {db['queries']['error_rate']}%")
            lines.append(f"- 平均查询时间: {db['performance']['avg_query_time_ms']} ms")
            lines.append(f"- 缓存命中率: {db['performance']['cache_hit_ratio']}%")

        if "application" in current:
            lines.append("\n## 应用性能")
            app = current["application"]
            lines.append(f"- 请求数: {app['requests']['count']}")
            lines.append(f"- 请求速率: {app['requests']['rate_per_sec']}/s")
            lines.append(f"- 错误率: {app['requests']['error_rate']}%")
            lines.append(f"- 平均响应时间: {app['response_time']['avg_ms']} ms")
            lines.append(f"- P50响应时间: {app['response_time']['p50_ms']} ms")
            lines.append(f"- P90响应时间: {app['response_time']['p90_ms']} ms")
            lines.append(f"- P99响应时间: {app['response_time']['p99_ms']} ms")

        # 统计信息
        stats = self.get_statistics(duration=3600)  # 最近1小时

        lines.append("\n## 统计摘要（最近1小时）")
        if "system" in stats:
            lines.append("\n### 系统资源")
            lines.append(f"- CPU平均: {stats['system']['cpu']['avg']}%")
            lines.append(f"- CPU最大: {stats['system']['cpu']['max']}%")
            lines.append(f"- 内存平均: {stats['system']['memory']['avg']}%")
            lines.append(f"- 内存最大: {stats['system']['memory']['max']}%")

        # 告警信息
        alerts = self.get_alerts(active_only=True)
        if alerts:
            lines.append("\n## 活跃告警")
            for alert in alerts[:10]:  # 最多显示10条
                lines.append(f"- [{alert['severity']}] {alert['message']} ({alert['timestamp']})")

        return "\n".join(lines)


# 全局实例
_tracker: Optional[PerformanceTracker] = None


def get_tracker() -> PerformanceTracker:
    """获取全局性能跟踪器"""
    global _tracker
    if _tracker is None:
        _tracker = PerformanceTracker()
        _tracker.start()
    return _tracker


def record_db_metrics(active_connections: int, total_queries: int, avg_query_time: float, **kwargs):
    """快捷记录数据库指标"""
    metrics = DatabaseMetrics(
        timestamp=time.time(),
        active_connections=active_connections,
        total_queries=total_queries,
        avg_query_time=avg_query_time,
        **kwargs,
    )
    get_tracker().record_database_metrics(metrics)


def record_app_metrics(request_count: int, error_count: int, avg_response_time: float, **kwargs):
    """快捷记录应用指标"""
    metrics = ApplicationMetrics(
        timestamp=time.time(),
        request_count=request_count,
        error_count=error_count,
        error_rate=error_count / max(request_count, 1),
        avg_response_time=avg_response_time,
        **kwargs,
    )
    get_tracker().record_application_metrics(metrics)
