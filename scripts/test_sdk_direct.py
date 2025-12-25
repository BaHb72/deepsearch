"""直接使用 AmazingData SDK 测试（绕过进程隔离）"""
import sys

print("=== AmazingData SDK 直接测试 ===")

try:
    # 直接导入 SDK
    from deepsearch.infrastructure.providers.implementations.amazingdata._sdk_loader import ad, HAS_AMAZINGDATA
    
    if not HAS_AMAZINGDATA:
        print("SDK 未找到")
        sys.exit(1)
    
    print(f"SDK 加载成功: {ad}")
    print(f"SDK 模块内容: {dir(ad)}")
    
    # 创建 TGW 对象并登录
    TGW = ad.TGW
    print(f"\nTGW 类: {TGW}")
    
    tgw = TGW()
    print("TGW 实例创建成功")
    
    print("\n正在登录...")
    # AmazingData SDK 使用关键字参数
    result = tgw.login(
        ip="101.230.159.234",
        port=8600,
        username="212200038719",
        password="212200038719@2025"
    )
    print(f"登录结果: {result}")
    
    if result == 0:  # 登录成功
        print("\n获取股票列表...")
        BaseData = ad.BaseData
        base_data = BaseData()
        stocks = base_data.get_code_list("EXTRA_STOCK_A")
        print(f"股票数量: {len(stocks) if stocks else 0}")
        if stocks:
            print(f"示例: {list(stocks)[:5]}")
    else:
        print(f"登录失败，错误码: {result}")
        
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
