#!/usr/bin/env python3
"""
清理占用的端口和进程
"""
import os
import subprocess


def cleanup_ports():
    """清理占用的端口"""
    print("正在清理占用的端口和进程...")

    # 获取所有运行main.py的Python进程
    try:
        output = subprocess.check_output(
            'wmic process where "name=\'python.exe\'" get processid,commandline',
            shell=True,
            text=True
        )

        lines = output.strip().split('\n')
        pids_to_kill = []

        for line in lines:
            if 'main.py' in line and line.strip():
                # 提取PID (最后一个数字)
                parts = line.strip().split()
                if parts:
                    pid = parts[-1]
                    if pid.isdigit():
                        pids_to_kill.append(pid)

        if pids_to_kill:
            print(f"找到 {len(pids_to_kill)} 个运行main.py的进程")
            for pid in pids_to_kill:
                print(f"  终止进程 PID: {pid}")
                try:
                    # 使用os.system执行Windows命令
                    os.system(f'taskkill /PID {pid} /F >nul 2>&1')
                except OSError as e:
                    print(f"  警告: 无法终止进程 {pid}: {e}")
            print("清理完成!")
        else:
            print("没有找到需要清理的进程")

    except Exception as e:
        print(f"错误: {e}")
        print("请手动关闭占用8000端口的进程")


if __name__ == "__main__":
    cleanup_ports()
