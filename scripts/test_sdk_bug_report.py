# encoding: utf-8
"""
AmazingData SDK 正确用法演示
============================

本脚本演示 query_kline 的正确调用方式：
1. 必须先获取交易日历 (get_calendar)
2. 创建 MarketData 时传入 calendar
3. period 参数使用 Period.xxx.value (int)

使用方法：
    uv run python scripts/test_sdk_bug_report.py
"""

import sys
from datetime import datetime


def main():
    print("=" * 70)
    print("AmazingData SDK 正确用法演示")
    print("=" * 70)
    print(f"执行时间: {datetime.now()}")
    print(f"Python版本: {sys.version}")
    print()

    # Step 1: 导入SDK
    print("[Step 1] 导入 AmazingData SDK...")
    try:
        import AmazingData as ad

        print(f"  SDK路径: {ad.__file__}")
    except ImportError as e:
        print(f"  导入失败: {e}")
        return

    # Step 2: 登录
    print()
    print("[Step 2] 登录...")
    login_params = {
        "username": "212200038719",
        "password": "212200038719@2025",
        "host": "101.230.159.234",
        "port": 8600,
    }
    try:
        result = ad.login(
            login_params["username"],
            login_params["password"],
            login_params["host"],
            login_params["port"],
        )
        print(f"  登录结果: {result}")
        if result not in (0, True):
            print("  登录失败，退出")
            return
    except Exception as e:
        print(f"  登录异常: {e}")
        return

    # Step 3: 获取交易日历（关键步骤！）
    print()
    print("[Step 3] 获取交易日历（关键步骤）...")
    try:
        base = ad.BaseData()
        calendar = base.get_calendar()
        print(f"  交易日历长度: {len(calendar)}")
        print(f"  前5个交易日: {list(calendar)[:5]}")
    except Exception as e:
        print(f"  获取日历失败: {e}")
        ad.logout(login_params["username"])
        return

    # Step 4: 使用 calendar 创建 MarketData
    print()
    print("[Step 4] 创建 MarketData（传入 calendar）...")
    try:
        market = ad.MarketData(calendar=calendar)
        print("  MarketData 创建成功")
    except Exception as e:
        print(f"  创建失败: {e}")
        ad.logout(login_params["username"])
        return

    # Step 5: 调用 query_kline
    print()
    print("[Step 5] 调用 query_kline...")
    query_params = {
        "code_list": ["000001.SZ"],
        "begin_date": 20241201,
        "end_date": 20241220,
        "period": ad.constant.Period.day.value,  # 传 int 值
    }
    print("  调用参数:")
    for key, value in query_params.items():
        if key == "period":
            print(f"    {key}: {value} (Period.day.value)")
        else:
            print(f"    {key}: {value}")

    try:
        kline = market.query_kline(**query_params)
        print()
        print("  ===== 查询成功！ =====")
        if kline:
            for code, data in kline.items():
                print(f"  {code}: {len(data)} 条记录")
                if hasattr(data, "head"):
                    print(data.head())
                elif len(data) > 0:
                    print(f"  第一条: {data[0]}")
    except Exception as e:
        print(f"  查询失败: {e}")
        import traceback

        traceback.print_exc()

    # Step 6: 登出
    print()
    print("[Step 6] 登出...")
    try:
        ad.logout(login_params["username"])
        print("  登出完成")
    except Exception as e:
        print(f"  登出异常: {e}")

    print()
    print("=" * 70)
    print("演示完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
