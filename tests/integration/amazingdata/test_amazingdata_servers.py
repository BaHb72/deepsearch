#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试不同的AmazingData服务器
"""

import os
import sys

import pytest

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import fetch_code_list


def test_servers():
    if not os.getenv("RUN_AMAZINGDATA_DIAGNOSTIC_TESTS"):
        pytest.skip("多服务器诊断测试默认关闭，设置 RUN_AMAZINGDATA_DIAGNOSTIC_TESTS=1 后执行。")

    print("\n" + "=" * 60)
    print("AmazingData 多服务器连接测试")
    print("=" * 60)

    try:
        import AmazingData as ad

        print("[OK] AmazingData SDK已导入")
    except ImportError as e:
        print(f"[FAIL] SDK未安装: {e}")
        return

    # 测试账号
    username = os.getenv("AMAZINGDATA_USERNAME", "").strip()
    password = os.getenv("AMAZINGDATA_PASSWORD", "").strip()
    if not username or not password:
        pytest.skip("缺少 AMAZINGDATA_USERNAME/AMAZINGDATA_PASSWORD，跳过服务器诊断测试。")

    # 多个服务器地址
    servers = [
        ("电信线路1", "120.86.124.106", 8600),
        ("电信线路2", "101.230.159.234", 8600),
        ("联通线路", "140.206.44.234", 8600),
    ]

    print("\n账号信息：")
    print(f"  用户名: {username}")
    print(f"  密码: {password}")

    for name, host, port in servers:
        print(f"\n测试 {name}: {host}:{port}")
        print("-" * 40)

        try:
            print("正在连接...")
            result = ad.login(username, password, host, port)

            if result == 0 or result is True:
                print(f"[SUCCESS] {name} 登录成功！")

                # 测试获取数据
                print("测试获取股票列表...")
                stock_list = fetch_code_list(ad)
                if not stock_list.empty:
                    print(f"[OK] 获取股票列表成功，共{len(stock_list)}只股票")
                else:
                    print("[WARNING] 股票列表为空")

                # 登出
                ad.logout()
                print("[OK] 已登出")

                print(f"\n✅ 可用服务器: {host}:{port}")
                return True
            else:
                print(f"[FAIL] {name} 登录失败，返回值: {result}")

        except SystemExit as exc:
            print(f"[WARNING] {name} 登录触发 SystemExit({exc})，按失败继续")
            continue
        except Exception as e:
            print(f"[ERROR] {name} 连接异常: {e}")

    print("\n所有服务器都无法连接，请检查：")
    print("1. 网络连接是否正常")
    print("2. 账号密码是否正确")
    print("3. 服务器是否在维护")

    return False


if __name__ == "__main__":
    test_servers()
