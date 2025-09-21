"""
直接测试进程池架构 - 不依赖WebAPI

Author: DeepSearch Team
Date: 2025-01-21
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
from colorama import init, Fore, Style

# 初始化彩色输出
init(autoreset=True)

def test_process_pool():
    """直接测试进程池功能"""
    print(f"{Fore.MAGENTA}{'='*60}")
    print(f"{Fore.MAGENTA}进程池架构直接测试 - 连续5次连接测试")
    print(f"{Fore.MAGENTA}{'='*60}\n")

    # 导入测试函数
    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_safe_wrapper import (
        test_connection_with_datasource
    )
    from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_process_pool import (
        get_global_pool
    )

    # 测试配置
    test_count = 5
    success_count = 0
    results = []

    print(f"{Fore.CYAN}开始连续测试...")
    print(f"{Fore.CYAN}{'='*40}\n")

    for i in range(1, test_count + 1):
        print(f"{Fore.YELLOW}测试 #{i} 开始...")
        start_time = time.time()

        try:
            # 执行测试
            result = test_connection_with_datasource(
                datasource_id="amazingdata",
                username="test_user",
                password="test_pass",
                host="101.230.159.234",
                port=8600
            )

            elapsed = (time.time() - start_time) * 1000

            if result["success"]:
                print(f"{Fore.GREEN}✓ 测试 #{i} 成功！耗时: {elapsed:.0f}ms")
                print(f"  Test ID: {result.get('test_id')}")
                success_count += 1
            else:
                print(f"{Fore.RED}✗ 测试 #{i} 失败: {result.get('error')}")

            results.append({
                "test_num": i,
                "success": result["success"],
                "latency": elapsed,
                "test_id": result.get("test_id"),
                "error": result.get("error")
            })

        except Exception as e:
            print(f"{Fore.RED}✗ 测试 #{i} 异常: {str(e)}")
            results.append({
                "test_num": i,
                "success": False,
                "error": str(e)
            })

        # 测试间隔
        if i < test_count:
            time.sleep(2)

    # 获取进程池状态
    print(f"\n{Fore.CYAN}{'='*40}")
    print(f"{Fore.CYAN}进程池状态:")
    try:
        pool = get_global_pool()
        status = pool.get_status()
        print(f"  总进程数: {status['total_processes']}")
        print(f"  最大进程数: {status['max_processes']}")

        processes = status.get('processes', {})
        if processes:
            print(f"  活跃进程:")
            for pid, info in processes.items():
                print(f"    - {pid}: PID={info.get('pid')}, Running={info.get('is_running')}")
    except Exception as e:
        print(f"{Fore.RED}  获取状态失败: {str(e)}")

    # 测试结果总结
    print(f"\n{Fore.MAGENTA}{'='*60}")
    print(f"{Fore.MAGENTA}测试结果总结:")
    print(f"{Fore.MAGENTA}{'='*60}")

    print(f"总测试次数: {test_count}")
    print(f"成功次数: {success_count}")
    print(f"失败次数: {test_count - success_count}")
    print(f"成功率: {(success_count/test_count)*100:.1f}%")

    # 详细结果
    print(f"\n{Fore.CYAN}详细结果:")
    for r in results:
        status = "✓" if r["success"] else "✗"
        color = Fore.GREEN if r["success"] else Fore.RED
        print(f"{color}  测试#{r['test_num']}: {status} - ", end="")
        if r["success"]:
            print(f"耗时: {r.get('latency', 0):.0f}ms")
        else:
            print(f"错误: {r.get('error', 'Unknown')}")

    if success_count == test_count:
        print(f"\n{Fore.GREEN}{'🎉 '*10}")
        print(f"{Fore.GREEN}太棒了！所有测试都成功了！")
        print(f"{Fore.GREEN}进程池架构完美解决了SDK状态残留问题！")
        print(f"{Fore.GREEN}{'🎉 '*10}")
        return True
    elif success_count > 0:
        print(f"\n{Fore.YELLOW}部分测试成功，但仍需要优化")
        print(f"{Fore.YELLOW}请检查失败的测试以了解问题原因")
        return False
    else:
        print(f"\n{Fore.RED}所有测试失败，可能是SDK未安装或配置问题")
        print(f"{Fore.RED}请确认AmazingData SDK已正确安装")
        return False


if __name__ == "__main__":
    try:
        success = test_process_pool()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)