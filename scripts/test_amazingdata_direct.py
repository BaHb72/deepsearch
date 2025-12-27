"""AmazingData SDK 直接测试（使用提供的凭证）

测试 SDK 是否能正常连接到服务器。

运行方式: uv run python scripts/test_amazingdata_direct.py
"""

import asyncio
from datetime import datetime

print("=" * 60)
print("AmazingData SDK 直接连接测试")
print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)


async def test_amazingdata():
    print("\n[1] 创建 AmazingData Provider...")
    try:
        from deepsearch.infrastructure.providers.implementations.amazingdata import (
            AmazingDataExtended,
        )

        # 直接使用凭证配置
        config = {
            "username": "212200038719",
            "password": "212200038719@2025",
            "host": "101.230.159.234",
            "port": 8600,
            "timeout": 10,
            "implementation_mode": "process",
        }

        print(f"    配置: host={config['host']}, port={config['port']}")
        print(f"    用户名: {config['username']}")

        provider = AmazingDataExtended(config)
        print(f"    Provider 创建成功: {type(provider).__name__}")

    except Exception as e:
        print(f"    [错误] 创建失败: {e}")
        import traceback

        traceback.print_exc()
        return

    print("\n[2] 初始化 Provider（连接服务器）...")
    try:
        result = await provider.initialize()
        print(f"    初始化结果: {result}")
        print(f"    连接状态: {getattr(provider, '_connected', 'unknown')}")
    except Exception as e:
        print(f"    [错误] 初始化失败: {e}")
        import traceback

        traceback.print_exc()
        return

    if not getattr(provider, "_connected", False):
        print("\n[警告] Provider 未连接，跳过后续测试")
        return

    print("\n[3] 测试获取股票列表...")
    try:
        stocks = await provider.get_all_stock_list()
        count = len(stocks) if stocks else 0
        print(f"    获取到 {count} 只股票")
        if stocks and count > 0:
            print(f"    示例: {stocks[:5]}...")
    except Exception as e:
        print(f"    [错误] {e}")

    print("\n[4] 测试获取行情快照...")
    try:
        test_codes = ["000001.SZ", "600000.SH"]
        for code in test_codes:
            snap = await provider.get_snapshot(code)
            if snap:
                print(f"    {code}: 获取成功")
                # 显示部分数据
                if hasattr(snap, "keys"):
                    print(f"      字段数: {len(snap)}")
            else:
                print(f"    {code}: 无数据")
    except Exception as e:
        print(f"    [错误] {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_amazingdata())
