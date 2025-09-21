"""
异步运行器

提供统一的异步运行环境，解决事件循环管理问题。
"""
import asyncio
import logging
import signal
import sys
import time
from contextlib import asynccontextmanager
from typing import Optional

from deepsearch.config import get_config
from deepsearch.core.runtime.engine import MainEngine
from deepsearch.core.managers.process_manager import process_manager


class AsyncRunner:
    """
    异步运行器
    
    管理主事件循环和引擎的生命周期
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.engine: Optional[MainEngine] = None
        self._shutdown_event = asyncio.Event()
        self._main_task: Optional[asyncio.Task] = None

    async def initialize_engine(self, mode: str = 'full', config: dict = None):
        """初始化引擎"""
        config = config or {}

        # 创建引擎
        self.engine = MainEngine()

        # 设置模式
        self.engine._mode = mode

        # 注册到 ProcessManager
        process_manager.register_engine(self.engine)

        # 异步初始化
        await self.engine.initialize_async()

        return self.engine

    async def start_engine(self, mode: str = 'full', config: dict = None):
        """启动引擎"""
        config = config or {}

        if mode == 'full':
            await self._start_full_mode(config)
        elif mode == 'engine':
            await self._start_engine_mode(config)
        elif mode == 'webui':
            await self._start_webui_mode(config)
        else:
            raise ValueError(f"未知的运行模式: {mode}")

    async def _start_full_mode(self, config: dict):
        """启动完整模式"""
        include_frontend = not config.get('no_frontend', False)

        await self.engine._start_phased_async(
            include_business=True,
            include_webui=True,
            include_frontend=include_frontend
        )

        # 显示启动信息
        app_config = get_config()
        self.logger.info(f"WebUI API: http://localhost:{app_config.webui.backend_port}")
        if not include_frontend:
            self.logger.info("提示：前端需要单独启动 - cd deepsearch/webui/frontend && npm run dev")

    async def _start_engine_mode(self, config: dict):
        """仅启动引擎模式"""
        await self.engine._start_phased_async(
            include_business=True,
            include_webui=False,
            include_frontend=False
        )

    async def _start_webui_mode(self, config: dict):
        """WebUI 模式"""
        infrastructure_only = config.get('infrastructure_only', True)
        include_frontend = config.get('include_frontend', False)
        include_webui = config.get('include_webui', False)
        await self.engine._start_phased_async(
            include_business=not infrastructure_only,
            include_webui=include_webui,
            include_frontend=include_frontend
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
                def _windows_signal_handler(signum, frame):
                    if loop.is_closed():
                        return
                    loop.call_soon_threadsafe(asyncio.create_task, self._handle_signal())

                for sig in (signal.SIGINT, signal.SIGTERM):
                    previous_signal_handlers[sig] = signal.getsignal(sig)
                    signal.signal(sig, _windows_signal_handler)

            # �ȴ�ֹͣ�ź�
            await self._shutdown_event.wait()

            # ֹͣ����
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
    async def run(cls, mode: str = 'full', config: dict = None):
        """运行引擎的便捷方法"""
        runner = cls()

        try:
            # 初始化引擎
            await runner.initialize_engine(mode, config)

            # 启动引擎
            await runner.start_engine(mode, config)

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
async def async_engine_context(mode: str = 'full', config: dict = None):
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


def run_async_engine(mode: str = 'full', config: dict = None):
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
