"""
数据源监控装饰器

提供装饰器简化监控集成
"""
import time
import functools
from typing import Optional, Any, Callable
from loguru import logger

from deepsearch.observability.monitoring.data_source_monitor import (
    get_monitor,
    DataSourceType,
    DataAccessType
)


def monitor_access(
    source_type: DataSourceType,
    access_type: DataAccessType,
    extract_symbol: Optional[Callable] = None
):
    """
    监控数据访问的装饰器
    
    Args:
        source_type: 数据源类型
        access_type: 访问类型
        extract_symbol: 从参数中提取股票代码的函数
    
    Example:
        @monitor_access(
            source_type=DataSourceType.AKSHARE,
            access_type=DataAccessType.REALTIME_QUOTE,
            extract_symbol=lambda args, kwargs: kwargs.get('symbol') or args[0] if args else None
        )
        async def get_realtime_quote(symbol: str):
            # 实现代码
            pass
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            monitor = get_monitor()
            start_time = time.time()
            success = False
            error_msg = None
            symbol = None
            
            # 提取股票代码
            if extract_symbol:
                try:
                    symbol = extract_symbol(args, kwargs)
                except:
                    pass
            
            # 获取模块名
            module = f"{func.__module__}.{func.__name__}"
            
            try:
                result = await func(*args, **kwargs)
                success = True
                
                # 计算数据大小
                data_size = len(str(result)) if result else 0
                
                return result
                
            except Exception as e:
                error_msg = str(e)
                raise
                
            finally:
                # 计算延迟
                latency_ms = (time.time() - start_time) * 1000
                
                # 记录监控数据
                monitor.record_access(
                    source=source_type,
                    access_type=access_type,
                    success=success,
                    latency_ms=latency_ms,
                    symbol=symbol,
                    module=module,
                    error_message=error_msg,
                    data_size=data_size if 'data_size' in locals() else 0
                )
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            monitor = get_monitor()
            start_time = time.time()
            success = False
            error_msg = None
            symbol = None
            
            # 提取股票代码
            if extract_symbol:
                try:
                    symbol = extract_symbol(args, kwargs)
                except:
                    pass
            
            # 获取模块名
            module = f"{func.__module__}.{func.__name__}"
            
            try:
                result = func(*args, **kwargs)
                success = True
                
                # 计算数据大小
                data_size = len(str(result)) if result else 0
                
                return result
                
            except Exception as e:
                error_msg = str(e)
                raise
                
            finally:
                # 计算延迟
                latency_ms = (time.time() - start_time) * 1000
                
                # 记录监控数据
                monitor.record_access(
                    source=source_type,
                    access_type=access_type,
                    success=success,
                    latency_ms=latency_ms,
                    symbol=symbol,
                    module=module,
                    error_message=error_msg,
                    data_size=data_size if 'data_size' in locals() else 0
                )
        
        # 根据函数类型返回合适的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class MonitorContext:
    """
    监控上下文管理器
    
    Example:
        async with MonitorContext(
            source_type=DataSourceType.QMT,
            access_type=DataAccessType.TICK_DATA,
            symbol="000001.SZ"
        ) as ctx:
            # 执行数据访问
            result = await fetch_data()
            ctx.set_data_size(len(result))
    """
    
    def __init__(
        self,
        source_type: DataSourceType,
        access_type: DataAccessType,
        symbol: Optional[str] = None,
        module: Optional[str] = None
    ):
        self.source_type = source_type
        self.access_type = access_type
        self.symbol = symbol
        self.module = module or "unknown"
        self.monitor = get_monitor()
        self.start_time = None
        self.data_size = 0
        self.success = False
        self.error_message = None
    
    def set_data_size(self, size: int):
        """设置数据大小"""
        self.data_size = size
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 计算延迟
        latency_ms = (time.time() - self.start_time) * 1000
        
        # 判断是否成功
        if exc_type is None:
            self.success = True
        else:
            self.error_message = str(exc_val)
        
        # 记录监控数据
        self.monitor.record_access(
            source=self.source_type,
            access_type=self.access_type,
            success=self.success,
            latency_ms=latency_ms,
            symbol=self.symbol,
            module=self.module,
            error_message=self.error_message,
            data_size=self.data_size
        )
        
        # 不抑制异常
        return False
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 计算延迟
        latency_ms = (time.time() - self.start_time) * 1000
        
        # 判断是否成功
        if exc_type is None:
            self.success = True
        else:
            self.error_message = str(exc_val)
        
        # 记录监控数据
        self.monitor.record_access(
            source=self.source_type,
            access_type=self.access_type,
            success=self.success,
            latency_ms=latency_ms,
            symbol=self.symbol,
            module=self.module,
            error_message=self.error_message,
            data_size=self.data_size
        )
        
        # 不抑制异常
        return False