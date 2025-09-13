"""
监控装饰器

提供简单易用的装饰器来监控数据源访问
"""
import time
import functools
import asyncio
from typing import Callable, Any, Optional
from loguru import logger

from ..monitoring.data_source_monitor import (
    DataSourceMonitor,
    DataAccessType,
    DataSourceType,
    get_monitor
)


def monitor_data_source(
    source: DataSourceType,
    access_type: DataAccessType,
    extract_symbol: Optional[Callable] = None
):
    """
    监控数据源访问的装饰器
    
    Args:
        source: 数据源类型
        access_type: 访问类型
        extract_symbol: 从参数中提取股票代码的函数
        
    使用示例:
    ```python
    @monitor_data_source(
        source=DataSourceType.AKSHARE,
        access_type=DataAccessType.HISTORICAL_KLINE,
        extract_symbol=lambda *args, **kwargs: kwargs.get('symbol') or args[0] if args else None
    )
    async def get_stock_hist(symbol: str, period: str):
        # 实际的数据获取逻辑
        pass
    ```
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 获取监控器实例
            monitor = get_monitor()
            
            # 提取股票代码
            symbol = None
            if extract_symbol:
                try:
                    symbol = extract_symbol(*args, **kwargs)
                except Exception:
                    pass
            
            # 获取调用模块
            module = func.__module__ if hasattr(func, '__module__') else 'unknown'
            
            # 记录开始时间
            start_time = time.time()
            error_message = None
            success = True
            result = None
            data_size = 0
            
            try:
                # 执行实际函数
                result = await func(*args, **kwargs)
                
                # 估算数据大小
                if result is not None:
                    # 特殊处理DataFrame
                    if hasattr(result, 'empty'):  # DataFrame或Series
                        if not result.empty:
                            data_size = result.memory_usage(deep=True).sum() if hasattr(result, 'memory_usage') else len(str(result))
                    elif hasattr(result, '__sizeof__'):
                        data_size = result.__sizeof__()
                    elif isinstance(result, dict):
                        data_size = len(str(result))
                    elif isinstance(result, (list, tuple)):
                        data_size = len(result) * 100  # 粗略估算
                        
                return result
                
            except Exception as e:
                success = False
                error_message = str(e)
                logger.error(f"{source.value}.{func.__name__} 失败: {error_message}")
                raise
                
            finally:
                # 计算耗时
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
                        'function': func.__name__,
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys())
                    }
                )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 获取监控器实例
            monitor = get_monitor()
            
            # 提取股票代码
            symbol = None
            if extract_symbol:
                try:
                    symbol = extract_symbol(*args, **kwargs)
                except Exception:
                    pass
            
            # 获取调用模块
            module = func.__module__ if hasattr(func, '__module__') else 'unknown'
            
            # 记录开始时间
            start_time = time.time()
            error_message = None
            success = True
            result = None
            data_size = 0
            
            try:
                # 执行实际函数
                result = func(*args, **kwargs)
                
                # 估算数据大小
                if result is not None:
                    # 特殊处理DataFrame
                    if hasattr(result, 'empty'):  # DataFrame或Series
                        if not result.empty:
                            data_size = result.memory_usage(deep=True).sum() if hasattr(result, 'memory_usage') else len(str(result))
                    elif hasattr(result, '__sizeof__'):
                        data_size = result.__sizeof__()
                    elif isinstance(result, dict):
                        data_size = len(str(result))
                    elif isinstance(result, (list, tuple)):
                        data_size = len(result) * 100  # 粗略估算
                        
                return result
                
            except Exception as e:
                success = False
                error_message = str(e)
                logger.error(f"{source.value}.{func.__name__} 失败: {error_message}")
                raise
                
            finally:
                # 计算耗时
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
                        'function': func.__name__,
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys())
                    }
                )
        
        # 根据函数类型返回对应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
            
    return decorator


def monitor_cache_access(
    cache_name: str = "default"
):
    """
    监控缓存访问的装饰器
    
    Args:
        cache_name: 缓存名称
        
    使用示例:
    ```python
    @monitor_cache_access(cache_name="stock_data")
    def get_from_cache(key: str):
        # 缓存访问逻辑
        pass
    ```
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            monitor = get_monitor()
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                cache_hit = result is not None
                
                # 记录缓存访问
                monitor.record_access(
                    source=DataSourceType.DATABASE,  # 使用DATABASE表示缓存
                    access_type=DataAccessType.REALTIME_QUOTE,  # 临时使用
                    success=True,
                    latency_ms=(time.time() - start_time) * 1000,
                    module=func.__module__ if hasattr(func, '__module__') else 'unknown',
                    metadata={
                        'cache_name': cache_name,
                        'cache_hit': cache_hit,
                        'function': func.__name__
                    }
                )
                
                return result
                
            except Exception as e:
                monitor.record_access(
                    source=DataSourceType.DATABASE,
                    access_type=DataAccessType.REALTIME_QUOTE,
                    success=False,
                    latency_ms=(time.time() - start_time) * 1000,
                    error_message=str(e),
                    module=func.__module__ if hasattr(func, '__module__') else 'unknown',
                    metadata={
                        'cache_name': cache_name,
                        'function': func.__name__
                    }
                )
                raise
                
        return wrapper
    return decorator


# 便捷装饰器 - 预定义常用场景

# AkShare数据源
monitor_akshare_hist = functools.partial(
    monitor_data_source,
    source=DataSourceType.AKSHARE,
    access_type=DataAccessType.HISTORICAL_KLINE,
    extract_symbol=lambda *args, **kwargs: kwargs.get('symbol', args[0] if args else None)
)

monitor_akshare_realtime = functools.partial(
    monitor_data_source,
    source=DataSourceType.AKSHARE,
    access_type=DataAccessType.REALTIME_QUOTE,
    extract_symbol=lambda *args, **kwargs: kwargs.get('symbol', args[0] if args else None)
)

# QMT数据源
monitor_qmt_hist = functools.partial(
    monitor_data_source,
    source=DataSourceType.QMT,
    access_type=DataAccessType.HISTORICAL_KLINE,
    extract_symbol=lambda *args, **kwargs: kwargs.get('symbol', args[0] if args else None)
)

monitor_qmt_realtime = functools.partial(
    monitor_data_source,
    source=DataSourceType.QMT,
    access_type=DataAccessType.REALTIME_QUOTE,
    extract_symbol=lambda *args, **kwargs: kwargs.get('symbols', args[0] if args else None)
)

# CloudFlare数据源
monitor_cloudflare = functools.partial(
    monitor_data_source,
    source=DataSourceType.CLOUDFLARE,
    extract_symbol=lambda *args, **kwargs: kwargs.get('symbol', args[0] if args else None)
)

# AmazingData数据源  
monitor_amazingdata = functools.partial(
    monitor_data_source,
    source=DataSourceType.AMAZINGDATA,
    extract_symbol=lambda *args, **kwargs: kwargs.get('symbol', args[0] if args else None)
)