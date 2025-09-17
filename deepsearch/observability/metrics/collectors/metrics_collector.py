"""
性能指标收集器

实时收集、聚合和分析数据源性能指标
"""
import asyncio
import time
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Deque, Tuple
from threading import Lock
import json
from pathlib import Path
import numpy as np

from loguru import logger

from deepsearch.infrastructure.providers.interfaces.base import DataSourceType
from deepsearch.observability.logging.monitoring_logger import (
    MonitoringRecord,
    OperationType,
    get_monitor_logger
)


@dataclass
class PerformanceSnapshot:
    """性能快照"""
    timestamp: float
    source_type: Optional[DataSourceType]
    operation: OperationType
    latency_ms: float
    success: bool
    request_size: int = 0
    response_size: int = 0
    

@dataclass
class AggregatedMetrics:
    """聚合指标"""
    time_window: str  # "1min", "5min", "1hour", "24hour"
    start_time: float
    end_time: float
    total_requests: int = 0
    success_count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0
    min_latency_ms: float = float('inf')
    max_latency_ms: float = 0
    p50_latency_ms: float = 0
    p90_latency_ms: float = 0
    p95_latency_ms: float = 0
    p99_latency_ms: float = 0
    avg_request_size: float = 0
    avg_response_size: float = 0
    throughput_rps: float = 0  # requests per second
    error_rate: float = 0
    
    def calculate_percentiles(self, latencies: List[float]):
        """计算延迟百分位数"""
        if not latencies:
            return
            
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)
        
        self.p50_latency_ms = sorted_latencies[int(n * 0.50)]
        self.p90_latency_ms = sorted_latencies[int(n * 0.90)]
        self.p95_latency_ms = sorted_latencies[int(n * 0.95)]
        self.p99_latency_ms = sorted_latencies[min(int(n * 0.99), n-1)]


