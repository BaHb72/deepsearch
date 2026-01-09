"""
信号处理模块

负责系统信号（SIGINT/SIGTERM）的统一处理。
"""

import asyncio
import signal
import sys
import threading
from typing import Awaitable, Callable, Optional, cast

from core.observability import get_logger

# 类型别名
StopCallback = Callable[[], Awaitable[None]]


class SignalHandler:
    """
    系统信号处理器

    负责：
    - 设置 SIGINT/SIGTERM 信号处理
    - 跨平台兼容（Unix/Windows）
    - 优雅关闭触发
    """

    def __init__(self) -> None:
        self._logger = get_logger("deepsearch.SignalHandler")
        self._stop_callback: Optional[StopCallback] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._original_sigint: signal.Handlers | None = None
        self._original_sigterm: signal.Handlers | None = None
        self._is_setup = False

    def setup(
        self,
        stop_callback: StopCallback,
        stop_event: asyncio.Event,
    ) -> None:
        """
        设置信号处理器

        Args:
            stop_callback: 收到信号时调用的异步回调
            stop_event: 停止事件，收到信号时会被设置
        """
        if self._is_setup:
            self._logger.warning("Signal handler already setup, skipping")
            return

        # 检查是否在主线程中
        if threading.current_thread() is not threading.main_thread():
            self._logger.warning("Not in main thread, skipping signal handler setup")
            return

        self._stop_callback = stop_callback
        self._stop_event = stop_event

        if sys.platform != "win32":
            self._setup_unix_handlers()
        else:
            self._setup_windows_handlers()

        self._is_setup = True
        self._logger.debug("Signal handlers configured")

    def _setup_unix_handlers(self) -> None:
        """设置 Unix 信号处理器（使用事件循环）"""
        try:
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self._handle_signal()))
        except RuntimeError:
            # 没有事件循环，使用标准信号处理
            self._setup_windows_handlers()

    def _setup_windows_handlers(self) -> None:
        """设置 Windows 信号处理器（标准方式）"""

        def signal_handler(signum: int, frame: object) -> None:
            self._logger.info(f"Received signal {signum}")
            # 使用线程安全的方式设置停止事件
            if self._stop_event:
                self._stop_event.set()
            # 如果在异步环境中，尝试创建任务
            try:
                asyncio.get_running_loop()
                asyncio.create_task(self._handle_signal())
            except RuntimeError:
                # 不在异步环境中，直接设置停止标志
                pass

        self._original_sigint = cast(signal.Handlers, signal.signal(signal.SIGINT, signal_handler))
        self._original_sigterm = cast(
            signal.Handlers, signal.signal(signal.SIGTERM, signal_handler)
        )

    async def _handle_signal(self) -> None:
        """处理系统信号"""
        self._logger.info("Received shutdown signal")
        if self._stop_event:
            self._stop_event.set()
        if self._stop_callback:
            await self._stop_callback()

    def restore(self) -> None:
        """恢复原始信号处理器"""
        if not self._is_setup:
            return

        # 检查是否在主线程中
        if threading.current_thread() is not threading.main_thread():
            return

        if sys.platform != "win32":
            try:
                loop = asyncio.get_event_loop()
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.remove_signal_handler(sig)
            except RuntimeError:
                pass
        else:
            if self._original_sigint:
                signal.signal(signal.SIGINT, self._original_sigint)
            if self._original_sigterm:
                signal.signal(signal.SIGTERM, self._original_sigterm)

        self._is_setup = False
        self._logger.debug("Signal handlers restored")
