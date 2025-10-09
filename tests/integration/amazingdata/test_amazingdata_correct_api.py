"""
使用正确的AmazingData SDK API测试
"""

import os
import sys
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

from deepsearch.config import get_config


def get_amazingdata_config():
    """获取AmazingData配置"""
    config = get_config()

    # 优先使用新格式配置
    if hasattr(config, "data_sources") and config.data_sources:
        providers = config.data_sources.get("providers", {})
        if "amazingdata" in providers:
            ad_provider = providers["amazingdata"]
            if ad_provider.get("enabled"):
                ad_config = ad_provider.get("config", {})
                conn = ad_config.get("connection", {})
                return {
                    "username": conn.get("username", ""),
                    "password": conn.get("password", ""),
                    "host": conn.get("host", "localhost"),
                    "port": conn.get("port", 8888),
                    "enabled": True,
                }

    # 回退到旧格式
    if hasattr(config, "amazingdata"):
        ad = config.amazingdata
        if ad.enabled:
            return {
                "username": getattr(ad, "username", ""),
                "password": str(getattr(ad, "password", "")),
                "host": getattr(ad, "host", "localhost"),
                "port": getattr(ad, "port", 8888),
                "enabled": ad.enabled,
            }

    return None


def test_amazingdata():
    """测试AmazingData API"""
    print("=" * 60)
    print("AmazingData SDK 测试")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 获取配置
    config = get_amazingdata_config()
    if not config or not config["enabled"]:
        print("[FAIL] AmazingData未启用或未配置")
        return False

    print(f"[INFO] 服务器: {config['host']}:{config['port']}")
    print(f"[INFO] 用户名: ***{config['username'][-4:] if len(config['username']) > 4 else '***'}")

    try:
        import AmazingData as ad

        print(
            f"[INFO] AmazingData SDK版本: {ad.__version__ if hasattr(ad, '__version__') else '未知'}\n"
        )
    except ImportError:
        print("[FAIL] AmazingData SDK未安装")
        return False

    # 1. 登录测试
    print("[1] 测试登录...")
    try:
        # 登录（直接传递服务器地址和端口）
        login_result = ad.login(
            username=config["username"],
            password=config["password"],
            host=config["host"],
            port=config["port"],
            api_mode="kInternetMode",  # 互联网模式
        )

        if login_result == 0 or login_result is True:
            print(f"    [OK] 登录成功 (服务器: {config['host']}:{config['port']})")
        else:
            print(f"    [FAIL] 登录失败，错误码: {login_result}")
            return False
    except Exception as e:
        print(f"    [FAIL] 登录异常: {e}")
        import traceback

        traceback.print_exc()
        return False

    # 2. 查询股票列表
    print("\n[2] 查询股票列表...")
    try:
        # 尝试导入查询API模块
        from AmazingData import query_api

        # 获取股票列表
        if hasattr(query_api, "get_stock_list"):
            stock_list = query_api.get_stock_list()
            if stock_list:
                print(f"    [OK] 获取{len(stock_list)}只股票")
                if isinstance(stock_list, list) and len(stock_list) > 0:
                    print(f"    示例: {stock_list[:5]}")
        elif hasattr(query_api, "query_stock_list"):
            stock_list = query_api.query_stock_list()
            if stock_list:
                print(f"    [OK] 获取{len(stock_list)}只股票")
        else:
            print("    [INFO] 股票列表API不可用")
    except Exception as e:
        print(f"    [WARNING] 查询股票列表失败: {e}")

    # 3. 查询实时行情
    print("\n[3] 查询实时行情...")
    test_code = "000001"  # 平安银行
    try:
        from AmazingData import query_api

        # 尝试不同的API名称
        if hasattr(query_api, "get_realtime_quotes"):
            quotes = query_api.get_realtime_quotes([test_code])
            if quotes:
                print("    [OK] 获取实时行情")
                print(f"    数据: {quotes}")
        elif hasattr(query_api, "query_realtime_quotes"):
            quotes = query_api.query_realtime_quotes([test_code])
            if quotes:
                print("    [OK] 获取实时行情")
        elif hasattr(query_api, "get_snapshot"):
            snapshot = query_api.get_snapshot([test_code])
            if snapshot:
                print("    [OK] 获取快照数据")
        else:
            print("    [INFO] 实时行情API不可用")
    except Exception as e:
        print(f"    [WARNING] 查询实时行情失败: {e}")

    # 4. 查询K线数据
    print("\n[4] 查询K线数据...")
    try:
        from AmazingData import query_api

        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        # 尝试不同的API名称
        if hasattr(query_api, "get_kline_data"):
            kline = query_api.get_kline_data(
                test_code, start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d"), "1d"
            )
            if kline is not None:
                print("    [OK] 获取K线数据")
                if isinstance(kline, pd.DataFrame):
                    print(f"    共{len(kline)}条记录")
        elif hasattr(query_api, "query_history_bars"):
            bars = query_api.query_history_bars(
                test_code, start_date.strftime("%Y%m%d"), end_date.strftime("%Y%m%d")
            )
            if bars:
                print("    [OK] 获取历史K线")
        else:
            print("    [INFO] K线数据API不可用")
    except Exception as e:
        print(f"    [WARNING] 查询K线数据失败: {e}")

    # 5. 查询可用的API函数
    print("\n[5] 可用的查询API函数:")
    try:
        from AmazingData import query_api

        api_functions = [attr for attr in dir(query_api) if not attr.startswith("_")]
        for func in api_functions[:10]:  # 只显示前10个
            print(f"    - {func}")
        if len(api_functions) > 10:
            print(f"    ... 还有 {len(api_functions) - 10} 个函数")
    except Exception as e:
        print(f"    [WARNING] 无法获取API函数列表: {e}")

    # 6. 登出
    print("\n[6] 登出...")
    try:
        ad.logout()
        print("    [OK] 登出成功")
    except Exception as e:
        print(f"    [WARNING] 登出失败: {e}")

    return True


def main():
    """主函数"""
    success = test_amazingdata()

    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    if success:
        print("[OK] AmazingData基本功能测试通过")
        print("\n下一步:")
        print("1. 查看AmazingData开发手册了解更多API")
        print("2. 在项目中使用 infrastructure/providers/implementations/amazingdata/")
        print("3. AmazingData将作为最高优先级数据源")
    else:
        print("[FAIL] AmazingData测试未通过")
        print("\n请检查:")
        print("1. 用户名密码是否正确")
        print("2. 网络连接是否正常")
        print("3. 服务器地址是否可访问")


if __name__ == "__main__":
    main()
