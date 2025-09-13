"""
统一重试处理器

在 DeepSearch 端控制所有数据源的重试逻辑
"""
import asyncio
import time
from typing import Callable, Any, Optional, Dict, List, TypeVar, Awaitable
from functools import wraps
from enum import Enum
from dataclasses import dataclass
from loguru import logger

T = TypeVar('T')


class RetryStrategy(Enum):
    """重试策略"""
    EXPONENTIAL = "exponential"  # 指数退避
    LINEAR = "linear"            # 线性退避
    FIXED = "fixed"              # 固定延迟
    ADAPTIVE = "adaptive"        # 自适应（根据错误类型）


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay: float = 1.0  # 基础延迟（秒）
    max_delay: float = 30.0  # 最大延迟
    exponential_base: float = 2.0  # 指数基数
    jitter: bool = True  # 是否添加随机抖动
    
    # 特定错误码的重试配置
    error_configs: Dict[int, Dict] = None
    
    def __post_init__(self):
        if self.error_configs is None:
            self.error_configs = {
                429: {"max_retries": 5, "base_delay": 2.0},  # Rate limit
                503: {"max_retries": 3, "base_delay": 1.0},  # Service unavailable
                502: {"max_retries": 2, "base_delay": 0.5},  # Bad gateway
                504: {"max_retries": 2, "base_delay": 1.0},  # Gateway timeout
            }


