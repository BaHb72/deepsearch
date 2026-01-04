"""
测试AmazingData API连接和功能
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

# 导入项目依赖
from core.config import get_config


def check_amazingdata_sdk():
    """检查AmazingData SDK是否已安装"""
    print("=" * 60)
    print("检查AmazingData SDK安装情况")
    print("=" * 60)

    try:
        import AmazingData as ad

        print("[OK] AmazingData SDK已安装")
        print(f"  模块: {ad}")
        if hasattr(ad, "__version__"):
            print(f"  版本: {ad.__version__}")
        return True
    except ImportError as e:
        print(f"[FAIL] AmazingData SDK未安装: {e}")
        print("\n需要安装AmazingData SDK:")
        print("  方法1: pip install AmazingData")
        print("  方法2: 使用third_party目录下的whl文件:")
        print("         uv pip install third_party/AmazingData-1.0.9-cp313-none-any.whl")
        return False


def check_amazingdata_config():
    """检查AmazingData配置"""
    print("\n" + "=" * 60)
    print("检查AmazingData配置")
    print("=" * 60)

    config = get_config()

    # 检查配置是否存在
    if not hasattr(config, "amazingdata"):
        print("[FAIL] 配置文件中没有amazingdata配置项")
        return False

    ad_config = config.amazingdata
    print("[OK] 找到AmazingData配置")
    print(f"  启用状态: {ad_config.enabled}")

    # 从connection配置获取主机和端口
    if hasattr(ad_config, "connection"):
        print(f"  主机地址: {ad_config.connection.host}")
        print(f"  端口: {ad_config.connection.port}")
        print(f"  用户名: {'已配置' if ad_config.connection.username else '未配置'}")
        print(f"  密码: {'已配置' if ad_config.connection.password else '未配置'}")
        print(f"  超时时间: {ad_config.connection.timeout}秒")
        print(f"  自动重连: {ad_config.connection.auto_reconnect}")
    else:
        # 兼容旧配置格式
        if hasattr(ad_config, "host"):
            print(f"  主机地址: {getattr(ad_config, 'host', 'N/A')}")
        if hasattr(ad_config, "port"):
            print(f"  端口: {getattr(ad_config, 'port', 'N/A')}")
        if hasattr(ad_config, "username"):
            print(f"  用户名: {'已配置' if getattr(ad_config, 'username', '') else '未配置'}")
        if hasattr(ad_config, "password"):
            print(f"  密码: {'已配置' if getattr(ad_config, 'password', '') else '未配置'}")
        if hasattr(ad_config, "timeout"):
            print(f"  超时时间: {getattr(ad_config, 'timeout', 10)}秒")
        if hasattr(ad_config, "auto_reconnect"):
            print(f"  自动重连: {getattr(ad_config, 'auto_reconnect', True)}")
        if hasattr(ad_config, "use_local"):
            print(f"  使用本地数据: {getattr(ad_config, 'use_local', False)}")
        if hasattr(ad_config, "local_path"):
            print(f"  本地数据路径: {getattr(ad_config, 'local_path', 'N/A')}")

    if not ad_config.enabled:
        print("\n[WARNING] AmazingData在配置中未启用")
        print("  请在配置文件中设置 amazingdata.enabled: true")

    # 检查用户名密码
    username = None
    password = None
    if hasattr(ad_config, "connection"):
        username = ad_config.connection.username
        password = ad_config.connection.password
    else:
        username = getattr(ad_config, "username", None)
        password = getattr(ad_config, "password", None)

    if not username or not password:
        print("\n[WARNING] AmazingData用户名或密码未配置")
        print("  请在配置文件中设置用户名和密码")

    return True


async def test_amazingdata_provider():
    """测试AmazingData Provider"""
    print("\n" + "=" * 60)
    print("测试AmazingData Provider")
    print("=" * 60)

    try:
        from core.infrastructure.providers.implementations.amazingdata.amazingdata import (
            HAS_AMAZINGDATA,
            AmazingDataConfig,
            AmazingDataProvider,
        )

        print("[OK] 成功导入AmazingDataProvider")
        print(f"  SDK状态: {'已安装' if HAS_AMAZINGDATA else '未安装'}")

        if not HAS_AMAZINGDATA:
            print("[FAIL] AmazingData SDK未安装，无法继续测试")
            return False
    except ImportError as e:
        print(f"[FAIL] 导入AmazingDataProvider失败: {e}")
        return False

    # 获取配置
    config = get_config()
    ad_config = config.amazingdata

    # 提取配置参数，兼容不同的配置格式
    if hasattr(ad_config, "connection"):
        # 新格式：从connection子配置读取
        username = ad_config.connection.username or ""
        password = ad_config.connection.password or ""
        host = ad_config.connection.host
        port = ad_config.connection.port
        timeout = ad_config.connection.timeout
        max_retries = ad_config.connection.max_retries
        heartbeat_interval = ad_config.connection.heartbeat_interval
        auto_reconnect = ad_config.connection.auto_reconnect
    else:
        # 旧格式：直接从根配置读取
        username = getattr(ad_config, "username", "")
        password = getattr(ad_config, "password", "")
        host = getattr(ad_config, "host", "localhost")
        port = getattr(ad_config, "port", 8888)
        timeout = getattr(ad_config, "timeout", 10)
        max_retries = getattr(ad_config, "max_retries", 3)
        heartbeat_interval = getattr(ad_config, "heartbeat_interval", 30)
        auto_reconnect = getattr(ad_config, "auto_reconnect", True)

    # 提取订阅配置
    if hasattr(ad_config, "subscription"):
        subscription_enabled = ad_config.subscription.enabled
        subscription_batch_size = ad_config.subscription.batch_size
        max_subscriptions = ad_config.subscription.max_symbols
    else:
        subscription_enabled = getattr(ad_config, "subscription_enabled", True)
        subscription_batch_size = getattr(ad_config, "subscription_batch_size", 100)
        max_subscriptions = getattr(ad_config, "max_subscriptions", 500)

    # 创建Provider配置
    try:
        provider_config = AmazingDataConfig(
            username=username,
            password=password,
            host=host,
            port=port,
            timeout=timeout,
            max_retries=max_retries,
            heartbeat_interval=heartbeat_interval,
            auto_reconnect=auto_reconnect,
            subscription_enabled=subscription_enabled,
            subscription_batch_size=subscription_batch_size,
            max_subscriptions=max_subscriptions,
        )
        print("[OK] 创建Provider配置成功")
    except Exception as e:
        print(f"[FAIL] 创建Provider配置失败: {e}")
        return False

    # 创建Provider实例
    try:
        provider = AmazingDataProvider(provider_config)
        print("[OK] 创建AmazingDataProvider实例成功")
    except Exception as e:
        print(f"[FAIL] 创建AmazingDataProvider实例失败: {e}")
        return False

    # 测试连接
    try:
        print("\n测试1: 连接到AmazingData...")
        connected = await provider.connect()
        if connected:
            print("[OK] 成功连接到AmazingData")
        else:
            print("[FAIL] 连接失败")
            return False
    except Exception as e:
        print(f"[FAIL] 连接测试失败: {e}")
        return False

    # 测试获取股票列表
    try:
        print("\n测试2: 获取股票列表...")
        from core.infrastructure.providers.interfaces.base import DataRequest

        request = DataRequest(data_type="stock_list", params={})

        stock_list = await provider.get_data(request)
        if stock_list:
            print("[OK] 成功获取股票列表")
            if isinstance(stock_list, list):
                print(f"  共{len(stock_list)}只股票")
                if stock_list:
                    print(f"  示例: {stock_list[:5]}")
        else:
            print("[FAIL] 获取股票列表失败")
    except Exception as e:
        print(f"[FAIL] 获取股票列表失败: {e}")

    # 测试获取实时行情
    try:
        print("\n测试3: 获取实时行情...")
        request = DataRequest(data_type="realtime_quote", params={"symbol": "000001.SZ"})

        quote = await provider.get_data(request)
        if quote:
            print("[OK] 成功获取000001.SZ的实时行情")
            print(f"  数据: {quote}")
        else:
            print("[FAIL] 获取实时行情失败")
    except Exception as e:
        print(f"[FAIL] 获取实时行情失败: {e}")

    # 测试获取K线数据
    try:
        print("\n测试4: 获取K线数据...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        request = DataRequest(
            data_type="kline",
            params={
                "symbol": "000001.SZ",
                "period": "1d",
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
            },
        )

        kline_data = await provider.get_data(request)
        if kline_data is not None:
            print("[OK] 成功获取K线数据")
            if isinstance(kline_data, pd.DataFrame):
                print(f"  共{len(kline_data)}条记录")
                if not kline_data.empty:
                    print("  最近5条数据:")
                    print(kline_data.tail(5))
        else:
            print("[FAIL] 获取K线数据失败")
    except Exception as e:
        print(f"[FAIL] 获取K线数据失败: {e}")

    # 断开连接
    try:
        await provider.disconnect()
        print("\n[OK] 成功断开连接")
    except Exception as e:
        print(f"\n[FAIL] 断开连接失败: {e}")

    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("AmazingData API 测试报告")
    print("=" * 60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 检查SDK
    has_sdk = check_amazingdata_sdk()

    # 检查配置
    has_config = check_amazingdata_config()

    # 如果SDK已安装，运行Provider测试
    if has_sdk:
        try:
            asyncio.run(test_amazingdata_provider())
        except Exception as e:
            print(f"\n[FAIL] Provider测试失败: {e}")
    else:
        print("\n[WARNING] 跳过Provider测试（SDK未安装）")

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    if has_sdk:
        print("[OK] AmazingData SDK已安装")
    else:
        print("[FAIL] AmazingData SDK未安装")

    if has_config:
        config = get_config()
        if config.amazingdata.enabled:
            print("[OK] AmazingData已在配置中启用")
        else:
            print("[WARNING] AmazingData在配置中未启用")

        # 检查用户名密码
        username = None
        password = None
        if hasattr(config.amazingdata, "connection"):
            username = config.amazingdata.connection.username
            password = config.amazingdata.connection.password
        else:
            username = getattr(config.amazingdata, "username", None)
            password = getattr(config.amazingdata, "password", None)

        if username and password:
            print("[OK] 用户凭证已配置")
        else:
            print("[WARNING] 用户凭证未配置")

    print("\n建议:")
    if not has_sdk:
        print(
            "1. 安装AmazingData SDK: uv pip install third_party/AmazingData-1.0.9-cp313-none-any.whl"
        )

    if has_config:
        config = get_config()
        if not config.amazingdata.enabled:
            print("2. 在配置文件中启用AmazingData: amazingdata.enabled: true")

        # 检查用户名密码
        username = None
        password = None
        if hasattr(config.amazingdata, "connection"):
            username = config.amazingdata.connection.username
            password = config.amazingdata.connection.password
        else:
            username = getattr(config.amazingdata, "username", None)
            password = getattr(config.amazingdata, "password", None)

        if not username or not password:
            print("3. 在配置文件中设置用户名和密码")


if __name__ == "__main__":
    main()
