#!/usr/bin/env python
"""
AmazingData SDK进程隔离测试脚本

测试进程隔离功能是否正常工作
"""
import sys
import time
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_safe_wrapper import (
    get_safe_wrapper, test_connection
)
from loguru import logger

def main():
    """主测试函数"""
    logger.info("=" * 60)
    logger.info("AmazingData SDK进程隔离测试")
    logger.info("=" * 60)

    # 测试参数（使用无效凭据测试崩溃隔离）
    test_params = {
        "username": "212200038719",
        "password": "212200038719@2025",
        "host": "101.230.159.234",
        "port": 8600
    }

    logger.info(f"测试参数: {test_params['username']}@{test_params['host']}:{test_params['port']}")

    # 测试1：使用便捷方法测试连接
    logger.info("\n[测试1] 使用test_connection便捷方法")
    logger.info("-" * 40)

    result = test_connection(
        username=test_params["username"],
        password=test_params["password"],
        host=test_params["host"],
        port=test_params["port"]
    )

    logger.info(f"测试结果: 成功={result['success']}")
    if result.get('error'):
        logger.error(f"错误信息: {result['error']}")
    logger.info(f"延迟: {result['latency_ms']:.2f}ms")

    # 显示统计信息
    stats = result.get('stats', {})
    if stats:
        logger.info("\n统计信息:")
        logger.info(f"  - 总调用次数: {stats.get('total_calls', 0)}")
        logger.info(f"  - 成功调用: {stats.get('successful_calls', 0)}")
        logger.info(f"  - 失败调用: {stats.get('failed_calls', 0)}")
        logger.info(f"  - 崩溃处理: {stats.get('crashes_handled', 0)}")

        proxy_stats = stats.get('proxy_stats', {})
        if proxy_stats:
            logger.info(f"  - 进程重启: {proxy_stats.get('process_restarts', 0)}")

    # 测试2：使用包装器测试多次调用
    logger.info("\n[测试2] 测试多次调用（验证进程稳定性）")
    logger.info("-" * 40)

    wrapper = get_safe_wrapper()

    for i in range(3):
        logger.info(f"\n第 {i+1} 次测试:")
        success, error = wrapper.safe_login(
            username=test_params["username"],
            password=test_params["password"],
            host=test_params["host"],
            port=test_params["port"],
            timeout=10.0
        )

        if success:
            logger.info("  ✓ 登录成功")
            wrapper.safe_logout()
        else:
            logger.error(f"  ✗ 登录失败: {error}")

        # 等待一下再继续
        if i < 2:
            time.sleep(1)

    # 最终统计
    logger.info("\n[最终统计]")
    logger.info("-" * 40)
    final_stats = wrapper.get_stats()
    logger.info(f"总调用: {final_stats.get('total_calls', 0)}")
    logger.info(f"成功: {final_stats.get('successful_calls', 0)}")
    logger.info(f"失败: {final_stats.get('failed_calls', 0)}")
    logger.info(f"重试: {final_stats.get('retries', 0)}")
    logger.info(f"崩溃处理: {final_stats.get('crashes_handled', 0)}")

    proxy_stats = final_stats.get('proxy_stats', {})
    if proxy_stats:
        logger.info(f"进程重启: {proxy_stats.get('process_restarts', 0)}")
        if proxy_stats.get('last_crash_time'):
            logger.info(f"最后崩溃时间: {proxy_stats['last_crash_time']}")
        if proxy_stats.get('last_crash_reason'):
            logger.info(f"最后崩溃原因: {proxy_stats['last_crash_reason']}")

    logger.info("\n" + "=" * 60)
    logger.info("测试完成！主进程保持稳定运行。")
    logger.info("=" * 60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())