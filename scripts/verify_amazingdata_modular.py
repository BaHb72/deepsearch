#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData SDK 模块化验证脚本

按功能分开测试,避免重复测试占用数据源限额:
- python verify_amazingdata_modular.py base      # 只测试BaseData
- python verify_amazingdata_modular.py market    # 只测试MarketData
- python verify_amazingdata_modular.py info      # 只测试InfoData
- python verify_amazingdata_modular.py all       # 测试全部(默认)
"""

import sys
sys.path.insert(0, "d:/Stock/code/deepsearch")

from datetime import datetime, timedelta
import pandas as pd

# ========== 公共配置 ==========
AMAZINGDATA_CONFIG = {
    "username": "212200038719",
    "password": "212200038719@2025",
    "host": "101.230.159.234",
    "port": 8600
}
LOCAL_PATH = "D://AmazingData_local_data//"

# 全局状态
_ad = None
_base = None
_calendar = None
_logged_in = False


def get_sdk():
    """获取SDK模块"""
    global _ad
    if _ad is None:
        import AmazingData as ad
        _ad = ad
    return _ad


def login():
    """登录(如果未登录)"""
    global _logged_in
    if _logged_in:
        return True
    
    ad = get_sdk()
    try:
        result = ad.login(
            username=AMAZINGDATA_CONFIG["username"],
            password=AMAZINGDATA_CONFIG["password"],
            host=AMAZINGDATA_CONFIG["host"],
            port=AMAZINGDATA_CONFIG["port"]
        )
        if result == 0 or result is True:
            print("  [OK] 登录成功")
            _logged_in = True
            return True
        else:
            print(f"  [FAIL] 登录失败: {result}")
            return False
    except Exception as e:
        print(f"  [FAIL] 登录异常: {e}")
        return False


def logout():
    """登出"""
    global _logged_in
    if _logged_in:
        try:
            get_sdk().logout(AMAZINGDATA_CONFIG["username"])
            print("  [INFO] 已登出")
        except:
            pass
        _logged_in = False


def get_base_data():
    """获取BaseData实例"""
    global _base
    if _base is None:
        _base = get_sdk().BaseData()
    return _base


def get_calendar():
    """获取交易日历(缓存)"""
    global _calendar
    if _calendar is None:
        _calendar = get_base_data().get_calendar()
    return _calendar


def record(category, name, success, count=0, msg="", sample=None):
    """记录测试结果"""
    status = "OK" if success else "FAIL"
    count_str = f"({count}条)" if count > 0 else ""
    msg_str = f" - {msg}" if msg else ""
    print(f"  [{status}] {name:25} {count_str}{msg_str}")
    if sample and success:
        sample_str = str(sample)[:80]
        print(f"       样本: {sample_str}")
    return success


# ========== BaseData 测试 ==========
def test_basedata():
    """测试BaseData模块"""
    print("\n" + "="*60)
    print("测试 BaseData 基础数据")
    print("="*60)
    
    if not login():
        return 0, 0
    
    base = get_base_data()
    passed = 0
    total = 0
    
    # 交易日历
    total += 1
    try:
        calendar = get_calendar()
        if calendar and len(calendar) > 0:
            if record("BaseData", "get_calendar", True, len(calendar), sample=calendar[:3]):
                passed += 1
        else:
            record("BaseData", "get_calendar", False, msg="无数据")
    except Exception as e:
        record("BaseData", "get_calendar", False, msg=str(e)[:40])
    
    # A股代码列表
    total += 1
    try:
        code_list = base.get_code_list(security_type='EXTRA_STOCK_A')
        if code_list and len(code_list) > 0:
            if record("BaseData", "get_code_list(A股)", True, len(code_list), sample=list(code_list)[:3]):
                passed += 1
        else:
            record("BaseData", "get_code_list(A股)", False, msg="无数据")
    except Exception as e:
        record("BaseData", "get_code_list(A股)", False, msg=str(e)[:40])
    
    # 股票基本信息
    total += 1
    try:
        code_info = base.get_code_info(security_type='EXTRA_STOCK_A')
        if code_info is not None and len(code_info) > 0:
            if record("BaseData", "get_code_info", True, len(code_info)):
                passed += 1
        else:
            record("BaseData", "get_code_info", False, msg="无数据")
    except Exception as e:
        record("BaseData", "get_code_info", False, msg=str(e)[:40])
    
    # ETF申赎清单
    total += 1
    try:
        etf_info, etf_constituent = base.get_etf_pcf(["510300.SH"])
        if etf_info is not None and len(etf_info) > 0:
            if record("BaseData", "get_etf_pcf", True, len(etf_info)):
                passed += 1
        else:
            record("BaseData", "get_etf_pcf", False, msg="无数据")
    except Exception as e:
        record("BaseData", "get_etf_pcf", False, msg=str(e)[:40])
    
    # 期权代码列表
    total += 1
    try:
        option_list = base.get_option_code_list()
        if option_list and len(option_list) > 0:
            if record("BaseData", "get_option_code_list", True, len(option_list)):
                passed += 1
        else:
            record("BaseData", "get_option_code_list", False, msg="无数据")
    except Exception as e:
        record("BaseData", "get_option_code_list", False, msg=str(e)[:40])
    
    # 期货代码列表
    total += 1
    try:
        future_list = base.get_future_code_list()
        if future_list and len(future_list) > 0:
            if record("BaseData", "get_future_code_list", True, len(future_list)):
                passed += 1
        else:
            record("BaseData", "get_future_code_list", False, msg="无数据")
    except Exception as e:
        record("BaseData", "get_future_code_list", False, msg=str(e)[:40])
    
    print(f"\nBaseData: {passed}/{total} 通过")
    return passed, total


# ========== MarketData 测试 ==========
def test_marketdata():
    """测试MarketData模块"""
    print("\n" + "="*60)
    print("测试 MarketData 历史行情")
    print("="*60)
    
    if not login():
        return 0, 0
    
    ad = get_sdk()
    calendar = get_calendar()
    passed = 0
    total = 0
    
    if calendar is None:
        print("  [SKIP] 无交易日历")
        return 0, 0
    
    try:
        market = ad.MarketData(calendar)
        print("  [INFO] MarketData 实例创建成功")
    except Exception as e:
        print(f"  [FAIL] MarketData 创建失败: {e}")
        return 0, 1
    
    today = int(datetime.now().strftime("%Y%m%d"))
    
    # 日K线 (Period.day = 10008)
    total += 1
    try:
        kline = market.query_kline(
            code_list=["000001.SZ"],
            begin_date=20241201,
            end_date=20241213,
            period=10008
        )
        if kline and "000001.SZ" in kline:
            data = kline["000001.SZ"]
            count = len(data) if hasattr(data, '__len__') else 1
            if record("MarketData", "query_kline(日K)", True, count):
                passed += 1
        else:
            record("MarketData", "query_kline(日K)", False, msg="无数据")
    except Exception as e:
        record("MarketData", "query_kline(日K)", False, msg=str(e)[:50])
    
    # 1分钟K线 (Period.min1 = 10000)
    total += 1
    try:
        kline_min = market.query_kline(
            code_list=["000001.SZ"],
            begin_date=today,
            end_date=today,
            period=10000
        )
        if kline_min and "000001.SZ" in kline_min:
            data = kline_min["000001.SZ"]
            count = len(data) if hasattr(data, '__len__') else 1
            if record("MarketData", "query_kline(1分钟)", True, count):
                passed += 1
        else:
            record("MarketData", "query_kline(1分钟)", False, msg="无数据")
    except Exception as e:
        record("MarketData", "query_kline(1分钟)", False, msg=str(e)[:50])
    
    # 历史快照
    total += 1
    try:
        snapshot = market.query_snapshot(
            code_list=["000001.SZ"],
            begin_date=today,
            end_date=today
        )
        if snapshot:
            keys = list(snapshot.keys())[:3]
            if "000001.SZ" in snapshot or keys:
                if record("MarketData", "query_snapshot", True, 1, sample=keys):
                    passed += 1
            else:
                record("MarketData", "query_snapshot", False, msg="无数据")
        else:
            record("MarketData", "query_snapshot", False, msg="返回空")
    except Exception as e:
        record("MarketData", "query_snapshot", False, msg=str(e)[:50])
    
    print(f"\nMarketData: {passed}/{total} 通过")
    return passed, total


# ========== InfoData 测试 ==========
def test_infodata():
    """测试InfoData模块"""
    print("\n" + "="*60)
    print("测试 InfoData 财务/股东数据")
    print("="*60)
    
    if not login():
        return 0, 0
    
    ad = get_sdk()
    passed = 0
    total = 0
    
    try:
        info = ad.InfoData()
    except Exception as e:
        print(f"  [FAIL] InfoData 创建失败: {e}")
        return 0, 1
    
    test_codes = ["000001.SZ"]
    end_dt = datetime.now()
    begin_dt = end_dt - timedelta(days=30)
    begin_date = int(begin_dt.strftime("%Y%m%d"))
    end_date = int(end_dt.strftime("%Y%m%d"))
    
    # 资产负债表
    total += 1
    try:
        balance = info.get_balance_sheet(test_codes, local_path=LOCAL_PATH, is_local=False)
        if balance and len(balance) > 0:
            if record("InfoData", "get_balance_sheet", True, len(balance)):
                passed += 1
        else:
            record("InfoData", "get_balance_sheet", False, msg="无数据")
    except Exception as e:
        record("InfoData", "get_balance_sheet", False, msg=str(e)[:40])
    
    # 利润表
    total += 1
    try:
        income = info.get_income(test_codes, local_path=LOCAL_PATH, is_local=False)
        if income and len(income) > 0:
            if record("InfoData", "get_income", True, len(income)):
                passed += 1
        else:
            record("InfoData", "get_income", False, msg="无数据")
    except Exception as e:
        record("InfoData", "get_income", False, msg=str(e)[:40])
    
    # 十大股东
    total += 1
    try:
        holder = info.get_share_holder(test_codes, local_path=LOCAL_PATH, is_local=False)
        if isinstance(holder, pd.DataFrame):
            if not holder.empty:
                if record("InfoData", "get_share_holder", True, len(holder)):
                    passed += 1
            else:
                record("InfoData", "get_share_holder", False, msg="空DataFrame")
        elif holder and len(holder) > 0:
            if record("InfoData", "get_share_holder", True, len(holder)):
                passed += 1
        else:
            record("InfoData", "get_share_holder", False, msg="无数据")
    except Exception as e:
        record("InfoData", "get_share_holder", False, msg=str(e)[:40])
    
    # 龙虎榜
    total += 1
    try:
        lhb_codes = ["000001.SZ", "600519.SH", "000002.SZ"]
        lhb = info.get_long_hu_bang(lhb_codes, local_path=LOCAL_PATH, begin_date=begin_date, end_date=end_date)
        if isinstance(lhb, pd.DataFrame):
            if not lhb.empty:
                if record("InfoData", "get_long_hu_bang", True, len(lhb)):
                    passed += 1
            else:
                record("InfoData", "get_long_hu_bang", False, msg="无上榜记录(正常)")
        elif lhb and len(lhb) > 0:
            if record("InfoData", "get_long_hu_bang", True, len(lhb)):
                passed += 1
        else:
            record("InfoData", "get_long_hu_bang", False, msg="无上榜记录(正常)")
    except Exception as e:
        record("InfoData", "get_long_hu_bang", False, msg=str(e)[:40])
    
    # 大宗交易
    total += 1
    try:
        block = info.get_block_trading(test_codes, local_path=LOCAL_PATH, is_local=False)
        if isinstance(block, pd.DataFrame):
            if not block.empty:
                if record("InfoData", "get_block_trading", True, len(block)):
                    passed += 1
            else:
                record("InfoData", "get_block_trading", False, msg="无数据")
        elif block and len(block) > 0:
            if record("InfoData", "get_block_trading", True, len(block)):
                passed += 1
        else:
            record("InfoData", "get_block_trading", False, msg="无数据")
    except Exception as e:
        record("InfoData", "get_block_trading", False, msg=str(e)[:40])
    
    # 融资融券明细
    total += 1
    try:
        margin = info.get_margin_detail(test_codes, local_path=LOCAL_PATH, is_local=False)
        if margin and len(margin) > 0:
            if record("InfoData", "get_margin_detail", True, len(margin)):
                passed += 1
        else:
            record("InfoData", "get_margin_detail", False, msg="无数据")
    except Exception as e:
        record("InfoData", "get_margin_detail", False, msg=str(e)[:40])
    
    # 指数成分
    total += 1
    try:
        idx = info.get_index_constituent(["000300.SH"], local_path=LOCAL_PATH, is_local=False)
        if idx and "000300.SH" in idx:
            if record("InfoData", "get_index_constituent", True, len(idx["000300.SH"])):
                passed += 1
        else:
            record("InfoData", "get_index_constituent", False, msg="无数据")
    except Exception as e:
        record("InfoData", "get_index_constituent", False, msg=str(e)[:40])
    
    print(f"\nInfoData: {passed}/{total} 通过")
    return passed, total


# ========== 主入口 ==========
def main():
    """主函数"""
    print("="*60)
    print("AmazingData SDK 模块化验证")
    print("="*60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 解析命令行参数
    module = "all"
    if len(sys.argv) > 1:
        module = sys.argv[1].lower()
    
    print(f"测试模块: {module}")
    
    total_passed = 0
    total_tests = 0
    
    try:
        if module in ["base", "all"]:
            p, t = test_basedata()
            total_passed += p
            total_tests += t
        
        if module in ["market", "all"]:
            p, t = test_marketdata()
            total_passed += p
            total_tests += t
        
        if module in ["info", "all"]:
            p, t = test_infodata()
            total_passed += p
            total_tests += t
        
        if module not in ["base", "market", "info", "all"]:
            print(f"\n未知模块: {module}")
            print("可用选项: base, market, info, all")
            return
    finally:
        logout()
    
    # 汇总
    print("\n" + "="*60)
    print(f"总计: {total_passed}/{total_tests} 通过 ({total_passed/total_tests*100:.1f}%)" if total_tests > 0 else "无测试执行")
    print("="*60)


if __name__ == "__main__":
    main()
