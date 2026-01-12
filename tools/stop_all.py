#!/usr/bin/env python3
"""
停止所有DeepSearch进程
"""
import sys

import psutil


def stop_all_deepsearch():
    """停止所有DeepSearch相关进程"""
    print("正在查找DeepSearch相关进程...")

    killed_count = 0

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            # 检查是否是Python进程
            if proc.info["name"] and "python" in proc.info["name"].lower():
                # 检查命令行参数是否包含main.py
                cmdline = proc.info.get("cmdline")
                if cmdline and any("main.py" in arg for arg in cmdline):
                    print(f"发现进程 PID: {proc.info['pid']}")
                    print(f"  命令行: {' '.join(cmdline)}")

                    # 终止进程
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                        print("  ✓ 已终止")
                        killed_count += 1
                    except psutil.TimeoutExpired:
                        proc.kill()
                        print("  ✓ 已强制终止")
                        killed_count += 1
                    except Exception as e:
                        print(f"  ✗ 终止失败: {e}")

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if killed_count > 0:
        print(f"\n成功终止 {killed_count} 个进程")
    else:
        print("\n没有找到运行中的DeepSearch进程")

    # 检查端口是否已释放
    print("\n检查8000端口...")
    for conn in psutil.net_connections():
        if conn.laddr.port == 8000 and conn.status == "LISTEN":
            print(f"警告: 端口8000仍被占用 (PID: {conn.pid})")
            return False

    print("端口8000已释放")
    return True


if __name__ == "__main__":
    if stop_all_deepsearch():
        print("\n清理完成! 现在可以重新启动系统了。")
        sys.exit(0)
    else:
        print("\n清理可能未完成，请稍后再试。")
        sys.exit(1)
