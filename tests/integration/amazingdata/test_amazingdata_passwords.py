#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试不同的密码格式
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_passwords():
    print("\n" + "=" * 60)
    print("AmazingData 密码格式测试")
    print("=" * 60)

    try:
        import AmazingData as ad
        print("[OK] AmazingData SDK已导入")
    except ImportError as e:
        print(f"[FAIL] SDK未安装: {e}")
        return

    username = '212200038719'
    host = '120.86.124.106'
    port = 8600

    # 尝试不同的密码格式
    passwords = [
        ('原配置密码', '212200038719@2025'),
        ('可能的密码1', '21220003871920250820'),  # 用户名+日期格式
        ('可能的密码2', '212200038719'),  # 与用户名相同
        ('可能的密码3', '20250820'),  # 只有日期
        ('可能的密码4', '212200038719@20250820'),  # 用户名@日期
    ]

    print(f"\n账号信息：")
    print(f"  用户名: {username}")
    print(f"  服务器: {host}:{port}")

    for name, password in passwords:
        print(f"\n测试密码 [{name}]: {password}")
        print("-" * 40)

        try:
            print(f"正在尝试登录...")
            result = ad.login(username, password, host, port)

            if result == 0 or result is True:
                print(f"[SUCCESS] 登录成功！正确的密码是: {password}")

                # 测试获取数据
                print("验证：获取股票列表...")
                stock_list = ad.BaseData.get_stock_list()
                if stock_list is not None:
                    print(f"[OK] 获取股票列表成功，共{len(stock_list)}只股票")

                # 登出
                ad.logout()
                print("[OK] 已登出")

                print(f"\n✅ 找到正确密码: {password}")
                print(f"请更新配置文件中的密码为: {password}")
                return True
            else:
                print(f"[FAIL] 密码错误")

        except Exception as e:
            print(f"[ERROR] 异常: {e}")

    print("\n所有密码都无法登录")
    print("请确认正确的密码格式")

    return False

if __name__ == "__main__":
    test_passwords()