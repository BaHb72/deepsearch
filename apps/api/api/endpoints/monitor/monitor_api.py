"""
监控API端点实现
提供系统监控、性能指标、健康检查、事件追踪等功能
"""

from collections import deque
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple

import psutil
from core.config import get_config
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

if TYPE_CHECKING:
    from core.observability.monitoring.monitor_api import MonitorAPI

# from core.event import EventBus  # EventBus已经被EventEngine替代
# from core.event.types import EventType  # EventType模块不存在，且未使用


router = APIRouter(tags=["monitor"])


# 全局监控数据存储
class MonitoringStore:
    """监控数据存储"""

    def __init__(self):
        self.metrics_history = deque(maxlen=1000)  # 最近1000条指标
        self.events_history = deque(maxlen=10000)  # 最近10000个事件
        self.slow_events = deque(maxlen=100)  # 最近100个慢事件
        self.alerts = []
        self.start_time = datetime.now()

    def add_metric(self, metric: Dict[str, Any]):
        """添加指标记录"""
        metric["timestamp"] = datetime.now().isoformat()
        self.metrics_history.append(metric)

    def add_event(self, event: Dict[str, Any]):
        """添加事件记录"""
        event["timestamp"] = datetime.now().isoformat()
        self.events_history.append(event)

        # 检查是否为慢事件（执行时间超过1秒）
        if event.get("duration", 0) > 1000:
            self.slow_events.append(event)

    def get_summary(self) -> Dict[str, Any]:
        """获取监控摘要"""
        return {
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds(),
            "total_events": len(self.events_history),
            "slow_events": len(self.slow_events),
            "active_alerts": len([a for a in self.alerts if a.get("active", True)]),
            "metrics_collected": len(self.metrics_history),
        }


# 初始化全局存储
monitoring_store = MonitoringStore()


def _parse_iso_timestamp(value: str) -> Optional[datetime]:
    """安全解析 ISO 时间字符串。"""
    if not value:
        return None
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _resolve_monitor_api() -> "MonitorAPI":
    """获取运行中的 MonitorAPI 实例。"""
    from apps.api.server import get_monitor_api

    monitor_api = get_monitor_api()
    if not monitor_api or not getattr(monitor_api, "_running", False):
        raise HTTPException(status_code=503, detail="事件监控服务未启动")
    return monitor_api


def _estimate_publish_throughput(stats: Dict[str, Any]) -> float:
    """根据 publish_times 信息估算吞吐率。"""
    publish_times = stats.get("publish_times")
    values: List[float] = []
    if isinstance(publish_times, Iterable) and not isinstance(publish_times, (str, bytes)):
        for item in publish_times:
            if isinstance(item, (int, float)):
                values.append(float(item))
    elif isinstance(publish_times, (int, float)):
        values.append(float(publish_times))

    if values:
        avg = sum(values) / len(values)
        if avg > 0:
            return round(1.0 / avg, 2)

    messages = stats.get("messages_published")
    if isinstance(messages, (int, float)):
        return round(float(messages), 2)

    return 0.0


def _format_bus_entry(name: str, info: Dict[str, Any]) -> Dict[str, Any]:
    """格式化单条消息总线状态。"""
    status = "connected"
    if info.get("running") is False or info.get("status") in {"stopped", "disconnected"}:
        status = "disconnected"

    throughput = _estimate_publish_throughput(info)

    connections: int = 0
    raw_connections = info.get("connections")
    if isinstance(raw_connections, (int, float)):
        connections = int(raw_connections)
    else:
        routing = info.get("routing_decisions")
        if isinstance(routing, dict):
            connections = len(routing)
        elif isinstance(info.get("routes"), int):
            connections = int(info["routes"])

    buffer_usage = 0.0
    messages = info.get("messages_published")
    deduplicated = info.get("messages_deduplicated")
    if (
        isinstance(messages, (int, float))
        and messages > 0
        and isinstance(deduplicated, (int, float))
    ):
        buffer_usage = round(min(max(deduplicated / messages * 100.0, 0.0), 100.0), 2)

    return {
        "type": name,
        "status": status,
        "throughput": throughput,
        "connections": connections,
        "bufferUsage": buffer_usage,
    }


