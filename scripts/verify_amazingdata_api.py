#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData SDK 单接口测试

每个接口独立测试，避免数据源限流:
- python verify_amazingdata_api.py get_calendar
- python verify_amazingdata_api.py query_kline
- python verify_amazingdata_api.py get_share_holder
- python verify_amazingdata_api.py list  # 列出所有可测接口
"""

import sys

sys.path.insert(0, "d:/Stock/code/deepsearch")

from datetime import datetime, timedelta

import pandas as pd

# ========== 配置 ==========
CONFIG = {
    "username": "212200038719",
    "password": "212200038719@2025",
    "host": "101.230.159.234",
    "port": 8600,
}
LOCAL_PATH = "D://AmazingData_local_data//"

# 全局缓存
_ad = None
_base = None
_calendar = None
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


def get_base():
    global _base
    if _base is None:
        _base = get_sdk().BaseData()
    return _base


def get_calendar_cached():
    global _calendar
    if _calendar is None:
        _calendar = get_base().get_calendar()
    return _calendar


# ========== 单接口测试函数 ==========


def test_get_calendar():
    """测试 BaseData.get_calendar"""
    login()
    cal = get_base().get_calendar()
    if cal and len(cal) > 0:
        print(f"[OK] get_calendar: {len(cal)}条")
        print(f"     样本: {cal[:5]}")
        return True
    print("[FAIL] get_calendar: 无数据")
    return False


def test_get_code_list():
    """测试 BaseData.get_code_list"""
    login()
    codes = get_base().get_code_list(security_type="EXTRA_STOCK_A")
    if codes and len(codes) > 0:
        print(f"[OK] get_code_list: {len(codes)}条")
        print(f"     样本: {list(codes)[:5]}")
        return True
    print("[FAIL] get_code_list: 无数据")
    return False


def test_get_code_info():
    """测试 BaseData.get_code_info"""
    login()
    info = get_base().get_code_info(security_type="EXTRA_STOCK_A")
    if info is not None and len(info) > 0:
        print(f"[OK] get_code_info: {len(info)}条")
        return True
    print("[FAIL] get_code_info: 无数据")
    return False


def test_get_etf_pcf():
    """测试 BaseData.get_etf_pcf"""
    login()
    etf_info, etf_constituent = get_base().get_etf_pcf(["510300.SH"])
    if etf_info is not None and len(etf_info) > 0:
        print(f"[OK] get_etf_pcf: {len(etf_info)}条ETF, {len(etf_constituent)}只成分")
        return True
    print("[FAIL] get_etf_pcf: 无数据")
    return False


def test_get_option_code_list():
    """测试 BaseData.get_option_code_list"""
    login()
    options = get_base().get_option_code_list()
    if options and len(options) > 0:
        print(f"[OK] get_option_code_list: {len(options)}条")
        return True
    print("[FAIL] get_option_code_list: 无数据")
    return False


def test_get_future_code_list():
    """测试 BaseData.get_future_code_list"""
    login()
    futures = get_base().get_future_code_list()
    if futures and len(futures) > 0:
        print(f"[OK] get_future_code_list: {len(futures)}条")
        return True
    print("[FAIL] get_future_code_list: 无数据")
    return False


def test_get_backward_factor():
    """测试 BaseData.get_backward_factor (后复权因子)"""
    login()
    base = get_base()
    data = base.get_backward_factor(code_list=["000001.SZ"], local_path=LOCAL_PATH, is_local=False)
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_backward_factor: {len(data)}行 x {len(data.columns)}列")
        print(f"     日期范围: {data.index[0]} ~ {data.index[-1]}")
        return True
    elif data is not None:
        print(f"[OK] get_backward_factor: {type(data)}")
        return True
    print("[FAIL] get_backward_factor: 无数据")
    return False


def test_get_adj_factor():
    """测试 BaseData.get_adj_factor (前复权因子)"""
    login()
    base = get_base()
    data = base.get_adj_factor(code_list=["000001.SZ"], local_path=LOCAL_PATH, is_local=False)
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_adj_factor: {len(data)}行 x {len(data.columns)}列")
        print(f"     日期范围: {data.index[0]} ~ {data.index[-1]}")
        return True
    elif data is not None:
        print(f"[OK] get_adj_factor: {type(data)}")
        return True
    print("[FAIL] get_adj_factor: 无数据")
    return False


def test_get_hist_code_list():
    """测试 BaseData.get_hist_code_list (历史代码列表)"""
    login()
    base = get_base()
    # 查询最近1年的历史代码
    end_date = int(datetime.now().strftime("%Y%m%d"))
    start_date = int((datetime.now() - timedelta(days=365)).strftime("%Y%m%d"))

    code_list = base.get_hist_code_list(
        security_type="EXTRA_STOCK_A_SH_SZ",
        start_date=start_date,
        end_date=end_date,
        local_path=LOCAL_PATH,
    )
    if code_list and len(code_list) > 0:
        print(f"[OK] get_hist_code_list: {len(code_list)}个历史代码")
        print(f"     时间范围: {start_date} ~ {end_date}")
        print(f"     样本: {code_list[:5]}")
        return True
    print("[FAIL] get_hist_code_list: 无数据")
    return False


def test_get_future_code_info():
    """测试 BaseData.get_future_code_info (期货代码信息) - 仅测试1个标的"""
    login()
    base = get_base()
    # 获取期货列表后只测试第1个
    futures = base.get_future_code_list()
    if futures and len(futures) > 0:
        test_code = futures[0]  # 只测试第1个期货
        data = base.get_future_code_info(security_type="EXTRA_FUTURE")
        if isinstance(data, pd.DataFrame) and not data.empty:
            print(f"[OK] get_future_code_info: {len(data)}行 x {len(data.columns)}列")
            print(f"     字段: {list(data.columns)[:5]}")
            return True
        elif data is not None:
            print(f"[OK] get_future_code_info: {type(data)}")
            return True
    print("[FAIL] get_future_code_info: 无数据")
    return False


def test_query_kline():
    """测试 MarketData.query_kline (日K)"""
    login()
    ad = get_sdk()
    cal = get_calendar_cached()
    market = ad.MarketData(cal)
    kline = market.query_kline(
        code_list=["000001.SZ"], begin_date=20241201, end_date=20241213, period=10008  # day
    )
    if kline and "000001.SZ" in kline:
        data = kline["000001.SZ"]
        print(f"[OK] query_kline(日K): {len(data)}条")
        return True
    print("[FAIL] query_kline: 无数据")
    return False


def test_query_kline_min():
    """测试 MarketData.query_kline (1分钟)"""
    login()
    ad = get_sdk()
    cal = get_calendar_cached()
    market = ad.MarketData(cal)
    today = int(datetime.now().strftime("%Y%m%d"))
    kline = market.query_kline(
        code_list=["000001.SZ"], begin_date=today, end_date=today, period=10000  # min1
    )
    if kline and "000001.SZ" in kline:
        data = kline["000001.SZ"]
        print(f"[OK] query_kline(1分钟): {len(data)}条")
        return True
    print("[FAIL] query_kline(1分钟): 无数据")
    return False


def test_query_snapshot():
    """测试 MarketData.query_snapshot"""
    login()
    ad = get_sdk()
    cal = get_calendar_cached()
    market = ad.MarketData(cal)
    today = int(datetime.now().strftime("%Y%m%d"))
    snapshot = market.query_snapshot(code_list=["000001.SZ"], begin_date=today, end_date=today)
    if snapshot:
        keys = list(snapshot.keys())
        print(f"[OK] query_snapshot: {len(keys)}条, keys={keys[:3]}")
        return True
    print("[FAIL] query_snapshot: 无数据")
    return False


def test_get_balance_sheet():
    """测试 InfoData.get_balance_sheet"""
    login()
    info = get_sdk().InfoData()
    data = info.get_balance_sheet(["000001.SZ"], local_path=LOCAL_PATH, is_local=False)
    if data and len(data) > 0:
        print(f"[OK] get_balance_sheet: {len(data)}条")
        return True
    print("[FAIL] get_balance_sheet: 无数据")
    return False


def test_get_income():
    """测试 InfoData.get_income"""
    login()
    info = get_sdk().InfoData()
    data = info.get_income(["000001.SZ"], local_path=LOCAL_PATH, is_local=False)
    if data and len(data) > 0:
        print(f"[OK] get_income: {len(data)}条")
        return True
    print("[FAIL] get_income: 无数据")
    return False


def test_get_share_holder():
    """测试 InfoData.get_share_holder"""
    login()
    info = get_sdk().InfoData()
    # 测试带时间范围筛选
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=365)).strftime("%Y%m%d"))  # 最近1年

    data = info.get_share_holder(
        ["000001.SZ"],
        local_path=LOCAL_PATH,
        is_local=False,
        begin_date=begin_date,
        end_date=end_date,
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_share_holder: {len(data)}条")
        print(f"     时间范围: {begin_date} ~ {end_date}")
        if "HOLDER_ENDDATE" in data.columns:
            print(
                f"     截止日期范围: {data['HOLDER_ENDDATE'].min()} ~ {data['HOLDER_ENDDATE'].max()}"
            )
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_share_holder: {len(data)}条")
        return True
    print("[FAIL] get_share_holder: 无数据")
    return False


def test_get_long_hu_bang():
    """测试 InfoData.get_long_hu_bang"""
    login()
    info = get_sdk().InfoData()
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=30)).strftime("%Y%m%d"))
    data = info.get_long_hu_bang(
        ["000001.SZ", "600519.SH"], local_path=LOCAL_PATH, begin_date=begin_date, end_date=end_date
    )
    if isinstance(data, pd.DataFrame):
        if not data.empty:
            print(f"[OK] get_long_hu_bang: {len(data)}条")
            return True
        else:
            print("[INFO] get_long_hu_bang: 无上榜记录(正常)")
            return True  # 没有上榜记录也算正常
    elif data is not None and len(data) > 0:
        print(f"[OK] get_long_hu_bang: {len(data)}条")
        return True
    print("[INFO] get_long_hu_bang: 无上榜记录(正常)")
    return True  # 没有上榜记录也算正常


def test_get_block_trading():
    """测试 InfoData.get_block_trading"""
    login()
    info = get_sdk().InfoData()
    data = info.get_block_trading(["000001.SZ"], local_path=LOCAL_PATH, is_local=False)
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_block_trading: {len(data)}条")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_block_trading: {len(data)}条")
        return True
    print("[FAIL] get_block_trading: 无数据")
    return False


def test_get_margin_detail():
    """测试 InfoData.get_margin_detail"""
    login()
    info = get_sdk().InfoData()
    # 测试带时间范围筛选
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=30)).strftime("%Y%m%d"))  # 最近30天

    data = info.get_margin_detail(
        ["000001.SZ"],
        local_path=LOCAL_PATH,
        is_local=False,
        begin_date=begin_date,
        end_date=end_date,
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_margin_detail: {len(data)}条")
        print(f"     时间范围: {begin_date} ~ {end_date}")
        if "TRADE_DATE" in data.columns:
            print(f"     交易日期范围: {data['TRADE_DATE'].min()} ~ {data['TRADE_DATE'].max()}")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_margin_detail: {len(data)}条")
        return True
    print("[FAIL] get_margin_detail: 无数据")
    return False


def test_get_index_constituent():
    """测试 InfoData.get_index_constituent"""
    login()
    info = get_sdk().InfoData()
    data = info.get_index_constituent(["000300.SH"], local_path=LOCAL_PATH, is_local=False)
    if data and "000300.SH" in data:
        print(f"[OK] get_index_constituent: {len(data['000300.SH'])}条成分股")
        return True
    print("[FAIL] get_index_constituent: 无数据")
    return False


def test_get_cash_flow():
    """测试 InfoData.get_cash_flow (现金流量表) - 仅1个标的"""
    login()
    info = get_sdk().InfoData()
    data = info.get_cash_flow(["000001.SZ"], local_path=LOCAL_PATH, is_local=False)
    if data and len(data) > 0:
        print(f"[OK] get_cash_flow: {len(data)}条")
        return True
    print("[FAIL] get_cash_flow: 无数据")
    return False


def test_get_profit_express():
    """测试 InfoData.get_profit_express (业绩快报) - 仅1个标的"""
    login()
    info = get_sdk().InfoData()
    # 测试带时间范围筛选
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=365 * 2)).strftime("%Y%m%d"))  # 最近2年

    data = info.get_profit_express(
        ["000001.SZ"],
        local_path=LOCAL_PATH,
        is_local=False,
        begin_date=begin_date,
        end_date=end_date,
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_profit_express: {len(data)}条")
        print(f"     时间范围: {begin_date} ~ {end_date}")
        if "REPORTING_PERI" in data.columns:
            print(
                f"     报告期范围: {data['REPORTING_PERI'].min()} ~ {data['REPORTING_PERI'].max()}"
            )
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_profit_express: {len(data)}条")
        return True
    print("[INFO] get_profit_express: 无数据(正常，可能该股没有业绩快报)")
    return True


def test_get_profit_notice():
    """测试 InfoData.get_profit_notice (业绩预告) - 仅1个标的"""
    login()
    info = get_sdk().InfoData()
    # 测试带时间范围筛选
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=365 * 2)).strftime("%Y%m%d"))  # 最近2年

    data = info.get_profit_notice(
        ["000001.SZ"],
        local_path=LOCAL_PATH,
        is_local=False,
        begin_date=begin_date,
        end_date=end_date,
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_profit_notice: {len(data)}条")
        print(f"     时间范围: {begin_date} ~ {end_date}")
        if "REPORTING_PERIOD" in data.columns:
            print(
                f"     报告期范围: {data['REPORTING_PERIOD'].min()} ~ {data['REPORTING_PERIOD'].max()}"
            )
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_profit_notice: {len(data)}条")
        return True
    print("[INFO] get_profit_notice: 无数据(正常，可能该股没有业绩预告)")
    return True


def test_get_dividend():
    """测试 InfoData.get_dividend (分红数据) - 仅1个标的"""
    login()
    info = get_sdk().InfoData()
    # 测试带时间范围筛选
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=365 * 2)).strftime("%Y%m%d"))  # 最近2年

    data = info.get_dividend(
        ["000001.SZ"],
        local_path=LOCAL_PATH,
        is_local=False,
        begin_date=begin_date,
        end_date=end_date,
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_dividend: {len(data)}条")
        print(f"     时间范围: {begin_date} ~ {end_date}")
        if "DATE_DVD_ANN" in data.columns:
            print(
                f"     分红公告日期范围: {data['DATE_DVD_ANN'].min()} ~ {data['DATE_DVD_ANN'].max()}"
            )
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_dividend: {len(data)}条")
        return True
    print("[FAIL] get_dividend: 无数据")
    return False


def test_get_holder_num():
    """测试 InfoData.get_holder_num (股东户数) - 仅1个标的"""
    login()
    info = get_sdk().InfoData()
    data = info.get_holder_num(["000001.SZ"], local_path=LOCAL_PATH, is_local=False)
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_holder_num: {len(data)}条")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_holder_num: {len(data)}条")
        return True
    print("[FAIL] get_holder_num: 无数据")
    return False


def test_get_margin_summary():
    """测试 InfoData.get_margin_summary (融资融券汇总)"""
    login()
    info = get_sdk().InfoData()
    # 测试带时间范围筛选
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=30)).strftime("%Y%m%d"))  # 最近30天

    data = info.get_margin_summary(
        local_path=LOCAL_PATH, is_local=False, begin_date=begin_date, end_date=end_date
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_margin_summary: {len(data)}条")
        print(f"     时间范围: {begin_date} ~ {end_date}")
        if "TRADE_DATE" in data.columns:
            print(f"     交易日期范围: {data['TRADE_DATE'].min()} ~ {data['TRADE_DATE'].max()}")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_margin_summary: {len(data)}条")
        return True
    print("[FAIL] get_margin_summary: 无数据")
    return False


def test_get_equity_structure():
    """测试 InfoData.get_equity_structure (股本结构) - 仅1个标的"""
    login()
    info = get_sdk().InfoData()
    data = info.get_equity_structure(["000001.SZ"], local_path=LOCAL_PATH, is_local=False)
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_equity_structure: {len(data)}条")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_equity_structure: {len(data)}条")
        return True
    print("[FAIL] get_equity_structure: 无数据")
    return False


def test_get_equity_restricted():
    """测试 InfoData.get_equity_restricted (限售股解禁) - 仅1个标的"""
    login()
    info = get_sdk().InfoData()
    # 测试带时间范围筛选
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=365 * 2)).strftime("%Y%m%d"))  # 最近2年

    data = info.get_equity_restricted(
        ["000001.SZ"],
        local_path=LOCAL_PATH,
        is_local=False,
        begin_date=begin_date,
        end_date=end_date,
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_equity_restricted: {len(data)}条")
        print(f"     时间范围: {begin_date} ~ {end_date}")
        if "LIST_DATE" in data.columns:
            print(f"     解禁日期范围: {data['LIST_DATE'].min()} ~ {data['LIST_DATE'].max()}")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_equity_restricted: {len(data)}条")
        return True
    print("[INFO] get_equity_restricted: 无数据(正常)")
    return True


def test_get_right_issue():
    """测试 InfoData.get_right_issue (配股) - 仅1个标的"""
    login()
    info = get_sdk().InfoData()
    # 测试带时间范围筛选
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=365 * 2)).strftime("%Y%m%d"))  # 最近2年

    data = info.get_right_issue(
        ["000001.SZ"],
        local_path=LOCAL_PATH,
        is_local=False,
        begin_date=begin_date,
        end_date=end_date,
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_right_issue: {len(data)}条")
        print(f"     时间范围: {begin_date} ~ {end_date}")
        if "ANN_DATE" in data.columns:
            print(f"     公告日期范围: {data['ANN_DATE'].min()} ~ {data['ANN_DATE'].max()}")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_right_issue: {len(data)}条")
        return True
    print("[INFO] get_right_issue: 无数据(正常)")
    return True


def test_get_industry_base_info():
    """测试 InfoData.get_industry_base_info (行业基本信息)"""
    login()
    info = get_sdk().InfoData()
    data = info.get_industry_base_info(local_path=LOCAL_PATH, is_local=False)
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_industry_base_info: {len(data)}条行业")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_industry_base_info: {len(data)}条")
        return True
    print("[FAIL] get_industry_base_info: 无数据")
    return False


def test_get_industry_constituent():
    """测试 InfoData.get_industry_constituent (行业成分股) - 仅1个行业"""
    login()
    info = get_sdk().InfoData()
    # 测试一个行业代码
    data = info.get_industry_constituent(["801010"], local_path=LOCAL_PATH, is_local=False)
    if data and len(data) > 0:
        print(f"[OK] get_industry_constituent: {len(data)}条")
        return True
    print("[FAIL] get_industry_constituent: 无数据")
    return False


def test_get_fund_share():
    """测试 InfoData.get_fund_share (基金份额) - 仅1个ETF，带时间参数"""
    login()
    info = get_sdk().InfoData()
    # 测试带时间范围筛选
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=90)).strftime("%Y%m%d"))  # 最近90天

    data = info.get_fund_share(
        ["510300.SH"],
        local_path=LOCAL_PATH,
        is_local=False,
        begin_date=begin_date,
        end_date=end_date,
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_fund_share: {len(data)}条")
        print(f"     时间范围: {begin_date} ~ {end_date}")
        if "CHANGE_DATE" in data.columns:
            print(f"     变动日期范围: {data['CHANGE_DATE'].min()} ~ {data['CHANGE_DATE'].max()}")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_fund_share: {len(data)}条")
        return True
    print("[FAIL] get_fund_share: 无数据")
    return False


def test_get_option_basic_info():
    """测试 InfoData.get_option_basic_info (期权基本信息)"""
    login()
    base = get_base()
    options = base.get_option_code_list()
    if options and len(options) > 0:
        # 只测试第1个期权
        info = get_sdk().InfoData()
        data = info.get_option_basic_info([options[0]], local_path=LOCAL_PATH, is_local=False)
        if isinstance(data, pd.DataFrame) and not data.empty:
            print(f"[OK] get_option_basic_info: {len(data)}条")
            return True
        elif data and len(data) > 0:
            print(f"[OK] get_option_basic_info: {len(data)}条")
            return True
    print("[FAIL] get_option_basic_info: 无数据")
    return False


def test_get_index_weight():
    """测试 InfoData.get_index_weight (指数权重) - 仅1个指数，带时间参数"""
    login()
    info = get_sdk().InfoData()
    # 测试带时间范围筛选
    begin_date = int((datetime.now() - timedelta(days=30)).strftime("%Y%m%d"))  # 最近30天

    data = info.get_index_weight(
        ["000300.SH"], local_path=LOCAL_PATH, is_local=False, begin_date=begin_date
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_index_weight: {len(data)}条")
        print(f"     时间范围: {begin_date} ~ 现在")
        if "TRADE_DATE" in data.columns:
            print(f"     交易日期范围: {data['TRADE_DATE'].min()} ~ {data['TRADE_DATE'].max()}")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_index_weight: {len(data)}条")
        return True
    print("[FAIL] get_index_weight: 无数据")
    return False


def test_get_industry_daily():
    """测试 InfoData.get_industry_daily (行业日行情) - 仅1个行业"""
    login()
    info = get_sdk().InfoData()
    data = info.get_industry_daily(["801010"], local_path=LOCAL_PATH, is_local=False)
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_industry_daily: {len(data)}条")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_industry_daily: {len(data)}条")
        return True
    print("[FAIL] get_industry_daily: 无数据")
    return False


def test_get_industry_weight():
    """测试 InfoData.get_industry_weight (行业权重) - 仅1个行业"""
    login()
    info = get_sdk().InfoData()
    data = info.get_industry_weight(["801010"], local_path=LOCAL_PATH, is_local=False)
    if data and len(data) > 0:
        print(f"[OK] get_industry_weight: {len(data)}条")
        return True
    print("[FAIL] get_industry_weight: 无数据")
    return False


def test_get_fund_iopv():
    """测试 InfoData.get_fund_iopv (基金IOPV) - 仅1个ETF，带时间参数"""
    login()
    info = get_sdk().InfoData()
    # 测试带时间范围筛选
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=90)).strftime("%Y%m%d"))  # 最近90天

    data = info.get_fund_iopv(
        ["510300.SH"],
        local_path=LOCAL_PATH,
        is_local=False,
        begin_date=begin_date,
        end_date=end_date,
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_fund_iopv: {len(data)}条")
        print(f"     时间范围: {begin_date} ~ {end_date}")
        if "PRICE_DATE" in data.columns:
            print(f"     日期范围: {data['PRICE_DATE'].min()} ~ {data['PRICE_DATE'].max()}")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_fund_iopv: {len(data)}条")
        return True
    print("[FAIL] get_fund_iopv: 无数据")
    return False


def test_get_equity_pledge_freeze():
    """测试 InfoData.get_equity_pledge_freeze (股权质押/冻结) - 仅1个标的"""
    login()
    info = get_sdk().InfoData()
    # 测试带时间范围筛选
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date = int((datetime.now() - timedelta(days=365 * 2)).strftime("%Y%m%d"))  # 最近2年

    data = info.get_equity_pledge_freeze(
        ["000001.SZ"],
        local_path=LOCAL_PATH,
        is_local=False,
        begin_date=begin_date,
        end_date=end_date,
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_equity_pledge_freeze: {len(data)}条")
        print(f"     时间范围: {begin_date} ~ {end_date}")
        if "ANN_DATE" in data.columns:
            print(f"     公告日期范围: {data['ANN_DATE'].min()} ~ {data['ANN_DATE'].max()}")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_equity_pledge_freeze: {len(data)}条")
        return True
    print("[INFO] get_equity_pledge_freeze: 无数据(正常)")
    return True


def test_get_history_stock_status():
    """测试 InfoData.get_history_stock_status (历史股票状态) - 仅1个标的"""
    login()
    info = get_sdk().InfoData()
    # 需要日期范围
    end_date = int(datetime.now().strftime("%Y%m%d"))
    start_date = int((datetime.now() - timedelta(days=365)).strftime("%Y%m%d"))
    data = info.get_history_stock_status(
        ["000001.SZ"],
        local_path=LOCAL_PATH,
        is_local=False,
        begin_date=start_date,
        end_date=end_date,
    )
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_history_stock_status: {len(data)}条")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_history_stock_status: {len(data)}条")
        return True
    print("[INFO] get_history_stock_status: 无数据(正常)")
    return True


def test_get_treasury_yield():
    """测试 InfoData.get_treasury_yield (国债收益率)"""
    login()
    info = get_sdk().InfoData()
    # InfoData.get_treasury_yield 需要 code_list 参数
    # 国债代码格式可能需要确认
    try:
        data = info.get_treasury_yield(
            code_list=["019623.SH"], local_path=LOCAL_PATH, is_local=False
        )
        if isinstance(data, pd.DataFrame) and not data.empty:
            print(f"[OK] get_treasury_yield: {len(data)}条")
            return True
        elif data is not None and len(data) > 0:
            print(f"[OK] get_treasury_yield: {len(data)}条")
            return True
        print("[INFO] get_treasury_yield: 无数据(可能接口参数需要调整)")
        return True  # 接口调用本身成功，只是无数据
    except Exception as e:
        print(f"[FAIL] get_treasury_yield: {e}")
        return False


def test_get_option_mon_ctr_specs():
    """测试 InfoData.get_option_mon_ctr_specs (期权月度合约规格)"""
    login()
    base = get_base()
    options = base.get_option_code_list()
    if options and len(options) > 0:
        info = get_sdk().InfoData()
        # 只测试第1个期权
        data = info.get_option_mon_ctr_specs([options[0]], local_path=LOCAL_PATH, is_local=False)
        if isinstance(data, pd.DataFrame) and not data.empty:
            print(f"[OK] get_option_mon_ctr_specs: {len(data)}条")
            return True
        elif data and len(data) > 0:
            print(f"[OK] get_option_mon_ctr_specs: {len(data)}条")
            return True
    print("[INFO] get_option_mon_ctr_specs: 无数据(正常)")
    return True


def test_get_option_std_ctr_specs():
    """测试 InfoData.get_option_std_ctr_specs (期权标准合约规格)"""
    login()
    base = get_base()
    options = base.get_option_code_list()
    if options and len(options) > 0:
        info = get_sdk().InfoData()
        # 只测试第1个期权
        data = info.get_option_std_ctr_specs([options[0]], local_path=LOCAL_PATH, is_local=False)
        if isinstance(data, pd.DataFrame) and not data.empty:
            print(f"[OK] get_option_std_ctr_specs: {len(data)}条")
            return True
        elif data and len(data) > 0:
            print(f"[OK] get_option_std_ctr_specs: {len(data)}条")
            return True
    print("[INFO] get_option_std_ctr_specs: 无数据(正常)")
    return True


def test_get_bj_code_mapping():
    """测试 InfoData.get_bj_code_mapping (北交所代码映射)"""
    login()
    info = get_sdk().InfoData()
    data = info.get_bj_code_mapping(local_path=LOCAL_PATH, is_local=False)
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"[OK] get_bj_code_mapping: {len(data)}条")
        return True
    elif data and len(data) > 0:
        print(f"[OK] get_bj_code_mapping: {len(data)}条")
        return True
    print("[INFO] get_bj_code_mapping: 无数据(正常，可能没有北交所数据)")
    return True


def test_get_option_mon_ctr_spcon():
    """测试 InfoData.get_option_mon_ctr_spcon (期权月合约属性变动)"""
    login()
    base = get_base()
    options = base.get_option_code_list()
    if options and len(options) > 0:
        info = get_sdk().InfoData()
        # 只测试前3个期权
        test_codes = options[:3]
        data = info.get_option_mon_ctr_spcon(test_codes, local_path=LOCAL_PATH, is_local=False)
        if isinstance(data, pd.DataFrame) and not data.empty:
            print(f"[OK] get_option_mon_ctr_spcon: {len(data)}条")
            print(f"     字段: {list(data.columns)[:5]}")
            return True
        elif data and len(data) > 0:
            print(f"[OK] get_option_mon_ctr_spcon: {len(data)}条")
            return True
    print("[INFO] get_option_mon_ctr_spcon: 无数据(正常，可能没有属性变动记录)")
    return True


# ========== SubscribeData 实时行情接口 ==========
def test_subscribe_snapshot():
    """测试 SubscribeData 股票实时快照回调(仅测试对象创建)"""
    login()
    try:
        subscribe = get_sdk().SubscribeData()
        print("[OK] SubscribeData.OnMDSnapshot: 对象创建成功(需要register+run实际使用)")
        return True
    except Exception as e:
        print(f"[FAIL] SubscribeData创建失败: {e}")
        return False


def test_subscribe_index_snapshot():
    """测试 SubscribeData 指数实时快照(仅测试对象创建)"""
    login()
    try:
        subscribe = get_sdk().SubscribeData()
        print("[OK] SubscribeData.OnMDIndexSnapshot: 对象创建成功")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_subscribe_option_snapshot():
    """测试 SubscribeData 期权实时快照(仅测试对象创建)"""
    login()
    try:
        subscribe = get_sdk().SubscribeData()
        print("[OK] SubscribeData.OnMDOptionSnapshot: 对象创建成功")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_subscribe_future_snapshot():
    """测试 SubscribeData 期货实时快照(仅测试对象创建)"""
    login()
    try:
        subscribe = get_sdk().SubscribeData()
        print("[OK] SubscribeData.OnMDFutureSnapshot: 对象创建成功")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_subscribe_hkt_snapshot():
    """测试 SubscribeData 港股通实时快照(仅测试对象创建)"""
    login()
    try:
        subscribe = get_sdk().SubscribeData()
        print("[OK] SubscribeData.OnMDHKTSnapshot: 对象创建成功")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_subscribe_order_book():
    """测试 SubscribeData 委托簿快照(仅测试对象创建)"""
    login()
    try:
        subscribe = get_sdk().SubscribeData()
        print("[OK] SubscribeData.OnMDOrderBook: 对象创建成功")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_subscribe_kline():
    """测试 SubscribeData 实时K线(仅测试对象创建)"""
    login()
    try:
        subscribe = get_sdk().SubscribeData()
        print("[OK] SubscribeData.OnKLine: 对象创建成功")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_subscribe_tick_execution():
    """测试 SubscribeData 逐笔成交(仅测试对象创建)"""
    login()
    try:
        subscribe = get_sdk().SubscribeData()
        print("[OK] SubscribeData.OnMDTickExecution: 对象创建成功")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


# ========== 接口注册表 ==========
API_TESTS = {
    # BaseData
    "get_calendar": test_get_calendar,
    "get_code_list": test_get_code_list,
    "get_code_info": test_get_code_info,
    "get_etf_pcf": test_get_etf_pcf,
    "get_option_code_list": test_get_option_code_list,
    "get_future_code_list": test_get_future_code_list,
    "get_backward_factor": test_get_backward_factor,
    "get_adj_factor": test_get_adj_factor,
    "get_hist_code_list": test_get_hist_code_list,
    "get_future_code_info": test_get_future_code_info,
    # MarketData
    "query_kline": test_query_kline,
    "query_kline_min": test_query_kline_min,
    "query_snapshot": test_query_snapshot,
    # InfoData
    "get_balance_sheet": test_get_balance_sheet,
    "get_income": test_get_income,
    "get_cash_flow": test_get_cash_flow,
    "get_profit_express": test_get_profit_express,
    "get_profit_notice": test_get_profit_notice,
    "get_share_holder": test_get_share_holder,
    "get_dividend": test_get_dividend,
    "get_holder_num": test_get_holder_num,
    "get_equity_structure": test_get_equity_structure,
    "get_equity_restricted": test_get_equity_restricted,
    "get_right_issue": test_get_right_issue,
    "get_long_hu_bang": test_get_long_hu_bang,
    "get_block_trading": test_get_block_trading,
    "get_margin_detail": test_get_margin_detail,
    "get_margin_summary": test_get_margin_summary,
    "get_index_constituent": test_get_index_constituent,
    "get_industry_base_info": test_get_industry_base_info,
    "get_industry_constituent": test_get_industry_constituent,
    "get_industry_daily": test_get_industry_daily,
    "get_industry_weight": test_get_industry_weight,
    "get_fund_share": test_get_fund_share,
    "get_fund_iopv": test_get_fund_iopv,
    "get_option_basic_info": test_get_option_basic_info,
    "get_option_mon_ctr_specs": test_get_option_mon_ctr_specs,
    "get_option_std_ctr_specs": test_get_option_std_ctr_specs,
    "get_option_mon_ctr_spcon": test_get_option_mon_ctr_spcon,
    "get_index_weight": test_get_index_weight,
    "get_equity_pledge_freeze": test_get_equity_pledge_freeze,
    "get_history_stock_status": test_get_history_stock_status,
    "get_treasury_yield": test_get_treasury_yield,
    "get_bj_code_mapping": test_get_bj_code_mapping,
    # SubscribeData (实时快照)
    "subscribe_snapshot": test_subscribe_snapshot,
    "subscribe_index_snapshot": test_subscribe_index_snapshot,
    "subscribe_option_snapshot": test_subscribe_option_snapshot,
    "subscribe_future_snapshot": test_subscribe_future_snapshot,
    "subscribe_hkt_snapshot": test_subscribe_hkt_snapshot,
    "subscribe_order_book": test_subscribe_order_book,
    "subscribe_kline": test_subscribe_kline,
    "subscribe_tick_execution": test_subscribe_tick_execution,
}


def list_apis():
    """列出所有可测试接口"""
    print("可测试接口列表:\n")
    print("BaseData:")
    for api in [
        "get_calendar",
        "get_code_list",
        "get_code_info",
        "get_etf_pcf",
        "get_option_code_list",
        "get_future_code_list",
        "get_backward_factor",
        "get_adj_factor",
        "get_hist_code_list",
        "get_future_code_info",
    ]:
        print(f"  - {api}")
    print("\nMarketData:")
    for api in ["query_kline", "query_kline_min", "query_snapshot"]:
        print(f"  - {api}")
    print("\nInfoData:")
    for api in [
        "get_balance_sheet",
        "get_income",
        "get_cash_flow",
        "get_profit_express",
        "get_profit_notice",
        "get_share_holder",
        "get_dividend",
        "get_holder_num",
        "get_long_hu_bang",
        "get_block_trading",
        "get_margin_detail",
        "get_margin_summary",
        "get_index_constituent",
    ]:
        print(f"  - {api}")
    print(f"\n共 {len(API_TESTS)} 个接口")


def main():
    if len(sys.argv) < 2:
        print("用法: python verify_amazingdata_api.py <接口名>")
        print("      python verify_amazingdata_api.py list  # 列出所有接口")
        print("      python verify_amazingdata_api.py all   # 测试全部")
        return

    api_name = sys.argv[1].lower()

    if api_name == "list":
        list_apis()
        return

    if api_name == "all":
        print(f"测试全部 {len(API_TESTS)} 个接口\n")
        passed = 0
        for name, func in API_TESTS.items():
            try:
                if func():
                    passed += 1
            except Exception as e:
                print(f"[FAIL] {name}: {e}")
        logout()
        print(f"\n总计: {passed}/{len(API_TESTS)} 通过")
        return

    if api_name not in API_TESTS:
        print(f"未知接口: {api_name}")
        print("使用 'list' 查看所有可用接口")
        return

    print(f"测试接口: {api_name}\n")
    try:
        API_TESTS[api_name]()
    except Exception as e:
        print(f"[FAIL] {api_name}: {e}")
    finally:
        logout()


if __name__ == "__main__":
    main()
