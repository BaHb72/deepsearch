#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData 实时数据获取测试

测试 AmazingData SDK 是否能获取实时行情数据
"""

import sys

sys.path.insert(0, "d:/Stock/code/deepsearch")

from datetime import datetime

# ========== 配置 ==========
CONFIG = {
    "username": "212200038719",
    "password": "212200038719@2025",
    "host": "101.230.159.234",
    "port": 8600,
}

_ad = None
_logged_in = False


def get_sdk():
    global _ad
    if _ad is None:
        import AmazingData as ad

        _ad = ad
    return _ad


def login():
    global _logged_in
    if _logged_in:
        return True
    ad = get_sdk()
    result = ad.login(**CONFIG)
    if result == 0 or result is True:
        print("[OK] 登录成功")
        _logged_in = True
        return True
    print(f"[FAIL] 登录失败: {result}")
    return False


def logout():
    global _logged_in
    if _logged_in:
        try:
            get_sdk().logout(CONFIG["username"])
        except:
            pass
        _logged_in = False


def test_realtime_snapshot():
    """测试实时行情快照 (query_snapshot)"""
    print("\n" + "=" * 50)
    print("测试 1: query_snapshot - 实时行情快照")
    print("=" * 50)

    login()
    ad = get_sdk()
    base = ad.BaseData()
    calendar = base.get_calendar()
    market = ad.MarketData(calendar)

    today = int(datetime.now().strftime("%Y%m%d"))
    test_codes = ["000001.SZ", "600519.SH", "000300.SH"]

    print(f"查询日期: {today}")
    print(f"测试标的: {test_codes}")

    snapshot = market.query_snapshot(code_list=test_codes, begin_date=today, end_date=today)

    if snapshot:
        print(f"\n[结果] query_snapshot 返回 {len(snapshot)} 个标的")
        for code, data in snapshot.items():
            if data is not None:
                print(
                    f"  {code}: 类型={type(data).__name__}, 长度={len(data) if hasattr(data, '__len__') else 'N/A'}"
                )
                # 尝试打印数据内容
                if hasattr(data, "keys"):
                    print(f"    字段: {list(data.keys())[:10]}")
                elif hasattr(data, "columns"):
                    print(f"    列: {list(data.columns)[:10]}")
                elif isinstance(data, (list, tuple)) and len(data) > 0:
                    print(f"    首条: {data[0] if len(data) > 0 else 'empty'}")
            else:
                print(f"  {code}: None")
        return True
    else:
        print("[FAIL] query_snapshot 返回空")
        return False


def test_realtime_kline_today():
    """测试当日分钟K线"""
    print("\n" + "=" * 50)
    print("测试 2: query_kline - 当日1分钟K线")
    print("=" * 50)

    login()
    ad = get_sdk()
    base = ad.BaseData()
    calendar = base.get_calendar()
    market = ad.MarketData(calendar)

    today = int(datetime.now().strftime("%Y%m%d"))
    test_codes = ["000001.SZ"]

    print(f"查询日期: {today}")
    print(f"测试标的: {test_codes}")

    kline = market.query_kline(
        code_list=test_codes, begin_date=today, end_date=today, period=10000  # 1分钟
    )

    if kline:
        print(f"\n[结果] query_kline 返回 {len(kline)} 个标的")
        for code, data in kline.items():
            if data is not None:
                print(f"  {code}: 类型={type(data).__name__}, ")
                if hasattr(data, "__len__"):
                    print(f"    条数: {len(data)}")
                if hasattr(data, "columns"):
                    print(f"    列: {list(data.columns)}")
                if hasattr(data, "head"):
                    print("    最新5条:")
                    print(data.tail(5).to_string())
            else:
                print(f"  {code}: None")
        return True
    else:
        print("[FAIL] query_kline 返回空")
        return False


def test_tick_data():
    """测试 Tick 数据"""
    print("\n" + "=" * 50)
    print("测试 3: query_tick - 逐笔成交数据")
    print("=" * 50)

    login()
    ad = get_sdk()
    base = ad.BaseData()
    calendar = base.get_calendar()
    market = ad.MarketData(calendar)

    today = int(datetime.now().strftime("%Y%m%d"))
    test_codes = ["000001.SZ"]

    print(f"查询日期: {today}")
    print(f"测试标的: {test_codes}")

    # 尝试使用 query_tick 如果存在
    if hasattr(market, "query_tick"):
        tick = market.query_tick(code_list=test_codes, begin_date=today, end_date=today)

        if tick:
            print(f"\n[结果] query_tick 返回 {len(tick)} 个标的")
            for code, data in tick.items():
                if data is not None:
                    print(f"  {code}: 类型={type(data).__name__}")
                    if hasattr(data, "__len__"):
                        print(f"    条数: {len(data)}")
                else:
                    print(f"  {code}: None")
            return True
        else:
            print("[INFO] query_tick 返回空 (可能非交易时间)")
            return True
    else:
        print("[INFO] MarketData 没有 query_tick 方法")
        # 列出所有 MarketData 方法
        methods = [m for m in dir(market) if not m.startswith("_")]
        print(f"    可用方法: {methods}")
        return True


def test_constants_and_periods():
    """显示 SDK 中的常量和周期定义"""
    print("\n" + "=" * 50)
    print("测试 4: SDK 常量和周期定义")
    print("=" * 50)

    ad = get_sdk()

    if hasattr(ad, "constant"):
        const = ad.constant
        print("\nad.constant 属性:")
        for attr in dir(const):
            if not attr.startswith("_"):
                val = getattr(const, attr, None)
                print(f"  {attr}: {type(val).__name__}")
                if hasattr(val, "__dict__"):
                    for k, v in vars(val).items():
                        if not k.startswith("_"):
                            print(f"    .{k} = {v}")
                elif hasattr(val, "value"):
                    print(f"    .value = {val.value}")

    return True


def main():
    print("=" * 60)
    print("AmazingData 实时数据获取测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = []

    try:
        results.append(("query_snapshot", test_realtime_snapshot()))
        results.append(("query_kline (1min)", test_realtime_kline_today()))
        results.append(("query_tick", test_tick_data()))
        results.append(("SDK 常量", test_constants_and_periods()))
    finally:
        logout()

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, result in results:
        status = "[OK]" if result else "[FAIL]"
        print(f"  {status} {name}")

    return all(r for _, r in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
