"""
熔断器混入模块

提供熔断保护能力，防止级联故障。
融合自 enhanced_manager.py 和 optimized_manager.py。

熔断器工作原理：
1. CLOSED（正常）: 允许所有请求，记录失败次数
2. 连续失败超过阈值 -> OPEN（熔断）: 拒绝所有请求
3. 超过恢复超时 -> HALF_OPEN（半开）: 允许少量测试请求
4. 测试成功 -> CLOSED，测试失败 -> OPEN

最佳实践参考：
- 熔断器应应用于每个独立的外部服务
- 配置应根据服务特性调整
- 应记录状态变更日志
- 应提供监控指标

使用方法:
    class MyManager(BaseDataSourceManager, CircuitBreakerMixin):
        async def initialize(self):
            await super().initialize()
            self._init_circuit_breakers()

        async def _fetch_from_source(self, source_type, ...):
            if self.is_circuit_open(source_type):
                raise CircuitOpenError(f"{source_type} 熔断器已打开")
            try:
                result = await self._do_fetch(source_type, ...)
                self.record_success(source_type)
                return result
            except Exception as e:
                self.record_failure(source_type)
                raise
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from loguru import logger

# 避免循环导入
try:
    from deepsearch.ports.data_sources import DataSourceType
except ImportError:
    DataSourceType = Any  # type: ignore


class CircuitState(Enum):
    """熔断器状态

    三态模型符合 Circuit Breaker 模式的标准实现。

    Attributes:
        CLOSED: 正常状态，允许请求通过
        OPEN: 熔断状态，拒绝所有请求（快速失败）
        HALF_OPEN: 半开状态，允许少量测试请求
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """熔断器配置

    Attributes:
        failure_threshold: 触发熔断的连续失败次数
        recovery_timeout: 熔断后多少秒尝试恢复
        half_open_attempts: 半开状态下需要多少次连续成功才能完全恢复
        excluded_exceptions: 不计入失败的异常类型（如 ValidationError）

    Example:
        >>> config = CircuitBreakerConfig(
        ...     failure_threshold=3,
        ...     recovery_timeout=30,
        ...     half_open_attempts=2,
        ... )
    """

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_attempts: int = 3
    excluded_exceptions: Set[type] = field(default_factory=set)


@dataclass
class CircuitBreakerState:
    """单个数据源的熔断器状态

    Attributes:
        state: 当前状态
        failures: 连续失败次数
        successes: 半开状态下的连续成功次数
        last_failure_time: 最后一次失败的时间戳
        last_state_change: 最后一次状态变更的时间戳
        total_failures: 累计失败次数（用于统计）
        total_successes: 累计成功次数（用于统计）
    """

    state: CircuitState = CircuitState.CLOSED
    failures: int = 0
    successes: int = 0
    last_failure_time: Optional[float] = None
    last_state_change: float = field(default_factory=time.time)
    # 统计信息
    total_failures: int = 0
    total_successes: int = 0
    state_changes: int = 0


