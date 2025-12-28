"""
测试 get_block_trading（修复后）
"""

import asyncio
import sys

from loguru import logger

logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level} | {message}")


async def test():
    print("=== 测试 get_block_trading (修复后) ===")

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

        print("[1] 初始化...")
        result = await provider.initialize()
        print(f"[2] 初始化: {result}, connected: {provider.is_connected()}")

        if not result:
            print("[ERROR] 初始化失败")
            return

        print("[3] 调用 get_block_trading(['600519.SH'])...")
        df = await provider.get_block_trading(["600519.SH"])

        print(f"[4] 返回类型: {type(df).__name__}")
        if hasattr(df, "empty"):
            print(f"[5] empty: {df.empty}")
        if hasattr(df, "shape"):
            print(f"[6] shape: {df.shape}")
        if hasattr(df, "columns") and len(df.columns) > 0:
            print(f"[7] columns: {list(df.columns)}")
        if hasattr(df, "head") and not df.empty:
            print(f"[8] head:\n{df.head()}")

        # 测试空列表（全市场）
        print("\n[9] 调用 get_block_trading([])...")
        df2 = await provider.get_block_trading([])
        print(
            f"[10] 全市场数据: empty={df2.empty if hasattr(df2,'empty') else 'N/A'}, shape={df2.shape if hasattr(df2,'shape') else 'N/A'}"
        )
        if hasattr(df2, "head") and not df2.empty:
            print(f"[11] head:\n{df2.head()}")

    except Exception as e:
        print(f"[ERROR] 失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test())
