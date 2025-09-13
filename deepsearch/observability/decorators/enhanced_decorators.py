"""
增强监控装饰器

提供全面的监控装饰器，自动收集和分析各种通信层的性能数据
"""
import asyncio
import functools
import time
import traceback
from typing import Any, Callable, Dict, Optional, Union
import inspect
import json

from loguru import logger

from deepsearch.data_providers.interfaces.base import DataSourceType
from deepsearch.observability.logging.monitoring_logger import (
    MonitoringContext,
    MonitoringRecord,
    OperationType,
    ErrorType,
    ErrorInfo,
    PerformanceMetrics,
    DataMetrics,
    get_monitor_logger
)
from deepsearch.monitoring.collectors.metrics_collector import get_metrics_collector
from deepsearch.monitoring.analyzers.error_analyzer import get_error_analyzer
from deepsearch.observability.monitoring.data_source_monitor import get_monitor, DataAccessType


def monitor_http_request(
    source_type: Optional[DataSourceType] = None,
    extract_url: Optional[Callable] = None
):
    """
    HTTP请求监控装饰器
    
    自动监控HTTP请求的完整生命周期，包括：
    - DNS解析时间
    - 连接建立时间
    - TLS握手时间
    - 数据传输时间
    - 总延迟
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 创建监控记录
            record = MonitoringRecord(
                source_type=source_type,
                operation=OperationType.HTTP_REQUEST
            )
            
            # 提取上下文信息
            record.context.module = func.__module__
            record.context.function = func.__name__
            
            # 提取URL
            url = None
            if extract_url:
                try:
                    url = extract_url(*args, **kwargs)
                except:
                    pass
            elif 'url' in kwargs:
                url = kwargs['url']
            elif len(args) > 0 and isinstance(args[0], str):
                url = args[0]
            
            if url:
                record.metadata['url'] = url
            
            # 记录请求大小
            if 'data' in kwargs:
                data = kwargs['data']
                if isinstance(data, (str, bytes)):
                    record.data.request_size = len(data)
                elif isinstance(data, dict):
                    record.data.request_size = len(json.dumps(data))
            
            # 开始计时
            start_time = time.time()
            record.performance.start_time = start_time
            
            try:
                # 执行实际请求
                result = await func(*args, **kwargs)
                
                # 记录成功
                record.success = True
                
                # 记录响应大小
                if result:
                    if isinstance(result, (str, bytes)):
                        record.data.response_size = len(result)
                    elif isinstance(result, dict):
                        record.data.response_size = len(json.dumps(result))
                    elif hasattr(result, '__sizeof__'):
                        record.data.response_size = result.__sizeof__()
                
                # 提取响应元数据
                if isinstance(result, dict):
                    if 'status_code' in result:
                        record.metadata['status_code'] = result['status_code']
                    if 'headers' in result:
                        record.metadata['headers'] = result['headers']
                
                return result
                
            except Exception as e:
                # 记录错误
                record.success = False
                record.error = ErrorInfo(
                    error_type=_classify_http_error(e),
                    error_message=str(e),
                    stack_trace=traceback.format_exc()
                )
                
                # 错误分析
                error_analyzer = get_error_analyzer()
                error_analyzer.analyze_error(
                    record.error,
                    source_type.value if source_type else "unknown",
                    record.metadata
                )
                
                raise
                
            finally:
                # 计算延迟
                end_time = time.time()
                record.performance.end_time = end_time
                record.performance.calculate_latency()
                
                # 记录到结构化日志
                monitor_logger = get_monitor_logger()
                monitor_logger.log(record)
                
                # 收集指标
                metrics_collector = get_metrics_collector()
                metrics_collector.collect(record)
                
                # 记录到数据源监控器
                if source_type:
                    monitor = get_monitor()
                    monitor.record_access(
                        source=source_type,
                        access_type=DataAccessType.REALTIME_QUOTE,
                        success=record.success,
                        latency_ms=record.performance.latency_ms,
                        module=record.context.module,
                        error_message=record.error.error_message if record.error else None,
                        data_size=record.data.response_size,
                        metadata=record.metadata
                    )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 同步版本的实现（类似异步版本）
            record = MonitoringRecord(
                source_type=source_type,
                operation=OperationType.HTTP_REQUEST
            )
            
            record.context.module = func.__module__
            record.context.function = func.__name__
            
            start_time = time.time()
            record.performance.start_time = start_time
            
            try:
                result = func(*args, **kwargs)
                record.success = True
                return result
                
            except Exception as e:
                record.success = False
                record.error = ErrorInfo(
                    error_type=_classify_http_error(e),
                    error_message=str(e),
                    stack_trace=traceback.format_exc()
                )
                raise
                
            finally:
                end_time = time.time()
                record.performance.end_time = end_time
                record.performance.calculate_latency()
                
                monitor_logger = get_monitor_logger()
                monitor_logger.log(record)
                
                metrics_collector = get_metrics_collector()
                metrics_collector.collect(record)
        
        # 根据函数类型返回对应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def monitor_database_query(table: Optional[str] = None):
    """
    数据库查询监控装饰器
    
    监控数据库查询性能，包括：
    - 查询执行时间
    - 返回行数
    - 连接池状态
    - 慢查询检测
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            record = MonitoringRecord(
                operation=OperationType.DATABASE_QUERY
            )
            
            record.context.module = func.__module__
            record.context.function = func.__name__
            
            # 提取查询信息
            query = None
            if 'query' in kwargs:
                query = kwargs['query']
            elif 'sql' in kwargs:
                query = kwargs['sql']
            elif len(args) > 0 and isinstance(args[0], str):
                query = args[0]
            
            if query:
                record.metadata['query'] = query[:500]  # 限制长度
            
            if table:
                record.metadata['table'] = table
            
            start_time = time.time()
            record.performance.start_time = start_time
            
            try:
                result = await func(*args, **kwargs)
                record.success = True
                
                # 记录返回行数
                if hasattr(result, '__len__'):
                    record.data.row_count = len(result)
                
                return result
                
            except Exception as e:
                record.success = False
                record.error = ErrorInfo(
                    error_type=ErrorType.DATA_ERROR,
                    error_message=str(e),
                    stack_trace=traceback.format_exc()
                )
                raise
                
            finally:
                end_time = time.time()
                record.performance.end_time = end_time
                record.performance.calculate_latency()
                
                # 检测慢查询（超过1秒）
                if record.performance.latency_ms > 1000:
                    logger.warning(
                        f"慢查询检测: {record.context.function} - "
                        f"{record.performance.latency_ms:.1f}ms"
                    )
                    record.metadata['slow_query'] = True
                
                monitor_logger = get_monitor_logger()
                monitor_logger.log(record)
                
                metrics_collector = get_metrics_collector()
                metrics_collector.collect(record)
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 同步版本实现
            record = MonitoringRecord(
                operation=OperationType.DATABASE_QUERY
            )
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                record.success = True
                return result
            except Exception as e:
                record.success = False
                record.error = ErrorInfo(
                    error_type=ErrorType.DATA_ERROR,
                    error_message=str(e)
                )
                raise
            finally:
                record.performance.end_time = time.time()
                record.performance.calculate_latency()
                monitor_logger = get_monitor_logger()
                monitor_logger.log(record)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def monitor_cache_operation(cache_name: str = "default"):
    """
    缓存操作监控装饰器
    
    监控缓存操作，包括：
    - 缓存命中率
    - 操作延迟
    - 缓存大小
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            record = MonitoringRecord(
                operation=OperationType.CACHE_ACCESS
            )
            
            record.context.module = func.__module__
            record.context.function = func.__name__
            record.metadata['cache_name'] = cache_name
            
            # 提取缓存键
            if 'key' in kwargs:
                record.metadata['cache_key'] = str(kwargs['key'])
            elif len(args) > 0:
                record.metadata['cache_key'] = str(args[0])
            
            start_time = time.time()
            record.performance.start_time = start_time
            
            try:
                result = func(*args, **kwargs)
                record.success = True
                
                # 判断缓存命中
                if result is not None:
                    record.data.cache_hit = True
                else:
                    record.data.cache_hit = False
                
                return result
                
            except Exception as e:
                record.success = False
                record.error = ErrorInfo(
                    error_type=ErrorType.UNKNOWN_ERROR,
                    error_message=str(e)
                )
                raise
                
            finally:
                record.performance.end_time = time.time()
                record.performance.calculate_latency()
                
                monitor_logger = get_monitor_logger()
                monitor_logger.log(record)
                
                metrics_collector = get_metrics_collector()
                metrics_collector.collect(record)
        
        return wrapper
    
    return decorator


def monitor_tcp_connection(host: Optional[str] = None, port: Optional[int] = None):
    """
    TCP连接监控装饰器
    
    监控TCP连接，特别是QMT数据源的Socket连接
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            record = MonitoringRecord(
                source_type=DataSourceType.QMT,
                operation=OperationType.TCP_CONNECT
            )
            
            record.context.module = func.__module__
            record.context.function = func.__name__
            
            if host:
                record.metadata['host'] = host
            if port:
                record.metadata['port'] = port
            
            start_time = time.time()
            record.performance.start_time = start_time
            
            try:
                result = await func(*args, **kwargs)
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
                
                monitor_logger = get_monitor_logger()
                monitor_logger.log(record)
                
                metrics_collector = get_metrics_collector()
                metrics_collector.collect(record)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            # 同步版本
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                record = MonitoringRecord(
                    source_type=DataSourceType.QMT,
                    operation=OperationType.TCP_CONNECT
                )
                
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
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
                    monitor_logger = get_monitor_logger()
                    monitor_logger.log(record)
            
            return sync_wrapper
    
    return decorator


