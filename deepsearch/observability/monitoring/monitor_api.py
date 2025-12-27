"""
监控系统 API 接口。

为未来的 Web UI 整合提供统一的数据访问接口。
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, cast

from loguru import logger

from deepsearch.observability.monitoring.event_monitor import EventSystemMonitor


class MonitorDataStore:
    """
    监控数据存储。

    特点：
    - 内存中保留最近的实时数据
    - 定期持久化到 JSON 文件
    - 提供统一的查询接口
    """

    def __init__(self, data_dir: Optional[Path] = None, max_records: int = 1000) -> None:
        """
        初始化数据存储。

        Args:
            data_dir: 数据存储目录
            max_records: 内存中保留的最大记录数
        """
        self._data_dir = Path(data_dir or "data/monitoring")
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # 实时数据队列
        self._realtime_data: Deque[Dict[str, Any]] = deque(maxlen=max_records)
        self._lock = threading.RLock()

        # 加载历史数据
        self._load_history()

    def add_record(self, record: Dict[str, Any]) -> None:
        """添加监控记录。"""
        with self._lock:
            self._realtime_data.append(record)

    def get_realtime_data(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取最新的实时数据。

        Args:
            limit: 返回的最大记录数

        Returns:
            最新的监控记录列表
        """
        with self._lock:
            records = list(self._realtime_data)
            return records[-limit:] if len(records) > limit else records

    def get_time_range_data(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """
        获取指定时间范围的数据。

        Args:
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            时间范围内的监控记录
        """
        with self._lock:
            records = []
            for record in self._realtime_data:
                timestamp = datetime.fromisoformat(record.get("timestamp", ""))
                if start_time <= timestamp <= end_time:
                    records.append(record)
            return records

    def save_to_file(self) -> None:
        """将当前数据保存到文件。"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self._data_dir / f"monitor_data_{timestamp}.json"

        with self._lock:
            data = list(self._realtime_data)

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"监控数据已保存到：{filename}")
        except Exception as e:
            logger.error(f"保存监控数据失败：{e}")

    def _load_history(self) -> None:
        """加载最近的历史数据。"""
        # 查找最新的数据文件
        files = sorted(self._data_dir.glob("monitor_data_*.json"), reverse=True)
        if not files:
            return

        latest_file = files[0]
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 只加载最近的数据
                maxlen = self._realtime_data.maxlen
                if isinstance(data, list):
                    records_to_load = data if maxlen is None else data[-maxlen:]
                    for record in records_to_load:
                        if isinstance(record, dict):
                            self._realtime_data.append(record)
            logger.info(f"已加载历史监控数据：{len(self._realtime_data)} 条记录")
        except Exception as e:
            logger.error(f"加载历史数据失败：{e}")


class MonitorAPI:
    """
    监控系统 API。

    提供适合 Web UI 整合的数据接口。
    """

    def __init__(self, monitor: EventSystemMonitor) -> None:
        """
        初始化监控 API。

        Args:
            monitor: 事件系统监控器
        """
        self._monitor = monitor
        self._data_store = MonitorDataStore()
        self._running = False
        self._update_thread: Optional[threading.Thread] = None

        # 配置更新间隔
        self._update_interval = 5  # 5秒更新一次，适合实时展示
        self._persist_interval = 300  # 5分钟持久化一次
        self._last_persist_time = time.time()

        # 注册到统计收集器
        from deepsearch.core.utils.statistics import get_statistics_collector

        self._statistics_collector = get_statistics_collector()
        self._statistics_collector.register_provider("monitor_api", self)

        # 如果 monitor 也是 StatisticsProvider，注册它
        if hasattr(monitor, "get_statistics"):
            self._statistics_collector.register_provider("event_monitor", monitor)

    def start(self) -> None:
        """启动 API 服务。"""
        if self._running:
            return

        self._running = True
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()
        logger.info("监控 API 已启动")

    def stop(self) -> None:
        """停止 API 服务。"""
        if not self._running:
            return

        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=10)

        # 最后保存一次数据
        self._data_store.save_to_file()

        # 从统计收集器注销
        self._statistics_collector.unregister_provider("monitor_api")
        if hasattr(self._monitor, "get_statistics"):
            self._statistics_collector.unregister_provider("event_monitor")

        logger.info("监控 API 已停止")

    def _update_loop(self) -> None:
        """定期更新数据。"""
        while self._running:
            try:
                # 获取最新监控数据
                record = self._create_monitor_record()
                self._data_store.add_record(record)

                # 定期持久化
                if time.time() - self._last_persist_time > self._persist_interval:
                    self._data_store.save_to_file()
                    self._last_persist_time = time.time()

            except Exception as e:
                logger.error(f"更新监控数据失败：{e}")

            time.sleep(self._update_interval)

    def _create_monitor_record(self) -> Dict[str, Any]:
        """创建监控记录。"""
        summary = self._monitor.get_summary()

        # 构建适合 Web UI 展示的数据结构
        record = {
            "timestamp": summary.get("timestamp", datetime.now().isoformat()),
            "health": {
                "status": summary.get("health", {}).get("status", "unknown"),
                "checks": summary.get("health", {}).get("checks", {}),
            },
            "metrics": {
                "events": self._format_event_metrics(summary.get("events", {})),
                "handlers": summary.get("handlers", {}),
                "queue_size": self._get_queue_size(),
                "slow_events": len(summary.get("slow_events", [])),
            },
            "alerts": self._generate_alerts(summary),
        }

        return record

    def _format_event_metrics(self, events: Dict[str, Any]) -> Dict[str, Any]:
        """格式化事件指标，便于图表展示。"""
        formatted = {}
        for event_type, metrics in events.items():
            formatted[event_type] = {
                "count": metrics.get("total", 0),
                "success_rate": round(metrics.get("success_rate", 1.0) * 100, 2),
                "avg_time_ms": round(metrics.get("avg_processing_time", 0) * 1000, 2),
                "min_time_ms": round(metrics.get("min_processing_time", 0) * 1000, 2),
                "max_time_ms": round(metrics.get("max_processing_time", 0) * 1000, 2),
            }
        return formatted

    def _get_queue_size(self) -> int:
        """获取队列大小。"""
        if hasattr(self._monitor._engine, "_queue"):
            return self._monitor._engine._queue.qsize()
        return 0

    def _generate_alerts(self, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成告警信息。"""
        alerts = []

        # 健康状态告警
        health_status = summary.get("health", {}).get("status", "healthy")
        if health_status != "healthy":
            alerts.append(
                {
                    "level": "error" if health_status == "unhealthy" else "warning",
                    "type": "health",
                    "message": f"系统健康状态：{health_status}",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # 慢事件告警
        slow_events = summary.get("slow_events", [])
        if len(slow_events) > 10:
            alerts.append(
                {
                    "level": "warning",
                    "type": "performance",
                    "message": f"检测到 {len(slow_events)} 个慢事件",
                    "timestamp": datetime.now().isoformat(),
                }
            )

        # 失败率告警
        events = summary.get("events", {})
        for event_type, metrics in events.items():
            success_rate = metrics.get("success_rate", 1.0)
            if success_rate < 0.95:
                alerts.append(
                    {
                        "level": "warning",
                        "type": "error_rate",
                        "message": f"事件 {event_type} 失败率过高：{(1 - success_rate) * 100:.1f}%",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        return alerts

    # ========== Web UI 调用的 API 方法 ==========

    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        获取仪表板数据。

        Returns:
            适合 Web UI 仪表板展示的汇总数据
        """
        latest_records = self._data_store.get_realtime_data(limit=20)

        if not latest_records:
            return self._get_empty_dashboard()

        latest = latest_records[-1]

        # 计算趋势
        trends = self._calculate_trends(latest_records)

        return {
            "current": {
                "timestamp": latest["timestamp"],
                "health_status": latest["health"]["status"],
                "total_events": sum(m["count"] for m in latest["metrics"]["events"].values()),
                "queue_size": latest["metrics"]["queue_size"],
                "slow_events": latest["metrics"]["slow_events"],
                "active_alerts": len([a for a in latest["alerts"] if a["level"] == "error"]),
            },
            "trends": trends,
            "alerts": latest["alerts"],
        }

    def get_realtime_metrics(self, event_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        获取实时指标数据。

        Args:
            event_types: 要获取的事件类型列表（None 表示所有）

        Returns:
            适合实时图表展示的指标数据
        """
        records = self._data_store.get_realtime_data(limit=100)

        if not records:
            return {"series": {}, "timestamps": []}

        # 构建时间序列数据
        series: Dict[str, Dict[str, List[float]]] = {}
        timestamps: List[str] = []

        for record in records:
            timestamps.append(record["timestamp"])

            for event_type, metrics in record["metrics"]["events"].items():
                if event_types and event_type not in event_types:
                    continue

                if event_type not in series:
                    series[event_type] = {"count": [], "success_rate": [], "avg_time_ms": []}

                series[event_type]["count"].append(float(metrics["count"]))
                series[event_type]["success_rate"].append(float(metrics["success_rate"]))
                series[event_type]["avg_time_ms"].append(float(metrics["avg_time_ms"]))

        return {"series": series, "timestamps": timestamps}

    def get_health_status(self) -> Dict[str, Any]:
        """
        获取健康状态详情。

        Returns:
            健康检查的详细信息
        """
        latest_records = self._data_store.get_realtime_data(limit=1)

        if not latest_records:
            return {"status": "unknown", "checks": {}}

        record = latest_records[0]
        health_value = record.get("health")
        if isinstance(health_value, dict):
            return cast(Dict[str, Any], health_value)
        return {"status": "unknown", "checks": {}}

    def get_slow_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        获取慢事件列表。

        Args:
            limit: 返回的最大数量

        Returns:
            慢事件详细信息列表
        """
        summary = self._monitor.get_summary()
        slow_events_data = summary.get("slow_events", [])

        valid_events: List[Dict[str, Any]] = []
        if isinstance(slow_events_data, list):
            for item in slow_events_data:
                if isinstance(item, dict):
                    valid_events.append(item)
        return valid_events[:limit]

    def get_historical_data(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取历史数据。

        Args:
            hours: 要获取的历史小时数

        Returns:
            指定时间范围的历史数据
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)

        records = self._data_store.get_time_range_data(start_time, end_time)

        return {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "record_count": len(records),
            "records": records,
        }

    def _calculate_trends(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算趋势数据。"""
        if len(records) < 2:
            return {}

        old = records[0]["metrics"]
        new = records[-1]["metrics"]

        # 计算事件总数变化
        old_total = sum(m["count"] for m in old["events"].values())
        new_total = sum(m["count"] for m in new["events"].values())

        return {
            "events_change": new_total - old_total,
            "queue_size_change": new["queue_size"] - old.get("queue_size", 0),
            "slow_events_change": new["slow_events"] - old.get("slow_events", 0),
        }

    def _get_empty_dashboard(self) -> Dict[str, Any]:
        """返回空的仪表板数据。"""
        return {
            "current": {
                "timestamp": datetime.now().isoformat(),
                "health_status": "unknown",
                "total_events": 0,
                "queue_size": 0,
                "slow_events": 0,
                "active_alerts": 0,
            },
            "trends": {},
            "alerts": [],
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        实现 StatisticsProvider 接口

        Returns:
            监控API的统计信息
        """
        # MonitorAPI 作为顶层组件，只返回自己的监控数据
        # 不再调用 collect_all 避免循环依赖

        # 获取最新的监控记录
        latest_records = self._data_store.get_realtime_data(limit=1)
        latest = latest_records[-1] if latest_records else None

        monitor_stats = {
            "timestamp": datetime.now().isoformat(),
            "monitor_running": self._running,
            "update_interval": self._update_interval,
            "data_store_size": len(self._data_store._realtime_data),
            "dashboard_data": self.get_dashboard_data(),
            "latest_record": latest,
        }

        return monitor_stats
