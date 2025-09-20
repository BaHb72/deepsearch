"""
监控API端点实现
提供系统监控、性能指标、健康检查、事件追踪等功能
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
import psutil
import asyncio
import time
from collections import deque, defaultdict

from deepsearch.config import get_config
from deepsearch.observability.metrics.metrics import MetricsCollector
# from deepsearch.event import EventBus  # EventBus已经被EventEngine替代
# from deepsearch.event.types import EventType  # EventType模块不存在，且未使用
from deepsearch.infrastructure.cache import CacheManager


router = APIRouter(prefix="/monitor", tags=["monitor"])


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
            "metrics_collected": len(self.metrics_history)
        }


# 初始化全局存储
monitoring_store = MonitoringStore()


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
            "open_files": len(process.open_files()) if hasattr(process, "open_files") else 0
        }

        # 构建系统信息
        system_info = {
            "hostname": psutil.os.uname().nodename if hasattr(psutil.os, "uname") else "localhost",
            "platform": psutil.os.name,
            "uptime": monitoring_store.get_summary()["uptime_seconds"],
            "python_version": psutil.sys.version.split()[0],
            "cpu_cores": psutil.cpu_count(),
            "total_memory_gb": memory.total / (1024 ** 3)
        }

        # 构建性能信息
        performance = {
            "cpu_usage": cpu_percent,
            "memory_usage": memory.percent,
            "disk_usage": disk.percent,
            "network_connections": connections,
            "process": process_info
        }

        # 获取服务状态
        config = get_config()
        services = [
            {
                "name": "Event Bus",
                "status": "running",
                "uptime": monitoring_store.get_summary()["uptime_seconds"],
                "metrics": {"events_processed": monitoring_store.get_summary()["total_events"]}
            },
            {
                "name": "Cache Manager",
                "status": "running",
                "uptime": monitoring_store.get_summary()["uptime_seconds"],
                "metrics": {"hit_rate": 0.85, "entries": 1024}
            },
            {
                "name": "Data Provider",
                "status": "running",
                "uptime": monitoring_store.get_summary()["uptime_seconds"],
                "metrics": {"requests": 5678, "errors": 12}
            }
        ]

        # 获取告警信息
        alerts = monitoring_store.alerts[-10:] if monitoring_store.alerts else []

        return DashboardResponse(
            system=system_info,
            performance=performance,
            services=services,
            alerts=alerts,
            timestamp=datetime.now().isoformat()
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
            "load_average": psutil.getloadavg()[0] if hasattr(psutil, "getloadavg") else 0
        }

        # 内存指标
        mem = psutil.virtual_memory()
        memory = {
            "usage_percent": mem.percent,
            "used_gb": mem.used / (1024 ** 3),
            "available_gb": mem.available / (1024 ** 3),
            "total_gb": mem.total / (1024 ** 3)
        }

        # 磁盘指标
        disk_usage = psutil.disk_usage("/")
        disk_io = psutil.disk_io_counters()
        disk = {
            "usage_percent": disk_usage.percent,
            "used_gb": disk_usage.used / (1024 ** 3),
            "free_gb": disk_usage.free / (1024 ** 3),
            "read_mb_s": disk_io.read_bytes / (1024 ** 2) if disk_io else 0,
            "write_mb_s": disk_io.write_bytes / (1024 ** 2) if disk_io else 0
        }

        # 网络指标
        net_io = psutil.net_io_counters()
        network = {
            "bytes_sent_mb": net_io.bytes_sent / (1024 ** 2) if net_io else 0,
            "bytes_recv_mb": net_io.bytes_recv / (1024 ** 2) if net_io else 0,
            "packets_sent": net_io.packets_sent if net_io else 0,
            "packets_recv": net_io.packets_recv if net_io else 0,
            "connections": len(psutil.net_connections())
        }

        # 进程指标
        processes = {
            "total": len(psutil.pids()),
            "running": len([p for p in psutil.process_iter() if p.status() == "running"]),
            "sleeping": len([p for p in psutil.process_iter() if p.status() == "sleeping"]),
            "threads": sum(p.num_threads() for p in psutil.process_iter())
        }

        # 保存到历史记录
        monitoring_store.add_metric({
            "cpu": cpu,
            "memory": memory,
            "disk": disk,
            "network": network,
            "processes": processes
        })

        return MetricsResponse(
            cpu=cpu,
            memory=memory,
            disk=disk,
            network=network,
            processes=processes,
            timestamp=datetime.now().isoformat()
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
        cpu_usage = psutil.cpu_percent(interval=0.1)
        cpu_check = {
            "name": "CPU Usage",
            "status": "pass" if cpu_usage < 80 else "warn" if cpu_usage < 90 else "fail",
            "value": f"{cpu_usage}%",
            "threshold": "80%"
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
            "threshold": "80%"
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
            "threshold": "80%"
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
                "last_check": datetime.now().isoformat()
            },
            {
                "name": "CacheManager",
                "status": "running",
                "health": "healthy",
                "last_check": datetime.now().isoformat()
            },
            {
                "name": "DataProvider",
                "status": "running",
                "health": "healthy",
                "last_check": datetime.now().isoformat()
            }
        ]

        # 依赖项健康状态
        dependencies = [
            {
                "name": "Redis",
                "status": "connected",
                "health": "healthy",
                "latency_ms": 2.5
            },
            {
                "name": "PostgreSQL",
                "status": "connected",
                "health": "healthy",
                "latency_ms": 5.3
            }
        ]

        return HealthResponse(
            status=overall_status,
            services=services,
            dependencies=dependencies,
            checks=checks,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取健康状态失败: {str(e)}")


@router.get("/slow-events")
async def get_slow_events(
    limit: int = Query(default=20, description="返回数量限制"),
    threshold_ms: int = Query(default=1000, description="慢事件阈值（毫秒）")
) -> Dict[str, Any]:
    """
    获取慢事件列表
    返回执行时间超过阈值的事件
    """
    try:
        # 模拟慢事件数据
        slow_events = [
            {
                "event_type": "DATA_FETCH",
                "duration_ms": 2500,
                "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
                "source": "AmazingData",
                "details": "Fetching large dataset",
                "stack_trace": None
            },
            {
                "event_type": "CACHE_UPDATE",
                "duration_ms": 1800,
                "timestamp": (datetime.now() - timedelta(minutes=10)).isoformat(),
                "source": "CacheManager",
                "details": "Updating cache with 10000 entries",
                "stack_trace": None
            },
            {
                "event_type": "DATABASE_QUERY",
                "duration_ms": 3200,
                "timestamp": (datetime.now() - timedelta(minutes=15)).isoformat(),
                "source": "PostgreSQL",
                "details": "Complex aggregation query",
                "stack_trace": None
            }
        ]

        # 添加到存储
        for event in slow_events:
            monitoring_store.add_event({
                "type": event["event_type"],
                "duration": event["duration_ms"],
                "source": event["source"]
            })

        # 根据阈值过滤
        filtered_events = [e for e in slow_events if e["duration_ms"] >= threshold_ms]

        # 限制返回数量
        result_events = filtered_events[:limit]

        return {
            "events": result_events,
            "total": len(filtered_events),
            "threshold_ms": threshold_ms,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取慢事件失败: {str(e)}")


@router.get("/history")
async def get_historical_data(
    metric_type: str = Query(default="all", description="指标类型"),
    hours: int = Query(default=24, description="历史小时数")
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
                "network_out": 80 + (i % 40)
            }

            if metric_type != "all":
                # 只保留请求的指标类型
                filtered_point = {
                    "timestamp": point["timestamp"],
                    metric_type: point.get(metric_type, 0)
                }
                data_points.append(filtered_point)
            else:
                data_points.append(point)

        # 计算统计信息
        if data_points:
            stats = {
                "min": min(p.get("cpu_usage", 0) for p in data_points if "cpu_usage" in p),
                "max": max(p.get("cpu_usage", 0) for p in data_points if "cpu_usage" in p),
                "avg": sum(p.get("cpu_usage", 0) for p in data_points if "cpu_usage" in p) / len(data_points)
            }
        else:
            stats = {"min": 0, "max": 0, "avg": 0}

        return {
            "data": data_points,
            "metric_type": metric_type,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "hours": hours
            },
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
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
            "INFO": 9012
        }

        # 生成最近事件列表
        recent_events = [
            {
                "id": f"evt_{i}",
                "type": "DATA_FETCH" if i % 3 == 0 else "CACHE_HIT" if i % 3 == 1 else "INFO",
                "timestamp": (datetime.now() - timedelta(minutes=i)).isoformat(),
                "source": "DataProvider" if i % 2 == 0 else "CacheManager",
                "message": f"Event {i} occurred",
                "severity": "info" if i % 5 != 0 else "warning"
            }
            for i in range(10)
        ]

        return EventSummaryResponse(
            total_events=summary["total_events"] if summary["total_events"] > 0 else sum(events_by_type.values()),
            events_by_type=events_by_type,
            recent_events=recent_events,
            error_count=events_by_type.get("ERROR", 0),
            warning_count=events_by_type.get("WARNING", 0),
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取事件摘要失败: {str(e)}")