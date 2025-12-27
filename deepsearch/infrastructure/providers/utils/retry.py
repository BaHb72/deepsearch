"""
统一重试与断路器工具

提供统一的同步/异步重试以及断路器封装
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Optional,
    ParamSpec,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from loguru import logger

T = TypeVar("T")
R = TypeVar("R")
P = ParamSpec("P")


class RetryStrategy(Enum):
    """重试策略枚举"""

    FIXED = "fixed"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"
    JITTER = "jitter"


class CircuitBreakerState(Enum):
    """断路器状态"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(RuntimeError):
    """在断路器打开时发起调用会抛出的异常"""


@dataclass
class RetryConfig:
    """重试参数配置"""

    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    exceptions: Tuple[Type[BaseException], ...] = (Exception,)

    def calculate_delay(self, attempt: int) -> float:
        """根据策略计算本轮重试延迟"""

        delay = self.base_delay

        if self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * (attempt + 1)
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (self.exponential_base**attempt)
        elif self.strategy == RetryStrategy.JITTER:
            delay = self.base_delay * (self.exponential_base**attempt)
            delay *= random.uniform(0.5, 1.5)

        if self.jitter and self.strategy != RetryStrategy.JITTER:
            delay *= random.uniform(0.8, 1.2)

        return min(delay, self.max_delay)


class CircuitBreaker:
    """简单断路器实现"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state: CircuitBreakerState = CircuitBreakerState.CLOSED
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change: float = time.time()

    def call(self, func: Callable[[], T]) -> T:
        """执行同步调用并应用断路器规则"""

        if self.state == CircuitBreakerState.OPEN:
            if self._can_attempt_recovery():
                self._transition(CircuitBreakerState.HALF_OPEN)
                self.success_count = 0
                logger.info("断路器进入半开状态，尝试恢复")
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open; call blocked")

        try:
            result = func()
        except BaseException:
            self._on_failure()
            raise

        self._on_success()
        return result

    async def async_call(self, func: Callable[[], Awaitable[T]]) -> T:
        """执行异步调用并应用断路器规则"""

        if self.state == CircuitBreakerState.OPEN:
            if self._can_attempt_recovery():
                self._transition(CircuitBreakerState.HALF_OPEN)
                self.success_count = 0
                logger.info("断路器进入半开状态，尝试恢复")
            else:
                raise CircuitBreakerOpenError("Circuit breaker is open; call blocked")

        try:
            result = await func()
        except BaseException:
            self._on_failure()
            raise

        self._on_success()
        return result

    def reset(self) -> None:
        """重置断路器状态"""

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self._transition(CircuitBreakerState.CLOSED)

    def _transition(self, new_state: CircuitBreakerState) -> None:
        self.state = new_state
        self.last_state_change = time.time()

    def _can_attempt_recovery(self) -> bool:
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) > self.recovery_timeout

    def _on_success(self) -> None:
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info("断路器恢复到关闭状态")
                self.reset()
        else:
            self.failure_count = 0

    def _on_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()

        if (
            self.state == CircuitBreakerState.HALF_OPEN
            or self.failure_count >= self.failure_threshold
        ):
            logger.warning("断路器打开，停止后续请求")
            self._transition(CircuitBreakerState.OPEN)

    def get_state(self) -> Dict[str, Any]:
        """返回断路器当前状态信息"""

        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "last_state_change": self.last_state_change,
        }


def with_retry(
    config: Optional[RetryConfig] = None,
) -> Callable[[Callable[P, Union[T, Awaitable[T]]]], Callable[P, Union[T, Awaitable[T]]]]:
    """装饰器：为函数增加重试能力"""

    retry_config = config or RetryConfig()

    def decorator(func: Callable[P, Union[T, Awaitable[T]]]) -> Callable[P, Union[T, Awaitable[T]]]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            callable_sync = cast(Callable[P, T], func)
            last_exception: Optional[BaseException] = None

            for attempt in range(retry_config.max_attempts):
                try:
                    return callable_sync(*args, **kwargs)
                except retry_config.exceptions as exc:
                    last_exception = exc
                    if attempt < retry_config.max_attempts - 1:
                        delay = retry_config.calculate_delay(attempt)
                        logger.warning(
                            "同步调用失败 ({}/{}): {}，等待 {:.2f}s 后重试",
                            attempt + 1,
                            retry_config.max_attempts,
                            exc,
                            delay,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "达到最大同步重试次数 ({}): {}", retry_config.max_attempts, exc
                        )

            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Retry failed without capturing an exception")

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            callable_async = cast(Callable[P, Awaitable[T]], func)
            last_exception: Optional[BaseException] = None

            for attempt in range(retry_config.max_attempts):
                try:
                    return await callable_async(*args, **kwargs)
                except retry_config.exceptions as exc:
                    last_exception = exc
                    if attempt < retry_config.max_attempts - 1:
                        delay = retry_config.calculate_delay(attempt)
                        logger.warning(
                            "异步调用失败 ({}/{}): {}，等待 {:.2f}s 后重试",
                            attempt + 1,
                            retry_config.max_attempts,
                            exc,
                            delay,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "达到最大异步重试次数 ({}): {}", retry_config.max_attempts, exc
                        )

            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Retry failed without capturing an exception")

        if asyncio.iscoroutinefunction(func):
            return cast(Callable[P, Union[T, Awaitable[T]]], async_wrapper)
        return cast(Callable[P, Union[T, Awaitable[T]]], sync_wrapper)

    return decorator


class SmartRetry:
    """组合断路器与重试的执行器"""

    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    async def execute(
        self, func: Callable[..., Union[T, Awaitable[T]]], *args: Any, **kwargs: Any
    ) -> T:
        last_exception: Optional[BaseException] = None
        is_coroutine = asyncio.iscoroutinefunction(func)
        async_callable = cast(Optional[Callable[..., Awaitable[T]]], func if is_coroutine else None)
        sync_callable = cast(Optional[Callable[..., T]], func if not is_coroutine else None)

        for attempt in range(self.retry_config.max_attempts):
            try:
                if is_coroutine and async_callable is not None:
                    return await self.circuit_breaker.async_call(
                        lambda: async_callable(*args, **kwargs)
                    )
                if sync_callable is not None:
                    return self.circuit_breaker.call(lambda: sync_callable(*args, **kwargs))
                raise RuntimeError("Unsupported callable passed to SmartRetry")
            except BaseException as exc:
                last_exception = exc

                if not isinstance(exc, self.retry_config.exceptions):
                    raise

                if self.circuit_breaker.state == CircuitBreakerState.OPEN:
                    logger.error("断路器已打开，终止后续重试")
                    raise

                if attempt < self.retry_config.max_attempts - 1:
                    delay = self.retry_config.calculate_delay(attempt)
                    logger.warning(
                        "智能重试失败 ({}/{}): {}，等待 {:.2f}s 后继续",
                        attempt + 1,
                        self.retry_config.max_attempts,
                        exc,
                        delay,
                    )
                    if is_coroutine:
                        await asyncio.sleep(delay)
                    else:
                        time.sleep(delay)

        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Retry failed without capturing an exception")
