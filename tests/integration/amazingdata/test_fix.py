#!/usr/bin/env python
"""测试数据源修复"""
import asyncio
from loguru import logger

async def test_amazingdata_init():
    """测试 AmazingData 初始化"""
    try:
        from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
            AmazingDataProvider, AmazingDataConfig
        )

        config = AmazingDataConfig(
            username="test",
            password="test",
            host="127.0.0.1",
            port=8600,
            timeout=10
        )

        provider = AmazingDataProvider(config)
        logger.success("✓ AmazingDataProvider 初始化成功")
        return True
    except Exception as e:
        logger.error(f"✗ AmazingDataProvider 初始化失败: {e}")
        return False

async def test_request_optimizer():
    """测试 RequestOptimizer"""
    try:
        from deepsearch.infrastructure.providers.implementations.akshare.request_optimizer import (
            RequestOptimizer, RequestPriority
        )

        optimizer = RequestOptimizer()
        await optimizer.start()

        # 测试 submit 方法
        loop = asyncio.get_event_loop()
        task_future = loop.create_future()
        task_future.set_result({"test": "data"})

        # 设置执行器
        optimizer.executor = lambda api, params: task_future

        # 提交请求
        result = await optimizer.submit(
            "test_api",
            {"param": "value"},
            RequestPriority.NORMAL,
            use_cache=False
        )

        await optimizer.stop()
        logger.success("✓ RequestOptimizer.submit 方法调用成功")
        return True
    except Exception as e:
        logger.error(f"✗ RequestOptimizer 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主测试函数"""
    logger.info("开始测试数据源修复...")

    # 测试 AmazingData 初始化
    test1 = await test_amazingdata_init()

    # 测试 RequestOptimizer
    test2 = await test_request_optimizer()

    if test1 and test2:
        logger.success("✓ 所有修复测试通过！")
    else:
        logger.error("✗ 部分测试失败，请检查修复")

    return test1 and test2

if __name__ == "__main__":
    asyncio.run(main())