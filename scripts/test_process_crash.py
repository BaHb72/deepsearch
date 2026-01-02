"""
测试脚本：模拟 AmazingData Worker 子进程崩溃，检查主进程是否会跟着退出。

目的：排查为什么子进程退出会导致主进程退出。
"""

import asyncio
import multiprocessing as mp
import os
import signal
import sys
import time
from multiprocessing import Process, Queue


def worker_that_crashes(queue: Queue, crash_after: float = 3.0):
    """模拟会崩溃的 Worker 进程"""
    print(f"[Worker PID={os.getpid()}] 启动，将在 {crash_after}s 后崩溃")
    time.sleep(crash_after)

    # 模拟 SDK 内部崩溃行为
    print("[Worker] 模拟崩溃: Request queue closed, terminating worker")
    print("[Worker] Worker process exiting")

    # 方式1: 直接 exit
    # sys.exit(1)

    # 方式2: os._exit (更激进)
    os._exit(1)


def test_basic_process_crash():
    """测试1: 基础的子进程崩溃，主进程会怎样？"""
    print("\n" + "=" * 60)
    print("测试1: 基础子进程崩溃测试")
    print("=" * 60)

    queue = Queue()
    worker = Process(target=worker_that_crashes, args=(queue, 2.0))
    worker.start()

    print(f"[主进程 PID={os.getpid()}] Worker 已启动 (PID={worker.pid})")

    # 等待 Worker 崩溃
    worker.join(timeout=5)

    if worker.is_alive():
        print("[主进程] Worker 仍在运行（异常）")
        worker.terminate()
    else:
        print(f"[主进程] Worker 已退出，exitcode={worker.exitcode}")

    print("[主进程] 测试完成，主进程正常继续运行 ✓")
    return True


def test_ipc_pipe_crash():
    """测试2: 通过 Pipe 通信时子进程崩溃"""
    print("\n" + "=" * 60)
    print("测试2: IPC Pipe 通信时子进程崩溃")
    print("=" * 60)

    from multiprocessing import Pipe

    def worker_with_pipe(conn, crash_after=2.0):
        print(f"[Worker PID={os.getpid()}] 通过 Pipe 通信")
        try:
            time.sleep(crash_after)
            print("[Worker] 崩溃前关闭连接")
            conn.close()
            os._exit(1)
        except Exception as e:
            print(f"[Worker] 异常: {e}")
            os._exit(1)

    parent_conn, child_conn = Pipe()
    worker = Process(target=worker_with_pipe, args=(child_conn, 2.0))
    worker.start()

    print(f"[主进程] Worker 已启动 (PID={worker.pid})")

    # 尝试从 Pipe 读取
    try:
        print("[主进程] 等待从 Pipe 读取...")
        if parent_conn.poll(timeout=5):
            data = parent_conn.recv()
            print(f"[主进程] 收到数据: {data}")
        else:
            print("[主进程] Pipe 超时，没有数据")
    except EOFError:
        print("[主进程] EOFError: 子进程关闭了连接")
    except Exception as e:
        print(f"[主进程] Pipe 读取异常: {type(e).__name__}: {e}")

    worker.join(timeout=3)
    print(f"[主进程] Worker exitcode={worker.exitcode}")
    print("[主进程] 测试完成 ✓")
    return True


