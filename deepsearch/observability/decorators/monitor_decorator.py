"""
数据源监控装饰器

提供便捷的监控集成方式，自动记录数据访问情况。
"""
import time
import functools
import asyncio
from typing import Any, Callable, Optional
import inspect

from loguru import logger

from deepsearch.observability.monitoring.data_source_monitor import (
    get_monitor,
    DataSourceType,
    DataAccessType
)


def monitor_access(
    source: DataSourceType,
    access_type: DataAccessType,
    extract_symbol: Optional[Callable] = None
):
    """
    数据访问监控装饰器
    
    Args:
        source: 数据源类型
        access_type: 访问类型
        extract_symbol: 从参数中提取股票代码的函数
    
    Example:
        @monitor_access(
            source=DataSourceType.AKSHARE,
            access_type=DataAccessType.REALTIME_QUOTE,
            extract_symbol=lambda args, kwargs: kwargs.get('symbol') or args[1] if len(args) > 1 else None
        )
        async def get_realtime_quote(self, symbol: str):
            # 实际的数据获取逻辑
            pass
    """
    def decorator(func):
        monitor = get_monitor()
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 提取股票代码
            symbol = None
            if extract_symbol:
                try:
                    symbol = extract_symbol(args, kwargs)
                except:
                    pass
            elif 'symbol' in kwargs:
                symbol = kwargs['symbol']
            elif len(args) > 1 and isinstance(args[1], str):
                symbol = args[1]
            
            # 获取调用模块
            frame = inspect.currentframe()
            if frame and frame.f_back:
                module = frame.f_back.f_globals.get('__name__', 'unknown')
            else:
                module = 'unknown'
            
            # 开始计时
            start_time = time.time()
            success = False
            error_message = None
            result = None
            data_size = 0
            
            try:
                # 执行实际函数
                result = await func(*args, **kwargs)
                success = True
                
                # 估算数据大小
                if result:
                    try:
                        import json
                        data_size = len(json.dumps(result, default=str))
                    except:
                        data_size = 0
                
                return result
                
            except Exception as e:
                success = False
                error_message = str(e)
                raise
                
            finally:
                # 计算延迟
                latency_ms = (time.time() - start_time) * 1000
                
                # 记录访问
                monitor.record_access(
                    source=source,
                    access_type=access_type,
                    success=success,
                    latency_ms=latency_ms,
                    symbol=symbol,
                    module=module,
                    error_message=error_message,
                    data_size=data_size,
                    metadata={
                        "function": func.__name__,
                        "has_result": result is not None
                    }
                )
                
                # 输出调试日志（成功时使用DEBUG级别，失败时使用WARNING级别）
                if success:
                    logger.debug(
                        f"[MONITOR] {source.value} -> {access_type.value} "
                        f"[{symbol}] {latency_ms:.1f}ms OK"
                    )
                else:
                    logger.warning(
                        f"[MONITOR] {source.value} -> {access_type.value} "
                        f"[{symbol}] FAILED: {error_message}"
                    )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 提取股票代码
            symbol = None
            if extract_symbol:
                try:
                    symbol = extract_symbol(args, kwargs)
                except:
                    pass
            elif 'symbol' in kwargs:
                symbol = kwargs['symbol']
            elif len(args) > 1 and isinstance(args[1], str):
                symbol = args[1]
            
            # 获取调用模块
            frame = inspect.currentframe()
            if frame and frame.f_back:
                module = frame.f_back.f_globals.get('__name__', 'unknown')
            else:
                module = 'unknown'
            
            # 开始计时
            start_time = time.time()
            success = False
            error_message = None
            result = None
            data_size = 0
            
            try:
                # 执行实际函数
                result = func(*args, **kwargs)
                success = True
                
                # 估算数据大小
                if result:
                    try:
                        import json
                        data_size = len(json.dumps(result, default=str))
                    except:
                        data_size = 0
                
                return result
                
            except Exception as e:
                success = False
                error_message = str(e)
                raise
                
            finally:
                # 计算延迟
                latency_ms = (time.time() - start_time) * 1000
                
                # 记录访问
                monitor.record_access(
                    source=source,
                    access_type=access_type,
                    success=success,
                    latency_ms=latency_ms,
                    symbol=symbol,
                    module=module,
                    error_message=error_message,
                    data_size=data_size,
                    metadata={
                        "function": func.__name__,
                        "has_result": result is not None
                    }
                )
                
                # 输出调试日志
                if success:
                    logger.debug(
                        f"[MONITOR] {source.value} -> {access_type.value} "
                        f"[{symbol}] {latency_ms:.1f}ms OK"
                    )
                else:
                    logger.warning(
                        f"[MONITOR] {source.value} -> {access_type.value} "
                        f"[{symbol}] FAILED: {error_message}"
                    )
        
        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def batch_monitor_access(
    source: DataSourceType,
    access_type: DataAccessType
):
    """
    批量数据访问监控装饰器（用于返回多条记录的API）
    
    Args:
        source: 数据源类型
        access_type: 访问类型
    """
    def decorator(func):
        monitor = get_monitor()
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 获取调用模块
            frame = inspect.currentframe()
            if frame and frame.f_back:
                module = frame.f_back.f_globals.get('__name__', 'unknown')
            else:
                module = 'unknown'
            
            # 开始计时
            start_time = time.time()
            success = False
            error_message = None
            result = None
            record_count = 0
            data_size = 0
            
            try:
                # 执行实际函数
                result = await func(*args, **kwargs)
                success = True
                
                # 统计记录数
                if isinstance(result, (list, tuple)):
                    record_count = len(result)
                elif isinstance(result, dict) and 'data' in result:
                    if isinstance(result['data'], (list, tuple)):
                        record_count = len(result['data'])
                
                # 估算数据大小
                if result:
                    try:
                        import json
                        data_size = len(json.dumps(result, default=str))
                    except:
                        data_size = 0
                
                return result
                
            except Exception as e:
                success = False
                error_message = str(e)
                raise
                
            finally:
                # 计算延迟
                latency_ms = (time.time() - start_time) * 1000
                
                # 记录访问
                monitor.record_access(
                    source=source,
                    access_type=access_type,
                    success=success,
                    latency_ms=latency_ms,
                    symbol=None,  # 批量操作没有特定股票
                    module=module,
                    error_message=error_message,
                    data_size=data_size,
                    metadata={
                        "function": func.__name__,
                        "record_count": record_count
                    }
                )
                
                # 输出调试日志
                if success:
                    logger.debug(
                        f"[MONITOR] {source.value} -> {access_type.value} "
                        f"[{record_count} records] {latency_ms:.1f}ms OK"
                    )
                else:
                    logger.warning(
                        f"[MONITOR] {source.value} -> {access_type.value} "
                        f"FAILED: {error_message}"
                    )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 同步版本的实现...
            pass
        
        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator