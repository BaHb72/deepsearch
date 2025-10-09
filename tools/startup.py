#!/usr/bin/env python3
"""
DeepSearch 系统启动脚本

该脚本会：
1. 检查并清理占用端口的旧进程
2. 启动后端和前端服务
3. 提供优雅的关闭机制
"""
import subprocess
import sys

import psutil


def cleanup_old_processes():
    """清理旧的进程和端口"""
    print("检查系统环境...")

    # 检查端口占用
    from deepsearch.config import get_config

    config = get_config()
    ports_to_check = [config.webui.backend_port, config.webui.frontend_port]  # 后端和前端端口

    for port in ports_to_check:
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == "LISTEN":
                pid = conn.pid
                if pid:
                    try:
                        proc = psutil.Process(pid)
                        proc_name = proc.name()
                        print(f"  发现端口 {port} 被进程 {proc_name} (PID={pid}) 占用")

                        # 如果是Python或Node进程，尝试终止
                        if "python" in proc_name.lower() or "node" in proc_name.lower():
                            print(f"  终止进程 PID={pid}...")
                            proc.terminate()
                            proc.wait(timeout=3)
                            print(f"  端口 {port} 已释放")
                    except Exception as e:
                        print(f"  警告: 无法终止进程 - {e}")


def main():
    """主函数"""
    print("=" * 60)
    print("  DeepSearch 量化交易系统")
    print("=" * 60)

    # 清理旧进程
    cleanup_old_processes()

    # 启动系统
    print("\n启动系统...")
    try:
        # 使用Python执行main.py
        subprocess.run([sys.executable, "main.py"])
    except KeyboardInterrupt:
        print("\n系统已退出")
    except Exception as e:
        print(f"\n启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
