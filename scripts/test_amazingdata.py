"""测试 AmazingData SDK 功能（使用系统配置）

此脚本用于诊断 AmazingData SDK 是否正常工作。
盘中运行可以确认夜间超时是否由服务器关闭导致。

运行方式: uv run python scripts/test_amazingdata.py
"""
import asyncio
import sys
from datetime import datetime

print("=" * 60)
print(f"AmazingData SDK 功能测试（使用系统配置）")
print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

async def test_amazingdata():
    # 1. 测试通过 DataSourceManager 获取 provider
    print("\n[1] 测试通过 DataSourceManager 获取 AmazingData provider...")
    try:
        from deepsearch.utils.data_sources import get_data_source_manager, DataSourceType
        
        manager = get_data_source_manager()
        provider = manager.get_provider(DataSourceType.AMAZINGDATA)
        
        if provider is None:
            print("    [警告] DataSourceManager 未返回 AmazingData provider")
            print("    可能原因: 数据源未配置或未启用")
        else:
            print(f"    成功获取 provider: {type(provider).__name__}")
            print(f"    是否连接: {getattr(provider, '_connected', 'unknown')}")
    except Exception as e:
        print(f"    [错误] {e}")

    # 2. 测试直接使用 AmazingDataExtended
    print("\n[2] 测试直接使用 AmazingDataExtended...")
    try:
        from deepsearch.config import get_config
        from deepsearch.infrastructure.providers.implementations.amazingdata import (
            AmazingDataExtended,
        )
        
        config = get_config()
        amazingdata_config = getattr(config, 'amazingdata', None)
        
        if amazingdata_config is None:
            print("    [警告] 配置中没有 amazingdata 配置项")
        else:
            print(f"    配置: host={getattr(amazingdata_config, 'host', 'N/A')}, "
                  f"port={getattr(amazingdata_config, 'port', 'N/A')}")
            
            # 尝试创建 provider
            provider = AmazingDataExtended(amazingdata_config)
            print(f"    创建 provider 成功")
            
            # 尝试初始化
            print("    正在初始化（可能需要几秒钟）...")
            result = await provider.initialize()
            print(f"    初始化结果: {result}")
            print(f"    连接状态: {provider._connected}")
            
            if provider._connected:
                # 3. 测试获取股票列表
                print("\n[3] 测试获取股票列表...")
                try:
                    stocks = await provider.get_all_stock_list()
                    count = len(stocks) if stocks else 0
                    print(f"    获取到 {count} 只股票")
                    if stocks and count > 0:
                        print(f"    示例: {stocks[:3]}...")
                except Exception as e:
                    print(f"    [错误] {e}")
                
                # 4. 测试获取行情快照
                print("\n[4] 测试获取行情快照...")
                try:
                    test_codes = ["000001.SZ", "600000.SH"]
                    for code in test_codes:
                        snap = await provider.get_snapshot(code)
                        if snap:
                            print(f"    {code}: 获取成功")
                        else:
                            print(f"    {code}: 无数据")
                except Exception as e:
                    print(f"    [错误] {e}")
            else:
                print("\n[3-4] 跳过数据测试（未连接）")
                
    except ImportError as e:
        print(f"    [错误] 导入失败: {e}")
    except Exception as e:
        print(f"    [错误] {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print("""
结果解读:
- 如果盘中运行正常，夜间运行失败，说明服务器夜间关闭
- 如果 "DataSourceManager 未返回 provider"，说明数据源未配置
- 如果初始化失败，检查 amazingdata 配置和网络连接
""")

if __name__ == "__main__":
    asyncio.run(test_amazingdata())
