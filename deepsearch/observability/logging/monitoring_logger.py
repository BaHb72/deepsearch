"""
结构化监控日志系统

提供统一的结构化日志记录，专门用于数据源监控
所有日志以JSON格式输出，便于data-source-monitor分析
"""
import json
import time
import traceback
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, List
from threading import Lock
import asyncio

from loguru import logger

from deepsearch.data_providers.interfaces.base import DataSourceType


class OperationType(Enum):
    """操作类型枚举"""
    HTTP_REQUEST = "http_request"
    DATABASE_QUERY = "database_query"
    CACHE_ACCESS = "cache_access"
    MESSAGE_PUBLISH = "message_publish"
    TCP_CONNECT = "tcp_connect"
    WEBSOCKET_MESSAGE = "websocket_message"
    BATCH_PROCESS = "batch_process"
    FAILOVER = "failover"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"


class ErrorType(Enum):
    """错误类型枚举"""
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    AUTH_ERROR = "auth_error"
    DATA_ERROR = "data_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    CONNECTION_ERROR = "connection_error"
    PARSE_ERROR = "parse_error"
    VALIDATION_ERROR = "validation_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class MonitoringContext:
    """监控上下文"""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None


@dataclass
class PerformanceMetrics:
    """性能指标"""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    latency_ms: Optional[float] = None
    queue_time_ms: Optional[float] = None
    process_time_ms: Optional[float] = None
    dns_time_ms: Optional[float] = None
    connect_time_ms: Optional[float] = None
    tls_time_ms: Optional[float] = None
    transfer_time_ms: Optional[float] = None
    
    def calculate_latency(self):
        """计算总延迟"""
        if self.end_time and self.start_time:
            self.latency_ms = (self.end_time - self.start_time) * 1000


@dataclass
class DataMetrics:
    """数据指标"""
    request_size: int = 0
    response_size: int = 0
    row_count: Optional[int] = None
    cache_hit: bool = False
    cache_key: Optional[str] = None
    compression_ratio: Optional[float] = None


@dataclass
class ErrorInfo:
    """错误信息"""
    error_type: ErrorType
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    is_recoverable: bool = True


@dataclass
class MonitoringRecord:
    """监控记录"""
    timestamp: float = field(default_factory=time.time)
    source_type: Optional[DataSourceType] = None
    operation: OperationType = OperationType.HTTP_REQUEST
    context: MonitoringContext = field(default_factory=MonitoringContext)
    performance: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    data: DataMetrics = field(default_factory=DataMetrics)
    error: Optional[ErrorInfo] = None
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        data = {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "source_type": self.source_type.value if self.source_type else None,
            "operation": self.operation.value,
            "context": asdict(self.context),
            "performance": asdict(self.performance),
            "data": asdict(self.data),
            "error": asdict(self.error) if self.error else None,
            "success": self.success,
            "metadata": self.metadata
        }
        return json.dumps(data, ensure_ascii=False, default=str)


