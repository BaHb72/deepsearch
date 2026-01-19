"""
系统数据聚合服务。

集中封装系统状态、指标、组件等数据的获取逻辑，
供 FastAPI 路由复用，避免重复的 psutil 与 Engine 调用。
"""

from __future__ import annotations

import inspect
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import psutil
from core.utils.time.market_time import now
from loguru import logger


class EngineUnavailableError(RuntimeError):
    """在需要 Engine 时未初始化。"""


class ComponentNotFoundError(RuntimeError):
    """指定组件不存在。"""


@dataclass
class NetworkSample:
    """网络采样快照。"""

    timestamp: float
    bytes_recv: int
    bytes_sent: int


class NetworkThroughputSampler:
    """计算网络吞吐的采样器。"""

    def __init__(self) -> None:
        self._previous: Optional[NetworkSample] = None

    def sample(self) -> Dict[str, float]:
        """返回当前采样与上一采样之间的收发速率 (KB/s)。"""
        try:
            counters = psutil.net_io_counters()
        except Exception as exc:  # pragma: no cover - psutil 内部异常罕见
            logger.debug(f"采集网络指标失败: {exc}")
            return {"network_in": 0.0, "network_out": 0.0}

        if counters is None:
            return {"network_in": 0.0, "network_out": 0.0}

        now = time.time()
        if not self._previous:
            self._previous = NetworkSample(now, counters.bytes_recv, counters.bytes_sent)
            return {"network_in": 0.0, "network_out": 0.0}

        interval = max(now - self._previous.timestamp, 1e-3)
        recv_rate = max((counters.bytes_recv - self._previous.bytes_recv) / 1024.0 / interval, 0.0)
        send_rate = max((counters.bytes_sent - self._previous.bytes_sent) / 1024.0 / interval, 0.0)

        self._previous = NetworkSample(now, counters.bytes_recv, counters.bytes_sent)
        return {"network_in": round(recv_rate, 2), "network_out": round(send_rate, 2)}


_NETWORK_SAMPLER = NetworkThroughputSampler()


