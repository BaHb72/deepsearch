#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试不同的AmazingData服务器
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_servers():
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
    username = "212200038719"
    password = "212200038719@2025"

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
                stock_list = ad.BaseData.get_stock_list()
                if stock_list is not None:
                    print(f"[OK] 获取股票列表成功，共{len(stock_list)}只股票")

                # 登出
                ad.logout()
                print("[OK] 已登出")

                print(f"\n✅ 可用服务器: {host}:{port}")
                return True
            else:
                print(f"[FAIL] {name} 登录失败，返回值: {result}")

        except Exception as e:
            print(f"[ERROR] {name} 连接异常: {e}")

    print("\n所有服务器都无法连接，请检查：")
    print("1. 网络连接是否正常")
    print("2. 账号密码是否正确")
    print("3. 服务器是否在维护")

    return False


if __name__ == "__main__":
    test_servers()
