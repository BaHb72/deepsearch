"""
WebUI 服务器管理器

统一管理服务器的生命周期、关闭处理和平台特定功能。
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional, TYPE_CHECKING

from uvicorn.config import Config, LOGGING_CONFIG
from uvicorn.server import Server
from starlette.types import ASGIApp

from deepsearch.observability import get_logger
from deepsearch.webui.api.models import WebServerConfig


if TYPE_CHECKING:
    from asyncio import WindowsProactorEventLoopPolicy as WindowsEventLoopPolicyBase
elif hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    WindowsEventLoopPolicyBase = asyncio.WindowsProactorEventLoopPolicy
else:  # pragma: no cover - 非 Windows 平台兜底

    class _WindowsEventLoopPolicyFallback(asyncio.DefaultEventLoopPolicy):
        """Windows 专用策略在非 Windows 平台的无操作实现"""

        pass

    WindowsEventLoopPolicyBase = _WindowsEventLoopPolicyFallback


class ServerManager:
    """
    统一的服务器管理器

    负责：
    - 服务器生命周期管理
    - 优雅关闭处理
    - 平台特定的事件循环配置
    - WebSocket 连接管理
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self._servers: dict[str, Server] = {}
        self._tasks: set[asyncio.Task] = set()
        self._shutdown_event = asyncio.Event()
        self._is_shutting_down: bool = False

    def setup_platform_specific(self):
        """设置平台特定的配置"""
        if sys.platform == "win32":
            self._setup_windows()
        else:
            self._setup_unix()

    def _setup_windows(self):
        """Windows 平台特定设置"""
        # 使用改进的事件循环策略
        asyncio.set_event_loop_policy(WindowsEventLoopPolicy())

        # 设置控制台处理器
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleCtrlHandler(None, False)
        except Exception:
            self.logger.debug("无法设置 Windows 控制台信号处理", exc_info=True)

    def _setup_unix(self):
        """Unix/Linux 平台特定设置"""
        # Unix 平台通常不需要特殊设置
        pass

    def create_server_config(
        self,
        app: ASGIApp,
        host: Optional[str] = None,
        port: Optional[int] = None,
        **overrides: object,
    ) -> Config:
        """
        创建统一的服务器配置

        Args:
            app: ASGI 应用
            host: 绑定地址
            port: 监听端口
            **kwargs: 其他配置选项

        Returns:
            uvicorn.Config 实例
        """
        if host is None or port is None:
            from deepsearch.config import get_config

            settings = get_config()
            if host is None:
                host = settings.webui.backend_host
            if port is None:
                port = settings.webui.backend_port

        log_config_override = "log_config" in overrides

        config_model = WebServerConfig(host=host, port=port)
        if overrides:
            config_model.apply_overrides(overrides)

        config_kwargs: dict[str, object] = {
            "host": config_model.host,
            "port": config_model.port,
            "log_level": config_model.log_level,
            "access_log": config_model.access_log,
            "ws": config_model.ws,
            "loop": config_model.loop,
            "lifespan": config_model.lifespan,
            "timeout_graceful_shutdown": config_model.timeout_graceful_shutdown,
            "reload": config_model.reload,
            "log_config": (
                config_model.log_config if log_config_override else LOGGING_CONFIG
            ),
        }

        if config_model.ssl_certfile is not None:
            config_kwargs["ssl_certfile"] = config_model.ssl_certfile
        if config_model.ssl_keyfile is not None:
            config_kwargs["ssl_keyfile"] = config_model.ssl_keyfile
        if config_model.ssl_keyfile_password is not None:
            config_kwargs["ssl_keyfile_password"] = config_model.ssl_keyfile_password
        if config_model.headers is not None:
            config_kwargs["headers"] = [tuple(header) for header in config_model.headers]

        config = Config(app=app, **config_kwargs)

        if config_model.extras:
            for key, value in config_model.extras.items():
                if hasattr(config, key):
                    setattr(config, key, value)
                else:
                    self.logger.debug("忽略未识别的 uvicorn.Config 参数：%s", key)

        return config

    async def start_server(self, app: ASGIApp, name: str = "main", **config_kwargs) -> Server:
        """
        启动服务器

        Args:
            app: ASGI 应用
            name: 服务器名称（用于管理多个服务器）
            **config_kwargs: 服务器配置

        Returns:
            Server 实例
        """
        if name in self._servers:
            raise ValueError(f"Server '{name}' already exists")

        config = self.create_server_config(app, **config_kwargs)
        server = GracefulShutdownServer(config, self)

        self._servers[name] = server

        # 创建服务器任务
        task = asyncio.create_task(server.serve())
        self._register_task(task)

        return server

    def _register_task(self, task: asyncio.Task):
        """注册任务以便跟踪"""
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown_all(self, timeout: float = 5.0):
        """关闭所有服务器"""
        if self._is_shutting_down:
            return

        self._is_shutting_down = True
        self.logger.info("正在关闭所有服务器...")

        # 设置关闭事件
        self._shutdown_event.set()

        # 关闭所有服务器
        shutdown_tasks = []
        for name, server in self._servers.items():
            self.logger.info(f"关闭服务器: {name}")
            if hasattr(server, "shutdown"):
                shutdown_tasks.append(server.shutdown())

        if shutdown_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*shutdown_tasks, return_exceptions=True), timeout=timeout
                )
            except asyncio.TimeoutError:
                self.logger.warning("服务器关闭超时")

        # 取消所有任务
        await self._cancel_all_tasks(timeout=2.0)

        self._servers.clear()
        self.logger.info("所有服务器已关闭")

    async def _cancel_all_tasks(self, timeout: float = 2.0):
        """取消所有注册的任务"""
        if not self._tasks:
            return

        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # 等待任务完成
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True), timeout=timeout
            )
        except asyncio.TimeoutError:
            self.logger.warning("任务取消超时")

    def is_shutting_down(self) -> bool:
        """检查是否正在关闭"""
        return self._is_shutting_down


