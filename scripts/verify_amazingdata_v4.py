#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData SDK 能力验证 (v4 - 按文档传入calendar)
"""

import sys

sys.path.insert(0, "d:/Stock/code/deepsearch")


def verify_amazingdata_v4():
    """按文档正确方式验证 AmazingData SDK"""
    print("=" * 60)
    print("AmazingData SDK 能力验证 (按文档)")
    print("=" * 60)

    results = {}

    def record(name, success, count=0, msg="", data=None):
        results[name] = {"success": success, "count": count}
        status = "OK" if success else "FAIL"
        count_str = f"({count}条)" if count > 0 else ""
        msg_str = f" - {msg}" if msg else ""
        print(f"  [{status}] {name} {count_str}{msg_str}")
        if data is not None and success:
            # 打印样本数据
            if isinstance(data, dict):
                for k, v in list(data.items())[:2]:
                    print(f"       样本: {k} -> {str(v)[:60]}...")
            elif isinstance(data, list) and len(data) > 0:
                print(f"       样本: {str(data[0])[:80]}...")

    import AmazingData as ad

    # ========== 第一步：登录 ==========
    print("\n[0] 登录...")
    try:
        result = ad.login("212200038719", "212200038719@2025", "101.230.159.234", 8600)
        if result == 0 or result is True:
            print("  [OK] 登录成功")
        else:
            print(f"  [FAIL] 登录失败: {result}")
            return
    except Exception as e:
        print(f"  [FAIL] 登录异常: {e}")
        return

    # ========== 第二步：创建 BaseData 获取基础数据 ==========
    print("\n[1] BaseData 基础数据")

    base = ad.BaseData()

    # 获取交易日历（后面要用）
    calendar = None
    try:
        calendar = base.get_calendar()
        if calendar and len(calendar) > 0:
            record("交易日历", True, len(calendar), data=calendar[:5])
        else:
            record("交易日历", False, msg="无数据")
    except Exception as e:
        record("交易日历", False, msg=str(e)[:40])

    # 获取股票列表（后面要用）
    code_list = None
    try:
        code_list = base.get_code_list(security_type="EXTRA_STOCK_A")
        if code_list and len(code_list) > 0:
            record("股票列表", True, len(code_list), data=code_list[:3])
        else:
            record("股票列表", False, msg="无数据")
    except Exception as e:
        record("股票列表", False, msg=str(e)[:40])

    # 股票信息
    try:
        data = base.get_code_info(security_type="EXTRA_STOCK_A")
        if data is not None and len(data) > 0:
            record("股票信息", True, len(data))
        else:
            record("股票信息", False, msg="无数据")
    except Exception as e:
        record("股票信息", False, msg=str(e)[:40])

    # ========== 第三步：创建 MarketData (传入calendar) ==========
    print("\n[2] MarketData 行情数据")

    if calendar is None:
        print("  [SKIP] 无交易日历，跳过MarketData测试")
    else:
        try:
            # 按文档：market_data_object = ad.MarketData(calendar)
            market = ad.MarketData(calendar)
            print("  [OK] MarketData 实例创建成功")

            # 快照数据
            try:
                # query_snapshot(code_list, begin_date, end_date)
                snapshot = market.query_snapshot(["000001"], begin_date=20241213, end_date=20241213)
                if snapshot and "000001" in snapshot:
                    record("快照数据", True, 1, data=snapshot)
                elif snapshot:
                    record("快照数据", True, len(snapshot) if hasattr(snapshot, "__len__") else 1)
                else:
                    record("快照数据", False, msg="无数据")
            except Exception as e:
                record("快照数据", False, msg=str(e)[:50])

            # K线数据
            try:
                kline = market.query_kline(
                    ["000001"], begin_date=20241201, end_date=20241213, period=10000  # 日K线
                )
                if kline and "000001" in kline:
                    kline_data = kline["000001"]
                    count = len(kline_data) if hasattr(kline_data, "__len__") else 1
                    record("K线数据(日)", True, count)
                    if count > 0:
                        print(
                            f"       字段: {list(kline_data[0].keys()) if isinstance(kline_data, list) and kline_data else 'N/A'}"
                        )
                else:
                    record("K线数据(日)", False, msg="无数据")
            except Exception as e:
                record("K线数据(日)", False, msg=str(e)[:50])

        except Exception as e:
            record("MarketData创建", False, msg=str(e)[:50])

    # ========== 第四步：InfoData 资讯数据 ==========
    print("\n[3] InfoData 资讯数据")

    try:
        info = ad.InfoData()

        # 股东信息
        try:
            data = info.get_share_holder(["000001"])
            if data and len(data) > 0:
                record("股东信息", True, len(data))
            else:
                record("股东信息", False, msg="无数据")
        except Exception as e:
            record("股东信息", False, msg=str(e)[:40])

        # 龙虎榜
        try:
            data = info.get_long_hu_bang(["000001"])
            if data and len(data) > 0:
                record("龙虎榜", True, len(data))
            else:
                record("龙虎榜", False, msg="无上榜记录")
        except Exception as e:
            record("龙虎榜", False, msg=str(e)[:40])

        # 指数成分
        try:
            data = info.get_index_constituent(["000300"])
            if data and "000300" in data:
                record("指数成分(沪深300)", True, len(data["000300"]))
            elif data and len(data) > 0:
                record("指数成分(沪深300)", True, len(data))
            else:
                record("指数成分(沪深300)", False, msg="无数据")
        except Exception as e:
            record("指数成分(沪深300)", False, msg=str(e)[:40])

    except Exception as e:
        record("InfoData创建", False, msg=str(e)[:40])

    # 登出
    try:
        ad.logout("212200038719")
    except:
        pass

    # ========== 打印汇总 ==========
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    success = sum(1 for r in results.values() if r["success"])
    total = len(results)
    print(f"\n[AMAZINGDATA] {success}/{total} 项通过")

    for name, r in results.items():
        status = "OK" if r["success"] else "FAIL"
        count = r.get("count", 0)
        count_str = f"({count}条)" if count > 0 else ""
        print(f"  {status:4} | {name:20} {count_str}")


if __name__ == "__main__":
    verify_amazingdata_v4()
