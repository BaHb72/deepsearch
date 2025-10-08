"""
统一重试处理器

在 DeepSearch 端控制所有数据源的重试逻辑
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from random import random
from typing import (
    Any,
    Awaitable,
    Callable,
    DefaultDict,
    Dict,
    Optional,
    Tuple,
    TypeVar,
    TypedDict,
    Union,
    cast,
)

from loguru import logger

T = TypeVar("T")


class RetryStrategy(Enum):
    """重试策略"""

    EXPONENTIAL = "exponential"  # 指数回退
    LINEAR = "linear"  # 线性回退
    FIXED = "fixed"  # 固定延迟
    ADAPTIVE = "adaptive"  # 自适应（根据错误类型）


class RetryOverride(TypedDict, total=False):
    """错误码重试覆盖配置"""

    max_retries: int
    base_delay: float
    max_delay: float
    exponential_base: float
    jitter: bool
    strategy: RetryStrategy


class RetryStats(TypedDict):
    total_retries: int
    successful_retries: int
    failed_retries: int
    retry_by_source: Dict[str, int]


class RetryStatsReport(RetryStats):
    success_rate: float


@dataclass(frozen=True)
class AdaptiveDelayProfile:
    """描述自适应延迟的增长模型"""

    multiplier: float
    growth: float
    cap: Optional[float] = None

    def compute(self, attempt: int) -> float:
        delay = self.multiplier * (self.growth**attempt)
        if self.cap is not None:
            return min(delay, self.cap)
        return delay


@dataclass
class RetryConfig:
    """重试配置"""

    max_retries: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay: float = 1.0  # 基础延迟（秒）
    max_delay: float = 30.0  # 最大延迟
    exponential_base: float = 2.0  # 指数底数
    jitter: bool = True  # 是否启用抖动

    # 错误码对应的特殊配置
    error_configs: Optional[Dict[int, RetryOverride]] = None

    def __post_init__(self) -> None:
        if self.error_configs is None:
            self.error_configs = {
                429: RetryOverride(max_retries=5, base_delay=2.0),  # Rate limit
                503: RetryOverride(max_retries=3, base_delay=1.0),  # Service unavailable
                502: RetryOverride(max_retries=2, base_delay=0.5),  # Bad gateway
                504: RetryOverride(max_retries=2, base_delay=1.0),  # Gateway timeout
            }

_ADAPTIVE_DELAY_PROFILES: Dict[int, AdaptiveDelayProfile] = {
    429: AdaptiveDelayProfile(multiplier=5.0, growth=2.0, cap=60.0),
    503: AdaptiveDelayProfile(multiplier=2.0, growth=1.5, cap=30.0),
    502: AdaptiveDelayProfile(multiplier=1.0, growth=1.2, cap=10.0),
    504: AdaptiveDelayProfile(multiplier=1.0, growth=1.2, cap=10.0),
}

_ERROR_ATTRIBUTE_PATHS: Tuple[Tuple[str, ...], ...] = (
    ("response", "status_code"),
    ("status_code",),
    ("code",),
)

_ERROR_MESSAGE_HINTS: Tuple[Tuple[str, int], ...] = (
    ("429", 429),
    ("503", 503),
    ("502", 502),
    ("504", 504),
)


def _create_retry_counter() -> DefaultDict[str, int]:
    return defaultdict(int)


def _create_stats() -> RetryStats:
    return {
        "total_retries": 0,
        "successful_retries": 0,
        "failed_retries": 0,
        "retry_by_source": _create_retry_counter(),
    }


class RetryHandler:
    """统一重试处理器"""

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self.stats: RetryStats = _create_stats()

    def get_delay(self, attempt: int, error_code: Optional[int] = None) -> float:
        """计算下一次重试的延迟"""
        override = self._get_override(error_code)

        base_delay = float(override.get("base_delay", self.config.base_delay)) if override else self.config.base_delay
        max_delay = float(override.get("max_delay", self.config.max_delay)) if override else self.config.max_delay
        strategy = override.get("strategy", self.config.strategy) if override else self.config.strategy
        exponential_base = float(override.get("exponential_base", self.config.exponential_base)) if override else self.config.exponential_base

        if strategy == RetryStrategy.EXPONENTIAL:
            delay = min(base_delay * (exponential_base**attempt), max_delay)
        elif strategy == RetryStrategy.LINEAR:
            delay = min(base_delay * (attempt + 1), max_delay)
        elif strategy == RetryStrategy.FIXED:
            delay = base_delay
        else:
            delay = self._adaptive_delay(attempt, error_code)

        jitter_enabled = bool(override.get("jitter", self.config.jitter)) if override else self.config.jitter
        if jitter_enabled:
            delay *= 0.5 + random()

        return float(delay)

    def _adaptive_delay(self, attempt: int, error_code: Optional[int]) -> float:
        """根据错误类型计算自适应延迟"""
        if error_code is not None:
            profile = _ADAPTIVE_DELAY_PROFILES.get(error_code)
            if profile is not None:
                return float(profile.compute(attempt))
        return float(self.config.base_delay * (1.5**attempt))

    async def retry_async(
        self, func: Callable[..., Awaitable[T]], *args, source_name: str = "unknown", **kwargs
    ) -> T:
        """异步重试装饰器"""
        last_error: Optional[Exception] = None

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

            except Exception as exc:
                last_error = exc

                # 判断是否应停止重试
                if attempt >= max_retries:
                    break

                # 解析错误码并应用专属配置
                error_code = self._extract_error_code(exc)
                override = self._get_override(error_code)
                if override and "max_retries" in override:
                    max_retries_for_error = int(override.get("max_retries", max_retries))
                    if attempt >= max_retries_for_error:
                        break

                # 计算延迟
                delay = self.get_delay(attempt, error_code)

                # 更新统计
                self.stats["total_retries"] += 1
                self.stats["retry_by_source"][source_name] += 1

                logger.warning(
                    f"请求失败，准备重试: {source_name} "
                    f"(第{attempt + 1}/{max_retries}次) "
                    f"错误: {str(exc)[:100]} "
                    f"延迟: {delay:.1f}秒"
                )

                # 等待延迟
                await asyncio.sleep(delay)

        # 所有重试都失败
        self.stats["failed_retries"] += 1
        logger.error(f"所有重试失败: {source_name} 错误: {str(last_error)[:200]}")
        if last_error is None:
            raise RuntimeError("Retry failed without capturing an exception")
        raise last_error

    def retry_sync(
        self, func: Callable[..., T], *args, source_name: str = "unknown", **kwargs
    ) -> T:
        """同步重试装饰器"""
        last_error: Optional[Exception] = None
        max_retries = self.config.max_retries

        for attempt in range(max_retries + 1):
            try:
                result = func(*args, **kwargs)

                if attempt > 0:
                    self.stats["successful_retries"] += 1
                    logger.info(f"重试成功: {source_name} (第{attempt}次)")

                return result

            except Exception as exc:
                last_error = exc

                if attempt >= max_retries:
                    break

                error_code = self._extract_error_code(exc)
                delay = self.get_delay(attempt, error_code)

                self.stats["total_retries"] += 1
                self.stats["retry_by_source"][source_name] += 1
                logger.warning(
                    f"准备重试: {source_name} ({attempt + 1}/{max_retries}) 延迟: {delay:.1f}秒"
                )

                time.sleep(delay)

        self.stats["failed_retries"] += 1
        if last_error is None:
            raise RuntimeError("Retry failed without capturing an exception")
        raise last_error

    def _extract_error_code(self, error: Exception) -> Optional[int]:
        """从异常对象中提取可用的错误码"""

        def _as_int(value: Any) -> Optional[int]:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        for attribute_path in _ERROR_ATTRIBUTE_PATHS:
            value: Any = error
            for attribute in attribute_path:
                value = getattr(value, attribute, None)
                if value is None:
                    break
            else:
                code = _as_int(value)
                if code is not None:
                    return code

        error_msg = str(error).lower()
        for marker, code_hint in _ERROR_MESSAGE_HINTS:
            if marker in error_msg:
                return code_hint
        return None

    def get_stats(self) -> RetryStatsReport:
        """获取重试统计"""
        total = self.stats["total_retries"]
        success_rate = self.stats["successful_retries"] / total if total > 0 else 0.0
        report: RetryStatsReport = {
            "total_retries": self.stats["total_retries"],
            "successful_retries": self.stats["successful_retries"],
            "failed_retries": self.stats["failed_retries"],
            "retry_by_source": dict(self.stats["retry_by_source"]),
            "success_rate": success_rate,
        }
        return report

    def reset_stats(self) -> None:
        """重置统计"""
        self.stats = _create_stats()

    def _get_override(self, error_code: Optional[int]) -> Optional[RetryOverride]:
        if error_code is None:
            return None
        configs = self.config.error_configs
        if not configs:
            return None
        return configs.get(error_code)


def with_retry(
    max_retries: int = 3,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    base_delay: float = 1.0,
    source_name: Optional[str] = None,
):
    """重试装饰器"""

    def decorator(func: Callable[..., Union[T, Awaitable[T]]]):
        config = RetryConfig(max_retries=max_retries, strategy=strategy, base_delay=base_delay)
        handler = RetryHandler(config)

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            name = source_name or func.__name__
            async_func = cast(Callable[..., Awaitable[T]], func)
            return await handler.retry_async(async_func, *args, source_name=name, **kwargs)

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            name = source_name or func.__name__
            sync_func = cast(Callable[..., T], func)
            return handler.retry_sync(sync_func, *args, source_name=name, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# 全局重试处理器实例（可选）
global_retry_handler = RetryHandler(
    RetryConfig(max_retries=3, strategy=RetryStrategy.ADAPTIVE, base_delay=1.0, jitter=True)
)


# 便捷函数
async def retry_async(func: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any) -> T:
    """便捷的异步重试函数"""
    return await global_retry_handler.retry_async(func, *args, **kwargs)


def retry_sync(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """便捷的同步重试函数"""
    return global_retry_handler.retry_sync(func, *args, **kwargs)

