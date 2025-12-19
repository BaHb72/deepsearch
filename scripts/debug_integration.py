#!/usr/bin/env python
"""调试 DataSourceManager 与 Provider 集成"""
import asyncio


async def debug_integration():
    from deepsearch.infrastructure.providers.managers.data_source_manager import DataSourceManager
    
    manager = DataSourceManager.get_instance()
    await manager.initialize()
    
    print("=== Provider 信息 ===")
    for source_type, provider in manager.providers.items():
        print(f"Source: {source_type}")
        print(f"  Provider: {type(provider).__name__}")
        print(f"  has get_stock_list: {hasattr(provider, 'get_stock_list')}")
        print(f"  has get_kline_data: {hasattr(provider, 'get_kline_data')}")  
        print(f"  has get_realtime_quotes: {hasattr(provider, 'get_realtime_quotes')}")
        print(f"  has get_stock_info: {hasattr(provider, 'get_stock_info')}")
        
        # 测试直接调用 Provider
        print("")
        print("=== 直接调用 Provider ===")
        
        if hasattr(provider, "get_stock_list"):
            try:
                result = await provider.get_stock_list(limit=3)
                count = len(result) if result else 0
                print(f"  get_stock_list: {count} 条")
            except Exception as e:
                print(f"  get_stock_list ERROR: {e}")
        
        if hasattr(provider, "get_realtime_quotes"):
            try:
                result = await provider.get_realtime_quotes(["000001"])
                if result is None:
                    print("  get_realtime_quotes: None")
                elif isinstance(result, list):
                    print(f"  get_realtime_quotes: {len(result)} 条 (list)")
                    if result:
                        print(f"    First: {result[0].get('symbol')}: {result[0].get('current')}")
                else:
                    print(f"  get_realtime_quotes: {type(result)}")
            except Exception as e:
                print(f"  get_realtime_quotes ERROR: {e}")
                import traceback
                traceback.print_exc()
                
        if hasattr(provider, "get_kline_data"):
            try:
                from datetime import datetime, timedelta
                result = await provider.get_kline_data(
                    symbol="000001",
                    period="1d",
                    start_date=(datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"),
                    end_date=datetime.now().strftime("%Y-%m-%d"),
                    limit=5
                )
                count = len(result) if result else 0
                print(f"  get_kline_data: {count} 条")
            except Exception as e:
                print(f"  get_kline_data ERROR: {e}")

    # 测试 Manager
    print("")
    print("=== 测试 Manager 方法 ===")
    
    print("Testing get_realtime_quotes...")
    try:
        result = await manager.get_realtime_quotes(["000001"])
        if result is None:
            print("  Manager.get_realtime_quotes: None")
        elif isinstance(result, dict):
            print(f"  Manager.get_realtime_quotes: {len(result)} 条 (dict)")
            for k, v in result.items():
                print(f"    {k}: {v.get('current')}")
        else:
            print(f"  Manager.get_realtime_quotes: {type(result)}")
    except Exception as e:
        print(f"  Manager.get_realtime_quotes ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_integration())
