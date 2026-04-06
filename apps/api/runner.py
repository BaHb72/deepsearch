"""
WebUI 运行器

提供独立运行 WebUI 的功能，支持前端和后端的启动管理。
"""

# === Windows 控制台编码设置 ===
# 必须在导入其他模块之前设置,确保后续日志输出正确
import sys

if sys.platform == "win32":
    try:
        from core.core.utils.file_encoding import PlatformEncodingHelper

        # 设置控制台编码为 UTF-8,解决 Windows 控制台中文乱码问题
        PlatformEncodingHelper.setup_console_encoding(encoding="utf-8")
    except Exception as e:
        # 如果设置失败,记录错误但不影响启动
        # 此时无法使用 logger,因为还未初始化,使用 print
        print(f"Warning: Failed to setup console encoding: {e}", file=sys.stderr)
# === 编码设置结束 ===

import asyncio
import atexit
import json
import os
import signal
import subprocess  # nosec B404
import sys
import threading
import time
import urllib.error
import urllib.request
from ipaddress import ip_address
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from core.config import get_config
from core.core import MainEngine
from core.observability import get_logger
from core.observability.logger import logger_manager

if TYPE_CHECKING:
    from core.core.runtime.engine_context import EngineContext

from .server import app, set_engine
from .server_manager import get_server_manager


