#!/usr/bin/env python3
"""
DeepSearch WebUI 独立启动脚本（已废弃）

此脚本已被新的 CLI 接口替代，请使用：
  python -m deepsearch webui

保留此文件仅为向后兼容。
"""
import asyncio
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Optional

from deepsearch.core import MainEngine
from deepsearch.observability import get_logger
from deepsearch.observability.logger import logger_manager
from deepsearch.webui.server_manager import get_server_manager


class StandaloneWebUIManager:
    """独立的WebUI管理器"""

    def __init__(self):
        # 初始化日志
        logger_manager.start()
        self.logger = get_logger(__name__)

        # 系统引擎实例（可以为空，通过WebUI启动）
        self.engine: Optional[MainEngine] = None
        self.engine_thread: Optional[threading.Thread] = None

        # WebUI服务器
        self.webui_server = None
        self.frontend_process = None

        # 前端目录
        self.frontend_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "deepsearch",
            "webui",
            "frontend",
        )

        # 运行标志
        self._running = True

    def start_engine(self) -> bool:
        """启动系统引擎（由WebUI调用）"""
        if self.engine and self.engine.is_running():
            self.logger.warning("引擎已经在运行")
            return False

        try:
            # 创建新的引擎实例
            self.engine = MainEngine()
            self.engine.initialize()

            # 在独立线程中启动引擎
            def run_engine():
                try:
                    # 只启动基础设施，业务组件通过WebUI控制
                    self.engine.start_infrastructure()
                    # 保持引擎运行
                    while self.engine.is_running():
                        time.sleep(1)
                except Exception as e:
                    self.logger.error(f"引擎运行错误: {e}", exc_info=True)

            self.engine_thread = threading.Thread(target=run_engine, daemon=True)
            self.engine_thread.start()

            self.logger.info("系统引擎已启动")
            return True

        except Exception as e:
            self.logger.error(f"启动引擎失败: {e}", exc_info=True)
            return False

    def stop_engine(self) -> bool:
        """停止系统引擎（由WebUI调用）"""
        if not self.engine:
            self.logger.warning("引擎未运行")
            return False

        try:
            self.engine.stop()
            if self.engine_thread:
                self.engine_thread.join(timeout=5)
            self.engine = None
            self.engine_thread = None
            self.logger.info("系统引擎已停止")
            return True

        except Exception as e:
            self.logger.error(f"停止引擎失败: {e}", exc_info=True)
            return False

    def start_frontend(self):
        """启动前端开发服务器"""
        if not os.path.exists(self.frontend_dir):
            self.logger.error(f"前端目录不存在: {self.frontend_dir}")
            return False

        try:
            # 检查依赖
            node_modules = os.path.join(self.frontend_dir, "node_modules")
            if not os.path.exists(node_modules):
                print("安装前端依赖...")
                subprocess.run(["npm", "install"], cwd=self.frontend_dir, check=True)

            # 启动前端
            print("启动前端服务...")
            if sys.platform == "win32":
                self.frontend_process = subprocess.Popen(
                    f'cd /d "{self.frontend_dir}" && npm run dev',
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:
                self.frontend_process = subprocess.Popen(
                    ["npm", "run", "dev"], cwd=self.frontend_dir
                )

            time.sleep(3)
            if self.frontend_process.poll() is None:
                print("前端服务已启动: http://localhost:3000")
                return True
            else:
                self.logger.error("前端服务启动失败")
                return False

        except Exception as e:
            self.logger.error(f"启动前端失败: {e}")
            return False

    def stop_frontend(self):
        """停止前端服务"""
        if self.frontend_process:
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.frontend_process.pid)],
                        capture_output=True,
                    )
                else:
                    self.frontend_process.terminate()
                    self.frontend_process.wait(timeout=3)
            except Exception as e:
                self.logger.error(f"停止前端失败: {e}")

    async def run_webui_server(self):
        """运行WebUI后端服务器"""
        from deepsearch.webui.server import app

        # 设置管理器引用
        app.state.manager = self

        # 使用服务器管理器
        server_manager = get_server_manager()

        try:
            # 启动服务器
            self.webui_server = await server_manager.start_server(
                app, name="webui", host="0.0.0.0", port=8000, log_level="info"
            )

            # 等待关闭
            await server_manager._shutdown_event.wait()

        except (asyncio.CancelledError, KeyboardInterrupt):
            # 正常退出
            pass
        except Exception as e:
            self.logger.error(f"服务器错误: {e}")
        finally:
            # 关闭所有服务器
            await server_manager.shutdown_all()

    def run(self):
        """运行WebUI系统"""
        print("\n" + "=" * 60)
        print("  DeepSearch WebUI 独立模式")
        print("=" * 60)

        # 启动前端
        self.start_frontend()

        # 启动后端
        print("\n启动WebUI后端服务...")

        # 设置信号处理
        def signal_handler(signum, frame):
            print("\n收到退出信号...")
            self._running = False
            if self.webui_server:
                self.webui_server.should_exit = True

        signal.signal(signal.SIGINT, signal_handler)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, signal_handler)

        try:
            # 运行WebUI服务器
            asyncio.run(self.run_webui_server())

        except KeyboardInterrupt:
            print("\n正在关闭...")
        except Exception as e:
            self.logger.error(f"运行错误: {e}")
        finally:
            self.shutdown()

    def shutdown(self):
        """关闭整个系统"""
        print("\n关闭系统...")

        # 停止引擎（如果在运行）
        if self.engine:
            self.stop_engine()

        # 停止前端
        self.stop_frontend()

        # 停止日志
        logger_manager.stop()

        print("系统已关闭\n")


def main():
    """主函数"""
    print("DeepSearch WebUI - 独立控制面板")
    print("-" * 60)
    print("提示：")
    print("  - WebUI地址: http://localhost:8000")
    print("  - 前端地址: http://localhost:3000")
    print("  - 通过Web界面控制系统启动/停止")
    print("  - 按 Ctrl+C 完全退出")
    print("-" * 60 + "\n")

    manager = StandaloneWebUIManager()
    manager.run()


if __name__ == "__main__":
    import warnings

    warnings.warn(
        "webui_standalone.py 已废弃，请使用 'python -m deepsearch webui' 命令",
        DeprecationWarning,
        stacklevel=2,
    )
    main()
