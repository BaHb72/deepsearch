"""
异步运行器

提供统一的异步运行环境，解决事件循环管理问题。
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from typing import Any, Dict, Mapping, Optional

from core.config import get_config
from core.core.managers.process_manager import process_manager
from core.core.runtime.engine import MainEngine, RuntimeModeInput
from core.observability import get_logger


class AsyncRunner:
    """
    异步运行器

    管理主事件循环和引擎的生命周期
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self.engine: Optional[MainEngine] = None
        self._shutdown_event = asyncio.Event()
        self._main_task: Optional[asyncio.Task] = None
        self.config: Dict[str, Any] = {}

    async def initialize_engine(
        self, mode: RuntimeModeInput = "full", config: Optional[Mapping[str, Any]] = None
    ) -> MainEngine:
        """初始化引擎"""
        config_dict: Dict[str, Any] = dict(config) if config is not None else {}
        self.config = config_dict

        # 创建引擎
        self.engine = MainEngine(mode=mode)

        # 设置模式
        # 注册到 ProcessManager
        process_manager.register_engine(self.engine)

        # 异步初始化
        await self.engine.initialize_async()

        return self.engine

    async def start_engine(
        self, mode: RuntimeModeInput = "full", config: Optional[Mapping[str, Any]] = None
    ) -> None:
        """启动引擎"""
        if config is None:
            config_dict = self.config
        else:
            config_dict = dict(config)
            self.config = config_dict

        if mode == "full":
            await self._start_full_mode(config_dict)
        elif mode == "engine":
            await self._start_engine_mode(config_dict)
        elif mode == "webui":
            await self._start_webui_mode(config_dict)
        else:
            raise ValueError(f"未知的运行模式: {mode}")

    def _require_engine(self) -> MainEngine:
        """Return the initialized engine or raise if missing."""
        if self.engine is None:
            raise RuntimeError("AsyncRunner engine is not initialized")
        return self.engine

    async def _start_full_mode(self, config: Mapping[str, Any]) -> None:
        """启动完整模式"""
        include_frontend = not config.get("no_frontend", False)

        engine = self._require_engine()
        await engine._start_phased_async(
            include_business=True, include_webui=True, include_frontend=include_frontend
        )

        # 显示启动信息
        app_config = get_config()
        self.logger.info(f"WebUI API: http://localhost:{app_config.webui.backend_port}")
        if not include_frontend:
            self.logger.info("提示：前端需要单独启动 - cd apps/web && npm run dev")

    async def _start_engine_mode(self, config: Mapping[str, Any]) -> None:
        """仅启动引擎模式"""
        engine = self._require_engine()
        await engine._start_phased_async(
            include_business=True, include_webui=False, include_frontend=False
        )

    async def _start_webui_mode(self, config: Mapping[str, Any]) -> None:
        """WebUI 模式"""
        infrastructure_only = config.get("infrastructure_only", True)
        include_frontend = config.get("include_frontend", False)
        include_webui = config.get("include_webui", False)
        engine = self._require_engine()
        await engine._start_phased_async(
            include_business=not infrastructure_only,
            include_webui=include_webui,
            include_frontend=include_frontend,
        )

    async def run_until_complete(self):
        """运行直到收到停止信号"""
        loop = asyncio.get_running_loop()

        previous_signal_handlers = {}
        try:
            if sys.platform != "win32":
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(
                        sig, lambda s=sig: asyncio.create_task(self._handle_signal())
                    )
            else:
                # Windows 平台: 使用改进的信号处理
                signal_count = [0]  # 使用列表以便在闭包中修改

                def _windows_signal_handler(signum, frame):
                    signal_count[0] += 1

                    if signal_count[0] >= 2:
                        # 第二次 Ctrl+C: 强制退出
                        self.logger.warning("收到第二次中断信号，强制退出")
                        import os

                        os._exit(1)

                    # 第一次: 尝试优雅关闭
                    if loop.is_closed():
                        return

                    try:
                        # 直接设置事件，比创建任务更可靠
                        loop.call_soon_threadsafe(self._shutdown_event.set)
                    except RuntimeError:
                        # 事件循环已关闭，忽略
                        pass

                for sig in (signal.SIGINT, signal.SIGTERM):
                    previous_signal_handlers[sig] = signal.getsignal(sig)
                    signal.signal(sig, _windows_signal_handler)

            # 等待停止信号
            await self._shutdown_event.wait()

            # 停止引擎
            if self.engine and self.engine.is_running():
                await self.engine.stop_async()
        finally:
            if previous_signal_handlers:
                for sig, handler in previous_signal_handlers.items():
                    signal.signal(sig, handler)

    async def _handle_signal(self):
        """处理信号"""
        self.logger.info("收到停止信号")
        self._shutdown_event.set()

    @classmethod
    async def run(
        cls, mode: RuntimeModeInput = "full", config: Optional[Mapping[str, Any]] = None
    ) -> None:
        """运行引擎的便捷方法"""
        runner = cls()

        try:
            # 初始化引擎
            await runner.initialize_engine(mode, config)

            # 启动引擎
            await runner.start_engine(mode, config)

            # 执行应用层引导
            try:
                from core.application.bootstrap import bootstrap_system

                await bootstrap_system()
            except ImportError:
                runner.logger.debug("未找到引导模块 deepsearch.application.bootstrap，跳过引导步骤")
            except Exception as e:
                runner.logger.error(f"引导步骤执行失败: {e}")

            # 运行直到停止
            await runner.run_until_complete()

        except Exception as e:
            runner.logger.error(f"运行失败: {e}", exc_info=True)
            raise
        finally:
            # 清理
            if runner.engine:
                process_manager.unregister_engine(runner.engine)


@asynccontextmanager
async def async_engine_context(
    mode: RuntimeModeInput = "full", config: Optional[Mapping[str, Any]] = None
):
    """
    异步引擎上下文管理器

    使用方式：
    ```python
    async with async_engine_context('full') as engine:
        # 使用引擎
        await asyncio.sleep(10)
    ```
    """
    runner = AsyncRunner()

    try:
        # 初始化并启动引擎
        await runner.initialize_engine(mode, config)
        await runner.start_engine(mode, config)

        yield runner.engine

    finally:
        # 停止引擎
        if runner.engine and runner.engine.is_running():
            await runner.engine.stop_async()

        # 清理
        if runner.engine:
            process_manager.unregister_engine(runner.engine)


def run_async_engine(mode: str = "full", config: Optional[Mapping[str, Any]] = None) -> None:
    """
    同步包装器，用于运行异步引擎

    这个函数会创建并管理整个事件循环
    """

    async def main():
        await AsyncRunner.run(mode, config)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n正在关闭...")