class RetryHandler:
    """统一重试处理器"""
    
    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.stats = {
            "total_retries": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "retry_by_source": {}
        }
    
    def get_delay(self, attempt: int, error_code: Optional[int] = None) -> float:
        """计算重试延迟"""
        # 检查特定错误码配置
        if error_code and error_code in self.config.error_configs:
            base_delay = self.config.error_configs[error_code].get(
                "base_delay", self.config.base_delay
            )
        else:
            base_delay = self.config.base_delay
        
        # 根据策略计算延迟
        if self.config.strategy == RetryStrategy.EXPONENTIAL:
            delay = min(
                base_delay * (self.config.exponential_base ** attempt),
                self.config.max_delay
            )
        elif self.config.strategy == RetryStrategy.LINEAR:
            delay = min(base_delay * (attempt + 1), self.config.max_delay)
        elif self.config.strategy == RetryStrategy.FIXED:
            delay = base_delay
        else:  # ADAPTIVE
            delay = self._adaptive_delay(attempt, error_code)
        
        # 添加抖动
        if self.config.jitter:
            import random
            delay = delay * (0.5 + random.random())
        
        return delay
    
    def _adaptive_delay(self, attempt: int, error_code: Optional[int]) -> float:
        """自适应延迟策略"""
        if error_code == 429:  # Rate limit - 长延迟
            return min(5.0 * (2 ** attempt), 60.0)
        elif error_code == 503:  # Service unavailable - 中等延迟
            return min(2.0 * (1.5 ** attempt), 30.0)
        elif error_code in [502, 504]:  # Gateway errors - 短延迟
            return min(1.0 * (1.2 ** attempt), 10.0)
        else:
            return self.config.base_delay * (1.5 ** attempt)
    
    async def retry_async(
        self,
        func: Callable[..., Awaitable[T]],
        *args,
        source_name: str = "unknown",
        **kwargs
    ) -> T:
        """异步重试装饰器"""
        last_error = None
        
        # 获取最大重试次数
        max_retries = self.config.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                # 执行函数
                result = await func(*args, **kwargs)
                
                # 成功后更新统计
                if attempt > 0:
                    self.stats["successful_retries"] += 1
                    logger.info(f"重试成功: {source_name} (第{attempt}次)")
                
                return result
                
            except Exception as e:
                last_error = e
                
                # 检查是否应该重试
                if attempt >= max_retries:
                    break
                
                # 从异常中提取错误码
                error_code = self._extract_error_code(e)
                
                # 检查特定错误码的重试次数
                if error_code in self.config.error_configs:
                    max_retries_for_error = self.config.error_configs[error_code].get(
                        "max_retries", max_retries
                    )
                    if attempt >= max_retries_for_error:
                        break
                
                # 计算延迟
                delay = self.get_delay(attempt, error_code)
                
                # 更新统计
                self.stats["total_retries"] += 1
                if source_name not in self.stats["retry_by_source"]:
                    self.stats["retry_by_source"][source_name] = 0
                self.stats["retry_by_source"][source_name] += 1
                
                logger.warning(
                    f"请求失败，准备重试: {source_name} "
                    f"(第{attempt + 1}/{max_retries}次) "
                    f"错误: {str(e)[:100]} "
                    f"延迟: {delay:.1f}秒"
                )
                
                # 等待延迟
                await asyncio.sleep(delay)
        
        # 所有重试都失败
        self.stats["failed_retries"] += 1
        logger.error(f"所有重试失败: {source_name} 错误: {str(last_error)[:200]}")
        raise last_error
    
    def retry_sync(
        self,
        func: Callable[..., T],
        *args,
        source_name: str = "unknown",
        **kwargs
    ) -> T:
        """同步重试装饰器"""
        last_error = None
        max_retries = self.config.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                result = func(*args, **kwargs)
                
                if attempt > 0:
                    self.stats["successful_retries"] += 1
                    logger.info(f"重试成功: {source_name} (第{attempt}次)")
                
                return result
                
            except Exception as e:
                last_error = e
                
                if attempt >= max_retries:
                    break
                
                error_code = self._extract_error_code(e)
                delay = self.get_delay(attempt, error_code)
                
                self.stats["total_retries"] += 1
                logger.warning(f"准备重试: {source_name} ({attempt + 1}/{max_retries}) 延迟: {delay:.1f}秒")
                
                time.sleep(delay)
        
        self.stats["failed_retries"] += 1
        raise last_error
    
    def _extract_error_code(self, error: Exception) -> Optional[int]:
        """从异常中提取HTTP错误码"""
        # 检查常见的HTTP异常
        if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            return error.response.status_code
        elif hasattr(error, 'status_code'):
            return error.status_code
        elif hasattr(error, 'code'):
            return error.code
        
        # 从错误消息中提取
        error_msg = str(error).lower()
        if '429' in error_msg:
            return 429
        elif '503' in error_msg:
            return 503
        elif '502' in error_msg:
            return 502
        elif '504' in error_msg:
            return 504
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取重试统计"""
        return {
            **self.stats,
            "success_rate": (
                self.stats["successful_retries"] / self.stats["total_retries"]
                if self.stats["total_retries"] > 0 else 0
            )
        }
    
    def reset_stats(self):
        """重置统计"""
        self.stats = {
            "total_retries": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "retry_by_source": {}
        }


def with_retry(
    max_retries: int = 3,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    base_delay: float = 1.0,
    source_name: str = None
):
    """重试装饰器"""
    def decorator(func):
        config = RetryConfig(
            max_retries=max_retries,
            strategy=strategy,
            base_delay=base_delay
        )
        handler = RetryHandler(config)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            name = source_name or func.__name__
            return await handler.retry_async(func, *args, source_name=name, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            name = source_name or func.__name__
            return handler.retry_sync(func, *args, source_name=name, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# 全局重试处理器实例（可选）
global_retry_handler = RetryHandler(
    RetryConfig(
        max_retries=3,
        strategy=RetryStrategy.ADAPTIVE,
        base_delay=1.0,
        jitter=True
    )
)


# 便捷函数
async def retry_async(func, *args, **kwargs):
    """便捷的异步重试函数"""
    return await global_retry_handler.retry_async(func, *args, **kwargs)


def retry_sync(func, *args, **kwargs):
    """便捷的同步重试函数"""
    return global_retry_handler.retry_sync(func, *args, **kwargs)