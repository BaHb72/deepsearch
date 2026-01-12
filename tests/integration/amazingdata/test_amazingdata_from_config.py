"""
从配置文件读取凭证测试AmazingData API
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from core.config import get_config


def test_amazingdata_config():
    """测试AmazingData配置和连接"""
    print("=" * 60)
    print("AmazingData API 测试（从配置文件读取凭证）")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 获取配置
    config = get_config()
    print(f"[INFO] 当前环境: {config.app.env}")

    # 优先检查新格式配置 (data_sources.providers.amazingdata)
    if hasattr(config, "data_sources") and config.data_sources:
        providers = config.data_sources.get("providers", {})
        if "amazingdata" in providers:
            print("[INFO] 使用新格式配置 (data_sources.providers.amazingdata)")
            ad_provider = providers["amazingdata"]

            enabled = ad_provider.get("enabled", False)
            ad_config_dict = ad_provider.get("config", {})
            conn_config = ad_config_dict.get("connection", {})

            host = conn_config.get("host", "localhost")
            port = conn_config.get("port", 8888)
            username = conn_config.get("username", "")
            password = conn_config.get("password", "")
            timeout = conn_config.get("timeout", 10)

            print("\n[INFO] AmazingData配置状态:")
            print(f"  启用: {enabled}")
            print(f"  服务器: {host}:{port}")
            print(f"  用户名: {'***' + username[-4:] if len(username) > 4 else '***'}")
            print(f"  密码: {'已设置' if password else '未设置'}")
            print(f"  超时: {timeout}秒")

            if not enabled:
                print("\n[WARNING] AmazingData未启用，请在配置文件中设置:")
                print("  data_sources.providers.amazingdata.enabled: true")
                return False

            if not username or not password:
                print("\n[ERROR] 用户名或密码未配置！")
                return False

            return {
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "timeout": timeout,
            }

    # 回退到旧格式配置 (amazingdata)
    if hasattr(config, "amazingdata"):
        print("[INFO] 使用旧格式配置 (amazingdata)")
        ad_config = config.amazingdata
        print("\n[INFO] AmazingData配置状态:")
        print(f"  启用: {ad_config.enabled}")

        # 获取连接配置
        if hasattr(ad_config, "connection"):
            conn_config = ad_config.connection
            host = conn_config.host
            port = conn_config.port
            username = conn_config.username
            password = conn_config.password
            timeout = conn_config.timeout
        else:
            # 兼容旧配置格式
            host = getattr(ad_config, "host", "localhost")
            port = getattr(ad_config, "port", 8888)
            username = getattr(ad_config, "username", "")
            password = str(getattr(ad_config, "password", ""))  # 确保密码是字符串
            timeout = getattr(ad_config, "timeout", 10)

        print(f"  服务器: {host}:{port}")
        print(f"  用户名: {'***' + username[-4:] if len(username) > 4 else '***'}")
        print(f"  密码: {'已设置' if password else '未设置'}")
        print(f"  超时: {timeout}秒")

        if not ad_config.enabled:
            print("\n[WARNING] AmazingData未启用，请在配置文件中设置 enabled: true")
            print("建议使用新格式配置 data_sources.providers.amazingdata")
            return False

        if not username or not password:
            print("\n[ERROR] 用户名或密码未配置！")
            return False

        return {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "timeout": timeout,
        }

    print("[FAIL] 配置文件中没有amazingdata配置项")
    return False


async def test_amazingdata_connection(credentials):
    """测试AmazingData连接"""
    print("\n" + "=" * 60)
    print("开始测试AmazingData连接")
    print("=" * 60)

    try:
        import AmazingData as ad

        print("[OK] AmazingData SDK已导入")
    except ImportError as e:
        print(f"[FAIL] AmazingData SDK未安装: {e}")
        print("请运行: uv pip install third_party/AmazingData-1.0.9-cp313-none-any.whl")
        return False

    # 创建客户端实例
    print("\n[1] 创建AmazingData客户端...")
    client = ad.AmazingDataClient()

    # 设置服务器
    print(f"[2] 设置服务器 {credentials['host']}:{credentials['port']}...")
    client.set_server(credentials["host"], credentials["port"])

    # 登录
    print(f"[3] 登录用户 {credentials['username'][:3]}***...")
    try:
        login_result = client.login(credentials["username"], credentials["password"])
        if login_result:
            print("[OK] 登录成功")
        else:
            print("[FAIL] 登录失败，请检查用户名密码")
            return False
    except Exception as e:
        print(f"[FAIL] 登录异常: {e}")
        return False

    # 测试获取股票列表
    print("\n[4] 测试获取股票列表...")
    try:
        stock_list = client.get_stock_list("A股")
        if stock_list and len(stock_list) > 0:
            print(f"[OK] 获取股票列表成功，共 {len(stock_list)} 只股票")
            print(f"    示例: {stock_list[:5] if len(stock_list) >= 5 else stock_list}")
        else:
            print("[FAIL] 获取股票列表为空")
    except Exception as e:
        print(f"[FAIL] 获取股票列表失败: {e}")

    # 测试获取实时行情
    print("\n[5] 测试获取实时行情...")
    test_symbol = "000001"  # 平安银行
    try:
        quote = client.get_realtime_quote(test_symbol)
        if quote:
            print(f"[OK] 获取 {test_symbol} 实时行情成功")
            print(f"    最新价: {quote.get('last', 'N/A')}")
            print(f"    涨跌幅: {quote.get('pct_chg', 'N/A')}%")
            print(f"    成交量: {quote.get('volume', 'N/A')}")
        else:
            print(f"[FAIL] 获取 {test_symbol} 实时行情失败")
    except Exception as e:
        print(f"[FAIL] 获取实时行情异常: {e}")

    # 测试获取K线数据
    print("\n[6] 测试获取K线数据...")
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        kline = client.get_kline(
            symbol=test_symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
        )

        if kline is not None and len(kline) > 0:
            print(f"[OK] 获取K线数据成功，共 {len(kline)} 条")
            if isinstance(kline, pd.DataFrame):
                print("    最近5条数据:")
                print(kline.tail(5))
            else:
                print(f"    数据类型: {type(kline)}")
        else:
            print("[FAIL] 获取K线数据失败")
    except Exception as e:
        print(f"[FAIL] 获取K线数据异常: {e}")

    # 登出
    print("\n[7] 登出...")
    try:
        client.logout()
        print("[OK] 登出成功")
    except Exception as e:
        print(f"[WARNING] 登出异常: {e}")

    return True


def main():
    """主函数"""
    # 测试配置
    credentials = test_amazingdata_config()

    if not credentials:
        print("\n[FAIL] 配置检查未通过，无法继续测试")
        print("\n请确保:")
        print("1. 配置文件中设置 amazingdata.enabled: true")
        print("2. 配置文件中设置正确的用户名和密码")
        print("3. 已安装AmazingData SDK")
        return

    # 检查SDK
    try:
        import AmazingData as ad

        print(
            f"\n[INFO] AmazingData SDK版本: {ad.__version__ if hasattr(ad, '__version__') else '未知'}"
        )
    except ImportError:
        print("\n[ERROR] AmazingData SDK未安装")
        print("请运行: uv pip install third_party/AmazingData-1.0.9-cp313-none-any.whl")
        return

    # 运行异步测试
    try:
        success = asyncio.run(test_amazingdata_connection(credentials))

        # 打印总结
        print("\n" + "=" * 60)
        print("测试总结")
        print("=" * 60)

        if success:
            print("[OK] AmazingData API测试通过")
            print("\n可以在项目中使用AmazingData作为数据源:")
            print("  - 通过 infrastructure/providers/implementations/amazingdata/")
            print("  - 数据源优先级最高（优先于CloudFlare和AkShare）")
        else:
            print("[FAIL] AmazingData API测试未通过")
            print("\n请检查:")
            print("  - 网络连接是否正常")
            print("  - 服务器地址是否正确")
            print("  - 用户名密码是否有效")

    except Exception as e:
        print(f"\n[ERROR] 测试过程出现异常: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
