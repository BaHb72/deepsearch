"""
数据源监控中心

统一监控和管理所有数据源的访问情况，提供性能分析和智能决策支持。
"""

import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, ClassVar, Deque, DefaultDict, Dict, List, Optional, Tuple, TypedDict

from loguru import logger

from deepsearch.ports.data_sources import DataAccessType, DataSourceType

_HIDDEN_SOURCES = {DataSourceType.DEFAULT, DataSourceType.CUSTOM}

DEFAULT_MODULE_KEY = "unknown"

class SourceSummary(TypedDict):
    count: int
    success: int
    error: int

class AccessStatistics(TypedDict):
    time_window: int
    total_requests: int
    source_stats: Dict[str, SourceSummary]
    type_stats: Dict[str, int]
    hot_symbols: List[Tuple[str, int]]
    module_stats: Dict[str, Dict[str, int]]

def _build_source_summary() -> SourceSummary:
    return {"count": 0, "success": 0, "error": 0}

def _build_int_counter() -> DefaultDict[str, int]:
    """Create a defaultdict for counting occurrences."""
    return defaultdict(int)

@dataclass
class AccessRecord:
    """数据访问记录"""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    source: DataSourceType = DataSourceType.DEFAULT
    access_type: DataAccessType = DataAccessType.REALTIME_QUOTE
    symbol: Optional[str] = None
    module: Optional[str] = None  # 调用模块
    success: bool = True
    latency_ms: float = 0
    error_message: Optional[str] = None
    data_size: int = 0  # 返回数据大小（字节）
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SourceMetrics:
    """数据源性能指标"""

    source: DataSourceType
    total_requests: int = 0
    success_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0
    total_data_size: int = 0
    last_access: Optional[float] = None
    last_error: Optional[str] = None
    error_timestamps: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    latency_history: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))

    @property
    def success_rate(self) -> float:
        """计算成功率"""
        if self.total_requests == 0:
            return 0.0
        return self.success_count / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        """计算平均延迟"""
        if self.success_count == 0:
            # 无数据时返回-1表示无效值，前端会处理为"暂无数据"
            return -1.0
        return self.total_latency_ms / self.success_count

    @property
    def recent_error_rate(self) -> float:
        """计算最近的错误率（最近5分钟）"""
        if not self.error_timestamps:
            return 0.0

        current_time = time.time()
        time_window = 300  # 5分钟窗口
        recent_errors = sum(1 for t in self.error_timestamps if current_time - t < time_window)

        # 如果最近5分钟没有任何错误，返回0
        if recent_errors == 0:
            return 0.0

        # 计算最近5分钟的总请求数（假设错误率不超过100%）
        # 使用最近的错误数和成功率来估算
        if self.total_requests > 0:
            # 基于历史成功率估算最近的请求数
            historical_error_rate = self.error_count / self.total_requests
            estimated_recent_requests = recent_errors / max(historical_error_rate, 0.01)
            return min(recent_errors / max(estimated_recent_requests, 1), 1.0)
        else:
            # 如果没有历史数据，假设错误率为100%
            return 1.0 if recent_errors > 0 else 0.0

    @property
    def p95_latency(self) -> float:
        """计算P95延迟"""
        if not self.latency_history:
            # 无数据时返回-1表示无效值
            return -1.0

        sorted_latencies = sorted(self.latency_history)
        p95_index = int(len(sorted_latencies) * 0.95)
        return (
            sorted_latencies[p95_index]
            if p95_index < len(sorted_latencies)
            else sorted_latencies[-1]
        )

