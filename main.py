#!/usr/bin/env python3
"""
DeepSearch - 量化交易系统统一入口

使用方法:
  python main.py          # 默认模式：启动完整系统（引擎+WebUI）
  python main.py --webui  # WebUI模式：仅启动WebUI，通过界面控制引擎
  python main.py --engine # 引擎模式：仅启动引擎，不启动WebUI
  python main.py --help   # 显示帮助信息
"""
import atexit
import logging
import os
import signal
import subprocess
import sys
import threading
import time

import argparse

from deepsearch.constants import EVENT_SYSTEM_READY, EVENT_TICK, EVENT_ORDER, EVENT_TRADE
from deepsearch.core import MainEngine
from deepsearch.observability.logger_config import setup_hierarchical_logging


def setup_default_handlers(engine: MainEngine) -> None:
    """
    设置默认的事件处理器
    
    这些是示例处理器，实际使用时应该根据需求替换
    """
    logger = logging.getLogger(__name__)

    # 示例处理器
    def handle_system_ready(event):
        logger.info("System ready event received")
    
    def handle_tick(event):
        logger.debug(f"Tick event: {event.data}")
    
    def handle_order(event):
        logger.info(f"Order event: {event.data}")
    
    def handle_trade(event):
        logger.info(f"Trade event: {event.data}")

    # 注册处理器
    handlers = {
        EVENT_SYSTEM_READY: handle_system_ready,
        EVENT_TICK: handle_tick,
        EVENT_ORDER: handle_order,
        EVENT_TRADE: handle_trade,
    }

    engine.register_handlers(handlers)

    # 对于需要异步处理的事件，单独注册
    engine.register_handler(EVENT_TICK, handle_tick, async_flag=True)


class ViteFrontendManager:
    """管理Vite前端服务"""

    def __init__(self):
        self.process = None
        self.frontend_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "deepsearch", "webui", "frontend"
        )
        self.logger = setup_hierarchical_logging().bind(name="前端服务")

    def start(self):
        """启动前端服务"""
        if not os.path.exists(self.frontend_dir):
            self.logger.error(f"前端目录不存在: {self.frontend_dir}")
            return False

        try:
            # 检查是否安装了依赖
            node_modules = os.path.join(self.frontend_dir, "node_modules")
            if not os.path.exists(node_modules):
                print("  前端依赖未安装，正在安装 (npm install)...")
                result = subprocess.run(["npm", "install"], cwd=self.frontend_dir, capture_output=True)
                if result.returncode != 0:
                    self.logger.error("前端依赖安装失败")
                    return False
                print("  前端依赖安装完成")

            # 启动vite服务
            print("  启动前端开发服务器...")
            # 使用shell=True以确保在Windows上正确运行
            if sys.platform == "win32":
                # Windows: 使用cmd /c
                self.process = subprocess.Popen(
                    f'cd /d "{self.frontend_dir}" && npm run dev',
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                self.process = subprocess.Popen(
                    ["npm", "run", "dev"],
                    cwd=self.frontend_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

            # 等待服务启动
            print("  等待前端服务启动...")
            time.sleep(5)  # 给更多时间启动

            if self.process.poll() is None:
                print("  前端服务已启动 (http://localhost:3000)")
                # 将输出设置为非阻塞模式，避免阻塞主线程
                return True
            else:
                # 读取错误输出
                stdout, stderr = self.process.communicate()
                if stdout:
                    self.logger.error(f"前端服务输出: {stdout.decode('utf-8', errors='ignore')}")
                if stderr:
                    self.logger.error(f"前端服务错误: {stderr.decode('utf-8', errors='ignore')}")
                self.logger.error("前端服务启动失败")
                return False

        except Exception as e:
            self.logger.error(f"启动前端服务失败: {e}")
            return False

    def stop(self):
        """停止前端服务"""
        if self.process:
            try:
                if sys.platform == "win32":
                    # Windows上使用taskkill，确保终止所有子进程
                    # 首先尝试正常终止
                    result = subprocess.run(
                        ["taskkill", "/T", "/PID", str(self.process.pid)],
                        capture_output=True,
                        text=True
                    )
                    # 如果正常终止失败，强制终止
                    if result.returncode != 0:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(self.process.pid)],
                            capture_output=True
                        )
                    # 等待进程结束
                    self.process.wait(timeout=3)
                else:
                    # Unix系统
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait()
                self.process = None
            except Exception as e:
                self.logger.error(f"停止前端服务失败: {e}")
                if self.process:
                    try:
                        self.process.kill()
                        self.process = None
                    except:
                        pass


