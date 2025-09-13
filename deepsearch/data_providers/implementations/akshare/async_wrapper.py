"""
AkShare异步包装器

将同步的akshare调用包装成异步调用，并添加超时控制。
"""
import asyncio
import functools
import time
from typing import Any, Callable, Optional
from loguru import logger


class AsyncWrapper:
    """异步包装器"""
    
    def __init__(self, timeout: float = 10.0):
        """
        初始化包装器
        
        Args:
            timeout: 默认超时时间（秒）
        """
        self.timeout = timeout
        self.executor = None  # 线程池执行器
        
    async def call_with_timeout(
        self, 
        func: Callable,
        *args,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Any:
        """
        异步调用同步函数，带超时控制
        
        Args:
            func: 要调用的同步函数
            *args: 位置参数
            timeout: 超时时间（秒），如果不提供则使用默认值
            **kwargs: 关键字参数
            
        Returns:
            函数返回值
            
        Raises:
            asyncio.TimeoutError: 超时
        """
        if timeout is None:
            timeout = self.timeout
            
        loop = asyncio.get_event_loop()
        
        try:
            # 使用asyncio.wait_for添加超时控制
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    self.executor,
                    functools.partial(func, *args, **kwargs)
                ),
                timeout=timeout
            )
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"函数 {func.__name__} 执行超时 ({timeout}秒)")
            raise
        except Exception as e:
            logger.error(f"函数 {func.__name__} 执行失败: {e}")
            raise
            
    async def batch_call(
        self,
        calls: list,
        max_concurrent: int = 5,
        timeout: Optional[float] = None
    ) -> list:
        """
        批量异步调用
        
        Args:
            calls: [(func, args, kwargs), ...] 调用列表
            max_concurrent: 最大并发数
            timeout: 每个调用的超时时间
            
        Returns:
            结果列表
        """
        if timeout is None:
            timeout = self.timeout
            
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def _call_with_semaphore(func, args, kwargs):
            async with semaphore:
                return await self.call_with_timeout(
                    func, *args, timeout=timeout, **kwargs
                )
                
        tasks = [
            _call_with_semaphore(func, args or (), kwargs or {})
            for func, args, kwargs in calls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                func_name = calls[i][0].__name__ if calls[i][0] else "unknown"
                logger.error(f"批量调用失败 [{func_name}]: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)
                
        return processed_results


# 全局包装器实例
_async_wrapper = None


def get_async_wrapper(timeout: float = 10.0) -> AsyncWrapper:
    """
    获取全局异步包装器
    
    Args:
        timeout: 默认超时时间
        
    Returns:
        AsyncWrapper实例
    """
    global _async_wrapper
    if _async_wrapper is None:
        _async_wrapper = AsyncWrapper(timeout=timeout)
    return _async_wrapper


def wrap_akshare_func(func: Callable, timeout: float = 10.0):
    """
    装饰器：将akshare函数包装成异步函数
    
    Args:
        func: akshare函数
        timeout: 超时时间
        
    Returns:
        异步包装函数
    """
    wrapper = get_async_wrapper(timeout)
    
    @functools.wraps(func)
    async def async_func(*args, **kwargs):
        return await wrapper.call_with_timeout(
            func, *args, timeout=timeout, **kwargs
        )
        
    return async_func


class AkShareAsync:
    """
    异步版本的AkShare接口
    
    使用方式:
    ```python
    ak_async = AkShareAsync()
    df = await ak_async.stock_zh_a_spot_em()
    ```
    """
    
    def __init__(self, timeout: float = 10.0):
        """
        初始化
        
        Args:
            timeout: 默认超时时间
        """
        self.wrapper = AsyncWrapper(timeout=timeout)
        self._cache = {}
        
    def __getattr__(self, name):
        """
        动态获取akshare函数的异步版本
        
        Args:
            name: 函数名
            
        Returns:
            异步包装函数
        """
        if name in self._cache:
            return self._cache[name]
            
        try:
            import akshare as ak
            func = getattr(ak, name)
            
            # 创建异步包装
            async def async_func(*args, **kwargs):
                return await self.wrapper.call_with_timeout(
                    func, *args, **kwargs
                )
                
            # 缓存包装函数
            self._cache[name] = async_func
            return async_func
            
        except AttributeError:
            raise AttributeError(f"akshare没有函数: {name}")
            
    async def parallel_fetch(
        self,
        fetch_tasks: list,
        max_concurrent: int = 5
    ):
        """
        并行获取多个数据
        
        Args:
            fetch_tasks: [(func_name, args, kwargs), ...]
            max_concurrent: 最大并发数
            
        Returns:
            结果列表
        """
        import akshare as ak
        
        calls = []
        for task in fetch_tasks:
            if isinstance(task, tuple):
                func_name = task[0]
                args = task[1] if len(task) > 1 else ()
                kwargs = task[2] if len(task) > 2 else {}
            else:
                func_name = task
                args = ()
                kwargs = {}
                
            func = getattr(ak, func_name)
            calls.append((func, args, kwargs))
            
        return await self.wrapper.batch_call(
            calls,
            max_concurrent=max_concurrent
        )