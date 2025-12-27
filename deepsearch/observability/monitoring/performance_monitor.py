"""
性能监控模块

提供系统性能监控、统计和分析功能
"""

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import DefaultDict, Deque, Dict, List, Optional, TypedDict

from loguru import logger


class MetricType(Enum):
    """指标类型"""

    REQUEST_COUNT = "request_count"
    REQUEST_LATENCY = "request_latency"
    CACHE_HIT_RATE = "cache_hit_rate"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    WORKER_HEALTH = "worker_health"
    BATCH_EFFICIENCY = "batch_efficiency"


MAX_METRICS_PER_TYPE = 10000


class PerformanceStats(TypedDict):
    total_requests: int
    successful_requests: int
    failed_requests: int
    cache_hits: int
    cache_misses: int
    total_latency: float
    batch_requests: int
    worker_failures: int


class AlertThresholds(TypedDict):
    error_rate: float
    latency_p99: float
    cache_hit_rate: float
    worker_health: float


class SummaryStats(TypedDict):
    total_requests: int
    successful_requests: int
    failed_requests: int
    error_rate: float
    cache_hit_rate: float
    batch_ratio: float
    throughput: float


class LatencyStats(TypedDict):
    min: float
    p50: float
    p90: float
    p99: float
    max: float
    avg: float


class CacheStats(TypedDict):
    hits: int
    misses: int
    hit_rate: float


class WorkerStats(TypedDict):
    failures: int


class PerformanceSnapshot(TypedDict):
    summary: SummaryStats
    latency: Optional[LatencyStats]
    cache: CacheStats
    workers: WorkerStats
    alerts: int


class AlertRecord(TypedDict):
    type: str
    message: str
    timestamp: datetime
    stats: PerformanceSnapshot


def _create_metric_buffer() -> Deque["PerformanceMetric"]:
    return deque(maxlen=MAX_METRICS_PER_TYPE)


@dataclass
class PerformanceMetric:
    """性能指标"""

    metric_type: MetricType
    value: float
    timestamp: float
    source: str
    tags: Dict[str, str]


