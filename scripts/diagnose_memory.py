import os
import sys
from datetime import datetime

import psutil


def get_process_memory_info():
    print(f"=== Memory Diagnosis {datetime.now()} ===")
    print(f"Total System Memory: {psutil.virtual_memory().total / 1024 / 1024:.2f} MB")
    print(f"Available Memory: {psutil.virtual_memory().available / 1024 / 1024:.2f} MB")
    print(f"Used Memory Percentage: {psutil.virtual_memory().percent}%")
    print("-" * 50)

    # 获取当前进程
    current_process = psutil.Process(os.getpid())
    print(
        f"Current Process (PID {current_process.pid}): {current_process.memory_info().rss / 1024 / 1024:.2f} MB"
    )

    # 查找所有 python 相关的进程
    python_processes = []
    for proc in psutil.process_iter(["pid", "name", "memory_info", "cmdline"]):
        try:
            pinfo = proc.info
            # 过滤 DeepSearch 相关进程 (一般是 python)
            if "python" in pinfo["name"].lower() or "deepsearch" in str(pinfo["cmdline"]).lower():
                mem_mb = pinfo["memory_info"].rss / 1024 / 1024
                python_processes.append(
                    {
                        "pid": pinfo["pid"],
                        "name": pinfo["name"],
                        "cmdline": pinfo["cmdline"],
                        "rss_mb": mem_mb,
                    }
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    # 按内存排序
    python_processes.sort(key=lambda x: x["rss_mb"], reverse=True)

    print(f"Top DeepSearch Related Processes:")
    for p in python_processes[:10]:
        cmd = " ".join(p["cmdline"]) if p["cmdline"] else "N/A"
        # 简化 cmdline 显示
        if "deepsearch" in cmd:
            cmd = "..." + cmd.split("deepsearch")[-1][:50] + "..."
        print(f"PID: {p['pid']:<6} | Memory: {p['rss_mb']:>8.2f} MB | Cmd: {cmd}")


if __name__ == "__main__":
    get_process_memory_info()
