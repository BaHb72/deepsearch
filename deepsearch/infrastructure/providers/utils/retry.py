"""
统一重试机制模块

提供智能重试策略，包括指数退避、熔断器模式等
"""
import asyncio
import random
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

from loguru import logger

T = TypeVar('T')


class RetryStrategy(Enum):
    """重试策略类型"""
    FIXED = "fixed"  # 固定间隔
    LINEAR = "linear"  # 线性增长
    EXPONENTIAL = "exponential"  # 指数退避
    JITTER = "jitter"  # 带抖动的指数退避


class CircuitBreakerState(Enum):
    """熔断器状态"""
    CLOSED = "closed"  # 正常（关闭）
    OPEN = "open"  # 熔断（开启）
    HALF_OPEN = "half_open"  # 半开（测试）


class RetryConfig:
    """重试配置"""

    def __init__(
            self,
            max_attempts: int = 3,
            strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
            base_delay: float = 1.0,
            max_delay: float = 60.0,
            exponential_base: float = 2.0,
            jitter: bool = True,
            exceptions: tuple = (Exception,)
    ):
        """
        初始化重试配置
        
        Args:
            max_attempts: 最大重试次数
            strategy: 重试策略
            base_delay: 基础延迟（秒）
            max_delay: 最大延迟（秒）
            exponential_base: 指数基数
            jitter: 是否添加随机抖动
            exceptions: 需要重试的异常类型
        """
        self.max_attempts = max_attempts
        self.strategy = strategy
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions

    def calculate_delay(self, attempt: int) -> float:
        """
        计算重试延迟
        
        Args:
            attempt: 当前重试次数（从0开始）
            
        Returns:
            延迟时间（秒）
        """
        if self.strategy == RetryStrategy.FIXED:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * (attempt + 1)
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (self.exponential_base ** attempt)
        elif self.strategy == RetryStrategy.JITTER:
            delay = self.base_delay * (self.exponential_base ** attempt)
            # 添加随机抖动 (0.5x - 1.5x)
            delay *= (0.5 + random.random())
        else:
            delay = self.base_delay

        # 添加通用抖动
        if self.jitter and self.strategy != RetryStrategy.JITTER:
            delay *= (0.8 + random.random() * 0.4)  # ±20%抖动

        # 限制最大延迟
        return min(delay, self.max_delay)


class CircuitBreaker:
    """
    熔断器实现
    
    监控失败率，当失败率过高时自动熔断，避免资源浪费
    """

    def __init__(
            self,
            failure_threshold: int = 5,
            recovery_timeout: float = 60.0,
            success_threshold: int = 2
    ):
        """
        初始化熔断器
        
        Args:
            failure_threshold: 失败阈值（连续失败次数）
            recovery_timeout: 恢复超时（秒）
            success_threshold: 成功阈值（半开状态需要的成功次数）
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = time.time()

    def call(self, func: Callable[[], T]) -> T:
        """
        通过熔断器调用函数
        
        Args:
            func: 要调用的函数
            
        Returns:
            函数返回值
            
        Raises:
            Exception: 熔断器开启时抛出异常
        """
        if self.state == CircuitBreakerState.OPEN:
            # 检查是否可以进入半开状态
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info("熔断器进入半开状态，开始测试")
            else:
                raise Exception("熔断器已开启，服务不可用")

        try:
            result = func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    async def async_call(self, func: Callable[[], T]) -> T:
        """
        通过熔断器异步调用函数
        
        Args:
            func: 要调用的异步函数
            
        Returns:
            函数返回值
            
        Raises:
            Exception: 熔断器开启时抛出异常
        """
        if self.state == CircuitBreakerState.OPEN:
            # 检查是否可以进入半开状态
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info("熔断器进入半开状态，开始测试")
            else:
                raise Exception("熔断器已开启，服务不可用")

        try:
            result = await func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """处理成功调用"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                logger.info("熔断器恢复正常（关闭）")
        else:
            self.failure_count = 0

    def _on_failure(self):
        """处理失败调用"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            logger.warning("熔断器测试失败，继续保持开启状态")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.error(f"连续失败{self.failure_count}次，熔断器开启")

    def reset(self):
        """重置熔断器"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = time.time()

    def get_status(self) -> dict:
        """获取熔断器状态"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_state_change": self.last_state_change
        }


def retry(config: Optional[RetryConfig] = None):
    """
    重试装饰器
    
    Args:
        config: 重试配置
        
    Returns:
        装饰器函数
    """
    if config is None:
        config = RetryConfig()

    def decorator(func):
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except config.exceptions as e:
                    last_exception = e
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"调用失败 (尝试 {attempt + 1}/{config.max_attempts}): {e}, "
                            f"{delay:.2f}秒后重试"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"达到最大重试次数 ({config.max_attempts}): {e}")

            raise last_exception

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except config.exceptions as e:
                    last_exception = e
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"异步调用失败 (尝试 {attempt + 1}/{config.max_attempts}): {e}, "
                            f"{delay:.2f}秒后重试"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"达到最大重试次数 ({config.max_attempts}): {e}")

            raise last_exception

        # 根据函数类型返回相应的包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class SmartRetry:
    """
    智能重试器
    
    结合重试策略和熔断器，提供更智能的错误处理
    """

    def __init__(
            self,
            retry_config: Optional[RetryConfig] = None,
            circuit_breaker: Optional[CircuitBreaker] = None
    ):
        """
        初始化智能重试器
        
        Args:
            retry_config: 重试配置
            circuit_breaker: 熔断器
        """
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    async def execute(
            self,
            func: Callable,
            *args,
            **kwargs
    ) -> Any:
        """
        执行函数，带智能重试和熔断
        
        Args:
            func: 要执行的函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            函数返回值
        """
        last_exception = None

        for attempt in range(self.retry_config.max_attempts):
            try:
                # 通过熔断器执行
                if asyncio.iscoroutinefunction(func):
                    return await self.circuit_breaker.async_call(
                        lambda: func(*args, **kwargs)
                    )
                else:
                    return self.circuit_breaker.call(
                        lambda: func(*args, **kwargs)
                    )
            except Exception as e:
                last_exception = e

                # 检查是否是需要重试的异常
                if not isinstance(e, self.retry_config.exceptions):
                    raise

                # 如果熔断器开启，直接失败
                if self.circuit_breaker.state == CircuitBreakerState.OPEN:
                    logger.error("熔断器已开启，停止重试")
                    raise

                # 计算重试延迟
                if attempt < self.retry_config.max_attempts - 1:
                    delay = self.retry_config.calculate_delay(attempt)
                    logger.warning(
                        f"智能重试失败 (尝试 {attempt + 1}/{self.retry_config.max_attempts}): {e}, "
                        f"{delay:.2f}秒后重试"
                    )
                    if asyncio.iscoroutinefunction(func):
                        await asyncio.sleep(delay)
                    else:
                        time.sleep(delay)

        logger.error(f"智能重试失败，达到最大尝试次数: {last_exception}")
        raise last_exception