class CircuitBreakerMixin:
    """熔断器混入

    为数据源管理器提供熔断保护能力。

    Attributes:
        _circuit_breakers: 各数据源的熔断器状态
        _circuit_config: 熔断器配置
        _on_circuit_state_change: 状态变更回调函数列表

    Example:
        >>> class Manager(CircuitBreakerMixin):
        ...     pass
        >>> mgr = Manager()
        >>> mgr._init_circuit_breakers(failure_threshold=3)
        >>> mgr.is_circuit_open(DataSourceType.AKSHARE)
        False
        >>> for _ in range(3):
        ...     mgr.record_failure(DataSourceType.AKSHARE)
        >>> mgr.is_circuit_open(DataSourceType.AKSHARE)
        True
    """

    # 类属性声明
    _circuit_breakers: Dict[Any, CircuitBreakerState]
    _circuit_config: CircuitBreakerConfig
    _on_circuit_state_change: List[Callable[[Any, CircuitState, CircuitState], None]]

    def _init_circuit_breakers(
            self,
            failure_threshold: int = 5,
            recovery_timeout: float = 60.0,
            half_open_attempts: int = 3,
            excluded_exceptions: Optional[Set[type]] = None,
    ) -> None:
        """初始化熔断器配置

        Args:
            failure_threshold: 触发熔断的连续失败次数
            recovery_timeout: 熔断后多少秒尝试恢复
            half_open_attempts: 半开状态下需要多少次连续成功才能完全恢复
            excluded_exceptions: 不计入失败的异常类型

        Note:
            此方法应在管理器初始化时调用。
        """
        self._circuit_breakers = {}
        self._circuit_config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_attempts=half_open_attempts,
            excluded_exceptions=excluded_exceptions or set(),
        )
        self._on_circuit_state_change = []

        logger.info(
            f"✅ 熔断器初始化成功: 失败阈值={failure_threshold}, "
            f"恢复超时={recovery_timeout}s, 半开测试次数={half_open_attempts}"
        )

    def add_circuit_state_listener(
            self,
            callback: Callable[[Any, CircuitState, CircuitState], None],
    ) -> None:
        """添加熔断器状态变更监听器

        Args:
            callback: 回调函数，接收 (source_type, old_state, new_state)

        Example:
            >>> def on_change(source, old, new):
            ...     print(f"{source}: {old} -> {new}")
            >>> mgr.add_circuit_state_listener(on_change)
        """
        if not hasattr(self, "_on_circuit_state_change"):
            self._on_circuit_state_change = []
        self._on_circuit_state_change.append(callback)

    def _get_or_create_state(self, source_type: Any) -> CircuitBreakerState:
        """获取或创建熔断器状态"""
        if not hasattr(self, "_circuit_breakers"):
            self._circuit_breakers = {}

        if source_type not in self._circuit_breakers:
            self._circuit_breakers[source_type] = CircuitBreakerState()
        return self._circuit_breakers[source_type]

    def _get_config(self) -> CircuitBreakerConfig:
        """获取熔断器配置"""
        if not hasattr(self, "_circuit_config"):
            self._circuit_config = CircuitBreakerConfig()
        return self._circuit_config

    def _notify_state_change(
            self,
            source_type: Any,
            old_state: CircuitState,
            new_state: CircuitState,
    ) -> None:
        """通知状态变更"""
        if not hasattr(self, "_on_circuit_state_change"):
            return

        for callback in self._on_circuit_state_change:
            try:
                callback(source_type, old_state, new_state)
            except Exception as e:
                logger.warning(f"熔断器状态变更回调失败: {e}")

    def is_circuit_open(self, source_type: Any) -> bool:
        """检查熔断器是否打开（阻止请求）

        Args:
            source_type: 数据源类型

        Returns:
            True 表示熔断器打开，应跳过该数据源

        Note:
            此方法会自动处理状态转换：
            - 如果处于 OPEN 状态且超过恢复超时，自动转换到 HALF_OPEN
        """
        state = self._get_or_create_state(source_type)
        config = self._get_config()

        if state.state == CircuitState.CLOSED:
            return False

        if state.state == CircuitState.OPEN:
            # 检查是否应该尝试恢复
            if self._should_attempt_reset(state, config):
                old_state = state.state
                state.state = CircuitState.HALF_OPEN
                state.successes = 0
                state.last_state_change = time.time()
                state.state_changes += 1

                source_name = (
                    source_type.value
                    if hasattr(source_type, "value")
                    else str(source_type)
                )
                logger.info(
                    f"🔄 数据源 {source_name} 熔断器进入半开状态，"
                    f"开始测试（最多 {config.half_open_attempts} 次）"
                )
                self._notify_state_change(source_type, old_state, state.state)
                return False

            return True

        # HALF_OPEN 状态允许请求通过（用于测试）
        return False

    def _should_attempt_reset(
            self,
            state: CircuitBreakerState,
            config: CircuitBreakerConfig,
    ) -> bool:
        """检查是否应该尝试重置熔断器"""
        if state.last_failure_time is None:
            return True
        return time.time() - state.last_failure_time >= config.recovery_timeout

    def record_success(self, source_type: Any) -> None:
        """记录成功请求

        Args:
            source_type: 数据源类型

        Note:
            - 在 HALF_OPEN 状态下，连续成功达到阈值会使熔断器恢复
            - 在 CLOSED 状态下，会重置失败计数
        """
        state = self._get_or_create_state(source_type)
        config = self._get_config()
        state.total_successes += 1

        source_name = (
            source_type.value if hasattr(source_type, "value") else str(source_type)
        )

        if state.state == CircuitState.HALF_OPEN:
            state.successes += 1

            if state.successes >= config.half_open_attempts:
                old_state = state.state
                state.state = CircuitState.CLOSED
                state.failures = 0
                state.successes = 0
                state.last_state_change = time.time()
                state.state_changes += 1

                logger.info(f"✅ 数据源 {source_name} 熔断器已恢复正常")
                self._notify_state_change(source_type, old_state, state.state)
            else:
                logger.debug(
                    f"数据源 {source_name} 半开测试成功 "
                    f"({state.successes}/{config.half_open_attempts})"
                )
        else:
            # CLOSED 状态，重置失败计数
            state.failures = 0

    def record_failure(
            self,
            source_type: Any,
            exception: Optional[Exception] = None,
    ) -> None:
        """记录失败请求

        Args:
            source_type: 数据源类型
            exception: 发生的异常（可选，用于判断是否计入失败）

        Note:
            - 如果异常类型在 excluded_exceptions 中，不计入失败
            - 在 HALF_OPEN 状态下失败会立即回到 OPEN 状态
        """
        config = self._get_config()

        # 检查是否应该排除此异常
        if exception is not None:
            for exc_type in config.excluded_exceptions:
                if isinstance(exception, exc_type):
                    logger.debug(f"异常 {type(exception).__name__} 被排除，不计入熔断器失败")
                    return

        state = self._get_or_create_state(source_type)
        state.failures += 1
        state.total_failures += 1
        state.last_failure_time = time.time()

        source_name = (
            source_type.value if hasattr(source_type, "value") else str(source_type)
        )

        if state.state == CircuitState.HALF_OPEN:
            # 半开状态下失败，立即回到打开状态
            old_state = state.state
            state.state = CircuitState.OPEN
            state.successes = 0
            state.last_state_change = time.time()
            state.state_changes += 1

            logger.warning(
                f"⚡ 数据源 {source_name} 半开测试失败，"
                f"熔断器重新打开，{config.recovery_timeout}秒后重试"
            )
            self._notify_state_change(source_type, old_state, state.state)

        elif state.failures >= config.failure_threshold:
            old_state = state.state
            state.state = CircuitState.OPEN
            state.successes = 0
            state.last_state_change = time.time()
            state.state_changes += 1

            logger.warning(
                f"⚡ 数据源 {source_name} 连续失败 {state.failures} 次，"
                f"熔断器打开，{config.recovery_timeout}秒后重试"
            )
            self._notify_state_change(source_type, old_state, state.state)
        else:
            logger.debug(
                f"数据源 {source_name} 失败 "
                f"({state.failures}/{config.failure_threshold})"
            )

    def reset_circuit(self, source_type: Any) -> None:
        """手动重置熔断器

        Args:
            source_type: 数据源类型

        Note:
            此方法会将熔断器重置到 CLOSED 状态，清除所有计数。
            通常用于管理员手动干预或测试。
        """
        state = self._get_or_create_state(source_type)
        old_state = state.state

        state.state = CircuitState.CLOSED
        state.failures = 0
        state.successes = 0
        state.last_failure_time = None
        state.last_state_change = time.time()
        state.state_changes += 1

        source_name = (
            source_type.value if hasattr(source_type, "value") else str(source_type)
        )
        logger.info(f"🔧 数据源 {source_name} 熔断器已手动重置")

        if old_state != CircuitState.CLOSED:
            self._notify_state_change(source_type, old_state, state.state)

    def get_circuit_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有熔断器状态

        Returns:
            各数据源的熔断器状态信息

        Example:
            >>> status = mgr.get_circuit_status()
            >>> for source, info in status.items():
            ...     print(f"{source}: {info['state']}")
        """
        if not hasattr(self, "_circuit_breakers"):
            return {}

        return {
            (
                source_type.value
                if hasattr(source_type, "value")
                else str(source_type)
            ): {
                "state": state.state.value,
                "failures": state.failures,
                "successes": state.successes,
                "last_failure_time": state.last_failure_time,
                "last_state_change": state.last_state_change,
                "total_failures": state.total_failures,
                "total_successes": state.total_successes,
                "state_changes": state.state_changes,
            }
            for source_type, state in self._circuit_breakers.items()
        }

    def get_healthy_sources(self, sources: List[Any]) -> List[Any]:
        """过滤出健康的数据源（熔断器未打开）

        Args:
            sources: 数据源列表

        Returns:
            熔断器未打开的数据源列表
        """
        return [s for s in sources if not self.is_circuit_open(s)]


__all__ = [
    "CircuitBreakerMixin",
    "CircuitState",
    "CircuitBreakerConfig",
    "CircuitBreakerState",
]
