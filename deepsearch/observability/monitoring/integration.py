"""
监控系统集成模块

为所有数据源提供统一的监控集成接口
自动注入监控能力到数据提供者
"""
import functools
import time
import traceback
from typing import Any, Callable, Dict, Optional
import asyncio

from loguru import logger

from deepsearch.infrastructure.providers.interfaces.base import DataSourceType
from deepsearch.observability.logging.monitoring_logger import (
    MonitoringRecord,
    MonitoringContext,
    OperationType,
    ErrorType,
    ErrorInfo,
    PerformanceMetrics,
    DataMetrics,
    get_monitor_logger
)
from deepsearch.monitoring.collectors.metrics_collector import get_metrics_collector
from deepsearch.monitoring.analyzers.error_analyzer import get_error_analyzer
from deepsearch.observability.monitoring.data_source_monitor import (
    get_monitor,
    DataAccessType
)
from deepsearch.observability.decorators.enhanced_decorators import (
    monitor_http_request,
    monitor_database_query,
    monitor_cache_operation,
    monitor_tcp_connection,
    monitor_batch_process,
    monitor_circuit_breaker
)


class MonitoringIntegration:
    """监控集成类"""
    
    def __init__(self, source_type: DataSourceType):
        """
        初始化监控集成
        
        Args:
            source_type: 数据源类型
        """
        self.source_type = source_type
        self.monitor = get_monitor()
        self.monitor_logger = get_monitor_logger()
        self.metrics_collector = get_metrics_collector()
        self.error_analyzer = get_error_analyzer()
        
        # 统计信息
        self.stats = {
            "total_requests": 0,
            "success_count": 0,
            "error_count": 0,
            "total_latency_ms": 0
        }
        
        logger.info(f"监控集成初始化完成: {source_type.value}")
    
    def wrap_http_method(self, method: Callable) -> Callable:
        """
        包装HTTP方法，自动添加监控
        
        Args:
            method: 要包装的HTTP方法
            
        Returns:
            包装后的方法
        """
        @functools.wraps(method)
        async def async_wrapper(*args, **kwargs):
            # 创建监控记录
            record = MonitoringRecord(
                source_type=self.source_type,
                operation=OperationType.HTTP_REQUEST
            )
            
            # 设置上下文
            record.context.module = method.__module__
            record.context.function = method.__name__
            
            # 提取URL（尝试多种方式）
            url = None
            if 'url' in kwargs:
                url = kwargs['url']
            elif len(args) > 0 and isinstance(args[0], str):
                url = args[0]
            
            if url:
                record.metadata['url'] = url
            
            # 开始计时
            start_time = time.time()
            record.performance.start_time = start_time
            
            try:
                # 执行实际方法
                result = await method(*args, **kwargs)
                
                # 记录成功
                record.success = True
                self.stats["success_count"] += 1
                
                # 估算响应大小
                if result:
                    if hasattr(result, '__sizeof__'):
                        record.data.response_size = result.__sizeof__()
                    elif isinstance(result, (dict, list)):
                        import json
                        record.data.response_size = len(json.dumps(result))
                
                return result
                
            except Exception as e:
                # 记录失败
                record.success = False
                self.stats["error_count"] += 1
                
                # 错误信息
                record.error = ErrorInfo(
                    error_type=self._classify_error(e),
                    error_message=str(e),
                    stack_trace=traceback.format_exc()
                )
                
                # 错误分析
                self.error_analyzer.analyze_error(
                    record.error,
                    self.source_type.value,
                    record.metadata
                )
                
                # 重新抛出异常
                raise
                
            finally:
                # 计算延迟
                end_time = time.time()
                record.performance.end_time = end_time
                record.performance.calculate_latency()
                
                # 更新统计
                self.stats["total_requests"] += 1
                if record.performance.latency_ms:
                    self.stats["total_latency_ms"] += record.performance.latency_ms
                
                # 记录到各个监控系统
                self._record_to_all_monitors(record)
        
        @functools.wraps(method)
        def sync_wrapper(*args, **kwargs):
            # 同步版本的实现
            record = MonitoringRecord(
                source_type=self.source_type,
                operation=OperationType.HTTP_REQUEST
            )
            
            start_time = time.time()
            try:
                result = method(*args, **kwargs)
                record.success = True
                self.stats["success_count"] += 1
                return result
                
            except Exception as e:
                record.success = False
                self.stats["error_count"] += 1
                record.error = ErrorInfo(
                    error_type=self._classify_error(e),
                    error_message=str(e),
                    stack_trace=traceback.format_exc()
                )
                raise
                
            finally:
                record.performance.end_time = time.time()
                record.performance.calculate_latency()
                self.stats["total_requests"] += 1
                self._record_to_all_monitors(record)
        
        # 根据方法类型返回对应的包装器
        if asyncio.iscoroutinefunction(method):
            return async_wrapper
        else:
            return sync_wrapper
    
    def wrap_tcp_method(self, method: Callable) -> Callable:
        """
        包装TCP连接方法，自动添加监控
        
        特别用于QMT等TCP Socket连接
        """
        @functools.wraps(method)
        async def async_wrapper(*args, **kwargs):
            record = MonitoringRecord(
                source_type=self.source_type,
                operation=OperationType.TCP_CONNECT
            )
            
            record.context.module = method.__module__
            record.context.function = method.__name__
            
            start_time = time.time()
            record.performance.start_time = start_time
            
            try:
                result = await method(*args, **kwargs)
                record.success = True
                return result
                
            except Exception as e:
                record.success = False
                record.error = ErrorInfo(
                    error_type=ErrorType.CONNECTION_ERROR,
                    error_message=str(e),
                    stack_trace=traceback.format_exc()
                )
                raise
                
            finally:
                record.performance.end_time = time.time()
                record.performance.calculate_latency()
                self._record_to_all_monitors(record)
        
        if asyncio.iscoroutinefunction(method):
            return async_wrapper
        else:
            # 同步版本
            @functools.wraps(method)
            def sync_wrapper(*args, **kwargs):
                record = MonitoringRecord(
                    source_type=self.source_type,
                    operation=OperationType.TCP_CONNECT
                )
                
                start_time = time.time()
                try:
                    result = method(*args, **kwargs)
                    record.success = True
                    return result
                except Exception as e:
                    record.success = False
                    record.error = ErrorInfo(
                        error_type=ErrorType.CONNECTION_ERROR,
                        error_message=str(e)
                    )
                    raise
                finally:
                    record.performance.end_time = time.time()
                    record.performance.calculate_latency()
                    self._record_to_all_monitors(record)
            
            return sync_wrapper
    
    def _record_to_all_monitors(self, record: MonitoringRecord):
        """记录到所有监控系统"""
        # 1. 结构化日志
        self.monitor_logger.log(record)
        
        # 2. 指标收集器
        self.metrics_collector.collect(record)
        
        # 3. 数据源监控器
        self.monitor.record_access(
            source=self.source_type,
            access_type=self._map_to_access_type(record.operation),
            success=record.success,
            latency_ms=record.performance.latency_ms,
            module=record.context.module,
            error_message=record.error.error_message if record.error else None,
            data_size=record.data.response_size,
            metadata=record.metadata
        )
    
    def _map_to_access_type(self, operation: OperationType) -> DataAccessType:
        """映射操作类型到访问类型"""
        mapping = {
            OperationType.HTTP_REQUEST: DataAccessType.REALTIME_QUOTE,
            OperationType.DATABASE_QUERY: DataAccessType.HISTORICAL_KLINE,
            OperationType.CACHE_ACCESS: DataAccessType.REALTIME_QUOTE,
            OperationType.TCP_CONNECT: DataAccessType.REALTIME_QUOTE,
            OperationType.BATCH_PROCESS: DataAccessType.HISTORICAL_KLINE,
        }
        return mapping.get(operation, DataAccessType.REALTIME_QUOTE)
    
    def _classify_error(self, error: Exception) -> ErrorType:
        """分类错误类型"""
        error_str = str(error).lower()
        
        if "timeout" in error_str:
            return ErrorType.TIMEOUT_ERROR
        elif "401" in error_str or "unauthorized" in error_str:
            return ErrorType.AUTH_ERROR
        elif "403" in error_str or "forbidden" in error_str:
            return ErrorType.AUTH_ERROR
        elif "429" in error_str or "rate limit" in error_str:
            return ErrorType.RATE_LIMIT_ERROR
        elif "connection" in error_str:
            return ErrorType.CONNECTION_ERROR
        elif "network" in error_str:
            return ErrorType.NETWORK_ERROR
        elif "parse" in error_str or "json" in error_str:
            return ErrorType.PARSE_ERROR
        elif "validation" in error_str or "invalid" in error_str:
            return ErrorType.VALIDATION_ERROR
        else:
            return ErrorType.UNKNOWN_ERROR
    
    def record_custom_metric(
        self,
        operation: str,
        latency_ms: float,
        success: bool,
        **metadata
    ):
        """
        记录自定义指标
        
        Args:
            operation: 操作名称
            latency_ms: 延迟（毫秒）
            success: 是否成功
            **metadata: 额外元数据
        """
        record = MonitoringRecord(
            source_type=self.source_type,
            operation=OperationType.HTTP_REQUEST,  # 默认类型
            success=success
        )
        
        record.performance.latency_ms = latency_ms
        record.metadata = metadata
        
        self._record_to_all_monitors(record)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        avg_latency = 0
        if self.stats["total_requests"] > 0:
            avg_latency = self.stats["total_latency_ms"] / self.stats["total_requests"]
        
        success_rate = 0
        if self.stats["total_requests"] > 0:
            success_rate = self.stats["success_count"] / self.stats["total_requests"]
        
        return {
            "source_type": self.source_type.value,
            "total_requests": self.stats["total_requests"],
            "success_count": self.stats["success_count"],
            "error_count": self.stats["error_count"],
            "success_rate": success_rate,
            "avg_latency_ms": avg_latency
        }


