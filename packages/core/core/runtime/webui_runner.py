"""
WebUI 运行器模块

负责 WebUI (uvicorn) 服务器的启动与管理。
"""

import asyncio
from typing import TYPE_CHECKING, Optional

from core.observability import get_logger
from core.utils.system.port_checker import PortChecker

if TYPE_CHECKING:
    from core.config.models.webui import WebUIConfig

    from .engine import MainEngine


class WebUIRunner:
    """
    WebUI 服务器运行器

    负责：
    - uvicorn 服务器的启动与配置
    - 端口可用性检查
    - 服务器生命周期管理
    """

    def __init__(self) -> None:
        self._logger = get_logger("deepsearch.WebUIRunner")
        self._task: Optional[asyncio.Task] = None
        self._server: Optional[object] = None
        self._actual_port: Optional[int] = None

    @property
    def actual_port(self) -> Optional[int]:
        """获取实际使用的端口"""
        return self._actual_port

    @property
    def task(self) -> Optional[asyncio.Task]:
        """获取 WebUI 任务"""
        return self._task

    async def start(
        self,
        engine: "MainEngine",
        config: "WebUIConfig",
    ) -> asyncio.Task:
        """
        启动 WebUI 服务器

        Args:
            engine: MainEngine 实例
            config: WebUI 配置

        Returns:
            WebUI 服务器任务

        Raises:
            RuntimeError: 端口被占用时抛出
        """
        import uvicorn

        from apps.api.server import app

        port = config.backend_port
        self._actual_port = port

        # 检查端口是否可用
        if not PortChecker.is_port_available(port, host="127.0.0.1"):
            await self._log_port_conflict(port)
            raise RuntimeError(
                f"端口 {port} 已被占用。请执行以下操作之一：\n"
                f"  1. 运行 'python -m deepsearch cleanup' 清理端口\n"
                f"  2. 停止占用端口的进程\n"
                f"  3. 修改配置文件中的 webui.backend_port"
            )

        self._logger.info(f"端口 {port} 可用，启动 WebUI 服务器...")

        # 设置引擎到 app_state
        app.state.app_state.set_engine(engine)

        # 配置 uvicorn 服务器
        server_config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=port,
            log_level="warning",
            loop="asyncio",
            access_log=False,
        )
        self._server = uvicorn.Server(server_config)

        # 禁用 uvicorn 的信号处理，由引擎统一管理
        if hasattr(self._server, "install_signal_handlers"):
            self._server.install_signal_handlers = lambda: None

        # 创建异步任务
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self._run_server())
        self._logger.info("WebUI 服务器任务已启动")

        return self._task

    async def _run_server(self) -> None:
        """运行服务器的内部方法"""
        try:
            self._logger.info("WebUI server starting...")
            await self._server.serve()  # type: ignore
            self._logger.info("WebUI server stopped normally")
        except asyncio.CancelledError:
            self._logger.info("WebUI task cancelled, cleaning up...")
            if self._server:
                setattr(self._server, "should_exit", True)
        except OSError as e:
            self._logger.error(f"OSError in server.serve(): {e}")
            if "Address already in use" in str(e):
                self._logger.error(
                    f"Port {self._actual_port} is already in use despite our checks!"
                )
            raise
        except Exception as e:
            self._logger.error(f"Unexpected error in server.serve(): {type(e).__name__}: {e}")
            import traceback

            self._logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        finally:
            if self._server:
                setattr(self._server, "should_exit", True)
            self._logger.info("WebUI task cleanup completed")

    async def stop(self) -> None:
        """停止 WebUI 服务器"""
        if self._server:
            setattr(self._server, "should_exit", True)

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(self._task), timeout=5.0)
            except asyncio.CancelledError, asyncio.TimeoutError:
                pass

        self._task = None
        self._server = None
        self._logger.info("WebUI runner stopped")

    async def _log_port_conflict(self, port: int) -> None:
        """记录端口冲突信息"""
        self._logger.error(f"端口 {port} 已被占用，无法启动 WebUI 服务器")
        try:
            import psutil

            for conn in psutil.net_connections():
                if hasattr(conn, "laddr") and conn.laddr.port == port and conn.status == "LISTEN":
                    try:
                        proc = psutil.Process(conn.pid)
                        self._logger.error(f"占用进程: {proc.name()} (PID: {conn.pid})")
                    except Exception:
                        self._logger.error(f"占用进程 PID: {conn.pid}")
                    break
        except Exception:
            pass
