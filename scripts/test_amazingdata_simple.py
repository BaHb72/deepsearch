"""AmazingData SDK 直接连接测试

通过进程隔离方式测试 AmazingData SDK 是否能正常连接。

运行方式: uv run python scripts/test_amazingdata_simple.py
"""
import asyncio
from datetime import datetime

print("=" * 60)
print(f"AmazingData SDK 直接连接测试")
print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)


async def test_amazingdata():
    # 1. 通过 DataSourceManager 初始化数据源
    print("\n[1] 初始化数据源系统...")
    try:
        from deepsearch.utils.data_sources import (
            get_data_source_manager,
            initialize_data_sources,
            DataSourceType,
        )

        await initialize_data_sources()
        manager = get_data_source_manager()
        print(f"    DataSourceManager 初始化成功")
        
        # 查看可用的数据源
        print(f"    已注册的 providers: {list(manager.providers.keys())}")
        
        provider = manager.get_provider(DataSourceType.AMAZINGDATA)
        if provider is None:
            print("    [警告] AmazingData provider 未找到")
        else:
            print(f"    获取到 AmazingData provider: {type(provider).__name__}")
            print(f"    连接状态: {getattr(provider, '_connected', 'unknown')}")
            
    except Exception as e:
        print(f"    [错误] {e}")
        import traceback
        traceback.print_exc()
        return

    # 2. 测试获取股票列表
    print("\n[2] 测试获取股票列表...")
    if provider:
        try:
            if hasattr(provider, "get_all_stock_list"):
                stocks = await provider.get_all_stock_list()
            elif hasattr(provider, "get_stock_list"):
                stocks = await provider.get_stock_list()
            else:
                stocks = None
                print("    [警告] provider 没有 get_stock_list 方法")

            if stocks is not None:
                count = len(stocks) if stocks else 0
                print(f"    获取到 {count} 只股票")
                if stocks and count > 0:
                    sample = stocks[:3] if hasattr(stocks, "__getitem__") else list(stocks)[:3]
                    print(f"    示例: {sample}...")
        except Exception as e:
            print(f"    [错误] {e}")

    # 3. 测试获取行情快照
    print("\n[3] 测试获取行情快照...")
    if provider:
        try:
            test_codes = ["000001.SZ", "600000.SH"]
            for code in test_codes:
                if hasattr(provider, "get_snapshot"):
                    snap = await provider.get_snapshot(code)
                elif hasattr(provider, "get_realtime_quote"):
                    snap = await provider.get_realtime_quote([code])
                else:
                    snap = None
                    print(f"    [警告] provider 没有快照获取方法")
                    break

                if snap:
                    print(f"    {code}: 获取成功")
                    if hasattr(snap, "items") or isinstance(snap, dict):
                        # 显示一些关键字段
                        keys = list(snap.keys())[:5] if hasattr(snap, "keys") else []
                        print(f"      字段: {keys}")
                else:
                    print(f"    {code}: 无数据")
        except Exception as e:
            print(f"    [错误] {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_amazingdata())
