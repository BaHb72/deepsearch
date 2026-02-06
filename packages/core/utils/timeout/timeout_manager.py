"""
状态感知的超时管理器

核心思想：超时时间应该根据数据源当前的工作状态动态调整，
而不是使用固定值。当数据源正在执行耗时但正常的操作时，
应该给予更多时间，而不是错误地触发超时。
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from typing import Dict, Iterator, Optional

from loguru import logger

from .config import (
    DEFAULT_TIMEOUT_CONFIGS,
    DataSourceState,
    SourceStateInfo,
    TimeoutConfig,
    load_timeout_configs_from_settings,
)


class TimeoutManager:
    """
    状态感知的超时管理器

    管理多个数据源的状态，并根据状态返回适当的超时时间。

    使用示例：

        manager = get_timeout_manager()

        # 设置状态
        manager.set_state("akshare", DataSourceState.BATCH_FETCHING, "get_stock_list")

        # 获取超时
        timeout = manager.get_timeout("akshare")  # 返回 batch_timeout

        # 使用上下文管理器
        with manager.operation("akshare", DataSourceState.FETCHING, "get_realtime"):
            # 在此期间状态为 FETCHING
            data = await fetch_data()
        # 退出后状态恢复为 IDLE
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._states: Dict[str, SourceStateInfo] = {}
        self._configs: Dict[str, TimeoutConfig] = DEFAULT_TIMEOUT_CONFIGS.copy()

    def register_source(
        self,
        source: str,
        config: Optional[TimeoutConfig] = None,
    ) -> None:
        """
        注册数据源

        Args:
            source: 数据源名称（如 "akshare", "amazingdata"）
            config: 超时配置，如果为 None 则使用默认配置
        """
        with self._lock:
            if config is not None:
                self._configs[source] = config
            elif source not in self._configs:
                self._configs[source] = TimeoutConfig()

            if source not in self._states:
                self._states[source] = SourceStateInfo()

            logger.debug("注册数据源超时配置: {} -> {}", source, self._configs[source])

    def get_config(self, source: str) -> TimeoutConfig:
        """获取数据源的超时配置"""
        with self._lock:
            return self._configs.get(source, TimeoutConfig())

    def set_state(
        self,
        source: str,
        state: DataSourceState,
        operation: str = "",
        expected_items: int = 0,
    ) -> None:
        """
        设置数据源状态

        Args:
            source: 数据源名称
            state: 新状态
            operation: 操作描述
            expected_items: 预期处理的数据条数（用于批量操作）
        """
        with self._lock:
            if source not in self._states:
                self._states[source] = SourceStateInfo()

            info = self._states[source]
            old_state = info.state
            info.state = state
            info.operation = operation
            info.expected_items = expected_items
            info.processed_items = 0

            if state != DataSourceState.IDLE:
                info.started_at = time.perf_counter()
            else:
                info.started_at = 0.0

            if old_state != state:
                logger.debug(
                    "数据源状态变更: {} | {} -> {} | operation={}",
                    source,
                    old_state.value,
                    state.value,
                    operation or "(none)",
                )

    def get_state(self, source: str) -> DataSourceState:
        """获取数据源当前状态"""
        with self._lock:
            info = self._states.get(source)
            return info.state if info else DataSourceState.IDLE

    def get_state_info(self, source: str) -> SourceStateInfo:
        """获取数据源状态详细信息"""
        with self._lock:
            return self._states.get(source, SourceStateInfo())

    def update_progress(self, source: str, processed_items: int) -> None:
        """
        更新批量操作进度

        Args:
            source: 数据源名称
            processed_items: 已处理的数据条数
        """
        with self._lock:
            if source in self._states:
                self._states[source].processed_items = processed_items

    def get_timeout(
        self,
        source: str,
        operation_type: Optional[str] = None,
    ) -> float:
        """
        根据数据源状态返回适当的超时时间

        Args:
            source: 数据源名称
            operation_type: 操作类型覆盖（如 "connect", "fetch", "batch"）
                           如果不指定，则根据当前状态自动选择

        Returns:
            超时时间（秒）
        """
        with self._lock:
            config = self._configs.get(source, TimeoutConfig())
            state_info = self._states.get(source, SourceStateInfo())
            state = state_info.state

            # 如果指定了操作类型，直接使用对应的超时
            if operation_type:
                timeout_map = {
                    "idle": config.idle_timeout,
                    "connect": config.connect_timeout,
                    "fetch": config.fetch_timeout,
                    "batch": config.batch_timeout,
                    "fallback": config.fallback_timeout,
                }
                return timeout_map.get(operation_type, config.fetch_timeout)

            # 根据当前状态选择超时
            state_timeout_map = {
                DataSourceState.IDLE: config.idle_timeout,
                DataSourceState.CONNECTING: config.connect_timeout,
                DataSourceState.FETCHING: config.fetch_timeout,
                DataSourceState.BATCH_FETCHING: config.batch_timeout,
                DataSourceState.ERROR: config.fallback_timeout,
            }

            return state_timeout_map.get(state, config.fetch_timeout)

    def get_remaining_timeout(self, source: str) -> float:
        """
        获取当前操作的剩余超时时间

        适用于需要知道"还剩多少时间"的场景。

        Returns:
            剩余超时时间（秒），如果操作已超时返回 0
        """
        with self._lock:
            info = self._states.get(source)
            if not info or info.state == DataSourceState.IDLE:
                return self.get_timeout(source)

            elapsed = time.perf_counter() - info.started_at
            total_timeout = self.get_timeout(source)
            remaining = max(0.0, total_timeout - elapsed)

            return remaining

    def is_likely_timeout(self, source: str, additional_time: float = 0.0) -> bool:
        """
        预测当前操作是否可能超时

        用于在操作进行中判断是否应该提前终止。

        Args:
            source: 数据源名称
            additional_time: 预计还需要的额外时间

        Returns:
            True 如果剩余时间不足
        """
        remaining = self.get_remaining_timeout(source)
        return remaining < additional_time

    @contextmanager
    def operation(
        self,
        source: str,
        state: DataSourceState,
        operation: str = "",
        expected_items: int = 0,
    ) -> Iterator[None]:
        """
        上下文管理器：在操作期间设置状态，操作完成后恢复为 IDLE

        使用示例：
            with manager.operation("akshare", DataSourceState.BATCH_FETCHING, "get_stock_list"):
                data = await fetch_all_stocks()

        Args:
            source: 数据源名称
            state: 操作期间的状态
            operation: 操作描述
            expected_items: 预期处理的数据条数
        """
        self.set_state(source, state, operation, expected_items)
        try:
            yield
        finally:
            self.set_state(source, DataSourceState.IDLE)

    def reset(self, source: Optional[str] = None) -> None:
        """
        重置数据源状态

        Args:
            source: 要重置的数据源，如果为 None 则重置所有
        """
        with self._lock:
            if source:
                if source in self._states:
                    self._states[source] = SourceStateInfo()
            else:
                for key in self._states:
                    self._states[key] = SourceStateInfo()

    def get_all_states(self) -> Dict[str, SourceStateInfo]:
        """获取所有数据源的状态（用于监控/调试）"""
        with self._lock:
            return {k: v for k, v in self._states.items()}


# 全局单例
_timeout_manager: Optional[TimeoutManager] = None
_manager_lock = threading.Lock()


def get_timeout_manager() -> TimeoutManager:
    """
    获取全局超时管理器单例

    线程安全的懒加载实现。
    """
    global _timeout_manager

    if _timeout_manager is None:
        with _manager_lock:
            if _timeout_manager is None:
                _timeout_manager = TimeoutManager()
                # 从配置系统加载超时值（覆盖代码级默认值）
                loaded_configs = load_timeout_configs_from_settings()
                for source, config in loaded_configs.items():
                    _timeout_manager.register_source(source, config)
                logger.debug("TimeoutManager 初始化完成（已加载配置）")

    return _timeout_manager


def reset_timeout_manager() -> None:
    """重置全局超时管理器（主要用于测试）"""
    global _timeout_manager
    with _manager_lock:
        _timeout_manager = None
