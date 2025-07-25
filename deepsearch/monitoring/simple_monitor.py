"""
简化的单机监控系统。

提供轻量级的性能监控和日志记录，无需外部依赖。
"""
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from loguru import logger

from deepsearch.monitoring.event_monitor import EventSystemMonitor


class SimpleMonitor:
    """
    简化的监控器，适用于单机系统。
    
    特点：
    - 无需额外依赖
    - 定期将指标写入日志文件
    - 可选的 JSON 格式输出便于分析
    - 低资源开销
    """

    def __init__(
            self,
            monitor: EventSystemMonitor,
            log_dir: Optional[Path] = None,
            interval: int = 300,  # 5分钟
            enable_json_log: bool = True
    ):
        """
        初始化简化监控器。
        
        Args:
            monitor: 事件系统监控器
            log_dir: 监控日志目录（默认为 logs/monitoring）
            interval: 记录间隔（秒）
            enable_json_log: 是否输出 JSON 格式日志
        """
        self._monitor = monitor
        self._interval = interval
        self._enable_json_log = enable_json_log
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # 设置日志目录
        if log_dir is None:
            log_dir = Path("logs/monitoring")
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)

        # 配置专门的监控日志记录器
        if enable_json_log:
            self._setup_json_logger()

    def _setup_json_logger(self) -> None:
        """设置 JSON 格式的日志记录器。"""
        json_log_file = self._log_dir / "metrics.json"
        logger.add(
            json_log_file,
            format="{message}",
            filter=lambda record: record["extra"].get("monitor_metrics", False),
            rotation="1 day",
            retention="7 days",
            encoding="utf-8"
        )

    def start(self) -> None:
        """启动监控。"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info(f"简化监控已启动，记录间隔：{self._interval}秒")

    def stop(self) -> None:
        """停止监控。"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("简化监控已停止")

    def _monitor_loop(self) -> None:
        """监控循环。"""
        while self._running:
            try:
                self._log_metrics()
            except Exception as e:
                logger.error(f"记录监控指标时出错：{e}")

            time.sleep(self._interval)

    def _log_metrics(self) -> None:
        """记录监控指标。"""
        summary = self._monitor.get_summary()

        # 提取关键指标
        metrics = self._extract_key_metrics(summary)

        # 记录到日志
        if self._enable_json_log:
            # JSON 格式（便于后续分析）
            logger.bind(monitor_metrics=True).info(json.dumps(metrics))

        # 人类可读的摘要
        self._log_human_readable_summary(metrics)

        # 如果有异常情况，记录警告
        self._check_and_warn(metrics)

    def _extract_key_metrics(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """提取关键指标。"""
        metrics = {
            "timestamp": summary.get("timestamp", datetime.now().isoformat()),
            "health_status": summary.get("health", {}).get("status", "unknown"),
            "events": {},
            "performance": {
                "total_events": 0,
                "avg_processing_time": 0,
                "slow_events_count": len(summary.get("slow_events", []))
            },
            "warnings": []
        }

        # 汇总事件指标
        events = summary.get("events", {})
        total_events = 0
        total_time = 0

        for event_type, event_metrics in events.items():
            total = event_metrics.get("total", 0)
            avg_time = event_metrics.get("avg_processing_time", 0)

            total_events += total
            total_time += total * avg_time

            # 只记录有活动的事件类型
            if total > 0:
                metrics["events"][event_type] = {
                    "count": total,
                    "success_rate": event_metrics.get("success_rate", 1.0),
                    "avg_time": round(avg_time, 3)
                }

        metrics["performance"]["total_events"] = total_events
        if total_events > 0:
            metrics["performance"]["avg_processing_time"] = round(total_time / total_events, 3)

        return metrics

    def _log_human_readable_summary(self, metrics: Dict[str, Any]) -> None:
        """记录人类可读的摘要。"""
        total_events = metrics["performance"]["total_events"]
        avg_time = metrics["performance"]["avg_processing_time"]
        slow_count = metrics["performance"]["slow_events_count"]
        health = metrics["health_status"]

        logger.info(
            f"监控摘要 | 健康状态: {health} | "
            f"处理事件: {total_events} | "
            f"平均耗时: {avg_time}s | "
            f"慢事件: {slow_count}"
        )

    def _check_and_warn(self, metrics: Dict[str, Any]) -> None:
        """检查指标并发出警告。"""
        warnings = []

        # 检查健康状态
        if metrics["health_status"] != "healthy":
            warnings.append(f"系统健康状态异常：{metrics['health_status']}")

        # 检查慢事件
        slow_count = metrics["performance"]["slow_events_count"]
        if slow_count > 10:
            warnings.append(f"慢事件过多：{slow_count} 个")

        # 检查平均处理时间
        avg_time = metrics["performance"]["avg_processing_time"]
        if avg_time > 0.5:  # 500ms
            warnings.append(f"平均处理时间过长：{avg_time}s")

        # 检查失败率
        for event_type, event_metrics in metrics["events"].items():
            success_rate = event_metrics.get("success_rate", 1.0)
            if success_rate < 0.95:  # 95% 成功率阈值
                warnings.append(f"事件 {event_type} 失败率过高：{(1 - success_rate) * 100:.1f}%")

        # 记录所有警告
        for warning in warnings:
            logger.warning(f"监控警告：{warning}")

        metrics["warnings"] = warnings

    def get_latest_metrics(self) -> Optional[Dict[str, Any]]:
        """获取最新的监控指标。"""
        try:
            summary = self._monitor.get_summary()
            return self._extract_key_metrics(summary)
        except Exception as e:
            logger.error(f"获取监控指标失败：{e}")
            return None


def setup_simple_monitoring(engine, bus=None, config=None) -> SimpleMonitor:
    """
    设置简化的监控系统。
    
    这是一个便捷函数，用于快速启动监控。
    
    Example:
        from deepsearch.monitoring import setup_simple_monitoring
        
        monitor = setup_simple_monitoring(engine)
        # 系统会自动开始记录监控日志
    """
    # 创建事件系统监控器
    event_monitor = EventSystemMonitor(engine, bus, config)
    event_monitor.start()

    # 创建简化监控器
    simple_monitor = SimpleMonitor(
        event_monitor,
        interval=config.get("interval", 300) if config else 300,
        enable_json_log=config.get("enable_json_log", True) if config else True
    )
    simple_monitor.start()

    return simple_monitor
