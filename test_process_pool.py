"""
测试进程池架构 - 验证连续5次测试是否成功

Author: DeepSearch Team
Date: 2025-01-21
"""

import asyncio
import aiohttp
import json
import time
from colorama import init, Fore, Style

# 初始化彩色输出
init(autoreset=True)

async def test_amazingdata_connection(session, test_num):
    """测试AmazingData连接"""
    url = "http://localhost:8000/api/data-source/test"

    payload = {
        "type": "amazingdata",
        "config": {
            "username": "test_user",
            "password": "test_pass",
            "host": "101.230.159.234",
            "port": 8600,
            "networkProvider": "telecom"
        }
    }

    start_time = time.time()

    try:
        print(f"{Fore.YELLOW}测试 #{test_num} 开始...")

        async with session.post(url, json=payload) as resp:
            elapsed = (time.time() - start_time) * 1000
            result = await resp.json()

            if result.get('success') or (result.get('data', {}).get('success')):
                print(f"{Fore.GREEN}✓ 测试 #{test_num} 成功！耗时: {elapsed:.0f}ms")
                if 'data' in result and 'test_id' in result['data'].get('details', {}):
                    print(f"  Test ID: {result['data']['details']['test_id']}")
                return True
            else:
                error_msg = result.get('message', '未知错误')
                if 'data' in result and 'message' in result['data']:
                    error_msg = result['data']['message']
                print(f"{Fore.RED}✗ 测试 #{test_num} 失败: {error_msg}")
                return False

    except Exception as e:
        print(f"{Fore.RED}✗ 测试 #{test_num} 异常: {str(e)}")
        return False


async def test_process_status(session):
    """获取进程池状态"""
    url = "http://localhost:8000/api/data-source/process-status"

    try:
        async with session.get(url) as resp:
            result = await resp.json()

            if result.get('success'):
                data = result.get('data', {})
                print(f"\n{Fore.CYAN}进程池状态:")
                print(f"  总进程数: {data.get('total_processes', 0)}")
                print(f"  最大进程数: {data.get('max_processes', 10)}")

                processes = data.get('processes', {})
                if processes:
                    print(f"  活跃进程:")
                    for pid, info in processes.items():
                        print(f"    - {pid}: PID={info.get('pid')}, Running={info.get('is_running')}")
            else:
                print(f"{Fore.RED}获取进程状态失败")

    except Exception as e:
        print(f"{Fore.RED}获取进程状态异常: {str(e)}")


async def main():
    """主测试函数"""
    print(f"{Fore.MAGENTA}{'='*60}")
    print(f"{Fore.MAGENTA}进程池架构测试 - 连续5次连接测试")
    print(f"{Fore.MAGENTA}{'='*60}\n")

    # 测试配置
    test_count = 5
    success_count = 0

    async with aiohttp.ClientSession() as session:
        # 先获取初始状态
        await test_process_status(session)

        print(f"\n{Fore.CYAN}开始连续测试...")
        print(f"{Fore.CYAN}{'='*40}\n")

        # 执行连续测试
        for i in range(1, test_count + 1):
            success = await test_amazingdata_connection(session, i)
            if success:
                success_count += 1

            # 测试间隔
            if i < test_count:
                await asyncio.sleep(2)

        # 显示最终状态
        print(f"\n{Fore.CYAN}{'='*40}")
        await test_process_status(session)

        # 测试结果总结
        print(f"\n{Fore.MAGENTA}{'='*60}")
        print(f"{Fore.MAGENTA}测试结果总结:")
        print(f"{Fore.MAGENTA}{'='*60}")

        print(f"总测试次数: {test_count}")
        print(f"成功次数: {success_count}")
        print(f"失败次数: {test_count - success_count}")
        print(f"成功率: {(success_count/test_count)*100:.1f}%")

        if success_count == test_count:
            print(f"\n{Fore.GREEN}{'🎉 '*10}")
            print(f"{Fore.GREEN}太棒了！所有测试都成功了！")
            print(f"{Fore.GREEN}进程池架构完美解决了SDK状态残留问题！")
            print(f"{Fore.GREEN}{'🎉 '*10}")
        elif success_count > 0:
            print(f"\n{Fore.YELLOW}部分测试成功，但仍需要优化")
        else:
            print(f"\n{Fore.RED}所有测试失败，请检查服务状态")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}测试被用户中断")
    except Exception as e:
        print(f"\n{Fore.RED}测试异常: {str(e)}")