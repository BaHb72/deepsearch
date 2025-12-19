#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData SDK 能力验证脚本 (使用正确接口)
"""

import sys
sys.path.insert(0, "d:/Stock/code/deepsearch")

def verify_amazingdata():
    """验证 AmazingData SDK 各项能力"""
    print("="*60)
    print("AmazingData SDK 能力验证")
    print("="*60)
    
    results = {}
    
    def record(name, success, count=0, msg=""):
        results[name] = {"success": success, "count": count}
        status = "OK" if success else "FAIL"
        count_str = f"({count}条)" if count > 0 else ""
        msg_str = f" - {msg}" if msg else ""
        print(f"  [{status}] {name} {count_str}{msg_str}")
    
    # 导入SDK
    try:
        import AmazingData as ad
    except ImportError as e:
        print(f"[FAIL] SDK 导入失败: {e}")
        return
    
    # 登录
    print("\n[0] 登录...")
    try:
        result = ad.login(
            "212200038719",
            "212200038719@2025",
            "101.230.159.234",
            8600
        )
        if result == 0 or result is True:
            print("  [OK] 登录成功")
        else:
            print(f"  [FAIL] 登录失败: {result}")
            return
    except Exception as e:
        print(f"  [FAIL] 登录异常: {e}")
        return
    
    # ========== BaseData 测试 ==========
    print("\n[1] 基础数据 (BaseData)")
    
    # 交易日历
    try:
        data = ad.BaseData.get_calendar("20241101", "20241130")
        if data and len(data) > 0:
            record("交易日历", True, len(data))
        else:
            record("交易日历", False, msg="无数据")
    except Exception as e:
        record("交易日历", False, msg=str(e)[:40])
    
    # 股票列表
    try:
        data = ad.BaseData.get_code_list()
        if data and len(data) > 0:
            record("股票列表", True, len(data))
        else:
            record("股票列表", False, msg="无数据")
    except Exception as e:
        record("股票列表", False, msg=str(e)[:40])
    
    # 股票信息
    try:
        data = ad.BaseData.get_code_info(["000001"])
        if data and len(data) > 0:
            record("股票信息", True, len(data))
        else:
            record("股票信息", False, msg="无数据")
    except Exception as e:
        record("股票信息", False, msg=str(e)[:40])
    
    # 复权因子
    try:
        data = ad.BaseData.get_adj_factor(["000001"], 20241101, 20241130)
        if data and "000001" in data and len(data["000001"]) > 0:
            record("复权因子", True, len(data["000001"]))
        else:
            record("复权因子", False, msg="无数据")
    except Exception as e:
        record("复权因子", False, msg=str(e)[:40])
    
    # ETF申赎清单
    try:
        data = ad.BaseData.get_etf_pcf(["510300"], 20241115)
        if data:
            record("ETF清单", True, 1)
        else:
            record("ETF清单", False, msg="无数据")
    except Exception as e:
        record("ETF清单", False, msg=str(e)[:40])
    
    # ========== MarketData 测试 ==========
    print("\n[2] 行情数据 (MarketData)")
    
    # K线数据
    try:
        market = ad.MarketData("212200038719")  # 需要传入用户名
        data = market.query_kline(
            ["000001"],
            begin_date=20241101,
            end_date=20241130,
            period="day"
        )
        if data and "000001" in data:
            records = data["000001"]
            count = len(records) if hasattr(records, '__len__') else 1
            record("K线数据(日)", True, count)
        else:
            record("K线数据(日)", False, msg="无数据")
    except Exception as e:
        record("K线数据(日)", False, msg=str(e)[:40])
    
    # 快照数据
    try:
        market = ad.MarketData("212200038719")
        data = market.query_snapshot(["000001"])
        if data and "000001" in data:
            record("快照数据", True, 1)
        else:
            record("快照数据", False, msg="无数据")
    except Exception as e:
        record("快照数据", False, msg=str(e)[:40])
    
    # ========== InfoData 测试 ==========
    print("\n[3] 资讯数据 (InfoData)")
    
    # 龙虎榜
    try:
        data = ad.InfoData.get_long_hu_bang("000001", 20240101, 20241130)
        if data and len(data) > 0:
            record("龙虎榜", True, len(data))
        else:
            record("龙虎榜", False, msg="无数据(可能无上榜)")
    except Exception as e:
        record("龙虎榜", False, msg=str(e)[:40])
    
    # 大宗交易
    try:
        data = ad.InfoData.get_block_trading("000001", 20240101, 20241130)
        if data and len(data) > 0:
            record("大宗交易", True, len(data))
        else:
            record("大宗交易", False, msg="无数据")
    except Exception as e:
        record("大宗交易", False, msg=str(e)[:40])
    
    # 融资融券
    try:
        data = ad.InfoData.get_margin_detail("000001", 20241101, 20241130)
        if data and len(data) > 0:
            record("融资融券", True, len(data))
        else:
            record("融资融券", False, msg="无数据")
    except Exception as e:
        record("融资融券", False, msg=str(e)[:40])
    
    # 股东信息
    try:
        data = ad.InfoData.get_share_holder("000001")
        if data and len(data) > 0:
            record("股东信息", True, len(data))
        else:
            record("股东信息", False, msg="无数据")
    except Exception as e:
        record("股东信息", False, msg=str(e)[:40])
    
    # 资产负债表
    try:
        data = ad.InfoData.get_balance_sheet("000001")
        if data and len(data) > 0:
            record("资产负债表", True, len(data))
        else:
            record("资产负债表", False, msg="无数据")
    except Exception as e:
        record("资产负债表", False, msg=str(e)[:40])
    
    # 利润表
    try:
        data = ad.InfoData.get_income("000001")
        if data and len(data) > 0:
            record("利润表", True, len(data))
        else:
            record("利润表", False, msg="无数据")
    except Exception as e:
        record("利润表", False, msg=str(e)[:40])
    
    # 现金流量表
    try:
        data = ad.InfoData.get_cash_flow("000001")
        if data and len(data) > 0:
            record("现金流量表", True, len(data))
        else:
            record("现金流量表", False, msg="无数据")
    except Exception as e:
        record("现金流量表", False, msg=str(e)[:40])
    
    # 指数成分
    try:
        data = ad.InfoData.get_index_constituent("000300")
        if data and len(data) > 0:
            record("指数成分", True, len(data))
        else:
            record("指数成分", False, msg="无数据")
    except Exception as e:
        record("指数成分", False, msg=str(e)[:40])
    
    # 行业分类
    try:
        data = ad.InfoData.get_industry_constituent("sw_l1")
        if data and len(data) > 0:
            record("行业分类", True, len(data))
        else:
            record("行业分类", False, msg="无数据")
    except Exception as e:
        record("行业分类", False, msg=str(e)[:40])
    
    # 登出
    try:
        ad.logout("212200038719")
    except:
        pass
    
    # 打印汇总
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)
    success = sum(1 for r in results.values() if r["success"])
    total = len(results)
    print(f"\n通过: {success}/{total}")
    
    print("\n分类统计:")
    print(f"  BaseData: 基础数据接口")
    print(f"  MarketData: 行情数据接口") 
    print(f"  InfoData: 资讯/财务数据接口")


if __name__ == "__main__":
    verify_amazingdata()
