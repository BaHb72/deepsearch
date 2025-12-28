"""
测试 ProcessIsolatedAmazingDataProvider.get_block_trading 方法
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))


async def test_block_trading():
    print("=== 测试 block-trading SDK 调用 ===")

    from deepsearch.webui.api.providers import DataProviderFactory, DataSourceType

    # 获取provider
    print("[1] 获取 AmazingData provider...")
    provider = await DataProviderFactory.get_provider_async(DataSourceType.AMAZINGDATA)
    print(f"[2] Provider type: {type(provider).__name__}")

    # 检查方法是否存在
    has_method = hasattr(provider, "get_block_trading")
    print(f"[3] has get_block_trading: {has_method}")

    if not has_method:
        print("[ERROR] provider 没有 get_block_trading 方法！")
        # 列出所有公共方法
        methods = [m for m in dir(provider) if not m.startswith("_")]
        print(f"[INFO] provider 的公共方法: {methods}")
        return

    # 调用方法
    print("[4] 调用 provider.get_block_trading(['600519.SH'])...")
    try:
        result = await provider.get_block_trading(["600519.SH"])
        print(f"[5] Result type: {type(result).__name__}")
        print(f"[6] Result is None: {result is None}")
        if hasattr(result, "empty"):
            print(f"[7] DataFrame empty: {result.empty}")
        if hasattr(result, "shape"):
            print(f"[8] DataFrame shape: {result.shape}")
        if hasattr(result, "columns"):
            print(f"[9] DataFrame columns: {list(result.columns)}")
        if hasattr(result, "head"):
            print(f"[10] DataFrame head:\n{result.head()}")
    except Exception as e:
        print(f"[ERROR] 调用失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_block_trading())
