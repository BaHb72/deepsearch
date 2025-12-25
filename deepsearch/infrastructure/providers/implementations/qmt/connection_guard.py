# encoding:utf-8
"""
MiniQMT 连接状态守卫

提供连接状态管理、日志节流和自动恢复探测功能。
用于解决 MiniQMT 客户端未启动时日志刷屏的问题。

Author: DeepSearch Team
Version: 1.0.0
"""

import time
from typing import Optional

from deepsearch.observability import get_logger

logger = get_logger(__name__)


class MiniQMTConnectionGuard:
    """
    MiniQMT 连接状态守卫 - 单例模式

    功能：
    1. 连接状态管理 - 跟踪 MiniQMT 是否可用
    2. 日志节流 - 避免重复错误日志刷屏
    3. 自动恢复探测 - 定期检查服务是否恢复

    使用示例:
        if not MiniQMTConnectionGuard.should_attempt_connection():
            return  # 跳过连接尝试

        try:
            # 尝试连接
            ...
            MiniQMTConnectionGuard.mark_available()
        except Exception as e:
            MiniQMTConnectionGuard.log_connection_error(str(e))
            MiniQMTConnectionGuard.mark_unavailable()
    """

    # 连接状态
    _is_available: Optional[bool] = None  # None=未检测, True=可用, False=不可用
    _last_check_time: float = 0
    _check_interval: float = 300  # 5分钟自动探测
    _consecutive_failures: int = 0
    _max_failures_before_silent: int = 3  # 连续3次失败后进入静默模式

    # 日志节流
    _last_error_log_time: float = 0
    _error_log_interval: float = 300  # 错误日志最小间隔5分钟
    _suppressed_count: int = 0

    # 首次检测标记
    _first_check_done: bool = False

    @classmethod
    def should_attempt_connection(cls) -> bool:
        """
        判断是否应该尝试连接

        Returns:
            True: 应该尝试连接
            False: 跳过此次连接尝试（服务不可用且未到重试时间）
        """
        now = time.time()

        # 首次检测总是允许
        if cls._is_available is None:
            return True

        # 服务可用，允许连接
        if cls._is_available is True:
            return True

        # 服务不可用，检查是否到了重试时间
        if cls._is_available is False:
            time_since_last_check = now - cls._last_check_time
            if time_since_last_check >= cls._check_interval:
                logger.debug(
                    f"MiniQMT 重试探测 (距上次检测 {time_since_last_check:.0f} 秒)"
                )
                return True
            return False

        return True

    @classmethod
    def mark_available(cls) -> None:
        """标记服务可用"""
        was_unavailable = cls._is_available is False

        cls._is_available = True
        cls._last_check_time = time.time()
        cls._consecutive_failures = 0
        cls._first_check_done = True

        if was_unavailable:
            logger.info("MiniQMT 连接已恢复")

    @classmethod
    def mark_unavailable(cls) -> None:
        """标记服务不可用"""
        cls._is_available = False
        cls._last_check_time = time.time()
        cls._consecutive_failures += 1
        cls._first_check_done = True

    @classmethod
    def log_connection_error(cls, message: str) -> bool:
        """
        带节流的连接错误日志

        Args:
            message: 错误消息

        Returns:
            True: 日志已输出
            False: 日志被抑制
        """
        now = time.time()

        # 首次错误总是输出
        if not cls._first_check_done:
            logger.warning(f"MiniQMT 连接失败: {message}")
            cls._last_error_log_time = now
            return True

        # 检查是否在节流期间
        time_since_last_log = now - cls._last_error_log_time
        if time_since_last_log < cls._error_log_interval:
            cls._suppressed_count += 1
            return False  # 抑制日志

        # 输出聚合信息
        if cls._suppressed_count > 0:
            logger.warning(
                f"MiniQMT 连接失败: {message} "
                f"(过去 {cls._error_log_interval:.0f} 秒抑制了 {cls._suppressed_count} 条重复日志)"
            )
        else:
            logger.warning(f"MiniQMT 连接失败: {message}")

        cls._last_error_log_time = now
        cls._suppressed_count = 0
        return True

    @classmethod
    def reset(cls) -> None:
        """
        重置所有状态

        用于手动强制重连时调用
        """
        cls._is_available = None
        cls._last_check_time = 0
        cls._consecutive_failures = 0
        cls._last_error_log_time = 0
        cls._suppressed_count = 0
        cls._first_check_done = False
        logger.info("MiniQMT 连接状态已重置")

    @classmethod
    def is_available(cls) -> Optional[bool]:
        """
        获取当前可用状态

        Returns:
            None: 未检测
            True: 可用
            False: 不可用
        """
        return cls._is_available

    @classmethod
    def get_status(cls) -> dict:
        """
        获取完整状态信息

        Returns:
            状态字典
        """
        return {
            "is_available": cls._is_available,
            "last_check_time": cls._last_check_time,
            "check_interval": cls._check_interval,
            "consecutive_failures": cls._consecutive_failures,
            "suppressed_log_count": cls._suppressed_count,
            "first_check_done": cls._first_check_done,
        }

    @classmethod
    def set_check_interval(cls, seconds: float) -> None:
        """
        设置重试探测间隔

        Args:
            seconds: 间隔秒数
        """
        cls._check_interval = max(30, seconds)  # 最小30秒

    @classmethod
    def set_error_log_interval(cls, seconds: float) -> None:
        """
        设置错误日志节流间隔

        Args:
            seconds: 间隔秒数
        """
        cls._error_log_interval = max(10, seconds)  # 最小10秒