class SystemManager:
    """系统管理器，统一管理后端和前端"""

    def __init__(self):
        self.engine = None
        self.frontend = ViteFrontendManager()
        self.logger = setup_hierarchical_logging().bind(name="系统管理")
        self._shutdown_event = threading.Event()
        self._running = False

    def start(self):
        """启动整个系统"""
        try:
            # 创建核心引擎
            self.engine = MainEngine()

            # 初始化系统
            self.engine.initialize()

            # 注册默认处理器
            setup_default_handlers(self.engine)

            # 启动基础设施组件
            self.engine.start_infrastructure()

            # 启动前端服务
            self.frontend.start()

            self._running = True

            # 显示启动信息
            print("\n" + "=" * 60)
            print("  DeepSearch 量化交易系统启动成功")
            print("=" * 60)
            print("  后端API: http://localhost:8000")
            print("  前端界面: http://localhost:3000")
            print("-" * 60)
            print("  提示: 业务组件需要通过WebUI界面手动启动")
            print("  按 Ctrl+C 退出系统")
            print("=" * 60 + "\n")

        except Exception as e:
            self.logger.error(f"系统启动失败: {e}", exc_info=True)
            self.stop()
            raise

    def wait(self):
        """等待系统运行"""
        try:
            while self._running and not self._shutdown_event.is_set():
                self._shutdown_event.wait(1)
        except KeyboardInterrupt:
            print("\n\n收到退出信号 (Ctrl+C)")

    def stop(self):
        """停止整个系统"""
        if not self._running:
            return

        self._running = False
        self._shutdown_event.set()

        print("\n" + "-" * 60)
        print("  正在关闭系统...")
        print("-" * 60)

        # 1. 先停止前端（避免前端还在访问后端）
        print("  [1/2] 停止前端服务...")
        self.frontend.stop()

        # 2. 再停止后端
        if self.engine:
            print("  [2/2] 停止后端服务...")
            try:
                self.engine.stop()
            except Exception as e:
                self.logger.error(f"停止引擎时出错: {e}")

        print("-" * 60)
        print("  系统已完全关闭")
        print("=" * 60 + "\n")


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="DeepSearch 量化交易系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
启动模式说明:
  默认模式: 同时启动交易引擎和WebUI
  WebUI模式: 仅启动WebUI，可通过界面控制引擎
  引擎模式: 仅启动引擎，适合无界面服务器

示例:
  python main.py              # 启动完整系统
  python main.py --webui      # 仅启动WebUI
  python main.py --engine     # 仅启动引擎
        """
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--webui',
        action='store_true',
        help='仅启动WebUI控制面板'
    )
    mode_group.add_argument(
        '--engine',
        action='store_true',
        help='仅启动交易引擎（无界面）'
    )

    return parser.parse_args()


def run_webui_mode():
    """运行WebUI模式"""
    # 导入独立WebUI管理器
    from tools.webui_standalone import StandaloneWebUIManager

    print("\n" + "=" * 60)
    print("  DeepSearch - WebUI独立模式")
    print("=" * 60)
    print("  - WebUI地址: http://localhost:3000")
    print("  - API地址: http://localhost:8000")
    print("  - 通过界面控制引擎启停")
    print("  - 按 Ctrl+C 退出")
    print("=" * 60 + "\n")

    manager = StandaloneWebUIManager()
    manager.run()


def run_engine_mode():
    """运行引擎模式"""
    print("\n" + "=" * 60)
    print("  DeepSearch - 引擎模式（无界面）")
    print("=" * 60)

    engine = MainEngine()

    def signal_handler(signum, frame):
        print(f"\n收到信号 {signum}，正在关闭引擎...")
        engine.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        engine.initialize()
        setup_default_handlers(engine)
        engine.start()

        print("  引擎已启动")
        print("  按 Ctrl+C 退出")
        print("=" * 60 + "\n")
        
        engine.run()
    except Exception as e:
        print(f"引擎启动失败: {e}", file=sys.stderr)
        return 1

    return 0


def run_full_mode():
    """运行完整模式（默认）"""
    manager = SystemManager()

    # 注册退出处理
    def cleanup():
        if manager._running:
            manager.stop()

    atexit.register(cleanup)

    # 设置信号处理
    def signal_handler(signum, frame):
        print(f"\n收到信号 {signum}，正在关闭系统...")
        manager._shutdown_event.set()
        manager.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        manager.start()
        manager.wait()
        manager.stop()
        return 0
    except Exception as e:
        print(f"系统错误: {e}", file=sys.stderr)
        manager.stop()
        return 1


def main() -> int:
    """主函数"""
    args = parse_args()

    if args.webui:
        run_webui_mode()
    elif args.engine:
        return run_engine_mode()
    else:
        return run_full_mode()

    return 0


if __name__ == "__main__":
    sys.exit(main())
