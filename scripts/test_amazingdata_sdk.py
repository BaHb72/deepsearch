#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData SDK 直接测试脚本

用于诊断 get_code_list 接口是否正常工作，绕过 DaskAdapter/Actor 层。

使用方法：
    uv run python scripts/test_amazingdata_sdk.py
"""

import sys
import time
from pathlib import Path

import yaml


def load_amazingdata_config():
    """从配置文件读取 AmazingData 凭证"""
    project_root = Path(__file__).parent.parent
    config_path = project_root / "packages" / "core" / "config" / "data_sources.yaml"

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    amazingdata_config = config["providers"]["amazingdata"]["config"]["connection"]
    return {
        "username": amazingdata_config["username"],
        "password": amazingdata_config["password"],
        "host": amazingdata_config["host"],
        "port": amazingdata_config["port"],
    }


def main():
    print("=" * 60)
    print("AmazingData SDK 直接测试")
    print("=" * 60)

    # 1. 加载 SDK
    print("\n[1/4] 加载 SDK...")
    start = time.perf_counter()
    try:
        import AmazingData as ad

        print(f"  SDK 加载成功: {ad}")
        print(f"  耗时: {time.perf_counter() - start:.2f}s")
    except ImportError as e:
        print(f"  SDK 加载失败: {e}")
        print("  请确保 AmazingData SDK 已安装")
        return 1

    # 2. 读取配置
    print("\n[2/4] 读取配置...")
    try:
        config = load_amazingdata_config()
        username = config["username"]
        password = config["password"]
        host = config["host"]
        port = config["port"]
        print(f"  host: {host}:{port}")
        print(f"  username: {username}")
    except Exception as e:
        print(f"  配置读取失败: {e}")
        import traceback

        traceback.print_exc()
        return 1

    # 3. 登录
    print("\n[3/4] 登录...")
    start = time.perf_counter()
    try:
        result = ad.login(username=username, password=password, host=host, port=port)
        elapsed = time.perf_counter() - start
        print(f"  登录结果: {result}")
        print(f"  耗时: {elapsed:.2f}s")
        if result != 0 and result is not True:
            print(f"  登录失败，错误码: {result}")
            return 1
    except Exception as e:
        print(f"  登录异常: {e}")
        import traceback

        traceback.print_exc()
        return 1

    # 4. 调用 get_code_list
    print("\n[4/4] 调用 BaseData.get_code_list()...")
    try:
        base_data = ad.BaseData()

        # 测试多种 security_type
        security_types = ["EXTRA_STOCK_A", "STOCK_SH", "STOCK_SZ"]
        for sec_type in security_types:
            print(f"\n  测试 security_type={sec_type}")
            start = time.perf_counter()
            try:
                result = base_data.get_code_list(security_type=sec_type)
                elapsed = time.perf_counter() - start

                if result is not None:
                    if hasattr(result, "__len__"):
                        print(f"    结果: {len(result)} 个代码")
                        if len(result) > 0:
                            # 显示前5个示例
                            sample = list(result)[:5] if hasattr(result, "__iter__") else result[:5]
                            print(f"    示例: {sample}")
                    else:
                        print(f"    结果类型: {type(result)}")
                        print(f"    结果值: {result}")
                else:
                    print(f"    结果: None")
                print(f"    耗时: {elapsed:.2f}s")
            except Exception as e:
                elapsed = time.perf_counter() - start
                print(f"    调用失败: {e}")
                print(f"    耗时: {elapsed:.2f}s")

    except Exception as e:
        print(f"  创建 BaseData 失败: {e}")
        import traceback

        traceback.print_exc()
        return 1

    # 附加测试：其他常用接口
    print("\n" + "-" * 60)
    print("附加测试：其他常用接口")
    print("-" * 60)

    # 交易日历
    print("\n  [附加1] get_trading_calendar...")
    start = time.perf_counter()
    try:
        calendar = ad.BaseData.get_trading_calendar("20241101", "20241130")
        elapsed = time.perf_counter() - start
        if calendar:
            print(f"    结果: {len(calendar)} 天")
        else:
            print(f"    结果: {calendar}")
        print(f"    耗时: {elapsed:.2f}s")
    except Exception as e:
        print(f"    失败: {e}")

    # 股票列表（另一种方式）
    print("\n  [附加2] get_stock_list...")
    start = time.perf_counter()
    try:
        stock_list = ad.BaseData.get_stock_list()
        elapsed = time.perf_counter() - start
        if stock_list:
            print(f"    结果: {len(stock_list)} 只")
        else:
            print(f"    结果: {stock_list}")
        print(f"    耗时: {elapsed:.2f}s")
    except Exception as e:
        print(f"    失败: {e}")

    # 登出
    print("\n" + "-" * 60)
    print("登出...")
    try:
        ad.logout()
        print("  登出成功")
    except Exception as e:
        print(f"  登出异常（可忽略）: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