class WebUIRunner:
    """WebUI 运行管理器"""

    def __init__(
        self,
        start_frontend: bool = True,
        frontend_port: Optional[int] = None,
        backend_host: Optional[str] = None,
        backend_port: Optional[int] = None,
        auto_open_browser: bool = False,
    ):
        """
        初始化 WebUI 运行器

        Args:
            start_frontend: 是否启动前端开发服务器
            frontend_port: 前端端口，None 表示从配置读取
            backend_host: 后端地址，None 表示从配置读取
            backend_port: 后端端口，None 表示从配置读取
            auto_open_browser: 是否自动打开浏览器
        """
        self.logger = get_logger(__name__)
        self.start_frontend = start_frontend

        # 从配置读取端口
        config = get_config()
        self.frontend_port = frontend_port or config.webui.frontend_port
        self.backend_host = backend_host or config.webui.backend_host
        self.backend_port = backend_port or config.webui.backend_port
        self.auto_open_browser = auto_open_browser

        # 引擎和服务器实例
        self.engine: Optional[MainEngine] = None
        self._engine_context: Optional["EngineContext"] = None
        self.engine_thread: Optional[threading.Thread] = None
        self.frontend_process: Optional[subprocess.Popen] = None
        self.server_manager = get_server_manager()

        # 前端目录 - Monorepo 结构: apps/web/
        # 从 apps/api/runner.py 往上两级到项目根目录，再进入 apps/web
        self.frontend_dir = Path(__file__).parent.parent / "web"

        # 运行状态
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._backend_ready_timeout_seconds = 45.0
        self._backend_ready_probe_interval_seconds = 0.5

    def start_engine(self, infrastructure_only: bool = True) -> bool:
        """
        启动系统引擎（使用上下文管理器）

        Args:
            infrastructure_only: 是否只启动基础设施

        Returns:
            是否成功启动
        """
        if self._engine_context is not None and self.engine:
            self.logger.warning("引擎已在运行")
            return False

        try:
            from core.core.runtime.engine_context import EngineContext

            # 创建引擎上下文
            self._engine_context = EngineContext(
                mode="webui", config={"infrastructure_only": infrastructure_only}
            )

            # 进入上下文
            self.engine = self._engine_context.__enter__()

            # 设置引擎到应用
            set_engine(self.engine)

            self.logger.info("系统引擎已启动")
            return True

        except Exception as e:
            self.logger.error(f"启动引擎失败: {e}", exc_info=True)
            # 清理上下文
            if self._engine_context is not None:
                self._engine_context.__exit__(None, None, None)
                self._engine_context = None
            return False

    def stop_engine(self) -> bool:
        """停止系统引擎"""
        if not self.engine:
            return False

        try:
            # 使用上下文管理器的退出方法
            if self._engine_context is not None:
                self._engine_context.__exit__(None, None, None)
                self._engine_context = None

            self.engine = None
            self.logger.info("系统引擎已停止")
            return True

        except Exception as e:
            self.logger.error(f"停止引擎失败: {e}", exc_info=True)
            return False

    def _start_frontend_server(self) -> bool:
        """启动前端开发服务器"""
        if not self.frontend_dir.exists():
            self.logger.error(f"前端目录不存在: {self.frontend_dir}")
            return False

        try:
            # 检查 node_modules
            node_modules = self.frontend_dir / "node_modules"
            if not node_modules.exists():
                print("正在安装前端依赖...")
                result = subprocess.run(
                    "npm install",
                    cwd=str(self.frontend_dir),
                    capture_output=True,
                    text=True,
                    shell=True,  # Windows 需要 shell=True 来解析 npm.cmd
                )  # nosec B602 B603 B607
                if result.returncode != 0:
                    self.logger.error(f"安装依赖失败: {result.stderr}")
                    return False

            # 启动前端服务
            print(f"启动前端服务 (端口: {self.frontend_port})...")
            env = os.environ.copy()
            env["PORT"] = str(self.frontend_port)
            backend_host = self._backend_display_host()
            env["VITE_PROXY_TARGET"] = f"http://{backend_host}:{self.backend_port}"
            env["VITE_WS_PROXY_TARGET"] = f"ws://{backend_host}:{self.backend_port}"

            if sys.platform == "win32":
                self.frontend_process = subprocess.Popen(
                    "npm run dev",
                    cwd=str(self.frontend_dir),
                    env=env,
                    shell=True,  # Windows 需要 shell=True 来解析 npm.cmd
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )  # nosec B602 B603 B607
            else:
                self.frontend_process = subprocess.Popen(
                    ["npm", "run", "dev"], cwd=str(self.frontend_dir), env=env  # nosec B603 B607
                )

            # 注册到 ProcessManager
            from core.core.managers.process_manager import process_manager

            process_manager.register_process(self.frontend_process, name="WebUI-Frontend-Dev")

            # 等待启动
            time.sleep(3)
            if self.frontend_process.poll() is None:
                print(f"[OK] Frontend service started: http://localhost:{self.frontend_port}")
                return True
            else:
                self.logger.error("前端服务启动失败")
                return False

        except Exception as e:
            self.logger.error(f"启动前端失败: {e}")
            return False

    def _stop_frontend_server(self):
        """停止前端服务"""
        if self.frontend_process:
            try:
                termination_timeout = 5 if sys.platform == "win32" else 3
                if sys.platform == "win32":
                    try:
                        import psutil as _psutil
                    except ImportError:
                        _psutil = None
                        self.logger.debug("未安装 psutil，回退到 Popen 接口终止前端进程")
                    if _psutil is not None:
                        try:
                            proc = _psutil.Process(self.frontend_process.pid)
                            children = proc.children(recursive=True)
                            for child in children:
                                try:
                                    child.terminate()
                                except _psutil.Error:
                                    self.logger.debug("终止前端子进程失败", exc_info=True)
                            _, alive = _psutil.wait_procs(children, timeout=3)
                            for stubborn in alive:
                                try:
                                    stubborn.kill()
                                except _psutil.Error:
                                    self.logger.debug("强制终止子进程失败", exc_info=True)
                        except _psutil.NoSuchProcess:
                            self.logger.debug("前端进程在终止前已退出")
                        except _psutil.Error:
                            self.logger.warning(
                                "使用 psutil 处理前端进程失败，将改用 Popen 接口",
                                exc_info=True,
                            )
                self.frontend_process.terminate()
                try:
                    self.frontend_process.wait(timeout=termination_timeout)
                except subprocess.TimeoutExpired:
                    self.logger.warning("终止前端进程超时，尝试强制关闭")
                    try:
                        self.frontend_process.kill()
                    except (OSError, ProcessLookupError):
                        self.logger.debug("强制关闭前端进程失败，可能已退出", exc_info=True)
                except (OSError, ProcessLookupError):
                    self.logger.debug("前端进程可能已经结束", exc_info=True)
                self.frontend_process = None
                self.logger.info("前端服务已停止")
            except Exception as e:
                self.logger.error(f"停止前端失败: {e}")

    async def _run_backend_server(self):
        """运行后端服务器"""
        try:
            # 检查端口是否已经被占用
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            check_host = self._resolve_check_host()
            result = sock.connect_ex((check_host, self.backend_port))
            sock.close()

            if result == 0:
                # 端口已经被占用，报错退出
                self.logger.error(f"端口 {self.backend_port} 已被占用")

                # 尝试获取占用进程信息
                try:
                    import psutil

                    for conn in psutil.net_connections():
                        if (
                            hasattr(conn, "laddr")
                            and conn.laddr.port == self.backend_port
                            and conn.status == "LISTEN"
                        ):
                            try:
                                proc = psutil.Process(conn.pid)
                                self.logger.error(f"占用进程: {proc.name()} (PID: {conn.pid})")
                            except Exception:
                                self.logger.error(f"占用进程 PID: {conn.pid}")
                            break
                except Exception:
                    self.logger.debug("无法获取占用端口的进程信息", exc_info=True)

                raise RuntimeError(
                    f"端口 {self.backend_port} 已被占用。请执行以下操作之一：\n"
                    f"  1. 运行 'python -m deepsearch cleanup' 清理端口\n"
                    f"  2. 停止占用端口的进程\n"
                    f"  3. 修改配置文件中的 webui.backend_port"
                )
            else:
                # 端口未被占用，启动服务器
                await self.server_manager.start_server(
                    app,
                    name="webui",
                    host=self.backend_host,
                    port=self.backend_port,
                    log_level="info",
                )
                display_host = self._backend_display_host()
                print(f"[OK] Backend service started: http://{display_host}:{self.backend_port}")
                ready = await self._wait_backend_ready()
                if not ready:
                    raise RuntimeError(
                        f"后端在 {self._backend_ready_timeout_seconds:.0f}s 内未就绪，已停止前端启动。"
                    )

                if self.start_frontend and not self._start_frontend_server():
                    raise RuntimeError("前端服务启动失败")

            # 自动打开浏览器
            if self.auto_open_browser:
                import webbrowser

                display_host = self._backend_display_host()
                if self.start_frontend:
                    url = f"http://localhost:{self.frontend_port}"
                else:
                    url = f"http://{display_host}:{self.backend_port}"
                webbrowser.open(url)

            # 等待关闭信号
            await self._shutdown_event.wait()

        except Exception as e:
            self.logger.error(f"后端服务器错误: {e}")
            raise
        finally:
            await self.server_manager.shutdown_all()

    def run(self):
        """运行 WebUI 系统"""
        self._running = True

        # 打印启动信息
        self._print_startup_info()

        # 设置信号处理
        self._setup_signal_handlers()

        try:
            # 运行后端服务器；后端就绪后再启动前端
            asyncio.run(self._run_backend_server())

        except KeyboardInterrupt:
            print("\n正在关闭...")
        except Exception as e:
            self.logger.error(f"运行错误: {e}")
        finally:
            self.shutdown()

    def shutdown(self):
        """关闭系统"""
        self._running = False
        self._shutdown_event.set()

        print("\n正在关闭系统...")

        # 停止引擎
        if self.engine:
            self.stop_engine()

        # 停止前端
        if self.frontend_process:
            self._stop_frontend_server()

        # 使用 ProcessManager 进行全面清理
        from core.core.managers.process_manager import process_manager

        process_manager.shutdown(timeout=10.0, force=sys.platform == "win32")

        print("系统已关闭")

    def _backend_display_host(self) -> str:
        """获取用于展示的后端地址"""
        try:
            ip_obj = ip_address(self.backend_host)
        except ValueError:
            return self.backend_host

        if ip_obj.is_unspecified:
            return "127.0.0.1"
        return self.backend_host

    def _resolve_check_host(self) -> str:
        """获取用于端口检测的主机名"""
        try:
            ip_obj = ip_address(self.backend_host)
        except ValueError:
            return self.backend_host

        if ip_obj.is_unspecified:
            return "127.0.0.1"
        return str(ip_obj)

    def _backend_status_probe_url(self) -> str:
        display_host = self._backend_display_host()
        return f"http://{display_host}:{self.backend_port}/api/system/status"

    def _probe_backend_ready_once(self) -> tuple[bool, str]:
        url = self._backend_status_probe_url()
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if response.status != 200:
                    return False, f"http-{response.status}"
                payload_bytes = response.read()
                if not payload_bytes:
                    return True, "ok-empty"
                payload = json.loads(payload_bytes.decode("utf-8", errors="ignore"))
                if isinstance(payload, dict) and payload.get("ready") is False:
                    # /api/system/status.ready 表示市场数据链路是否完全就绪，
                    # 不是后端 HTTP 服务可用性的硬门槛；此处仅要求后端可访问。
                    return True, "ok-market-not-ready"
                return True, "ok"
        except urllib.error.HTTPError as exc:
            return False, f"http-{exc.code}"
        except urllib.error.URLError as exc:
            return False, f"url-error:{exc.reason}"
        except TimeoutError:
            return False, "timeout"
        except Exception as exc:  # pragma: no cover - 防御式兜底
            return False, f"error:{exc}"

    async def _wait_backend_ready(self) -> bool:
        timeout = self._backend_ready_timeout_seconds
        interval = self._backend_ready_probe_interval_seconds
        started_at = time.monotonic()
        attempts = 0
        last_reason = ""
        probe_url = self._backend_status_probe_url()
        self.logger.info(f"等待后端就绪: {probe_url} (timeout={timeout:.1f}s)")

        while time.monotonic() - started_at < timeout:
            attempts += 1
            ready, reason = await asyncio.to_thread(self._probe_backend_ready_once)
            if ready:
                elapsed = time.monotonic() - started_at
                self.logger.info(
                    f"后端已就绪: {probe_url} (attempts={attempts} elapsed={elapsed:.2f}s)"
                )
                return True

            if reason != last_reason:
                self.logger.debug(f"后端尚未就绪: {probe_url} (reason={reason})")
                last_reason = reason
            await asyncio.sleep(interval)

        self.logger.error(
            f"后端就绪等待超时: {probe_url} (timeout={timeout:.1f}s last_reason={last_reason or 'unknown'})"
        )
        return False

    def _print_startup_info(self):
        """打印启动信息"""
        print("\n" + "=" * 60)
        print("  DeepSearch WebUI")
        print("=" * 60)
        print(f"  后端地址: http://{self._backend_display_host()}:{self.backend_port}")
        if self.start_frontend:
            print(f"  前端地址: http://localhost:{self.frontend_port}")
        print("  按 Ctrl+C 退出")
        print("=" * 60 + "\n")

    def _setup_signal_handlers(self):
        """设置信号处理器"""
        self._signal_count = 0

        def signal_handler(signum, frame):
            self._signal_count += 1
            if self._signal_count == 1:
                print("\n收到退出信号，正在优雅关闭...")
                # 只设置关闭事件，让事件循环自然退出
                # 不要调用 sys.exit()，否则会绕过 asyncio 的清理机制
                self._shutdown_event.set()
            elif self._signal_count >= 2:
                # 第二次 Ctrl+C: 强制退出
                print("\n强制退出...")
                # 先尝试清理关键资源
                try:
                    self._stop_frontend_server()
                except Exception:
                    pass
                os._exit(1)

        signal.signal(signal.SIGINT, signal_handler)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, signal_handler)
        # Windows上注册atexit处理器作为备份
        atexit.register(self.shutdown)


