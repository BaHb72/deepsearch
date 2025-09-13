"""
WebUI 运行器

提供独立运行 WebUI 的功能，支持前端和后端的启动管理。
"""
import asyncio
import atexit
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from deepsearch.config import get_config
from deepsearch.core import MainEngine
from deepsearch.observability.logger import logger_manager
from .server import app, set_engine
from .server_manager import get_server_manager


class WebUIRunner:
    """WebUI 运行管理器"""

    def __init__(self,
                 start_frontend: bool = True,
                 frontend_port: Optional[int] = None,
                 backend_port: Optional[int] = None,
                 auto_open_browser: bool = False):
        """
        初始化 WebUI 运行器
        
        Args:
            start_frontend: 是否启动前端开发服务器
            frontend_port: 前端端口，None 表示从配置读取
            backend_port: 后端端口，None 表示从配置读取
            auto_open_browser: 是否自动打开浏览器
        """
        self.logger = logging.getLogger(__name__)
        self.start_frontend = start_frontend

        # 从配置读取端口
        config = get_config()
        self.frontend_port = frontend_port or config.webui.frontend_port
        self.backend_port = backend_port or config.webui.backend_port
        self.auto_open_browser = auto_open_browser

        # 引擎和服务器实例
        self.engine: Optional[MainEngine] = None
        self.engine_thread: Optional[threading.Thread] = None
        self.frontend_process: Optional[subprocess.Popen] = None
        self.server_manager = get_server_manager()

        # 前端目录
        self.frontend_dir = Path(__file__).parent / "frontend"

        # 运行状态
        self._running = False
        self._shutdown_event = asyncio.Event()

    def start_engine(self, infrastructure_only: bool = True) -> bool:
        """
        启动系统引擎（使用上下文管理器）
        
        Args:
            infrastructure_only: 是否只启动基础设施
            
        Returns:
            是否成功启动
        """
        if hasattr(self, '_engine_context') and self.engine:
            self.logger.warning("引擎已在运行")
            return False

        try:
            from deepsearch.core.runtime.engine_context import EngineContext

            # 创建引擎上下文
            self._engine_context = EngineContext(
                mode='webui',
                config={'infrastructure_only': infrastructure_only}
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
            if hasattr(self, '_engine_context'):
                self._engine_context.__exit__(None, None, None)
                self._engine_context = None
            return False

    def stop_engine(self) -> bool:
        """停止系统引擎"""
        if not self.engine:
            return False

        try:
            # 使用上下文管理器的退出方法
            if hasattr(self, '_engine_context'):
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
                    ["npm", "install"],
                    cwd=str(self.frontend_dir),
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    self.logger.error(f"安装依赖失败: {result.stderr}")
                    return False

            # 启动前端服务
            print(f"启动前端服务 (端口: {self.frontend_port})...")
            env = os.environ.copy()
            env["PORT"] = str(self.frontend_port)

            if sys.platform == "win32":
                self.frontend_process = subprocess.Popen(
                    f'cd /d "{self.frontend_dir}" && npm run dev',
                    shell=True,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                self.frontend_process = subprocess.Popen(
                    ["npm", "run", "dev"],
                    cwd=str(self.frontend_dir),
                    env=env
                )

            # 注册到 ProcessManager
            from deepsearch.core.managers.process_manager import process_manager
            process_manager.register_process(
                self.frontend_process,
                name="WebUI-Frontend-Dev"
            )

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
                if sys.platform == "win32":
                    # Windows上使用taskkill强制终止进程树
                    result = subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.frontend_process.pid)],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        # 如果taskkill失败，尝试直接终止
                        try:
                            self.frontend_process.terminate()
                        except (OSError, ProcessLookupError) as e:
                            logger.debug(f"前端进程可能已经终止: {e}")
                else:
                    self.frontend_process.terminate()
                    self.frontend_process.wait(timeout=3)
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
            result = sock.connect_ex(('localhost', self.backend_port))
            sock.close()

            if result == 0:
                # 端口已经被占用，报错退出
                self.logger.error(f"端口 {self.backend_port} 已被占用")

                # 尝试获取占用进程信息
                try:
                    import psutil
                    for conn in psutil.net_connections():
                        if hasattr(conn, 'laddr') and conn.laddr.port == self.backend_port and conn.status == 'LISTEN':
                            try:
                                proc = psutil.Process(conn.pid)
                                self.logger.error(f"占用进程: {proc.name()} (PID: {conn.pid})")
                            except:
                                self.logger.error(f"占用进程 PID: {conn.pid}")
                            break
                except:
                    pass

                raise RuntimeError(
                    f"端口 {self.backend_port} 已被占用。请执行以下操作之一：\n"
                    f"  1. 运行 'python -m deepsearch cleanup' 清理端口\n"
                    f"  2. 停止占用端口的进程\n"
                    f"  3. 修改配置文件中的 webui.backend_port"
                )
            else:
                # 端口未被占用，启动服务器
                server = await self.server_manager.start_server(
                    app,
                    name="webui",
                    host="0.0.0.0",
                    port=self.backend_port,
                    log_level="info"
                )
                print(f"[OK] Backend service started: http://localhost:{self.backend_port}")

            # 自动打开浏览器
            if self.auto_open_browser:
                import webbrowser
                url = f"http://localhost:{self.frontend_port if self.start_frontend else self.backend_port}"
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
            # 启动前端（如果需要）
            if self.start_frontend:
                self._start_frontend_server()

            # 运行后端服务器
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
        from deepsearch.core.managers.process_manager import process_manager
        process_manager.shutdown(timeout=10.0, force=sys.platform == "win32")

        print("系统已关闭")

    def _print_startup_info(self):
        """打印启动信息"""
        print("\n" + "=" * 60)
        print("  DeepSearch WebUI")
        print("=" * 60)
        print(f"  后端地址: http://localhost:{self.backend_port}")
        if self.start_frontend:
            print(f"  前端地址: http://localhost:{self.frontend_port}")
        print("  按 Ctrl+C 退出")
        print("=" * 60 + "\n")

    def _setup_signal_handlers(self):
        """设置信号处理器"""

        def signal_handler(signum, frame):
            print("\n收到退出信号...")
            self._running = False
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, signal_handler)
        else:
            # Windows上注册atexit处理器
            atexit.register(self.shutdown)



def run_standalone(
        start_frontend: bool = True,
        frontend_port: Optional[int] = None,
        backend_port: Optional[int] = None,
        auto_open_browser: bool = False,
        start_engine: bool = True,
        infrastructure_only: bool = True
):
    """
    独立运行 WebUI
    
    Args:
        start_frontend: 是否启动前端
        frontend_port: 前端端口，None 表示从配置读取
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
        backend_port=backend_port,
        auto_open_browser=auto_open_browser
    )

    # 启动引擎（如果需要）
    if start_engine:
        runner.start_engine(infrastructure_only=infrastructure_only)

    # 运行系统
    runner.run()


if __name__ == "__main__":
    # 测试独立运行
    run_standalone()