class StructuredMonitorLogger:
    """结构化监控日志记录器"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # 日志输出路径
        self.log_dir = Path("data/logs/datasources")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前日志文件
        self.current_log_file = self._get_log_file_path()
        
        # 监控数据导出路径
        self.export_dir = Path("data/monitoring/exports")
        self.export_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓冲区（用于批量写入）
        self.buffer: List[MonitoringRecord] = []
        self.buffer_size = 100
        self.buffer_lock = Lock()
        
        # 统计信息
        self.stats = {
            "total_records": 0,
            "success_count": 0,
            "error_count": 0,
            "by_source": {},
            "by_operation": {},
            "by_error_type": {}
        }
        
        # 启动异步写入任务
        self._flush_task = None
        self._start_flush_task()
        
        self._initialized = True
        logger.info("结构化监控日志系统初始化完成")
    
    def _get_log_file_path(self) -> Path:
        """获取当前日志文件路径"""
        date_str = datetime.now().strftime("%Y%m%d")
        return self.log_dir / f"monitor_{date_str}.jsonl"
    
    def _start_flush_task(self):
        """启动异步刷新任务"""
        async def flush_loop():
            while True:
                await asyncio.sleep(5)  # 每5秒刷新一次
                self.flush()
        
        try:
            loop = asyncio.get_event_loop()
            self._flush_task = loop.create_task(flush_loop())
        except RuntimeError:
            # 如果没有事件循环，使用同步模式
            pass
    
    def log(self, record: MonitoringRecord):
        """记录监控日志"""
        with self.buffer_lock:
            self.buffer.append(record)
            
            # 更新统计信息
            self._update_stats(record)
            
            # 如果缓冲区满了，立即刷新
            if len(self.buffer) >= self.buffer_size:
                self.flush()
    
    def _update_stats(self, record: MonitoringRecord):
        """更新统计信息"""
        self.stats["total_records"] += 1
        
        if record.success:
            self.stats["success_count"] += 1
        else:
            self.stats["error_count"] += 1
        
        # 按数据源统计
        if record.source_type:
            source_key = record.source_type.value
            if source_key not in self.stats["by_source"]:
                self.stats["by_source"][source_key] = {"success": 0, "error": 0}
            
            if record.success:
                self.stats["by_source"][source_key]["success"] += 1
            else:
                self.stats["by_source"][source_key]["error"] += 1
        
        # 按操作类型统计
        op_key = record.operation.value
        if op_key not in self.stats["by_operation"]:
            self.stats["by_operation"][op_key] = 0
        self.stats["by_operation"][op_key] += 1
        
        # 按错误类型统计
        if record.error:
            error_key = record.error.error_type.value
            if error_key not in self.stats["by_error_type"]:
                self.stats["by_error_type"][error_key] = 0
            self.stats["by_error_type"][error_key] += 1
    
    def flush(self):
        """刷新缓冲区到文件"""
        with self.buffer_lock:
            if not self.buffer:
                return
            
            # 检查是否需要切换日志文件
            current_file = self._get_log_file_path()
            if current_file != self.current_log_file:
                self.current_log_file = current_file
            
            # 写入日志文件
            try:
                with open(self.current_log_file, "a", encoding="utf-8") as f:
                    for record in self.buffer:
                        f.write(record.to_json() + "\n")
                
                # 清空缓冲区
                self.buffer.clear()
                
            except Exception as e:
                logger.error(f"写入监控日志失败: {e}")
    
    def export_stats(self):
        """导出统计信息"""
        stats_file = self.export_dir / "realtime_metrics.json"
        
        export_data = {
            "timestamp": time.time(),
            "datetime": datetime.now().isoformat(),
            "stats": self.stats,
            "recent_errors": self._get_recent_errors()
        }
        
        try:
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.error(f"导出统计信息失败: {e}")
    
    def _get_recent_errors(self, limit: int = 100) -> List[Dict]:
        """获取最近的错误记录"""
        errors = []
        
        # 从当前日志文件读取最近的错误
        if self.current_log_file.exists():
            try:
                with open(self.current_log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            if not data.get("success") and data.get("error"):
                                errors.append(data)
                                if len(errors) >= limit:
                                    break
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.error(f"读取错误记录失败: {e}")
        
        return errors
    
    def log_http_request(
        self,
        source_type: DataSourceType,
        url: str,
        method: str = "GET",
        status_code: Optional[int] = None,
        response_time: Optional[float] = None,
        error: Optional[Exception] = None,
        **kwargs
    ) -> MonitoringRecord:
        """记录HTTP请求"""
        record = MonitoringRecord(
            source_type=source_type,
            operation=OperationType.HTTP_REQUEST,
            success=error is None and status_code and 200 <= status_code < 400
        )
        
        # 设置元数据
        record.metadata = {
            "url": url,
            "method": method,
            "status_code": status_code,
            **kwargs
        }
        
        # 设置性能指标
        if response_time:
            record.performance.latency_ms = response_time * 1000
        
        # 设置错误信息
        if error:
            record.error = ErrorInfo(
                error_type=self._classify_error(error),
                error_message=str(error),
                stack_trace=traceback.format_exc()
            )
        
        self.log(record)
        return record
    
    def log_database_query(
        self,
        query: str,
        execution_time: float,
        row_count: Optional[int] = None,
        error: Optional[Exception] = None,
        **kwargs
    ) -> MonitoringRecord:
        """记录数据库查询"""
        record = MonitoringRecord(
            operation=OperationType.DATABASE_QUERY,
            success=error is None
        )
        
        record.metadata = {
            "query": query[:500],  # 限制查询长度
            **kwargs
        }
        
        record.performance.latency_ms = execution_time * 1000
        
        if row_count is not None:
            record.data.row_count = row_count
        
        if error:
            record.error = ErrorInfo(
                error_type=ErrorType.DATA_ERROR,
                error_message=str(error),
                stack_trace=traceback.format_exc()
            )
        
        self.log(record)
        return record
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """分类错误类型"""
        error_str = str(error).lower()
        
        if "timeout" in error_str:
            return ErrorType.TIMEOUT_ERROR
        elif "auth" in error_str or "permission" in error_str:
            return ErrorType.AUTH_ERROR
        elif "connection" in error_str or "connect" in error_str:
            return ErrorType.CONNECTION_ERROR
        elif "rate" in error_str and "limit" in error_str:
            return ErrorType.RATE_LIMIT_ERROR
        elif "parse" in error_str or "decode" in error_str:
            return ErrorType.PARSE_ERROR
        elif "network" in error_str:
            return ErrorType.NETWORK_ERROR
        elif "validation" in error_str or "invalid" in error_str:
            return ErrorType.VALIDATION_ERROR
        else:
            return ErrorType.UNKNOWN_ERROR


# 全局实例
monitor_logger = StructuredMonitorLogger()


def get_monitor_logger() -> StructuredMonitorLogger:
    """获取监控日志记录器实例"""
    return monitor_logger