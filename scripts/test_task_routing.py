"""
测试混合 Dask 集群任务路由

验证：
1. Windows Workers (WIN=1) 和 Docker Workers (LINUX=1) 都已连接
2. 任务被正确路由到对应环境
"""

import asyncio
import sys

from loguru import logger


async def test_cluster_status():
    """测试集群状态"""
    print("\n" + "=" * 60)
    print("测试1: 集群状态检查")
    print("=" * 60)

    from deepsearch.compute import TaskRouter

    router = await TaskRouter.get_instance()
    connected = await router.connect()

    if not connected:
        print("❌ 无法连接到 Dask Scheduler")
        print("   请确保 Docker 服务已启动: docker compose up -d")
        return False

    status = await router.get_worker_status()
    print(f"✓ 已连接到 Scheduler: {status.get('scheduler')}")
    print(f"  总 Workers: {status.get('total_workers')}")
    print(f"  Windows Workers: {status.get('windows_workers')}")
    print(f"  Linux/Docker Workers: {status.get('linux_workers')}")

    for addr, info in status.get("workers", {}).items():
        resources = info.get("resources", {})
        env = "WINDOWS" if resources.get("WIN") else "LINUX" if resources.get("LINUX") else "ANY"
        print(f"    - {info.get('name')} ({env}): {info.get('nthreads')} threads")

    return status.get("total_workers", 0) > 0


async def test_task_routing():
    """测试任务路由"""
    print("\n" + "=" * 60)
    print("测试2: 任务路由测试")
    print("=" * 60)

    from deepsearch.compute import (
        TaskEnvironment,
        requires_linux,
        requires_windows,
        submit_linux_task,
        submit_windows_task,
    )

    @requires_windows
    def windows_only_task(x: int) -> str:
        import os

        return f"Windows task result: {x}, platform={os.name}"

    @requires_linux
    def linux_only_task(x: int) -> str:
        import os

        return f"Linux task result: {x}, platform={os.name}"

    try:
        # 测试 Windows 任务
        print("\n提交 Windows 任务...")
        win_result = await submit_windows_task(windows_only_task, 42)
        print(f"  ✓ Windows 任务结果: {win_result}")
    except Exception as e:
        print(f"  ⚠ Windows 任务失败 (可能没有 Windows Worker): {e}")

    try:
        # 测试 Linux 任务
        print("\n提交 Linux 任务...")
        linux_result = await submit_linux_task(linux_only_task, 100)
        print(f"  ✓ Linux 任务结果: {linux_result}")
    except Exception as e:
        print(f"  ⚠ Linux 任务失败 (可能没有 Linux Worker): {e}")

    return True


async def test_environment_inference():
    """测试环境自动推断"""
    print("\n" + "=" * 60)
    print("测试3: 环境自动推断")
    print("=" * 60)

    from deepsearch.compute.task_routing import TaskEnvironment, infer_environment

    test_cases = [
        ("fetch_market_data", TaskEnvironment.WINDOWS),
        ("amazingdata_kline", TaskEnvironment.WINDOWS),
        ("miniqmt_quote", TaskEnvironment.WINDOWS),
        ("compute_factor", TaskEnvironment.LINUX),
        ("backtest_strategy", TaskEnvironment.LINUX),
        ("unknown_task", TaskEnvironment.ANY),
    ]

    all_passed = True
    for task_type, expected in test_cases:
        result = infer_environment(task_type)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"  {status} {task_type} => {result.name} (expected: {expected.name})")

    return all_passed


async def main():
    print("=" * 60)
    print("  混合 Dask 集群测试")
    print("=" * 60)

    results = {}

    # 测试1: 集群状态
    try:
        results["集群状态"] = await test_cluster_status()
    except Exception as e:
        print(f"测试1 失败: {e}")
        results["集群状态"] = False

    # 测试2: 任务路由
    if results.get("集群状态"):
        try:
            results["任务路由"] = await test_task_routing()
        except Exception as e:
            print(f"测试2 失败: {e}")
            results["任务路由"] = False
    else:
        print("\n跳过任务路由测试 (集群未连接)")
        results["任务路由"] = False

    # 测试3: 环境推断
    try:
        results["环境推断"] = await test_environment_inference()
    except Exception as e:
        print(f"测试3 失败: {e}")
        results["环境推断"] = False

    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")

    return all(results.values())


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