def monitor_batch_process(batch_name: Optional[str] = None):
    """
    批量处理监控装饰器
    
    监控批量数据处理操作
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            record = MonitoringRecord(
                operation=OperationType.BATCH_PROCESS
            )
            
            record.context.module = func.__module__
            record.context.function = func.__name__
            
            if batch_name:
                record.metadata['batch_name'] = batch_name
            
            # 提取批量大小
            if 'batch_size' in kwargs:
                record.metadata['batch_size'] = kwargs['batch_size']
            elif 'items' in kwargs and hasattr(kwargs['items'], '__len__'):
                record.metadata['batch_size'] = len(kwargs['items'])
            
            start_time = time.time()
            record.performance.start_time = start_time
            
            try:
                result = await func(*args, **kwargs)
                record.success = True
                
                # 记录处理结果
                if isinstance(result, (list, tuple)):
                    record.metadata['processed_count'] = len(result)
                
                return result
                
            except Exception as e:
                record.success = False
                record.error = ErrorInfo(
                    error_type=ErrorType.UNKNOWN_ERROR,
                    error_message=str(e),
                    stack_trace=traceback.format_exc()
                )
                raise
                
            finally:
                record.performance.end_time = time.time()
                record.performance.calculate_latency()
                
                # 计算处理速率
                if 'batch_size' in record.metadata and record.performance.latency_ms > 0:
                    rate = record.metadata['batch_size'] / (record.performance.latency_ms / 1000)
                    record.metadata['processing_rate'] = f"{rate:.1f} items/sec"
                
                monitor_logger = get_monitor_logger()
                monitor_logger.log(record)
                
                metrics_collector = get_metrics_collector()
                metrics_collector.collect(record)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            # 同步版本
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                record = MonitoringRecord(
                    operation=OperationType.BATCH_PROCESS
                )
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    record.success = True
                    return result
                except Exception as e:
                    record.success = False
                    raise
                finally:
                    record.performance.end_time = time.time()
                    record.performance.calculate_latency()
                    monitor_logger = get_monitor_logger()
                    monitor_logger.log(record)
            
            return sync_wrapper
    
    return decorator


def monitor_circuit_breaker(threshold: int = 5, timeout: int = 60):
    """
    熔断器监控装饰器
    
    监控熔断器状态变化和触发情况
    """
    def decorator(func: Callable) -> Callable:
        # 熔断器状态
        state = {
            "failures": 0,
            "last_failure_time": 0,
            "is_open": False
        }
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 检查熔断器状态
            if state["is_open"]:
                if time.time() - state["last_failure_time"] < timeout:
                    raise Exception(f"熔断器开启中，请等待{timeout}秒后重试")
                else:
                    state["is_open"] = False
                    state["failures"] = 0
            
            try:
                result = await func(*args, **kwargs)
                
                # 成功则重置失败计数
                if state["failures"] > 0:
                    logger.info(f"熔断器恢复: {func.__name__}")
                state["failures"] = 0
                
                return result
                
            except Exception as e:
                state["failures"] += 1
                state["last_failure_time"] = time.time()
                
                if state["failures"] >= threshold:
                    state["is_open"] = True
                    logger.error(f"熔断器触发: {func.__name__} - 连续失败{threshold}次")
                
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            # 同步版本
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                if state["is_open"]:
                    if time.time() - state["last_failure_time"] < timeout:
                        raise Exception(f"熔断器开启中")
                    else:
                        state["is_open"] = False
                        state["failures"] = 0
                
                try:
                    result = func(*args, **kwargs)
                    state["failures"] = 0
                    return result
                except Exception as e:
                    state["failures"] += 1
                    state["last_failure_time"] = time.time()
                    if state["failures"] >= threshold:
                        state["is_open"] = True
                    raise
            
            return sync_wrapper
    
    return decorator


def _classify_http_error(error: Exception) -> ErrorType:
    """分类HTTP错误"""
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
    else:
        return ErrorType.UNKNOWN_ERROR