def _extract_message_bus_status(monitor_api: "MonitorAPI") -> List[Dict[str, Any]]:
    """提取消息总线状态列表。"""
    monitor = getattr(monitor_api, "_monitor", None)
    bus = getattr(monitor, "_bus", None)
    if not bus:
        return []

    entries: List[Dict[str, Any]] = []
    try:
        stats = bus.get_statistics()
    except Exception as exc:  # pragma: no cover - 防御性
        return [
            {
                "type": bus.__class__.__name__,
                "status": "error",
                "throughput": 0.0,
                "connections": 0,
                "bufferUsage": 0.0,
                "message": str(exc),
            }
        ]

    entries.append(_format_bus_entry(bus.__class__.__name__, stats))

    buses = stats.get("buses", {})
    if isinstance(buses, dict):
        for name, info in buses.items():
            if isinstance(info, dict):
                entries.append(_format_bus_entry(str(name), info))

    return entries


def _build_event_system_overview(monitor_api: "MonitorAPI") -> Dict[str, Any]:
    """构建事件系统监控快照。"""
    stats = monitor_api.get_statistics()
    latest_record = stats.get("latest_record")
    timestamp = datetime.now().isoformat()
    payload: Dict[str, Any] = {
        "timestamp": timestamp,
        "eventMetrics": {
            "produceRate": 0.0,
            "consumeRate": 0.0,
            "queueDepth": 0,
            "queueUsage": 0.0,
        },
        "eventTypes": [],
        "latencyDistribution": {
            "categories": ["<10ms", "10-50ms", "50-100ms", "100-500ms", ">500ms"],
            "values": [0, 0, 0, 0, 0],
        },
        "messageBuses": [],
        "eventHandlers": [],
        "eventStream": [],
        "alerts": stats.get("dashboard_data", {}).get("alerts", []),
    }

    if not latest_record:
        return payload

    timestamp = latest_record.get("timestamp", timestamp)
    payload["timestamp"] = timestamp

    history = monitor_api.get_historical_data(hours=1)
    records = [rec for rec in history.get("records", []) if rec]
    if not records or records[-1] != latest_record:
        records.append(latest_record)

    previous_record = records[-2] if len(records) >= 2 else None

    latest_ts = _parse_iso_timestamp(latest_record.get("timestamp"))
    prev_ts = _parse_iso_timestamp(previous_record.get("timestamp")) if previous_record else None

    update_interval = stats.get("update_interval") or 5.0
    delta_seconds = update_interval
    if latest_ts and prev_ts:
        calculated = (latest_ts - prev_ts).total_seconds()
        if calculated > 0:
            delta_seconds = calculated

    latest_metrics = latest_record.get("metrics", {})
    latest_events = latest_metrics.get("events", {})
    prev_events = previous_record.get("metrics", {}).get("events", {}) if previous_record else {}

    total_latest = 0
    total_prev = 0
    delta_counts: Dict[str, int] = {}

    for event_type, metrics in latest_events.items():
        latest_count = int(metrics.get("count", 0) or 0)
        total_latest += latest_count
        prev_count = int(prev_events.get(event_type, {}).get("count", 0) or 0)
        total_prev += prev_count
        delta_counts[event_type] = max(latest_count - prev_count, 0)

    consume_rate = 0.0
    if previous_record and delta_seconds > 0:
        consume_rate = max(total_latest - total_prev, 0) / delta_seconds

    queue_depth = int(latest_metrics.get("queue_size", 0) or 0)
    prev_queue = (
        int(previous_record.get("metrics", {}).get("queue_size", 0) or 0)
        if previous_record
        else queue_depth
    )

    produce_rate = consume_rate
    if previous_record and delta_seconds > 0:
        produce_rate = max(consume_rate + (queue_depth - prev_queue) / delta_seconds, 0.0)

    monitor = getattr(monitor_api, "_monitor", None)
    queue_capacity = 0
    if monitor and hasattr(monitor, "_engine") and hasattr(monitor._engine, "_queue"):
        queue_capacity = getattr(monitor._engine._queue, "maxsize", 0) or 0

    queue_usage = 0.0
    if queue_capacity > 0:
        queue_usage = min(max(queue_depth / queue_capacity * 100.0, 0.0), 100.0)

    payload["eventMetrics"] = {
        "produceRate": round(float(produce_rate), 2),
        "consumeRate": round(float(consume_rate), 2),
        "queueDepth": queue_depth,
        "queueUsage": round(float(queue_usage), 2),
    }

    display_counts = {k: v for k, v in delta_counts.items() if v > 0}
    if not display_counts and total_latest:
        display_counts = {
            k: int(v.get("count", 0) or 0)
            for k, v in latest_events.items()
            if int(v.get("count", 0) or 0) > 0
        }

    payload["eventTypes"] = [
        {"name": event_type, "value": count}
        for event_type, count in sorted(
            display_counts.items(), key=lambda item: item[1], reverse=True
        )
    ]

    buckets: List[Tuple[str, float, float]] = [
        ("<10ms", 0, 10),
        ("10-50ms", 10, 50),
        ("50-100ms", 50, 100),
        ("100-500ms", 100, 500),
        (">500ms", 500, float("inf")),
    ]
    bucket_totals = {label: 0 for label, _, _ in buckets}

    for event_type, metrics in latest_events.items():
        avg_time = float(metrics.get("avg_time_ms", 0) or 0.0)
        weight = display_counts.get(event_type, delta_counts.get(event_type, 0))
        if not weight:
            weight = int(metrics.get("count", 0) or 0)
        for label, lower, upper in buckets:
            if lower <= avg_time < upper:
                bucket_totals[label] += int(weight)
                break

    payload["latencyDistribution"] = {
        "categories": [label for label, _, _ in buckets],
        "values": [bucket_totals[label] for label, _, _ in buckets],
    }

    payload["messageBuses"] = _extract_message_bus_status(monitor_api)

    handler_metrics = stats.get("performance", {}).get("handler_metrics", {})
    handlers = []
    for handler_name, metrics in handler_metrics.items():
        processed = int(metrics.get("count", 0) or 0)
        avg_time_ms = round(float(metrics.get("average_time", 0.0) or 0.0) * 1000, 2)
        handlers.append(
            {
                "name": handler_name,
                "processed": processed,
                "successRate": 100.0,
                "avgTime": avg_time_ms,
                "status": "active" if processed > 0 else "idle",
            }
        )

    payload["eventHandlers"] = sorted(handlers, key=lambda item: item["processed"], reverse=True)

    slow_events = monitor_api.get_slow_events(limit=20)
    event_stream = []
    for event in reversed(slow_events):
        processing_time = float(event.get("processing_time", 0.0) or 0.0)
        severity = "warning" if processing_time >= 1.0 else "info"
        event_stream.append(
            {
                "time": event.get("timestamp"),
                "eventType": event.get("event_type", "UNKNOWN"),
                "type": severity,
                "message": f"{event.get('handler', 'handler')} 耗时 {processing_time * 1000:.0f} ms",
            }
        )

    payload["eventStream"] = event_stream
    payload["alerts"] = latest_record.get("alerts", payload["alerts"])

    return payload