class DataSourceMonitor:
    """数据源监控中心"""

    # 单例实例
    _instance: ClassVar[Optional["DataSourceMonitor"]] = None
    _lock: ClassVar[Lock] = Lock()
    _initialized: ClassVar[bool] = False

    def __new__(cls) -> "DataSourceMonitor":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if type(self)._initialized:
            return

        # 访问记录（保留最近10000条）
        self.access_history: Deque[AccessRecord] = deque(maxlen=10000)

        # 各数据源的性能指标
        self.source_metrics: Dict[DataSourceType, SourceMetrics] = {}
        for source_type in DataSourceType:
            self.source_metrics[source_type] = SourceMetrics(source=source_type)

        # 访问统计（按访问类型）
        self.access_stats: DefaultDict[DataAccessType, DefaultDict[str, int]] = defaultdict(
            _build_int_counter
        )

        # 热点数据统计（最常访问的股票）
        self.hot_symbols: DefaultDict[str, int] = defaultdict(int)

        # 模块访问统计
        self.module_stats: DefaultDict[str, DefaultDict[str, int]] = defaultdict(_build_int_counter)

        # 配置
        self.alert_error_threshold = 10  # 连续错误次数阈值
        self.alert_latency_threshold = 5000  # 延迟阈值（毫秒）
        self.health_check_interval = 30  # 健康检查间隔（秒）

        # 数据源健康状态
        self.source_health: Dict[DataSourceType, bool] = {source: True for source in DataSourceType}

        # 锁
        self._metrics_lock = Lock()

        type(self)._initialized = True
        logger.info("数据源监控中心初始化完成")

    def record_access(
        self,
        source: DataSourceType,
        access_type: DataAccessType,
        success: bool,
        latency_ms: float,
        symbol: Optional[str] = None,
        module: Optional[str] = None,
        error_message: Optional[str] = None,
        data_size: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        记录数据访问

        Args:
            source: 数据源类型
            access_type: 访问类型
            success: 是否成功
            latency_ms: 延迟（毫秒）
            symbol: 股票代码
            module: 调用模块
            error_message: 错误信息
            data_size: 数据大小
            metadata: 额外元数据

        Returns:
            请求ID
        """
        module_key: str = module if module is not None else DEFAULT_MODULE_KEY

        # 创建访问记录
        record = AccessRecord(
            source=source,
            access_type=access_type,
            symbol=symbol,
            module=module_key,
            success=success,
            latency_ms=latency_ms,
            error_message=error_message,
            data_size=data_size,
            metadata=metadata or {},
        )

        with self._metrics_lock:
            # 添加到历史记录
            self.access_history.append(record)

            # 更新数据源指标
            metrics = self.source_metrics[source]
            metrics.total_requests += 1
            metrics.last_access = record.timestamp

            if success:
                metrics.success_count += 1
                metrics.total_latency_ms += latency_ms
                metrics.total_data_size += data_size
                metrics.latency_history.append(latency_ms)
            else:
                metrics.error_count += 1
                metrics.last_error = error_message
                metrics.error_timestamps.append(record.timestamp)

            # 更新访问统计
            self.access_stats[access_type][source.value] += 1

            # 更新热点数据
            if symbol:
                self.hot_symbols[symbol] += 1

            # 更新模块统计
            self.module_stats[module_key][source.value] += 1

            # 检查是否需要告警
            self._check_alerts(source, metrics)

        # 记录日志
        if success:
            logger.debug(
                f"数据访问成功: {source.value} -> {access_type.value} "
                f"[{symbol}] {latency_ms:.1f}ms"
            )
        else:
            logger.warning(
                f"数据访问失败: {source.value} -> {access_type.value} "
                f"[{symbol}] {error_message}"
            )

        return record.request_id

    def _check_alerts(self, source: DataSourceType, metrics: SourceMetrics) -> None:
        """检查是否需要发出告警"""
        # 检查连续错误 - 降低阈值到20%，并且需要至少有10次请求才判断
        if metrics.total_requests >= 10 and metrics.recent_error_rate > 0.2:  # 最近错误率超过20%
            logger.warning(f"数据源 {source.value} 错误率较高: {metrics.recent_error_rate:.1%}")
            # 只有当错误率非常高时才标记为不健康
            if metrics.recent_error_rate > 0.8:  # 错误率超过80%才标记为不健康
                self.source_health[source] = False
                logger.error(
                    f"数据源 {source.value} 错误率过高，标记为不健康: {metrics.recent_error_rate:.1%}"
                )

        # 检查延迟
        if metrics.p95_latency > self.alert_latency_threshold:
            logger.warning(f"数据源 {source.value} 延迟过高: " f"P95={metrics.p95_latency:.1f}ms")

    def get_source_health(self, source: DataSourceType) -> Dict[str, Any]:
        """
        获取数据源健康状态

        Args:
            source: 数据源类型

        Returns:
            健康状态信息
        """
        metrics = self.source_metrics[source]

        return {
            "source": source.value,
            "healthy": self.source_health[source],
            "total_requests": metrics.total_requests,
            "success_rate": metrics.success_rate,
            "avg_latency_ms": metrics.avg_latency_ms,
            "p95_latency_ms": metrics.p95_latency,
            "recent_error_rate": metrics.recent_error_rate,
            "last_access": (
                datetime.fromtimestamp(metrics.last_access).isoformat()
                if metrics.last_access
                else None
            ),
            "last_error": metrics.last_error,
        }

    def get_all_health_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有数据源的健康状态"""
        return {
            source.value: self.get_source_health(source)
            for source in DataSourceType
            if source not in _HIDDEN_SOURCES
        }

    def get_access_statistics(self, time_window: int = 3600) -> AccessStatistics:
        """
        获取访问统计

        Args:
            time_window: 时间窗口（秒）

        Returns:
            统计信息
        """
        current_time = time.time()
        cutoff_time = current_time - time_window

        # 筛选时间窗口内的记录
        recent_records = [r for r in self.access_history if r.timestamp >= cutoff_time]

        # 按数据源统计
        source_stats: DefaultDict[str, SourceSummary] = defaultdict(_build_source_summary)
        for record in recent_records:
            stats = source_stats[record.source.value]
            stats["count"] += 1
            if record.success:
                stats["success"] += 1
            else:
                stats["error"] += 1

        # 按访问类型统计
        type_stats: DefaultDict[str, int] = defaultdict(int)
        for record in recent_records:
            type_stats[record.access_type.value] += 1

        # 热点股票TOP10
        hot_symbols_top10 = sorted(self.hot_symbols.items(), key=lambda x: x[1], reverse=True)[:10]
        module_stats_snapshot = {
            module_name: dict(stats)
            for module_name, stats in self.module_stats.items()
        }

        return {
            "time_window": time_window,
            "total_requests": len(recent_records),
            "source_stats": dict(source_stats),
            "type_stats": dict(type_stats),
            "hot_symbols": hot_symbols_top10,
            "module_stats": module_stats_snapshot,
        }

    def get_recommendation(
        self, access_type: DataAccessType, require_realtime: bool = False
    ) -> Optional[DataSourceType]:
        """
        获取推荐的数据源

        Args:
            access_type: 访问类型
            require_realtime: 是否需要实时数据

        Returns:
            推荐的数据源
        """
        # 候选数据源
        candidates = []

        for source in DataSourceType:
            metrics = self.source_metrics[source]

            # 跳过不健康的数据源
            if not self.source_health[source]:
                continue

            # 跳过没有访问记录的数据源
            if metrics.total_requests == 0:
                continue

            # 计算得分
            score = self._calculate_source_score(metrics, require_realtime)
            candidates.append((source, score))

        if not candidates:
            return None

        # 按得分排序，返回最优的
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _calculate_source_score(self, metrics: SourceMetrics, require_realtime: bool) -> float:
        """
        计算数据源得分

        Args:
            metrics: 数据源指标
            require_realtime: 是否需要实时数据

        Returns:
            得分（0-100）
        """
        score = 100.0

        # 成功率权重：40%
        score *= metrics.success_rate * 0.4

        # 延迟权重：30%
        if metrics.avg_latency_ms < 100:
            latency_score = 1.0
        elif metrics.avg_latency_ms < 500:
            latency_score = 0.8
        elif metrics.avg_latency_ms < 1000:
            latency_score = 0.6
        elif metrics.avg_latency_ms < 3000:
            latency_score = 0.4
        else:
            latency_score = 0.2
        score += latency_score * 30

        # 最近错误率权重：20%
        score -= metrics.recent_error_rate * 20

        # 数据新鲜度权重：10%（如果需要实时数据）
        if require_realtime and metrics.last_access:
            freshness = max(0, 1 - (time.time() - metrics.last_access) / 60)
            score += freshness * 10

        return max(0, min(100, score))

    def reset_metrics(self, source: Optional[DataSourceType] = None) -> None:
        """
        重置指标

        Args:
            source: 数据源类型，如果为None则重置所有
        """
        with self._metrics_lock:
            if source:
                self.source_metrics[source] = SourceMetrics(source=source)
                self.source_health[source] = True
                logger.info(f"重置数据源 {source.value} 的监控指标")
            else:
                for source_type in DataSourceType:
                    self.source_metrics[source_type] = SourceMetrics(source=source_type)
                    self.source_health[source_type] = True
                self.access_history.clear()
                self.access_stats.clear()
                self.hot_symbols.clear()
                self.module_stats.clear()
                logger.info("重置所有监控指标")

    def update_health_status(
        self, source: DataSourceType, is_healthy: bool, reset_metrics_if_healthy: bool = True
    ) -> None:
        """
        强制更新数据源健康状态

        Args:
            source: 数据源类型
            is_healthy: 是否健康
            reset_metrics_if_healthy: 健康时是否重置错误指标
        """
        with self._metrics_lock:
            self.source_health[source] = is_healthy

            if is_healthy and reset_metrics_if_healthy:
                # 健康时重置错误相关指标
                metrics = self.source_metrics[source]
                # 创建一个新的错误时间戳队列，清空历史错误
                metrics.error_timestamps = deque(maxlen=100)
                metrics.last_error = None
                # 如果没有历史成功记录，添加一次成功记录
                if metrics.success_count == 0:
                    metrics.success_count = 1
                    metrics.total_requests = 1
                    metrics.total_latency_ms = 50
                    metrics.latency_history.append(50)
                logger.info(f"强制更新数据源 {source.value} 为健康状态并重置错误指标")
            else:
                logger.info(f"强制更新数据源 {source.value} 健康状态为: {is_healthy}")

    def export_metrics(self) -> Dict[str, Any]:
        """
        导出所有监控指标

        Returns:
            完整的监控数据
        """
        return {
            "timestamp": datetime.now().isoformat(),
            "health_status": self.get_all_health_status(),
            "statistics": self.get_access_statistics(),
            "recent_access": [
                {
                    "request_id": r.request_id,
                    "timestamp": r.timestamp,
                    "source": r.source.value,
                    "access_type": r.access_type.value,
                    "symbol": r.symbol,
                    "module": r.module,
                    "success": r.success,
                    "latency_ms": r.latency_ms,
                    "error": r.error_message,
                }
                for r in list(self.access_history)[-100:]  # 最近100条
            ],
        }

# 全局监控实例
data_source_monitor = DataSourceMonitor()

def get_monitor() -> DataSourceMonitor:
    """获取全局监控实例"""
    return data_source_monitor
