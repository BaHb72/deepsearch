#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData 扩展接口完整测试脚本

测试所有7个扩展接口的日期范围参数功能:
【第一批扩展】
- get_equity_pledge_freeze: 股权质押/冻结
- get_equity_restricted: 限售股解禁
- get_dividend: 分红数据

【第二批扩展】
- get_right_issue: 配股数据
- get_margin_summary: 融资融券交易汇总
- get_margin_detail: 融资融券标的明细
- get_long_hu_bang: 龙虎榜
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
    "port": 8600
}
LOCAL_PATH = "D://AmazingData_local_data//"

# 全局缓存
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
        print("[OK] 登录成功\n")
        _logged_in = True
        return True
    print(f"[FAIL] 登录失败: {result}")
    return False


def print_section(title):
    """打印章节标题"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def test_result(success, data, interface_name, extra_info=""):
    """统一的测试结果输出"""
    if isinstance(data, pd.DataFrame) and not data.empty:
        print(f"      ✓ 成功获取 {len(data)} 条数据")
        print(f"      字段数: {len(data.columns)}")
        print(extra_info if extra_info else "")
        print(f"      主要字段: {list(data.columns[:5])}")
        return True
    elif success:
        print(f"      ○ 无数据(正常,可能该股{interface_name})")
        return True
    else:
        print(f"      ✗ 失败: 无法获取数据")
        return False


def test_all_extended_apis():
    """测试所有扩展接口"""
    if not login():
        return False
    
    info = get_sdk().InfoData()
    
    # 准备日期参数
    end_date = int(datetime.now().strftime("%Y%m%d"))
    begin_date_2y = int((datetime.now() - timedelta(days=365*2)).strftime("%Y%m%d"))  # 2年
    begin_date_30d = int((datetime.now() - timedelta(days=30)).strftime("%Y%m%d"))    # 30天
    
    print_section("AmazingData 扩展接口完整测试 (共7个接口)")
    
    # ========== 第一批扩展 ==========
    print_section("第一批扩展 (股东权益相关)")
    
    # 1. get_equity_pledge_freeze
    print(f"\n[1/7] 测试 get_equity_pledge_freeze (股权质押/冻结)")
    print(f"      参数: code_list=['000001.SZ'], begin_date={begin_date_2y}, end_date={end_date}")
    try:
        data = info.get_equity_pledge_freeze(
            ["000001.SZ"], 
            local_path=LOCAL_PATH, 
            is_local=False,
            begin_date=begin_date_2y,
            end_date=end_date
        )
        extra = ""
        if isinstance(data, pd.DataFrame) and not data.empty and 'ANN_DATE' in data.columns:
            extra = f"      公告日期范围: {data['ANN_DATE'].min()} ~ {data['ANN_DATE'].max()}"
        test_result(True, data, "没有质押/冻结记录", extra)
    except Exception as e:
        print(f"      ✗ 失败: {e}")
    
    # 2. get_equity_restricted
    print(f"\n[2/7] 测试 get_equity_restricted (限售股解禁)")
    print(f"      参数: code_list=['000001.SZ'], begin_date={begin_date_2y}, end_date={end_date}")
    try:
        data = info.get_equity_restricted(
            ["000001.SZ"], 
            local_path=LOCAL_PATH, 
            is_local=False,
            begin_date=begin_date_2y,
            end_date=end_date
        )
        extra = ""
        if isinstance(data, pd.DataFrame) and not data.empty and 'LIST_DATE' in data.columns:
            extra = f"      解禁日期范围: {data['LIST_DATE'].min()} ~ {data['LIST_DATE'].max()}"
        test_result(True, data, "没有限售股解禁", extra)
    except Exception as e:
        print(f"      ✗ 失败: {e}")
    
    # 3. get_dividend
    print(f"\n[3/7] 测试 get_dividend (分红数据)")
    print(f"      参数: code_list=['000001.SZ'], begin_date={begin_date_2y}, end_date={end_date}")
    try:
        data = info.get_dividend(
            ["000001.SZ"], 
            local_path=LOCAL_PATH, 
            is_local=False,
            begin_date=begin_date_2y,
            end_date=end_date
        )
        extra = ""
        if isinstance(data, pd.DataFrame) and not data.empty and 'DATE_DVD_ANN' in data.columns:
            extra = f"      公告日期范围: {data['DATE_DVD_ANN'].min()} ~ {data['DATE_DVD_ANN'].max()}"
        test_result(True, data, "在此期间没有分红", extra)
    except Exception as e:
        print(f"      ✗ 失败: {e}")
    
    # ========== 第二批扩展 ==========
    print_section("第二批扩展 (市场异动与融资融券)")
    
    # 4. get_right_issue
    print(f"\n[4/7] 测试 get_right_issue (配股数据)")
    print(f"      参数: code_list=['000001.SZ'], begin_date={begin_date_2y}, end_date={end_date}")
    try:
        data = info.get_right_issue(
            ["000001.SZ"], 
            local_path=LOCAL_PATH, 
            is_local=False,
            begin_date=begin_date_2y,
            end_date=end_date
        )
        extra = ""
        if isinstance(data, pd.DataFrame) and not data.empty and 'ANN_DATE' in data.columns:
            extra = f"      公告日期范围: {data['ANN_DATE'].min()} ~ {data['ANN_DATE'].max()}"
        test_result(True, data, "没有配股记录", extra)
    except Exception as e:
        print(f"      ✗ 失败: {e}")
    
    # 5. get_margin_summary
    print(f"\n[5/7] 测试 get_margin_summary (融资融券汇总)")
    print(f"      参数: begin_date={begin_date_30d}, end_date={end_date}")
    try:
        data = info.get_margin_summary(
            local_path=LOCAL_PATH, 
            is_local=False,
            begin_date=begin_date_30d,
            end_date=end_date
        )
        extra = ""
        if isinstance(data, pd.DataFrame) and not data.empty and 'TRADE_DATE' in data.columns:
            extra = f"      交易日期范围: {data['TRADE_DATE'].min()} ~ {data['TRADE_DATE'].max()}"
        test_result(True, data, "全市场融资融券汇总", extra)
    except Exception as e:
        print(f"      ✗ 失败: {e}")
    
    # 6. get_margin_detail
    print(f"\n[6/7] 测试 get_margin_detail (融资融券明细)")
    print(f"      参数: code_list=['000001.SZ'], begin_date={begin_date_30d}, end_date={end_date}")
    try:
        data = info.get_margin_detail(
            ["000001.SZ"], 
            local_path=LOCAL_PATH, 
            is_local=False,
            begin_date=begin_date_30d,
            end_date=end_date
        )
        extra = ""
        if isinstance(data, pd.DataFrame) and not data.empty and 'TRADE_DATE' in data.columns:
            extra = f"      交易日期范围: {data['TRADE_DATE'].min()} ~ {data['TRADE_DATE'].max()}"
        test_result(True, data, "个股融资融券明细", extra)
    except Exception as e:
        print(f"      ✗ 失败: {e}")
    
    # 7. get_long_hu_bang
    print(f"\n[7/7] 测试 get_long_hu_bang (龙虎榜)")
    print(f"      参数: code_list=['000001.SZ'], begin_date={begin_date_30d}, end_date={end_date}")
    try:
        data = info.get_long_hu_bang(
            ["000001.SZ"], 
            local_path=LOCAL_PATH,
            is_local=False,
            begin_date=begin_date_30d,
            end_date=end_date
        )
        extra = ""
        if isinstance(data, pd.DataFrame) and not data.empty and 'TRADE_DATE' in data.columns:
            extra = f"      上榜日期范围: {data['TRADE_DATE'].min()} ~ {data['TRADE_DATE'].max()}"
        test_result(True, data, "没有上榜记录", extra)
    except Exception as e:
        print(f"      ✗ 失败: {e}")
    
    print_section("测试完成")
    print("\n✓ 所有7个扩展接口测试完成")
    print("  - 第一批扩展: 3个 (股权质押/冻结, 限售股解禁, 分红数据)")
    print("  - 第二批扩展: 4个 (配股, 融资融券汇总, 融资融券明细, 龙虎榜)")
    print("\n详细文档: docs/amazingdata_extension_summary.md\n")
    
    return True


if __name__ == "__main__":
    try:
        test_all_extended_apis()
    except KeyboardInterrupt:
        print("\n\n测试中断")
    except Exception as e:
        print(f"\n\n测试失败: {e}")
        import traceback
        traceback.print_exc()
