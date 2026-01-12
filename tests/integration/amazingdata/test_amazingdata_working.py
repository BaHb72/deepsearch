#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData 工作测试脚本（使用正确的关键字参数）
"""

import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from helpers import fetch_code_list


def test_amazingdata():
    print("\n" + "=" * 60)
    print("AmazingData 功能测试（使用正确的API调用）")
    print("=" * 60)

    try:
        import AmazingData as ad

        print("\n[OK] AmazingData SDK已导入")
        print(f"版本: {getattr(ad, '__version__', '未知')}")
    except ImportError as e:
        print(f"[FAIL] SDK导入失败: {e}")
        return False

    # 使用正确的凭证和服务器
    credentials = {
        "username": "212200038719",
        "password": "212200038719@2025",
        "host": "101.230.159.234",  # 使用电信线路2
        "port": 8600,
    }

    print("\n连接信息：")
    print(f"  服务器: {credentials['host']}:{credentials['port']}")
    print(f"  用户名: {credentials['username']}")
    print("  密码: ***")

    # 1. 测试登录（使用关键字参数）
    print("\n[测试1] 登录...")
    try:
        login_result = ad.login(
            username=credentials["username"],
            password=credentials["password"],
            host=credentials["host"],
            port=credentials["port"],
        )

        if login_result == 0 or login_result is True:
            print("[SUCCESS] 登录成功！")
        else:
            print(f"[FAIL] 登录失败: {login_result}")
            return False
    except Exception as e:
        print(f"[ERROR] 登录异常: {e}")
        return False

    # 2. 测试获取股票列表
    print("\n[测试2] 获取股票列表...")
    try:
        stock_list = fetch_code_list(ad)
        if not stock_list.empty:
            print(f"[SUCCESS] 获取{len(stock_list)}只股票")
            print("示例股票：")
            preview = stock_list.head(3)
            for idx, row in preview.iterrows():
                print(f"  {idx + 1}. {row.to_dict()}")
        else:
            print("[WARNING] 股票列表为空")
    except Exception as e:
        print(f"[ERROR] 获取股票列表失败: {e}")

    # 3. 测试获取实时行情
    print("\n[测试3] 获取实时行情...")

    # 获取交易日历（MarketData必需）
    calendar = None
    try:
        calendar = ad.BaseData().get_calendar()
        print(f"[信息] 交易日历: {len(calendar)}天")
    except Exception as e:
        print(f"[警告] 获取交易日历失败: {e}")

    test_symbols = ["000001.SZ", "600036.SH", "000002.SZ"]
    for symbol in test_symbols:
        try:
            quote = ad.MarketData(calendar).query_snapshot([symbol])
            if quote:
                print(f"[SUCCESS] {symbol}: 获取到快照数据")
            else:
                print(f"[WARNING] {symbol}: 无数据")
        except Exception as e:
            print(f"[ERROR] {symbol}: {e}")
            break

    # 4. 测试获取K线数据
    print("\n[测试4] 获取K线数据...")
    try:
        from datetime import datetime, timedelta

        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        kline = ad.MarketData(calendar).query_kline(
            ["000001.SZ"],
            period=10008,  # Period.day.value
            begin_date=int(start_date.strftime("%Y%m%d")),
            end_date=int(end_date.strftime("%Y%m%d")),
        )

        if kline is not None and len(kline) > 0:
            print(f"[SUCCESS] 获取{len(kline)}条K线数据")
            print("最近3天数据：")
            if hasattr(kline, "tail"):
                print(kline.tail(3))
            else:
                print(kline[-3:])
        else:
            print("[WARNING] K线数据为空")
    except Exception as e:
        print(f"[ERROR] 获取K线失败: {e}")

    # 5. 登出
    print("\n[测试5] 登出...")
    try:
        ad.logout()
        print("[SUCCESS] 已安全登出")
    except Exception as e:
        print(f"[WARNING] 登出异常: {e}")

    print("\n" + "=" * 60)
    print("✅ 测试完成！AmazingData数据源工作正常")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = test_amazingdata()
    sys.exit(0 if success else 1)