class PerformanceMonitor:
    """
    性能监控器

    功能：
    1. 收集各种性能指标
    2. 计算统计数据
    3. 生成性能报告
    4. 触发告警
    """

    def __init__(
        self, window_size: int = 3600, alert_enabled: bool = True
    ) -> None:  # 监控窗口大小（秒）
        """
        初始化性能监控器

        Args:
            window_size: 监控窗口大小
            alert_enabled: 是否启用告警
        """
        self.window_size = window_size
        self.alert_enabled = alert_enabled

        # 指标存储 {metric_type: deque of PerformanceMetric}
        self.metrics: DefaultDict[MetricType, Deque[PerformanceMetric]] = defaultdict(
            _create_metric_buffer
        )

        # 统计数据
        self.stats: PerformanceStats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_latency": 0.0,
            "batch_requests": 0,
            "worker_failures": 0,
        }

        # 告警阈值
        self.alert_thresholds: AlertThresholds = {
            "error_rate": 0.1,  # 错误率超过10%
            "latency_p99": 5.0,  # P99延迟超过5秒
            "cache_hit_rate": 0.3,  # 缓存命中率低于30%
            "worker_health": 0.5,  # Worker健康度低于50%
        }

        # 最近的告警
        self.recent_alerts: Deque[AlertRecord] = deque(maxlen=100)

        # 启动定期清理任务
        asyncio.create_task(self._cleanup_task())

    def record_request(
        self,
        source: str,
        api_name: str,
        latency: float,
        success: bool,
        cached: bool = False,
        batch: bool = False,
    ) -> None:
        """
        记录请求

        Args:
            source: 数据源
            api_name: API名称
            latency: 延迟（秒）
            success: 是否成功
            cached: 是否命中缓存
            batch: 是否批量请求
        """
        self.stats["total_requests"] += 1

        if success:
            self.stats["successful_requests"] += 1
        else:
            self.stats["failed_requests"] += 1

        if cached:
            self.stats["cache_hits"] += 1
        else:
            self.stats["cache_misses"] += 1

        if batch:
            self.stats["batch_requests"] += 1

        self.stats["total_latency"] += latency

        # 记录延迟指标
        metric = PerformanceMetric(
            metric_type=MetricType.REQUEST_LATENCY,
            value=latency,
            timestamp=time.time(),
            source=source,
            tags={
                "api_name": api_name,
                "success": str(success),
                "cached": str(cached),
                "batch": str(batch),
            },
        )

        self._add_metric(metric)

        # 检查告警
        if self.alert_enabled:
            self._check_alerts()

    def record_cache_access(self, cache_type: str, hit: bool, data_type: str) -> None:
        """
        记录缓存访问

        Args:
            cache_type: 缓存类型（L1/L2/L3）
            hit: 是否命中
            data_type: 数据类型
        """
        metric = PerformanceMetric(
            metric_type=MetricType.CACHE_HIT_RATE,
            value=1.0 if hit else 0.0,
            timestamp=time.time(),
            source=cache_type,
            tags={"data_type": data_type},
        )

        self._add_metric(metric)

    def record_worker_status(
        self, worker_url: str, healthy: bool, latency: Optional[float] = None
    ) -> None:
        """
        记录Worker状态

        Args:
            worker_url: Worker URL
            healthy: 是否健康
            latency: 延迟
        """
        if not healthy:
            self.stats["worker_failures"] += 1

        metric = PerformanceMetric(
            metric_type=MetricType.WORKER_HEALTH,
            value=1.0 if healthy else 0.0,
            timestamp=time.time(),
            source=worker_url,
            tags={"latency": str(latency) if latency else "N/A"},
        )

        self._add_metric(metric)

    def _add_metric(self, metric: PerformanceMetric) -> None:
        """添加指标"""
        self.metrics[metric.metric_type].append(metric)

        # 限制队列大小
        if len(self.metrics[metric.metric_type]) > MAX_METRICS_PER_TYPE:
            self.metrics[metric.metric_type].popleft()

    def get_statistics(self, duration: Optional[int] = None) -> PerformanceSnapshot:
        """
        获取统计信息

        Args:
            duration: 统计时长（秒），None表示全部

        Returns:
            统计信息
        """
        if duration:
            cutoff_time = time.time() - duration
        else:
            cutoff_time = 0

        # 计算各种统计
        latencies: List[float] = []
        for metric in self.metrics[MetricType.REQUEST_LATENCY]:
            if metric.timestamp >= cutoff_time:
                latencies.append(metric.value)

        # 计算延迟分位数
        latency_stats: Optional[LatencyStats] = None
        if latencies:
            latencies.sort()
            latency_stats = {
                "min": latencies[0],
                "p50": self._percentile(latencies, 50),
                "p90": self._percentile(latencies, 90),
                "p99": self._percentile(latencies, 99),
                "max": latencies[-1],
                "avg": sum(latencies) / len(latencies),
            }

        # 计算缓存命中率
        cache_hits = sum(
            1
            for m in self.metrics[MetricType.CACHE_HIT_RATE]
            if m.timestamp >= cutoff_time and m.value > 0
        )
        cache_total = sum(
            1 for m in self.metrics[MetricType.CACHE_HIT_RATE] if m.timestamp >= cutoff_time
        )
        cache_hit_rate = cache_hits / cache_total if cache_total > 0 else 0

        # 计算错误率
        error_rate = self.stats["failed_requests"] / max(self.stats["total_requests"], 1)

        # 计算吞吐量（请求/秒）
        if duration:
            throughput = self.stats["total_requests"] / duration
        else:
            throughput = 0

        # 计算批量效率
        batch_ratio = self.stats["batch_requests"] / max(self.stats["total_requests"], 1)

        return {
            "summary": {
                "total_requests": self.stats["total_requests"],
                "successful_requests": self.stats["successful_requests"],
                "failed_requests": self.stats["failed_requests"],
                "error_rate": error_rate,
                "cache_hit_rate": cache_hit_rate,
                "batch_ratio": batch_ratio,
                "throughput": throughput,
            },
            "latency": latency_stats,
            "cache": {
                "hits": self.stats["cache_hits"],
                "misses": self.stats["cache_misses"],
                "hit_rate": cache_hit_rate,
            },
            "workers": {"failures": self.stats["worker_failures"]},
            "alerts": len(self.recent_alerts),
        }

    def _percentile(self, data: List[float], percentile: int) -> float:
        """计算分位数"""
        if not data:
            return 0

        index = int(len(data) * percentile / 100)
        if index >= len(data):
            index = len(data) - 1

        return data[index]

    def _check_alerts(self) -> None:
        """检查告警条件"""
        stats = self.get_statistics(duration=300)  # 最近5分钟

        # 检查错误率
        if stats["summary"]["error_rate"] > self.alert_thresholds["error_rate"]:
            self._trigger_alert(
                "HIGH_ERROR_RATE", f"错误率过高: {stats['summary']['error_rate']:.2%}"
            )

        # 检查延迟
        latency_stats = stats["latency"]
        if (
            latency_stats is not None
            and latency_stats["p99"] > self.alert_thresholds["latency_p99"]
        ):
            self._trigger_alert("HIGH_LATENCY", f"P99延迟过高: {latency_stats['p99']:.2f}s")

        # 检查缓存命中率
        if stats["cache"]["hit_rate"] < self.alert_thresholds["cache_hit_rate"]:
            self._trigger_alert(
                "LOW_CACHE_HIT_RATE", f"缓存命中率过低: {stats['cache']['hit_rate']:.2%}"
            )

    def _trigger_alert(self, alert_type: str, message: str) -> None:
        """触发告警"""
        alert: AlertRecord = {
            "type": alert_type,
            "message": message,
            "timestamp": datetime.now(),
            "stats": self.get_statistics(duration=60),
        }

        self.recent_alerts.append(alert)
        logger.warning(f"[性能告警] {alert_type}: {message}")

    async def _cleanup_task(self) -> None:
        """定期清理过期数据"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟清理一次

                cutoff_time = time.time() - self.window_size

                # 清理过期指标
                for metric_type in self.metrics:
                    while (
                        self.metrics[metric_type]
                        and self.metrics[metric_type][0].timestamp < cutoff_time
                    ):
                        self.metrics[metric_type].popleft()

                logger.debug("完成性能数据清理")

            except Exception as e:
                logger.error(f"清理任务失败: {e}")

    def generate_report(self) -> str:
        """
        生成性能报告

        Returns:
            Markdown格式的报告
        """
        stats_1m = self.get_statistics(duration=60)
        stats_5m = self.get_statistics(duration=300)
        stats_1h = self.get_statistics(duration=3600)

        report = []
        report.append("# 性能监控报告")
        report.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 总体统计
        report.append("\n## 总体统计")
        report.append(f"- 总请求数: {self.stats['total_requests']:,}")
        report.append(
            f"- 成功率: {(self.stats['successful_requests'] / max(self.stats['total_requests'], 1)):.2%}"
        )
        report.append(f"- 缓存命中率: {stats_1h['cache']['hit_rate']:.2%}")
        report.append(f"- 批量请求比例: {stats_1h['summary']['batch_ratio']:.2%}")

        # 延迟统计
        report.append("\n## 延迟统计")
        report.append("\n| 时间段 | P50 | P90 | P99 | 平均 |")
        report.append("|--------|-----|-----|-----|------|")

        for label, snapshot in [("1分钟", stats_1m), ("5分钟", stats_5m), ("1小时", stats_1h)]:
            latency_stats = snapshot["latency"]
            if latency_stats is None:
                continue
            report.append(
                f"| {label} | {latency_stats['p50']:.3f}s | "
                f"{latency_stats['p90']:.3f}s | {latency_stats['p99']:.3f}s | "
                f"{latency_stats['avg']:.3f}s |"
            )

        # 告警信息
        if self.recent_alerts:
            report.append("\n## 最近告警")
            for alert in list(self.recent_alerts)[-5:]:  # 最近5条
                report.append(
                    f"- [{alert['timestamp'].strftime('%H:%M:%S')}] "
                    f"{alert['type']}: {alert['message']}"
                )

        return "\n".join(report)


# 全局监控器实例
_monitor = None


def get_monitor() -> PerformanceMonitor:
    """获取全局监控器实例"""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor
