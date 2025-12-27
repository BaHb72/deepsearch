"""
使用正确的AmazingData SDK API测试
"""

import os
import sys
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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

    base_data = None
    market_data = None

    # 2. 查询股票列表
    print("\n[2] 查询股票列表...")
    try:
        base_data = ad.BaseData()
        stock_list = base_data.get_code_list(security_type="EXTRA_STOCK_A")
        if stock_list:
            print(f"    [OK] 获取{len(stock_list)}只股票")
            preview = list(stock_list)[:5]
            print(f"    示例: {preview}")
        else:
            print("    [INFO] 未返回股票列表")
    except Exception as e:
        print(f"    [WARNING] 查询股票列表失败: {e}")

    # 3. 查询实时行情
    print("\n[3] 查询实时行情...")
    test_code = "000001"  # 平安银行
    try:
        calendar = None
        if base_data is not None:
            calendar = base_data.get_calendar()
        market_data = ad.MarketData(calendar) if calendar else ad.MarketData()
        today = int(datetime.now().strftime("%Y%m%d"))
        snapshot = market_data.query_snapshot([test_code], begin_date=today, end_date=today)
        if isinstance(snapshot, dict) and snapshot.get(test_code):
            print("    [OK] 获取实时行情")
        else:
            print("    [INFO] 实时行情接口未返回数据")
    except Exception as e:
        print(f"    [WARNING] 查询实时行情失败: {e}")

    # 4. 查询K线数据
    print("\n[4] 查询K线数据...")
    try:
        if market_data is None:
            market_data = ad.MarketData()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        period_value = getattr(getattr(ad.constant, "Period", None), "day", None)
        period_value = getattr(period_value, "value", "day")
        kline_dict = market_data.query_kline(
            [test_code],
            begin_date=int(start_date.strftime("%Y%m%d")),
            end_date=int(end_date.strftime("%Y%m%d")),
            period=period_value,
        )
        records = kline_dict.get(test_code) if isinstance(kline_dict, dict) else None
        if records:
            print(f"    [OK] 获取K线数据，共{len(records)}条")
        else:
            print("    [INFO] K线接口未返回数据")
    except Exception as e:
        print(f"    [WARNING] 查询K线数据失败: {e}")

    # 5. 查询常用能力概览
    print("\n[5] 常用能力概览:")
    try:
        base_attrs = [attr for attr in dir(base_data or ad.BaseData()) if not attr.startswith("_")]
        market_attrs = [
            attr for attr in dir(market_data or ad.MarketData()) if not attr.startswith("_")
        ]
        print(f"    BaseData: {base_attrs[:8]}")
        print(f"    MarketData: {market_attrs[:8]}")
    except Exception as e:
        print(f"    [WARNING] 无法列举接口能力: {e}")

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
