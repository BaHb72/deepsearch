"""诊断 AmazingData SDK 状态"""
import asyncio

async def diagnose():
    from deepsearch.infrastructure.providers.implementations.amazingdata import AmazingDataExtended
    
    config = {
        "username": "212200038719", 
        "password": "212200038719@2025", 
        "host": "101.230.159.234", 
        "port": 8600, 
        "implementation_mode": "optimized"
    }
    
    provider = AmazingDataExtended(config)
    await provider.initialize()
    
    print("=== 内部状态 ===")
    print(f"_connected: {provider._connected}")
    print(f"_base_data: {provider._base_data}")
    print(f"_process_proxy: {getattr(provider, '_process_proxy', None)}")
    
    # 如果有 process_proxy，检查其状态
    proxy = getattr(provider, "_process_proxy", None)
    if proxy:
        print(f"\n=== Process Proxy 状态 ===")
        print(f"proxy type: {type(proxy)}")
        print(f"is_connected: {getattr(proxy, 'is_connected', None)}")
        if hasattr(proxy, "get_status"):
            status = proxy.get_status()
            print(f"status: {status}")
    
    # 等待后再试
    print("\n等待5秒后重试...")
    await asyncio.sleep(5)
    
    stocks = await provider.get_stock_list()
    print(f"\n股票列表: {len(stocks) if stocks else 0} 只")

asyncio.run(diagnose())
