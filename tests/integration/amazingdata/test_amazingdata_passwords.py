#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试不同的密码格式
"""

import os
import sys

import pytest

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import fetch_code_list


def test_passwords():
    if not os.getenv("RUN_AMAZINGDATA_DIAGNOSTIC_TESTS"):
        pytest.skip("密码格式诊断测试默认关闭，设置 RUN_AMAZINGDATA_DIAGNOSTIC_TESTS=1 后执行。")

    print("\n" + "=" * 60)
    print("AmazingData 密码格式测试")
    print("=" * 60)

    try:
        import AmazingData as ad

        print("[OK] AmazingData SDK已导入")
    except ImportError as e:
        print(f"[FAIL] SDK未安装: {e}")
        return

    username = os.getenv("AMAZINGDATA_USERNAME", "").strip()
    host = os.getenv("AMAZINGDATA_HOST", "120.86.124.106").strip()
    port = int(os.getenv("AMAZINGDATA_PORT", "8600"))
    if not username:
        pytest.skip("缺少 AMAZINGDATA_USERNAME，跳过密码格式诊断测试。")

    # 尝试不同的密码格式
    passwords = [
        ("环境变量密码", os.getenv("AMAZINGDATA_PASSWORD", "").strip()),
        ("可能的密码1", f"{username}20250820"),  # 用户名+日期格式
        ("可能的密码2", username),  # 与用户名相同
        ("可能的密码3", "20250820"),  # 只有日期
        ("可能的密码4", f"{username}@20250820"),  # 用户名@日期
    ]
    passwords = [(name, pwd) for name, pwd in passwords if pwd]

    print("\n账号信息：")
    print(f"  用户名: {username}")
    print(f"  服务器: {host}:{port}")
    if not passwords:
        pytest.skip("缺少可测试的密码候选，跳过密码格式诊断测试。")

    for name, password in passwords:
        print(f"\n测试密码 [{name}]: {password}")
        print("-" * 40)

        try:
            print("正在尝试登录...")
            result = ad.login(username, password, host, port)

            if result == 0 or result is True:
                print(f"[SUCCESS] 登录成功！正确的密码是: {password}")

                # 测试获取数据
                print("验证：获取股票列表...")
                stock_list = fetch_code_list(ad)
                if not stock_list.empty:
                    print(f"[OK] 获取股票列表成功，共{len(stock_list)}只股票")
                else:
                    print("[WARNING] 股票列表为空")

                # 登出
                ad.logout()
                print("[OK] 已登出")

                print(f"\n✅ 找到正确密码: {password}")
                print(f"请更新配置文件中的密码为: {password}")
                return True
            else:
                print("[FAIL] 密码错误")

        except SystemExit as exc:
            print(f"[WARNING] SDK登录触发 SystemExit({exc})，按失败继续尝试下一组密码")
            continue
        except Exception as e:
            print(f"[ERROR] 异常: {e}")

    print("\n所有密码都无法登录")
    print("请确认正确的密码格式")

    return False


if __name__ == "__main__":
    test_passwords()