def run_standalone(
    start_frontend: bool = True,
    frontend_port: Optional[int] = None,
    backend_host: Optional[str] = None,
    backend_port: Optional[int] = None,
    auto_open_browser: bool = False,
    start_engine: bool = True,
    infrastructure_only: bool = True,
):
    """
    独立运行 WebUI

    Args:
        start_frontend: 是否启动前端
        frontend_port: 前端端口，None 表示从配置读取
        backend_host: 后端地址，None 表示从配置读取
        backend_port: 后端端口，None 表示从配置读取
        auto_open_browser: 是否自动打开浏览器
        start_engine: 是否启动引擎
        infrastructure_only: 是否只启动基础设施
    """
    # 确保日志系统已启动
    logger_manager.start()

    # 创建运行器
    runner = WebUIRunner(
        start_frontend=start_frontend,
        frontend_port=frontend_port,
        backend_host=backend_host,
        backend_port=backend_port,
        auto_open_browser=auto_open_browser,
    )

    # 启动引擎（如果需要）
    if start_engine:
        runner.start_engine(infrastructure_only=infrastructure_only)

    # 运行系统
    runner.run()


if __name__ == "__main__":
    import warnings

    warnings.warn(
        "直接运行 runner.py 已废弃，请使用: uv run deepsearch run --mode webui",
        DeprecationWarning,
        stacklevel=1,
    )
    run_standalone()