class GracefulShutdownServer(Server):
    """支持优雅关闭的服务器"""

    def __init__(self, config: Config, manager: ServerManager):
        super().__init__(config)
        self.manager = manager
        self._setup_logger()

    def _setup_logger(self):
        """确保 logger 存在"""
        if not hasattr(self, "logger"):
            self.logger = get_logger("uvicorn.error")

    async def shutdown(self, sockets=None):
        """优雅关闭服务器"""
        self.logger.info("正在优雅关闭服务器...")

        # 设置关闭标志
        self.should_exit = True

        # 等待请求完成
        await asyncio.sleep(0.1)

        # 调用父类关闭
        try:
            await super().shutdown(sockets)
        except (asyncio.CancelledError, RuntimeError, GeneratorExit):
            # 这些是正常的关闭异常
            pass
        except Exception as e:
            self.logger.error(f"关闭时出错: {e}")

    async def serve(self, sockets=None):
        """运行服务器"""
        try:
            await super().serve(sockets)
        except (asyncio.CancelledError, KeyboardInterrupt):
            # 正常退出
            pass
        except Exception as e:
            self.logger.error(f"服务器错误: {e}")
            raise
        finally:
            # 确保清理
            try:
                await self.shutdown(sockets)
            except Exception:
                self.logger.debug("关闭服务器时忽略了异常", exc_info=True)


class WindowsEventLoopPolicy(WindowsEventLoopPolicyBase):
    """Windows 平台的事件循环策略"""

    def new_event_loop(self):
        """创建新的事件循环"""
        loop = super().new_event_loop()

        # 设置异常处理器
        def exception_handler(loop, context):
            exception = context.get("exception")
            message = context.get("message", "")

            # 过滤无害的异常
            if self._should_ignore_exception(exception, message, context):
                return

            # 其他异常正常处理
            loop.default_exception_handler(context)

        loop.set_exception_handler(exception_handler)
        return loop

    def _should_ignore_exception(self, exception, message, context):
        """判断是否应该忽略异常"""
        # 关闭时的错误
        if isinstance(exception, (RuntimeError, OSError)):
            if "Event loop is closed" in str(exception):
                return True

        # 任务被销毁
        if "Task was destroyed but it is pending" in message:
            return True

        # 正常的取消
        if isinstance(exception, (asyncio.CancelledError, GeneratorExit)):
            return True

        # Lifespan 相关
        if "lifespan" in str(context.get("task", "")):
            return True

        # Starlette 路由错误
        if "starlette.routing" in str(exception):
            return True

        return False


# 全局服务器管理器实例
_server_manager: Optional[ServerManager] = None


def get_server_manager() -> ServerManager:
    """获取全局服务器管理器实例"""
    global _server_manager
    if _server_manager is None:
        _server_manager = ServerManager()
        _server_manager.setup_platform_specific()
    return _server_manager


@asynccontextmanager
async def managed_lifespan(app: ASGIApp) -> AsyncIterator[None]:
    """
    统一的 lifespan 管理器

    处理应用的启动和关闭，包括异常处理。
    """
    manager = get_server_manager()

    try:
        # 启动逻辑
        yield
    except GeneratorExit:
        # 正常的生成器退出
        pass
    except asyncio.CancelledError:
        # 任务被取消
        pass
    finally:
        # 清理逻辑
        if not manager.is_shutting_down():
            await manager.shutdown_all()
