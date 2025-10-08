"""
引擎上下文管理器

提供引擎生命周期的上下文管理，确保资源的正确初始化和清理。
"""

import asyncio
import logging
import signal
from contextlib import contextmanager
from typing import Any, Dict, Optional

from deepsearch.core.managers.process_manager import process_manager
from deepsearch.core.runtime.async_runner import AsyncRunner
from deepsearch.core.runtime.engine import MainEngine, RuntimeModeInput
from deepsearch.observability import get_logger


def _log_debug(logger: logging.Logger, message: str) -> None:
    """统一处理调试日志，避免重复的编码噪音。"""
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(message)


async def _shutdown_engine(engine: MainEngine, logger: logging.Logger) -> None:
    """停止引擎并从 ProcessManager 注销。"""
    if engine.is_running():
        logger.info("正在停止引擎...")
        await engine.stop_async()
    process_manager.unregister_engine(engine)


class EngineContext:
    """
    引擎上下文管理器

    使用方式：
    ```python
    with EngineContext(mode='full', config={'include_frontend': False}) as engine:
        # 使用引擎
        while engine.is_running():
            time.sleep(1)
    ```
    """

    def __init__(self, mode: RuntimeModeInput = "full", config: Optional[Dict[str, Any]] = None):
        """
        初始化引擎上下文

        Args:
            mode: 运行模式 ('full', 'engine', 'webui')
            config: 额外的配置参数
        """
        self.mode: RuntimeModeInput = mode
        self.config = config or {}
        self.engine: Optional[MainEngine] = None
        self.logger = get_logger(__name__)
        self._original_sigint = None
        self._original_sigterm = None
        self._stop_requested = False
        self._runner: Optional[AsyncRunner] = None

    def __enter__(self) -> MainEngine:
        """进入上下文，创建并启动引擎"""
        _log_debug(
            self.logger,
            f"[EngineContext.__enter__] 进入引擎上下文, mode={self.mode}, config={self.config}",
        )

        if self.engine is not None:
            raise RuntimeError("EngineContext is not reentrant; engine is already running")

        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                loop_running = False
            else:
                loop_running = True

            if loop_running:
                raise RuntimeError(
                    "EngineContext detected an active asyncio event loop. "
                    "Use AsyncEngineContext in asynchronous environments."
                )

            self._runner = AsyncRunner()
            _log_debug(self.logger, "[EngineContext.__enter__] 启动异步生命周期")
            self.engine = asyncio.run(self._enter_async())

            _log_debug(self.logger, "[EngineContext.__enter__] 设置信号处理器")
            self._setup_signal_handlers()

            _log_debug(
                self.logger,
                f"[EngineContext.__enter__] 引擎上下文设置完成, engine.is_running()={self.engine.is_running()}",
            )
            return self.engine

        except Exception:
            self._cleanup()
            raise

    async def _enter_async(self) -> MainEngine:
        """异步初始化引擎并按照目标模式启动。"""
        engine = await self._ensure_runner().initialize_engine(self.mode, self.config)
        await self._ensure_runner().start_engine(self.mode, self.config)
        return engine

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文，清理资源"""
        _log_debug(self.logger, f"[EngineContext.__exit__] 退出引擎上下文, exc_type={exc_type}")
        self._cleanup()
        return False

    def _ensure_runner(self) -> AsyncRunner:
        if self._runner is None:
            raise RuntimeError("EngineContext runner is not initialized")
        return self._runner

    def _setup_signal_handlers(self):
        """设置信号处理器"""

        def signal_handler(signum, frame):
            if not self._stop_requested:
                self._stop_requested = True
                self.logger.info(f"收到信号 {signum}，正在优雅关闭...")
                if self.engine and self.engine.is_running():
                    self.engine.stop()

        self._original_sigint = signal.signal(signal.SIGINT, signal_handler)
        self._original_sigterm = signal.signal(signal.SIGTERM, signal_handler)

    def _restore_signal_handlers(self):
        """恢复原始信号处理器"""
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)

    def _cleanup(self):
        """清理资源"""
        try:
            engine = None
            if self.engine is not None:
                engine = self.engine
            elif self._runner and getattr(self._runner, "engine", None):
                engine = self._runner.engine
            if engine and self._runner:
                if engine.is_running():
                    try:
                        engine.stop()
                    except Exception as stop_error:
                        self.logger.error(f"停止引擎失败: {stop_error}")
                process_manager.unregister_engine(engine)
        except Exception as e:
            self.logger.error(f"清理资源时出错: {e}")
        finally:
            self._restore_signal_handlers()
            self.engine = None
            if self._runner:
                self._runner.engine = None
            self._runner = None
            self._stop_requested = False


@contextmanager
def managed_engine(mode: RuntimeModeInput = "full", **kwargs: Any):
    """
    便捷的上下文管理器函数

    使用方式：
    ```python
    with managed_engine('full', no_frontend=True) as engine:
        while engine.is_running():
            time.sleep(1)
    ```
    """
    context = EngineContext(mode, kwargs)
    engine = None
    try:
        engine = context.__enter__()
        yield engine
    finally:
        context.__exit__(None, None, None)


class AsyncEngineContext:
    """
    异步引擎上下文管理器

    用于异步环境下的引擎管理。
    """

    def __init__(self, mode: RuntimeModeInput = "full", config: Optional[Dict[str, Any]] = None):
        self.mode: RuntimeModeInput = mode
        self.config = config or {}
        self.engine: Optional[MainEngine] = None
        self.logger = get_logger(__name__)
        self._runner: Optional[AsyncRunner] = None

    async def __aenter__(self) -> MainEngine:
        """异步进入上下文"""
        _log_debug(
            self.logger,
            f"[AsyncEngineContext.__aenter__] 进入上下文, mode={self.mode}, config={self.config}",
        )
        self._runner = AsyncRunner()
        self.engine = await self._runner.initialize_engine(self.mode, self.config)
        await self._runner.start_engine(self.mode, self.config)
        return self.engine

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步退出上下文"""
        _log_debug(self.logger, f"[AsyncEngineContext.__aexit__] 退出上下文, exc_type={exc_type}")
        try:
            engine = None
            if self.engine is not None:
                engine = self.engine
            elif self._runner and getattr(self._runner, "engine", None):
                engine = self._runner.engine
            if engine:
                await _shutdown_engine(engine, self.logger)
        except Exception as e:
            self.logger.error(f"异步清理资源时出错: {e}")
        finally:
            self.engine = None
            if self._runner:
                self._runner.engine = None
            self._runner = None
        return False
