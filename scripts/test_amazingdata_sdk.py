#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData SDK 直接测试脚本
"""

import sys

sys.path.insert(0, "d:/Stock/code/deepsearch")


def test_amazingdata_direct():
    """直接测试 AmazingData SDK"""
    print("=" * 60)
    print("AmazingData SDK 直接测试")
    print("=" * 60)

    # 尝试导入SDK
    try:
        import AmazingData as ad

        print("[OK] SDK 导入成功")
    except ImportError as e:
        print(f"[FAIL] SDK 导入失败: {e}")
        return

    # 登录
    print("\n[1] 登录测试...")
    try:
        result = ad.login("212200038719", "212200038719@2025", "101.230.159.234", 8600)
        print(f"  登录返回值: {result}")
        if result == 0 or result is True:
            print("  [OK] 登录成功")
        else:
            print(f"  [FAIL] 登录失败，错误码: {result}")
            return
    except Exception as e:
        print(f"  [FAIL] 登录异常: {e}")
        return

    # 测试基础数据
    print("\n[2] 基础数据测试...")

    # 交易日历
    try:
        if hasattr(ad, "BaseData"):
            calendar = ad.BaseData.get_trading_calendar("20241101", "20241130")
            if calendar:
                print(f"  [OK] 交易日历: {len(calendar)}天")
            else:
                print("  [FAIL] 交易日历: 无数据")
    except Exception as e:
        print(f"  [FAIL] 交易日历: {str(e)[:50]}")

    # 股票列表
    try:
        if hasattr(ad, "BaseData"):
            stock_list = ad.BaseData.get_stock_list()
            if stock_list:
                print(f"  [OK] 股票列表: {len(stock_list)}只")
            else:
                print("  [FAIL] 股票列表: 无数据")
    except Exception as e:
        print(f"  [FAIL] 股票列表: {str(e)[:50]}")

    # 测试行情数据
    print("\n[3] 行情数据测试...")

    # 获取交易日历（query_kline必需）
    calendar = None
    try:
        if hasattr(ad, "BaseData"):
            calendar = ad.BaseData().get_calendar()
            print(f"  [INFO] 交易日历获取成功: {len(calendar)}天")
    except Exception as e:
        print(f"  [WARN] 交易日历获取失败: {str(e)[:40]}")

    # K线数据 - 使用新API
    try:
        if hasattr(ad, "MarketData"):
            market = ad.MarketData(calendar)  # 传入calendar
            if hasattr(market, "query_kline"):
                kline = market.query_kline(
                    ["000001.SZ"],
                    begin_date=20241101,
                    end_date=20241130,
                    period=10008,  # Period.day.value
                )
                if kline and "000001.SZ" in kline:
                    print(f"  [OK] K线数据: {len(kline['000001.SZ'])}条")
                else:
                    print(f"  [INFO] K线数据: {type(kline)}")
    except Exception as e:
        print(f"  [FAIL] K线数据: {str(e)[:60]}")

    # 快照数据 - 使用新API
    try:
        if hasattr(ad, "MarketData"):
            market = ad.MarketData(calendar)  # 复用已获取的calendar
            if hasattr(market, "query_snapshot"):
                snapshot = market.query_snapshot(["000001.SZ"])
                if snapshot and "000001.SZ" in snapshot:
                    print("  [OK] 快照数据: 获取成功")
                else:
                    print(f"  [INFO] 快照数据: {type(snapshot)}")
    except Exception as e:
        print(f"  [FAIL] 快照数据: {str(e)[:60]}")

    # 测试财务数据
    print("\n[4] 财务数据测试...")

    try:
        if hasattr(ad, "InfoData"):
            # 财务指标
            if hasattr(ad.InfoData, "get_main_indicators"):
                indicators = ad.InfoData.get_main_indicators("000001")
                if indicators:
                    print("  [OK] 主要指标: 获取成功")
                else:
                    print("  [INFO] 主要指标: 无数据")
    except Exception as e:
        print(f"  [FAIL] 主要指标: {str(e)[:60]}")

    try:
        if hasattr(ad, "InfoData"):
            # 十大股东
            if hasattr(ad.InfoData, "get_top10_shareholders"):
                shareholders = ad.InfoData.get_top10_shareholders("000001")
                if shareholders:
                    print("  [OK] 十大股东: 获取成功")
                else:
                    print("  [INFO] 十大股东: 无数据")
    except Exception as e:
        print(f"  [FAIL] 十大股东: {str(e)[:60]}")

    # 登出
    print("\n[5] 登出...")
    try:
        ad.logout()
        print("  [OK] 登出成功")
    except Exception as e:
        print(f"  [INFO] 登出: {e}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_amazingdata_direct()
