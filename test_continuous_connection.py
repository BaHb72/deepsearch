"""
测试AmazingData连续连接功能

验证进程复用机制和logout功能是否正常工作。

Author: DeepSearch Team
Date: 2025-01-21
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any


async def test_connection(session: aiohttp.ClientSession, test_num: int) -> Dict[str, Any]:
    """执行单次测试"""
    url = "http://localhost:8000/api/data-source/test"

    payload = {
        "type": "amazingdata",
        "config": {
            "username": "test_user",
            "password": "test_password",
            "host": "101.230.159.234",
            "port": 8600,
            "networkProvider": "telecom"
        }
    }

    start_time = time.time()

    try:
        async with session.post(url, json=payload) as resp:
            result = await resp.json()
            latency = (time.time() - start_time) * 1000

            return {
                "test_num": test_num,
                "success": result.get("success", False),
                "message": result.get("message", ""),
                "latency_ms": latency,
                "process_id": result.get("data", {}).get("process_id"),
                "error": result.get("error")
            }
    except Exception as e:
        return {
            "test_num": test_num,
            "success": False,
            "message": f"请求失败: {e}",
            "latency_ms": (time.time() - start_time) * 1000,
            "error": str(e)
        }


async def get_process_status(session: aiohttp.ClientSession) -> Dict[str, Any]:
    """获取进程池状态"""
    url = "http://localhost:8000/api/data-source/process-status"

    try:
        async with session.get(url) as resp:
            return await resp.json()
    except Exception as e:
        return {"error": str(e)}


async def main():
    """主测试函数"""
    print("=" * 60)
    print("AmazingData 连续连接测试")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        # 测试1: 快速连续测试（应该复用进程）
        print("\n阶段1: 快速连续测试（5秒间隔，5次）")
        print("-" * 40)

        for i in range(5):
            result = await test_connection(session, i + 1)

            print(f"测试 #{result['test_num']}:")
            print(f"  - 成功: {result['success']}")
            print(f"  - 延迟: {result['latency_ms']:.0f}ms")
            print(f"  - 进程ID: {result.get('process_id', 'N/A')}")

            if not result['success']:
                print(f"  - 错误: {result.get('error', result.get('message'))}")

            # 短暂等待
            if i < 4:
                await asyncio.sleep(5)

        # 获取进程状态
        print("\n进程池状态:")
        status = await get_process_status(session)
        if "data" in status:
            data = status["data"]
            print(f"  - 总进程数: {data.get('total_processes', 0)}")
            print(f"  - 最大进程数: {data.get('max_processes', 10)}")

            for proc_id, proc_info in data.get("processes", {}).items():
                print(f"\n  进程 {proc_id}:")
                print(f"    - PID: {proc_info.get('pid')}")
                print(f"    - 运行中: {proc_info.get('is_running')}")
                print(f"    - 运行时间: {proc_info.get('uptime_seconds', 0):.1f}秒")
                print(f"    - 完成请求: {proc_info.get('requests_completed', 0)}")
                print(f"    - 失败请求: {proc_info.get('requests_failed', 0)}")
                print(f"    - 重启次数: {proc_info.get('restart_count', 0)}")

        # 测试2: 等待超过复用窗口后再测试（应该创建新进程）
        print("\n阶段2: 等待35秒后测试（超过复用窗口）")
        print("-" * 40)

        await asyncio.sleep(35)

        result = await test_connection(session, 6)
        print(f"测试 #{result['test_num']}:")
        print(f"  - 成功: {result['success']}")
        print(f"  - 延迟: {result['latency_ms']:.0f}ms")
        print(f"  - 进程ID: {result.get('process_id', 'N/A')}")
        print(f"  - 说明: 应该创建了新进程")

        # 最终状态
        print("\n最终进程池状态:")
        status = await get_process_status(session)
        if "data" in status:
            data = status["data"]
            print(f"  - 总进程数: {data.get('total_processes', 0)}")

            for proc_id, proc_info in data.get("processes", {}).items():
                print(f"  - {proc_id}: PID={proc_info.get('pid')}, "
                      f"运行={proc_info.get('is_running')}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n测试中断")
    except Exception as e:
        print(f"\n测试失败: {e}")