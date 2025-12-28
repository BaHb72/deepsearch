"""
完整测试：block_trading 和 long_hu_bang
"""

import asyncio
import sys

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")


async def test():
    print("=== 完整测试 AmazingData SDK ===\n")

    try:
        from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_extended import (
            AmazingDataExtended,
        )
        from deepsearch.infrastructure.providers.implementations.amazingdata.config import (
            ensure_amazingdata_provider_config,
        )

        config = ensure_amazingdata_provider_config(
            {
                "enabled": True,
                "username": "212200038719",
                "password": "212200038719@2025",
                "host": "101.230.159.234",
                "port": 8600,
            }
        )

        provider = AmazingDataExtended(config)

        print("[1] 初始化 Provider...")
        result = await provider.initialize()
        print(f"    初始化结果: {result}, 连接状态: {provider.is_connected()}\n")

        if not result:
            print("[ERROR] 初始化失败")
            return

        # 测试 get_block_trading
        print("[2] 测试 get_block_trading(['600519.SH'])...")
        try:
            df = await provider.get_block_trading(["600519.SH"])
            print(f"    返回类型: {type(df).__name__}")
            if hasattr(df, "empty"):
                print(f"    empty: {df.empty}, shape: {df.shape}")
                if not df.empty and hasattr(df, "head"):
                    print(f"    前3行:\n{df.head(3)}")
            print("    [OK] get_block_trading 成功\n")
        except Exception as e:
            print(f"    [FAIL] get_block_trading 失败: {e}\n")

        # 测试 get_long_hu_bang (龙虎榜)
        print("[3] 测试 get_long_hu_bang('600519.SH')...")
        try:
            if hasattr(provider, "get_long_hu_bang"):
                df2 = await provider.get_long_hu_bang("600519.SH")
                print(f"    返回类型: {type(df2).__name__}")
                if hasattr(df2, "empty"):
                    print(f"    empty: {df2.empty}, shape: {df2.shape}")
                    if not df2.empty and hasattr(df2, "head"):
                        print(f"    前3行:\n{df2.head(3)}")
                print("    [OK] get_long_hu_bang 成功\n")
            else:
                print("    [WARN] Provider 没有 get_long_hu_bang 方法\n")
                # 尝试检查可用方法
                methods = [
                    m
                    for m in dir(provider)
                    if "long" in m.lower() or "dragon" in m.lower() or "hu" in m.lower()
                ]
                print(f"    相关方法: {methods}\n")
        except Exception as e:
            print(f"    [FAIL] get_long_hu_bang 失败: {e}\n")

        # 检查Provider有哪些方法
        print("[4] Provider 可用方法 (block/trading/long/dragon 相关):")
        relevant = [
            m
            for m in dir(provider)
            if any(k in m.lower() for k in ["block", "trading", "long", "dragon", "tiger", "hu"])
        ]
        for m in relevant:
            print(f"    - {m}")

        print("\n=== 测试完成 ===")

    except Exception as e:
        print(f"[ERROR] 失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test())