def test_amazingdata_proxy_simulation():
    """测试3: 模拟 AmazingDataProcessProxy 的使用模式"""
    print("\n" + "=" * 60)
    print("测试3: 模拟 AmazingDataProcessProxy 使用模式")
    print("=" * 60)

    import pickle
    import threading
    from multiprocessing import Pipe

    def worker_loop(conn):
        """模拟 _worker_loop"""
        print(f"[Worker PID={os.getpid()}] worker_loop 启动")
        try:
            while True:
                if conn.poll(timeout=1.0):
                    data = conn.recv_bytes()
                    request = pickle.loads(data)
                    print(f"[Worker] 收到请求: {request}")

                    if request.get("type") == "crash":
                        print("[Worker] 收到崩溃指令！")
                        print("[Worker] Request queue closed, terminating worker")
                        conn.close()
                        os._exit(1)

                    response = {"status": "ok", "echo": request}
                    conn.send_bytes(pickle.dumps(response))
        except Exception as e:
            print(f"[Worker] 异常退出: {e}")
            os._exit(1)

    parent_conn, child_conn = Pipe()
    worker = Process(target=worker_loop, args=(child_conn,))
    worker.start()

    print(f"[主进程] Worker 已启动 (PID={worker.pid})")

    # 发送正常请求
    try:
        request = {"type": "ping", "data": "hello"}
        parent_conn.send_bytes(pickle.dumps(request))

        if parent_conn.poll(timeout=3):
            response = pickle.loads(parent_conn.recv_bytes())
            print(f"[主进程] 收到响应: {response}")

        # 发送崩溃指令
        print("[主进程] 发送崩溃指令...")
        crash_request = {"type": "crash"}
        parent_conn.send_bytes(pickle.dumps(crash_request))

        # 尝试再次读取
        time.sleep(1)
        print("[主进程] 尝试从已崩溃的 Worker 读取...")

        if parent_conn.poll(timeout=3):
            response = pickle.loads(parent_conn.recv_bytes())
            print(f"[主进程] 意外收到响应: {response}")
        else:
            print("[主进程] Pipe 超时（预期行为）")

    except EOFError:
        print("[主进程] EOFError: Worker 已关闭连接")
    except BrokenPipeError:
        print("[主进程] BrokenPipeError: Pipe 已断开")
    except Exception as e:
        print(f"[主进程] 异常: {type(e).__name__}: {e}")

    worker.join(timeout=3)
    print(f"[主进程] Worker exitcode={worker.exitcode}")
    print("[主进程] 测试完成 ✓")
    return True


def test_with_actual_proxy():
    """测试4: 使用实际的 AmazingDataProcessProxy"""
    print("\n" + "=" * 60)
    print("测试4: 使用实际的 AmazingDataProcessProxy")
    print("=" * 60)

    try:
        from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_proxy import (
            AmazingDataProcessProxy,
        )

        proxy = AmazingDataProcessProxy(restart_on_crash=False)
        print(f"[主进程] 创建 Proxy 成功")

        started = proxy.start()
        print(f"[主进程] Proxy 启动: {started}")

        if not started:
            print("[主进程] Proxy 启动失败，跳过测试")
            return False

        # 获取 Worker PID
        worker_pid = getattr(proxy.worker_process, "pid", None)
        print(f"[主进程] Worker PID: {worker_pid}")

        # 执行健康检查
        health = proxy.health_check()
        print(f"[主进程] 健康状态: {health}")

        # 强制杀死 Worker 进程
        print("[主进程] 强制杀死 Worker 进程...")
        if worker_pid:
            try:
                os.kill(worker_pid, signal.SIGTERM)
                time.sleep(1)
            except Exception as e:
                print(f"[主进程] kill 失败: {e}")

        # 再次检查健康状态
        time.sleep(1)
        try:
            health = proxy.health_check()
            print(f"[主进程] 杀死后健康状态: {health}")
        except Exception as e:
            print(f"[主进程] 健康检查异常: {e}")

        proxy.stop()
        print("[主进程] 测试完成 ✓")
        return True

    except ImportError as e:
        print(f"[主进程] 导入失败: {e}")
        return False
    except Exception as e:
        print(f"[主进程] 测试异常: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("子进程崩溃传播测试")
    print(f"主进程 PID: {os.getpid()}")
    print("=" * 60)

    results = {}

    # 测试1: 基础崩溃
    try:
        results["基础崩溃"] = test_basic_process_crash()
    except Exception as e:
        print(f"测试1 失败: {e}")
        results["基础崩溃"] = False

    # 测试2: Pipe 崩溃
    try:
        results["Pipe崩溃"] = test_ipc_pipe_crash()
    except Exception as e:
        print(f"测试2 失败: {e}")
        results["Pipe崩溃"] = False

    # 测试3: 模拟 Proxy
    try:
        results["模拟Proxy"] = test_amazingdata_proxy_simulation()
    except Exception as e:
        print(f"测试3 失败: {e}")
        results["模拟Proxy"] = False

    # 测试4: 实际 Proxy
    try:
        results["实际Proxy"] = test_with_actual_proxy()
    except Exception as e:
        print(f"测试4 失败: {e}")
        results["实际Proxy"] = False

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")

    print("\n" + "=" * 60)
    print("主进程正常退出（如果你看到这行，说明子进程崩溃没有杀死主进程）")
    print("=" * 60)


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    main()