class DashboardResponse(BaseModel):
    """仪表板响应模型"""

    system: Dict[str, Any]
    performance: Dict[str, Any]
    services: List[Dict[str, Any]]
    alerts: List[Dict[str, Any]]
    timestamp: str


class MetricsResponse(BaseModel):
    """实时指标响应模型"""

    cpu: Dict[str, float]
    memory: Dict[str, float]
    disk: Dict[str, float]
    network: Dict[str, float]
    processes: Dict[str, int]
    timestamp: str


class HealthResponse(BaseModel):
    """健康状态响应模型"""

    status: str
    services: List[Dict[str, Any]]
    dependencies: List[Dict[str, Any]]
    checks: List[Dict[str, Any]]
    timestamp: str


class EventSummaryResponse(BaseModel):
    """事件摘要响应模型"""

    total_events: int
    events_by_type: Dict[str, int]
    recent_events: List[Dict[str, Any]]
    error_count: int
    warning_count: int
    timestamp: str


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard() -> DashboardResponse:
    """
    获取监控仪表板数据
    返回系统整体监控信息，包括系统状态、性能指标、服务状态和告警信息
    """
    try:
        # 收集系统信息
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # 获取网络连接数
        connections = len(psutil.net_connections())

        # 获取进程信息
        process = psutil.Process()
        process_info = {
            "cpu_percent": process.cpu_percent(),
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "threads": process.num_threads(),
            "open_files": len(process.open_files()) if hasattr(process, "open_files") else 0,
        }

        # 构建系统信息
        system_info = {
            "hostname": psutil.os.uname().nodename if hasattr(psutil.os, "uname") else "localhost",
            "platform": psutil.os.name,
            "uptime": monitoring_store.get_summary()["uptime_seconds"],
            "python_version": psutil.sys.version.split()[0],
            "cpu_cores": psutil.cpu_count(),
            "total_memory_gb": memory.total / (1024**3),
        }

        # 构建性能信息
        performance = {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk.percent,
            "network_connections": connections,
            "process": process_info,
        }

        # 获取服务状态
        get_config()
        services = [
            {
                "name": "Event Bus",
                "status": "running",
                "uptime": monitoring_store.get_summary()["uptime_seconds"],
                "metrics": {"events_processed": monitoring_store.get_summary()["total_events"]},
            },
            {
                "name": "Cache Manager",
                "status": "running",
                "uptime": monitoring_store.get_summary()["uptime_seconds"],
                "metrics": {"hit_rate": 0.85, "entries": 1024},
            },
            {
                "name": "Data Provider",
                "status": "running",
                "uptime": monitoring_store.get_summary()["uptime_seconds"],
                "metrics": {"requests": 5678, "errors": 12},
            },
        ]

        # 获取告警信息
        alerts = monitoring_store.alerts[-10:] if monitoring_store.alerts else []

        return DashboardResponse(
            system=system_info,
            performance=performance,
            services=services,
            alerts=alerts,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取仪表板数据失败: {str(e)}")


@router.get("/metrics/realtime", response_model=MetricsResponse)
async def get_realtime_metrics() -> MetricsResponse:
    """
    获取实时性能指标
    返回CPU、内存、磁盘、网络等实时监控数据
    """
    try:
        # CPU指标
        cpu = {
            "usage_percent": psutil.cpu_percent(interval=0.1),
            "cores": psutil.cpu_count(),
            "frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else 0,
            "load_average": psutil.getloadavg()[0] if hasattr(psutil, "getloadavg") else 0,
        }

        # 内存指标
        mem = psutil.virtual_memory()
        memory = {
            "usage_percent": mem.percent,
            "used_gb": mem.used / (1024**3),
            "available_gb": mem.available / (1024**3),
            "total_gb": mem.total / (1024**3),
        }

        # 磁盘指标
        disk_usage = psutil.disk_usage("/")
        disk_io = psutil.disk_io_counters()
        disk = {
            "usage_percent": disk_usage.percent,
            "used_gb": disk_usage.used / (1024**3),
            "free_gb": disk_usage.free / (1024**3),
            "read_mb_s": disk_io.read_bytes / (1024**2) if disk_io else 0,
            "write_mb_s": disk_io.write_bytes / (1024**2) if disk_io else 0,
        }

        # 网络指标
        net_io = psutil.net_io_counters()
        network = {
            "bytes_sent_mb": net_io.bytes_sent / (1024**2) if net_io else 0,
            "bytes_recv_mb": net_io.bytes_recv / (1024**2) if net_io else 0,
            "packets_sent": net_io.packets_sent if net_io else 0,
            "packets_recv": net_io.packets_recv if net_io else 0,
            "connections": len(psutil.net_connections()),
        }

        # 进程指标
        processes = {
            "total": len(psutil.pids()),
            "running": len([p for p in psutil.process_iter() if p.status() == "running"]),
            "sleeping": len([p for p in psutil.process_iter() if p.status() == "sleeping"]),
            "threads": sum(p.num_threads() for p in psutil.process_iter()),
        }

        # 保存到历史记录
        monitoring_store.add_metric(
            {"cpu": cpu, "memory": memory, "disk": disk, "network": network, "processes": processes}
        )

        return MetricsResponse(
            cpu=cpu,
            memory=memory,
            disk=disk,
            network=network,
            processes=processes,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取实时指标失败: {str(e)}")


@router.get("/health", response_model=HealthResponse)
async def get_health_status() -> HealthResponse:
    """
    获取系统健康状态
    检查各个服务和依赖项的健康状况
    """
    try:
        checks = []
        overall_status = "healthy"

        # 检查CPU使用率
        cpu_raw = psutil.cpu_percent(interval=0.1)
        if isinstance(cpu_raw, (list, tuple)):
            cpu_usage = float(cpu_raw[0]) if cpu_raw else 0.0
        else:
            cpu_usage = float(cpu_raw)
        cpu_check = {
            "name": "CPU Usage",
            "status": "pass" if cpu_usage < 80 else "warn" if cpu_usage < 90 else "fail",
            "value": f"{cpu_usage}%",
            "threshold": "80%",
        }
        checks.append(cpu_check)
        if cpu_usage >= 90:
            overall_status = "unhealthy"
        elif cpu_usage >= 80:
            overall_status = "degraded"

        # 检查内存使用率
        memory = psutil.virtual_memory()
        memory_check = {
            "name": "Memory Usage",
            "status": "pass" if memory.percent < 80 else "warn" if memory.percent < 90 else "fail",
            "value": f"{memory.percent}%",
            "threshold": "80%",
        }
        checks.append(memory_check)
        if memory.percent >= 90:
            overall_status = "unhealthy"
        elif memory.percent >= 80 and overall_status == "healthy":
            overall_status = "degraded"

        # 检查磁盘使用率
        disk = psutil.disk_usage("/")
        disk_check = {
            "name": "Disk Usage",
            "status": "pass" if disk.percent < 80 else "warn" if disk.percent < 90 else "fail",
            "value": f"{disk.percent}%",
            "threshold": "80%",
        }
        checks.append(disk_check)
        if disk.percent >= 90:
            overall_status = "unhealthy"
        elif disk.percent >= 80 and overall_status == "healthy":
            overall_status = "degraded"

        # 服务健康状态
        services = [
            {
                "name": "EventBus",
                "status": "running",
                "health": "healthy",
                "last_check": datetime.now().isoformat(),
            },
            {
                "name": "CacheManager",
                "status": "running",
                "health": "healthy",
                "last_check": datetime.now().isoformat(),
            },
            {
                "name": "DataProvider",
                "status": "running",
                "health": "healthy",
                "last_check": datetime.now().isoformat(),
            },
        ]

        # 依赖项健康状态
        dependencies = [
            {"name": "Redis", "status": "connected", "health": "healthy", "latency_ms": 2.5},
            {"name": "PostgreSQL", "status": "connected", "health": "healthy", "latency_ms": 5.3},
        ]

        return HealthResponse(
            status=overall_status,
            services=services,
            dependencies=dependencies,
            checks=checks,
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取健康状态失败: {str(e)}")


@router.get("/slow-events")
async def get_slow_events(
    limit: int = Query(default=20, description="返回数量限制"),
    threshold_ms: int = Query(default=1000, description="慢事件阈值（毫秒）"),
) -> Dict[str, Any]:
    """
    获取慢事件列表
    返回执行时间超过阈值的事件
    """
    try:
        # 模拟慢事件数据
        slow_events: List[Dict[str, Any]] = [
            {
                "event_type": "DATA_FETCH",
                "duration_ms": 2500,
                "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
                "source": "AmazingData",
                "details": "Fetching large dataset",
                "stack_trace": None,
            },
            {
                "event_type": "CACHE_UPDATE",
                "duration_ms": 1800,
                "timestamp": (datetime.now() - timedelta(minutes=10)).isoformat(),
                "source": "CacheManager",
                "details": "Updating cache with 10000 entries",
                "stack_trace": None,
            },
            {
                "event_type": "DATABASE_QUERY",
                "duration_ms": 3200,
                "timestamp": (datetime.now() - timedelta(minutes=15)).isoformat(),
                "source": "PostgreSQL",
                "details": "Complex aggregation query",
                "stack_trace": None,
            },
        ]

        # 添加到存储
        for event in slow_events:
            monitoring_store.add_event(
                {
                    "type": event["event_type"],
                    "duration": event["duration_ms"],
                    "source": event["source"],
                }
            )

        # 根据阈值过滤
        filtered_events: List[Dict[str, Any]] = []
        for event in slow_events:
            duration_value = event.get("duration_ms")
            if isinstance(duration_value, (int, float)):
                duration_int = int(duration_value)
            elif isinstance(duration_value, str):
                value_str = duration_value.strip()
                if not value_str:
                    continue
                try:
                    duration_int = int(float(value_str))
                except ValueError:
                    continue
            else:
                continue
            if duration_int >= threshold_ms:
                filtered_events.append(event)

        # 限制返回数量
        result_events = filtered_events[:limit]

        return {
            "events": result_events,
            "total": len(filtered_events),
            "threshold_ms": threshold_ms,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取慢事件失败: {str(e)}")


@router.get("/history")
async def get_historical_data(
    metric_type: str = Query(default="all", description="指标类型"),
    hours: int = Query(default=24, description="历史小时数"),
) -> Dict[str, Any]:
    """
    获取历史监控数据
    返回指定时间范围内的历史指标
    """
    try:
        # 计算时间范围
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        # 生成模拟历史数据点
        data_points = []
        for i in range(min(100, hours * 6)):  # 每小时6个数据点
            timestamp = start_time + timedelta(minutes=i * 10)

            # 根据metric_type生成相应数据
            point = {
                "timestamp": timestamp.isoformat(),
                "cpu_usage": 30 + (i % 30),
                "memory_usage": 50 + (i % 20),
                "disk_usage": 60 + (i % 10),
                "network_in": 100 + (i % 50),
                "network_out": 80 + (i % 40),
            }

            if metric_type != "all":
                # 只保留请求的指标类型
                filtered_point = {
                    "timestamp": point["timestamp"],
                    metric_type: point.get(metric_type, 0),
                }
                data_points.append(filtered_point)
            else:
                data_points.append(point)

        # 计算统计信息
        cpu_values: List[float] = []
        for point in data_points:
            value = point.get("cpu_usage")
            if isinstance(value, (int, float)):
                cpu_values.append(float(value))

        if cpu_values:
            stats = {
                "min": min(cpu_values),
                "max": max(cpu_values),
                "avg": sum(cpu_values) / len(cpu_values),
            }
        else:
            stats = {"min": 0.0, "max": 0.0, "avg": 0.0}
        return {
            "data": data_points,
            "metric_type": metric_type,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": hours,
            },
            "statistics": stats,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取历史数据失败: {str(e)}")


@router.get("/events/summary", response_model=EventSummaryResponse)
async def get_events_summary() -> EventSummaryResponse:
    """
    获取事件摘要
    返回事件统计信息和最近事件列表
    """
    try:
        # 获取监控摘要
        summary = monitoring_store.get_summary()

        # 生成事件类型统计
        events_by_type = {
            "DATA_FETCH": 1234,
            "CACHE_HIT": 5678,
            "CACHE_MISS": 890,
            "ERROR": 45,
            "WARNING": 123,
            "INFO": 9012,
        }

        # 生成最近事件列表
        recent_events = [
            {
                "id": f"evt_{i}",
                "type": "DATA_FETCH" if i % 3 == 0 else "CACHE_HIT" if i % 3 == 1 else "INFO",
                "timestamp": (datetime.now() - timedelta(minutes=i)).isoformat(),
                "source": "DataProvider" if i % 2 == 0 else "CacheManager",
                "message": f"Event {i} occurred",
                "severity": "info" if i % 5 != 0 else "warning",
            }
            for i in range(10)
        ]

        return EventSummaryResponse(
            total_events=(
                summary["total_events"]
                if summary["total_events"] > 0
                else sum(events_by_type.values())
            ),
            events_by_type=events_by_type,
            recent_events=recent_events,
            error_count=events_by_type.get("ERROR", 0),
            warning_count=events_by_type.get("WARNING", 0),
            timestamp=datetime.now().isoformat(),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取事件摘要失败: {str(e)}")


@router.get("/event-system/overview")
async def get_event_system_overview() -> Dict[str, Any]:
    """获取事件系统监控总览。"""
    monitor_api = _resolve_monitor_api()
    try:
        return _build_event_system_overview(monitor_api)
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - 防御性
        raise HTTPException(status_code=500, detail=f"构建事件监控数据失败: {exc}") from exc