def inject_monitoring(provider_class, source_type: DataSourceType):
    """
    注入监控能力到数据提供者类
    
    自动为所有网络请求方法添加监控
    
    Args:
        provider_class: 数据提供者类
        source_type: 数据源类型
        
    Returns:
        增强后的类
    """
    # 创建监控集成
    monitoring = MonitoringIntegration(source_type)
    
    # 需要监控的方法名模式
    http_method_patterns = [
        'fetch', 'get', 'post', 'request', 'query', 'download'
    ]
    
    tcp_method_patterns = [
        'connect', 'socket', 'tcp'
    ]
    
    # 遍历类的所有方法
    for attr_name in dir(provider_class):
        if attr_name.startswith('_'):
            continue  # 跳过私有方法
        
        attr = getattr(provider_class, attr_name)
        if not callable(attr):
            continue
        
        # 检查是否需要包装
        lower_name = attr_name.lower()
        
        # HTTP方法
        if any(pattern in lower_name for pattern in http_method_patterns):
            wrapped = monitoring.wrap_http_method(attr)
            setattr(provider_class, attr_name, wrapped)
            logger.debug(f"已为 {provider_class.__name__}.{attr_name} 注入HTTP监控")
        
        # TCP方法
        elif any(pattern in lower_name for pattern in tcp_method_patterns):
            wrapped = monitoring.wrap_tcp_method(attr)
            setattr(provider_class, attr_name, wrapped)
            logger.debug(f"已为 {provider_class.__name__}.{attr_name} 注入TCP监控")
    
    # 添加监控实例到类
    provider_class._monitoring = monitoring
    
    return provider_class


# 导出监控装饰器，方便使用
__all__ = [
    'MonitoringIntegration',
    'inject_monitoring',
    'monitor_http_request',
    'monitor_database_query',
    'monitor_cache_operation',
    'monitor_tcp_connection',
    'monitor_batch_process',
    'monitor_circuit_breaker'
]