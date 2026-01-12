"""直接测试 MiniQMT 获取当日数据是否包含 amount"""

import asyncio
import sys

sys.path.insert(0, r"d:\Stock\code\deepsearch")


async def test_miniqmt_data():
    from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
        MiniQMTCollector,
    )

    collector = MiniQMTCollector()

    # 检查是否已连接
    print(f"Connected: {collector.connected}")

    if not collector.connected:
        # 尝试初始化
        try:
            await collector.initialize()
            print(f"After initialize - Connected: {collector.connected}")
        except Exception as e:
            print(f"Initialize failed: {e}")
            return

    # 获取几只股票的 tick 数据
    test_codes = ["000001.SZ", "600000.SH", "300750.SZ"]

    try:
        data = await collector.get_full_tick(test_codes)
        if data:
            for symbol, tick_data in data.items():
                amount = tick_data.get("amount", 0)
                volume = tick_data.get("volume", 0)
                last = tick_data.get("lastPrice", 0)
                print(f"{symbol}: amount={amount}, volume={volume}, last={last}")
        else:
            print("No data returned")
    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_miniqmt_data())
