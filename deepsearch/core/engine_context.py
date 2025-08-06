"""
引擎上下文管理器

提供引擎生命周期的上下文管理，确保资源的正确初始化和清理。
"""
import logging
import signal
from contextlib import contextmanager
from typing import Dict, Any, Optional

from deepsearch.config import get_config
from deepsearch.core.engine import MainEngine
from deepsearch.core.process_manager import process_manager


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

    def __init__(self, mode: str = 'full', config: Optional[Dict[str, Any]] = None):
        """
        初始化引擎上下文
        
        Args:
            mode: 运行模式 ('full', 'engine', 'webui')
            config: 额外的配置参数
        """
        self.mode = mode
        self.config = config or {}
        self.engine: Optional[MainEngine] = None
        self.logger = logging.getLogger(__name__)
        self._original_sigint = None
        self._original_sigterm = None
        self._stop_requested = False

    def __enter__(self) -> MainEngine:
        """进入上下文，创建并启动引擎"""
        self.logger.debug(f"[EngineContext.__enter__] 进入引擎上下文, mode={self.mode}, config={self.config}")

        try:
            # 创建引擎实例
            self.logger.debug("[EngineContext.__enter__] 创建 MainEngine 实例")
            self.engine = MainEngine()

            # 注册到 ProcessManager
            self.logger.debug("[EngineContext.__enter__] 注册引擎到 ProcessManager")
            process_manager.register_engine(self.engine)

            # 设置信号处理
            self.logger.debug("[EngineContext.__enter__] 设置信号处理器")
            self._setup_signal_handlers()

            # 初始化引擎
            self.logger.info("[EngineContext.__enter__] 初始化引擎...")
            # 使用异步初始化
            import asyncio
            asyncio.run(self.engine.initialize_async())
            self.logger.debug("[EngineContext.__enter__] 引擎初始化完成")

            # 根据模式启动引擎
            self.logger.debug(f"[EngineContext.__enter__] 根据模式 '{self.mode}' 启动引擎")
            if self.mode == 'full':
                self._start_full_mode()
            elif self.mode == 'engine':
                self._start_engine_mode()
            elif self.mode == 'webui':
                self._start_webui_mode()
            else:
                raise ValueError(f"未知的运行模式: {self.mode}")

            self.logger.debug(
                f"[EngineContext.__enter__] 引擎上下文设置完成, engine.is_running()={self.engine.is_running()}")
            return self.engine

        except Exception as e:
            self.logger.error(f"[EngineContext.__enter__] 初始化失败: {e}", exc_info=True)
            # 如果初始化失败，确保清理
            self._cleanup()
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文，清理资源"""
        self.logger.debug(f"[EngineContext.__exit__] 退出引擎上下文, exc_type={exc_type}")
        self._cleanup()
        # 不抑制异常
        return False

    def _start_full_mode(self):
        """启动完整模式"""
        include_frontend = not self.config.get('no_frontend', False)
        self.logger.debug(f"[EngineContext._start_full_mode] 启动完整模式, include_frontend={include_frontend}")

        # 使用异步启动
        import asyncio
        asyncio.run(self.engine._start_phased_async(
            include_business=True,
            include_webui=True,
            include_frontend=include_frontend
        ))

        # 显示启动信息
        config = get_config()
        self.logger.info(f"WebUI API: http://localhost:{config.webui.backend_port}")
        if not include_frontend:
            self.logger.info("提示：前端需要单独启动 - cd deepsearch/webui/frontend && npm run dev")

        self.logger.debug(f"[EngineContext._start_full_mode] 完整模式启动完成")

    def _start_engine_mode(self):
        """仅启动引擎模式"""
        self.engine.start_infrastructure()
        self.logger.info("引擎基础设施已启动")

    def _start_webui_mode(self):
        """WebUI 模式（由 WebUIRunner 处理）"""
        # WebUI 模式的具体逻辑由 WebUIRunner 处理
        # 这里只做基本的引擎启动
        infrastructure_only = self.config.get('infrastructure_only', True)
        import asyncio
        asyncio.run(self.engine._start_phased_async(
            include_business=not infrastructure_only,
            include_webui=False,  # WebUIRunner 自己管理 WebUI
            include_frontend=False  # WebUIRunner 自己管理前端
        ))

    def _setup_signal_handlers(self):
        """设置信号处理器"""

        def signal_handler(signum, frame):
            if not self._stop_requested:
                self._stop_requested = True
                self.logger.info(f"收到信号 {signum}，正在优雅关闭...")
                if self.engine and self.engine.is_running():
                    self.engine.stop()

        # 保存原始处理器
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
            # 停止引擎
            if self.engine:
                if self.engine.is_running():
                    self.logger.info("正在停止引擎...")
                    import asyncio
                    asyncio.run(self.engine.stop_async())

                # 从 ProcessManager 注销
                process_manager.unregister_engine(self.engine)

            # 恢复信号处理器
            self._restore_signal_handlers()

        except Exception as e:
            self.logger.error(f"清理资源时出错: {e}")


@contextmanager
def managed_engine(mode: str = 'full', **kwargs):
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

    def __init__(self, mode: str = 'full', config: Optional[Dict[str, Any]] = None):
        self.mode = mode
        self.config = config or {}
        self.engine: Optional[MainEngine] = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self) -> MainEngine:
        """异步进入上下文"""
        # 创建同步上下文
        self._sync_context = EngineContext(self.mode, self.config)
        self.engine = self._sync_context.__enter__()
        return self.engine

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步退出上下文"""
        if self._sync_context:
            self._sync_context.__exit__(exc_type, exc_val, exc_tb)
        return False