class MetricsCollector:
    """性能指标收集器"""
    
    def __init__(self):
        # 原始数据存储（保留最近1小时的数据）
        self.raw_metrics: Deque[PerformanceSnapshot] = deque(maxlen=100000)
        
        # 按数据源和操作类型分组的指标
        self.metrics_by_source: Dict[str, Deque[PerformanceSnapshot]] = defaultdict(
            lambda: deque(maxlen=10000)
        )
        self.metrics_by_operation: Dict[str, Deque[PerformanceSnapshot]] = defaultdict(
            lambda: deque(maxlen=10000)
        )
        
        # 聚合指标缓存
        self.aggregated_cache: Dict[str, AggregatedMetrics] = {}
        
        # 实时统计（最近1分钟）
        self.realtime_window = deque(maxlen=1000)
        
        # 性能趋势分析
        self.trend_data: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        
        # 异常检测
        self.anomaly_threshold = {
            "latency_spike": 3.0,  # 延迟超过平均值的倍数
            "error_rate_threshold": 0.1,  # 错误率阈值
            "throughput_drop": 0.5  # 吞吐量下降比例
        }
        
        # 线程锁
        self.lock = Lock()
        
        # 导出路径
        self.export_dir = Path("data/monitoring/exports")
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        # 启动后台任务
        self._start_background_tasks()
        
        logger.info("性能指标收集器初始化完成")
    
    def _start_background_tasks(self):
        """启动后台任务"""
        async def aggregate_loop():
            """定期聚合指标"""
            while True:
                await asyncio.sleep(60)  # 每分钟聚合一次
                self.aggregate_metrics()
                self.export_metrics()
        
        async def cleanup_loop():
            """定期清理旧数据"""
            while True:
                await asyncio.sleep(3600)  # 每小时清理一次
                self.cleanup_old_data()
        
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(aggregate_loop())
            loop.create_task(cleanup_loop())
        except RuntimeError:
            # 如果没有事件循环，跳过异步任务
            pass
    
    def collect(self, record: MonitoringRecord):
        """收集监控记录"""
        if not record.performance.latency_ms:
            return
        
        snapshot = PerformanceSnapshot(
            timestamp=record.timestamp,
            source_type=record.source_type,
            operation=record.operation,
            latency_ms=record.performance.latency_ms,
            success=record.success,
            request_size=record.data.request_size,
            response_size=record.data.response_size
        )
        
        with self.lock:
            # 添加到原始数据
            self.raw_metrics.append(snapshot)
            self.realtime_window.append(snapshot)
            
            # 按分类存储
            if snapshot.source_type:
                self.metrics_by_source[snapshot.source_type.value].append(snapshot)
            self.metrics_by_operation[snapshot.operation.value].append(snapshot)
            
            # 更新趋势数据
            self._update_trend(snapshot)
            
            # 检测异常
            self._detect_anomalies(snapshot)
    
    def _update_trend(self, snapshot: PerformanceSnapshot):
        """更新趋势数据"""
        key = f"{snapshot.source_type.value if snapshot.source_type else 'unknown'}_{snapshot.operation.value}"
        self.trend_data[key].append((snapshot.timestamp, snapshot.latency_ms))
        
        # 只保留最近24小时的趋势数据
        cutoff_time = time.time() - 86400
        self.trend_data[key] = [
            (ts, lat) for ts, lat in self.trend_data[key]
            if ts > cutoff_time
        ]
    
    def _detect_anomalies(self, snapshot: PerformanceSnapshot):
        """检测性能异常"""
        # 获取历史平均值
        key = f"{snapshot.source_type.value if snapshot.source_type else 'unknown'}_{snapshot.operation.value}"
        historical = self.trend_data.get(key, [])
        
        if len(historical) < 10:
            return  # 数据不足，无法检测
        
        # 计算历史平均延迟
        latencies = [lat for _, lat in historical[-100:]]  # 最近100个样本
        avg_latency = np.mean(latencies)
        std_latency = np.std(latencies)
        
        # 检测延迟异常
        if snapshot.latency_ms > avg_latency + self.anomaly_threshold["latency_spike"] * std_latency:
            logger.warning(
                f"检测到延迟异常: {key} - "
                f"当前:{snapshot.latency_ms:.1f}ms, "
                f"平均:{avg_latency:.1f}ms"
            )
            self._record_anomaly("latency_spike", snapshot, {
                "current_latency": snapshot.latency_ms,
                "avg_latency": avg_latency,
                "std_latency": std_latency
            })
    
    def _record_anomaly(self, anomaly_type: str, snapshot: PerformanceSnapshot, details: Dict):
        """记录异常"""
        anomaly_file = self.export_dir / "anomalies.jsonl"
        
        anomaly_record = {
            "timestamp": snapshot.timestamp,
            "datetime": datetime.fromtimestamp(snapshot.timestamp).isoformat(),
            "anomaly_type": anomaly_type,
            "source_type": snapshot.source_type.value if snapshot.source_type else None,
            "operation": snapshot.operation.value,
            "details": details
        }
        
        try:
            with open(anomaly_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(anomaly_record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"记录异常失败: {e}")
    
    def aggregate_metrics(self):
        """聚合性能指标"""
        current_time = time.time()
        
        # 定义时间窗口
        windows = [
            ("1min", 60),
            ("5min", 300),
            ("1hour", 3600),
            ("24hour", 86400)
        ]
        
        with self.lock:
            for window_name, window_seconds in windows:
                cutoff_time = current_time - window_seconds
                
                # 过滤时间窗口内的数据
                window_data = [
                    m for m in self.raw_metrics
                    if m.timestamp > cutoff_time
                ]
                
                if not window_data:
                    continue
                
                # 创建聚合指标
                aggregated = self._create_aggregated_metrics(
                    window_name,
                    cutoff_time,
                    current_time,
                    window_data
                )
                
                # 缓存聚合结果
                self.aggregated_cache[window_name] = aggregated
    
    def _create_aggregated_metrics(
        self,
        window_name: str,
        start_time: float,
        end_time: float,
        data: List[PerformanceSnapshot]
    ) -> AggregatedMetrics:
        """创建聚合指标"""
        metrics = AggregatedMetrics(
            time_window=window_name,
            start_time=start_time,
            end_time=end_time
        )
        
        if not data:
            return metrics
        
        # 基础统计
        metrics.total_requests = len(data)
        metrics.success_count = sum(1 for d in data if d.success)
        metrics.error_count = metrics.total_requests - metrics.success_count
        
        # 延迟统计
        latencies = [d.latency_ms for d in data]
        metrics.total_latency_ms = sum(latencies)
        metrics.min_latency_ms = min(latencies)
        metrics.max_latency_ms = max(latencies)
        metrics.calculate_percentiles(latencies)
        
        # 数据大小统计
        request_sizes = [d.request_size for d in data if d.request_size > 0]
        response_sizes = [d.response_size for d in data if d.response_size > 0]
        
        if request_sizes:
            metrics.avg_request_size = np.mean(request_sizes)
        if response_sizes:
            metrics.avg_response_size = np.mean(response_sizes)
        
        # 计算速率
        duration = end_time - start_time
        if duration > 0:
            metrics.throughput_rps = metrics.total_requests / duration
        
        if metrics.total_requests > 0:
            metrics.error_rate = metrics.error_count / metrics.total_requests
        
        return metrics
    
    def get_realtime_metrics(self) -> Dict:
        """获取实时指标（最近1分钟）"""
        with self.lock:
            if not self.realtime_window:
                return {}
            
            current_time = time.time()
            cutoff_time = current_time - 60
            
            recent_data = [
                m for m in self.realtime_window
                if m.timestamp > cutoff_time
            ]
            
            if not recent_data:
                return {}
            
            # 按数据源分组统计
            by_source = defaultdict(lambda: {"success": 0, "error": 0, "latencies": []})
            
            for snapshot in recent_data:
                key = snapshot.source_type.value if snapshot.source_type else "unknown"
                if snapshot.success:
                    by_source[key]["success"] += 1
                else:
                    by_source[key]["error"] += 1
                by_source[key]["latencies"].append(snapshot.latency_ms)
            
            # 计算统计指标
            result = {}
            for source, data in by_source.items():
                latencies = data["latencies"]
                result[source] = {
                    "total": data["success"] + data["error"],
                    "success": data["success"],
                    "error": data["error"],
                    "error_rate": data["error"] / (data["success"] + data["error"]),
                    "avg_latency": np.mean(latencies),
                    "p95_latency": np.percentile(latencies, 95) if latencies else 0
                }
            
            return result
    
    def get_performance_trend(
        self,
        source_type: Optional[str] = None,
        operation: Optional[str] = None,
        hours: int = 24
    ) -> List[Dict]:
        """获取性能趋势"""
        cutoff_time = time.time() - hours * 3600
        
        # 构建键
        if source_type and operation:
            keys = [f"{source_type}_{operation}"]
        elif source_type:
            keys = [k for k in self.trend_data.keys() if k.startswith(source_type)]
        elif operation:
            keys = [k for k in self.trend_data.keys() if k.endswith(operation)]
        else:
            keys = list(self.trend_data.keys())
        
        result = []
        for key in keys:
            data_points = [
                {"timestamp": ts, "latency": lat}
                for ts, lat in self.trend_data.get(key, [])
                if ts > cutoff_time
            ]
            
            if data_points:
                result.append({
                    "key": key,
                    "data": data_points
                })
        
        return result
    
    def export_metrics(self):
        """导出性能指标"""
        try:
            # 导出聚合指标
            aggregated_file = self.export_dir / "performance_report.json"
            with open(aggregated_file, "w", encoding="utf-8") as f:
                export_data = {
                    "timestamp": time.time(),
                    "datetime": datetime.now().isoformat(),
                    "aggregated": {
                        k: {
                            "time_window": v.time_window,
                            "total_requests": v.total_requests,
                            "success_count": v.success_count,
                            "error_rate": v.error_rate,
                            "p50_latency": v.p50_latency_ms,
                            "p90_latency": v.p90_latency_ms,
                            "p95_latency": v.p95_latency_ms,
                            "p99_latency": v.p99_latency_ms,
                            "throughput_rps": v.throughput_rps
                        }
                        for k, v in self.aggregated_cache.items()
                    },
                    "realtime": self.get_realtime_metrics()
                }
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
            
            logger.debug("性能指标导出成功")
            
        except Exception as e:
            logger.error(f"导出性能指标失败: {e}")
    
    def cleanup_old_data(self):
        """清理旧数据"""
        cutoff_time = time.time() - 86400  # 保留24小时
        
        with self.lock:
            # 清理趋势数据
            for key in list(self.trend_data.keys()):
                self.trend_data[key] = [
                    (ts, lat) for ts, lat in self.trend_data[key]
                    if ts > cutoff_time
                ]
                
                if not self.trend_data[key]:
                    del self.trend_data[key]
        
        logger.info("旧数据清理完成")


# 全局实例
metrics_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """获取指标收集器实例"""
    return metrics_collector