class SystemDataService:
    """后端系统数据的聚合服务。"""

    def __init__(self, sampler: Optional[NetworkThroughputSampler] = None) -> None:
        self._sampler = sampler or _NETWORK_SAMPLER

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------
    @property
    def _app_state(self):  # noqa: D401 - 简短属性说明
        """访问 FastAPI Server 全局状态。"""
        from apps.api.server import app_state  # 延迟导入避免循环

        return app_state

    def _get_engine(self):
        return getattr(self._app_state, "engine", None)

    def _ensure_engine(self):
        engine = self._get_engine()
        if not engine:
            raise EngineUnavailableError("主引擎尚未初始化")
        return engine

    def _get_monitor(self):
        return getattr(self._app_state, "monitor", None)

    def _get_monitor_api(self):
        return getattr(self._app_state, "monitor_api", None)

    def _get_statistics_collector(self):
        try:
            from core.core.utils.statistics import get_statistics_collector

            return get_statistics_collector()
        except Exception as exc:  # pragma: no cover - collector 初始化失败较少见
            logger.debug(f"获取 statistics collector 失败: {exc}")
            return None

    # ------------------------------------------------------------------
    # 数据采集方法
    # ------------------------------------------------------------------
    def _collect_system_metrics(self, uptime_hint: float = 0.0) -> Dict[str, Any]:
        """采集 CPU/内存/磁盘/网络等基础指标。"""
        metrics: Dict[str, Any] = {
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "disk_usage": 0.0,
            "network_in": 0.0,
            "network_out": 0.0,
            "process_count": 0,
            "uptime": max(uptime_hint, 0.0),
        }

        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            if isinstance(cpu_percent, (list, tuple)):
                cpu_value = float(cpu_percent[0]) if cpu_percent else 0.0
            else:
                cpu_value = float(cpu_percent)
            metrics["cpu_usage"] = round(cpu_value, 2)

            memory = psutil.virtual_memory()
            metrics["memory_usage"] = round(memory.percent, 2)

            disk_usage = self._resolve_disk_usage()
            metrics["disk_usage"] = disk_usage

            metrics["process_count"] = len(psutil.pids())

            metrics.update(self._sampler.sample())
        except Exception as exc:  # pragma: no cover - 环境差异导致的 psutil 异常
            logger.warning(f"采集系统指标失败: {exc}")

        if metrics["uptime"] <= 0:
            try:
                metrics["uptime"] = max(time.time() - psutil.boot_time(), 0.0)
            except Exception as exc:
                logger.opt(exception=exc).debug("无法读取系统启动时间")

        return metrics

    def _collect_detailed_metrics(self) -> Dict[str, Any]:
        """构造 `/metrics` 端点需要的详细指标。"""
        cpu_freq_current = 0.0
        try:
            cpu_freq = psutil.cpu_freq()
        except Exception as exc:
            logger.opt(exception=exc).debug("无法获取 CPU 频率信息")
            cpu_freq = None

        if cpu_freq:
            cpu_freq_current = round(cpu_freq.current, 2)

        cpu_times_user = cpu_times_system = cpu_times_idle = 0.0
        try:
            cpu_times = psutil.cpu_times()
            cpu_times_user = round(getattr(cpu_times, "user", 0.0), 2)
            cpu_times_system = round(getattr(cpu_times, "system", 0.0), 2)
            cpu_times_idle = round(getattr(cpu_times, "idle", 0.0), 2)
        except Exception as exc:
            logger.opt(exception=exc).debug("无法获取 CPU 时间信息")

        memory_payload = {
            "total": 0,
            "available": 0,
            "used": 0,
            "cached": 0,
        }
        try:
            mem_info = psutil.virtual_memory()
            memory_payload.update(
                {
                    "total": mem_info.total,
                    "available": mem_info.available,
                    "used": mem_info.used,
                    "cached": getattr(mem_info, "cached", 0),
                }
            )
        except Exception as exc:
            logger.opt(exception=exc).debug("无法获取内存使用信息")

        read_bytes = write_bytes = read_count = write_count = 0
        try:
            disk_io = psutil.disk_io_counters()
            if disk_io:
                read_bytes = disk_io.read_bytes
                write_bytes = disk_io.write_bytes
                read_count = disk_io.read_count
                write_count = disk_io.write_count
        except Exception as exc:
            logger.opt(exception=exc).debug("无法获取磁盘 IO 信息")

        return {
            "cpu": {
                "cores": psutil.cpu_count() or 0,
                "frequency": cpu_freq_current,
                "user_time": cpu_times_user,
                "system_time": cpu_times_system,
                "idle_time": cpu_times_idle,
            },
            "memory": memory_payload,
            "io": {
                "read_bytes": read_bytes,
                "write_bytes": write_bytes,
                "read_count": read_count,
                "write_count": write_count,
            },
        }

    def _resolve_disk_usage(self) -> float:
        """返回首个有效分区的磁盘占用百分比。"""
        mount_point = None
        try:
            partitions = psutil.disk_partitions()
            for partition in partitions:
                if partition.fstype:
                    mount_point = partition.mountpoint
                    break
        except Exception:
            mount_point = None

        if not mount_point:
            mount_point = "\\" if getattr(psutil, "WINDOWS", False) else "/"

        try:
            usage = psutil.disk_usage(mount_point)
            percent_value = getattr(usage, "percent", 0.0)
            return round(float(percent_value), 2)
        except Exception:
            return 0.0

    def _extract_event_engine_metrics(self, engine) -> Tuple[int, int]:
        """读取事件引擎的队列长度与事件计数。"""
        queue_size = 0
        event_count = 0

        event_engine = getattr(engine, "_event_engine", None) or getattr(
            engine, "event_engine", None
        )
        if not event_engine:
            return queue_size, event_count

        try:
            if hasattr(event_engine, "_queue"):
                queue = event_engine._queue  # noqa: SLF001 - 保留对内部属性的访问以兼容现有实现
                if hasattr(queue, "qsize"):
                    queue_size = queue.qsize()
            if hasattr(event_engine, "_event_count"):
                event_count = int(event_engine._event_count)
        except Exception as exc:
            logger.debug(f"读取事件引擎指标失败: {exc}")

        return queue_size, event_count

    # ------------------------------------------------------------------
    # 对外公开的方法
    # ------------------------------------------------------------------
    def get_overview(self) -> Dict[str, Any]:
        """汇总系统运行状态。"""
        current_time = now()
        overview: Dict[str, Any] = {
            "timestamp": current_time.timestamp(),
            "updated_at": current_time.isoformat(),
            "engine": {
                "running": False,
                "uptime": 0.0,
                "event_count": 0,
                "queue_size": 0,
            },
            "monitor": {
                "running": False,
                "api_running": False,
            },
            "components": {},
            "mode": "unknown",
            "status": "stopped",
        }

        engine = self._get_engine()
        if engine:
            try:
                engine_status = engine.get_status()
                overview["engine"]["running"] = bool(engine_status.get("running"))
                overview["engine"]["uptime"] = engine_status.get("uptime", 0.0) or 0.0
                overview["mode"] = engine_status.get("mode", "unknown")
                overview["start_time"] = engine_status.get("start_time")

                queue_size, event_count = self._extract_event_engine_metrics(engine)
                overview["engine"]["queue_size"] = queue_size
                overview["engine"]["event_count"] = event_count

                components: Dict[str, Dict[str, Any]] = {}
                for name, comp in engine_status.get("components", {}).items():
                    components[name] = {
                        "status": comp.get("status"),
                        "type": comp.get("type"),
                    }
                overview["components"] = components
            except Exception as exc:
                logger.warning(f"读取 Engine 状态失败: {exc}")

        monitor = self._get_monitor()
        if monitor:
            overview["monitor"]["running"] = getattr(monitor, "_monitoring", False)

        monitor_api = self._get_monitor_api()
        if monitor_api:
            overview["monitor"]["api_running"] = getattr(monitor_api, "_running", False)

        collector = self._get_statistics_collector()
        if collector:
            try:
                summary = collector.get_summary()
                overview["total_components"] = summary.get("total_providers", 0)
                overview["healthy_components"] = summary.get("healthy_providers", 0)
                overview["key_metrics"] = summary.get("key_metrics", {})
            except Exception as exc:
                logger.debug(f"获取统计摘要失败: {exc}")

        metrics = self._collect_system_metrics(overview["engine"].get("uptime", 0.0))
        overview.update(metrics)
        overview["status"] = "running" if overview["engine"]["running"] else "stopped"
        return overview

    def get_metrics(self) -> Dict[str, Any]:
        """返回详细的系统度量数据。"""
        payload = self._collect_detailed_metrics()
        payload["timestamp"] = now().isoformat()
        return payload

    def get_statistics(self) -> Dict[str, Any]:
        """组合统计信息与监控摘要。"""
        stats = {
            "timestamp": now().isoformat(),
            "engine": {},
            "monitoring": {},
            "summary": {},
            "providers": {},
            "performance": {},
        }

        try:
            overview = self.get_overview()
            stats["engine"] = overview.get("engine", {})
            stats["monitoring"] = overview.get("monitor", {})
        except Exception as exc:
            logger.debug(f"获取概览信息失败: {exc}")

        collector = self._get_statistics_collector()
        if collector:
            try:
                stats["summary"] = collector.get_summary()
                stats["providers"] = collector.collect_all(use_cache=True).get("providers", {})
            except Exception as exc:
                logger.debug(f"读取统计数据失败: {exc}")

        monitor_api = self._get_monitor_api()
        if monitor_api:
            try:
                dashboard = monitor_api.get_dashboard_data()
                current = dashboard.get("current", {})
                stats["performance"] = {
                    "total_events": current.get("total_events", 0),
                    "queue_size": current.get("queue_size", 0),
                    "slow_events": current.get("slow_events", 0),
                    "active_alerts": current.get("active_alerts", 0),
                }
            except Exception as exc:
                logger.debug(f"读取监控数据失败: {exc}")

        return stats

    def list_components(self) -> Dict[str, Any]:
        """列出所有组件详情。"""
        engine = self._ensure_engine()
        try:
            components = engine.get_all_components()
        except Exception as exc:
            raise RuntimeError(f"获取组件信息失败: {exc}") from exc

        components_data: Dict[str, Dict[str, Any]] = {}
        result = {"timestamp": now().isoformat(), "components": components_data}

        for name, component in components.items():
            component_data = {
                "name": name,
                "display_name": getattr(component, "display_name", name),
                "description": getattr(component, "description", ""),
                "type": getattr(getattr(component, "component_type", None), "value", "unknown"),
                "status": getattr(getattr(component, "status", None), "value", "unknown"),
                "error_message": getattr(component, "error_message", None),
                "start_time": self._format_dt(getattr(component, "start_time", None)),
                "stop_time": self._format_dt(getattr(component, "stop_time", None)),
                "dependencies": list(getattr(component, "dependencies", [])),
                "config": getattr(component, "config", {}),
                "metrics": getattr(component, "metrics", {}),
            }

            if hasattr(component, "get_status_info"):
                try:
                    info = component.get_status_info()
                    component_data["info"] = info or {}
                    if (
                        name == "cache"
                        and component_data.get("error_message")
                        and isinstance(component_data.get("info"), dict)
                    ):
                        info_dict = component_data["info"]
                        info_dict.setdefault("error_message", component_data["error_message"])
                        info_dict.setdefault("disconnect_reason", component_data["error_message"])
                except Exception as exc:
                    logger.debug(f"获取组件 {name} 状态信息失败: {exc}")

            components_data[name] = component_data

        return result

    def get_component(self, component_name: str) -> Dict[str, Any]:
        """获取单个组件详情。"""
        engine = self._ensure_engine()
        component = engine.get_component_by_name(component_name)
        if not component:
            raise ComponentNotFoundError(component_name)

        payload = {
            "name": component_name,
            "display_name": getattr(component, "display_name", component_name),
            "description": getattr(component, "description", ""),
            "type": getattr(getattr(component, "component_type", None), "value", "unknown"),
            "status": getattr(getattr(component, "status", None), "value", "unknown"),
            "error_message": getattr(component, "error_message", None),
            "start_time": self._format_dt(getattr(component, "start_time", None)),
            "stop_time": self._format_dt(getattr(component, "stop_time", None)),
            "dependencies": list(getattr(component, "dependencies", [])),
            "config": getattr(component, "config", {}),
            "metrics": getattr(component, "metrics", {}),
        }

        if hasattr(component, "get_status_info"):
            try:
                payload["info"] = component.get_status_info() or {}
            except Exception as exc:
                logger.debug(f"获取组件 {component_name} info 失败: {exc}")

        return {"timestamp": now().isoformat(), "component": payload}

    async def check_component_health(self, component_name: str) -> Dict[str, Any]:
        """执行组件健康检查。"""
        engine = self._ensure_engine()
        component = engine.get_component_by_name(component_name)
        if not component:
            raise ComponentNotFoundError(component_name)

        is_healthy = True
        if hasattr(component, "health_check"):
            try:
                health_fn = component.health_check
                if inspect.iscoroutinefunction(health_fn):
                    result = await health_fn()
                    is_healthy = bool(result)
                else:
                    outcome = health_fn()
                    if inspect.isawaitable(outcome):
                        awaited = await outcome
                        is_healthy = bool(awaited)
                    else:
                        is_healthy = bool(outcome)
            except Exception as exc:
                logger.error(f"组件 {component_name} 健康检查失败: {exc}")
                is_healthy = False

        return {
            "timestamp": now().isoformat(),
            "component": component_name,
            "healthy": is_healthy,
            "status": "healthy" if is_healthy else "unhealthy",
        }

    # ------------------------------------------------------------------
    # 静态工具
    # ------------------------------------------------------------------
    @staticmethod
    def _format_dt(value: Optional[datetime]) -> Optional[str]:
        if not value:
            return None
        return value.isoformat()


_SYSTEM_DATA_SERVICE: Optional["SystemDataService"] = None


def get_system_data_service() -> SystemDataService:
    """单例访问器，便于在路由间共享。"""
    global _SYSTEM_DATA_SERVICE
    if _SYSTEM_DATA_SERVICE is None:
        _SYSTEM_DATA_SERVICE = SystemDataService()
    return _SYSTEM_DATA_SERVICE
