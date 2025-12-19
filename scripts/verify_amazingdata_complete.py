#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData SDK 完整能力验证 (按开发手册)

API结构:
- BaseData(): 基础数据(日历、股票列表、复权因子等)
- MarketData(calendar): 历史行情(K线、快照)
- InfoData(): 财务/股东/交易异动数据
- SubscribeData(): 实时数据订阅
"""

import sys
sys.path.insert(0, "d:/Stock/code/deepsearch")

def verify_amazingdata_complete():
    """按开发手册完整验证 AmazingData SDK"""
    print("="*70)
    print("AmazingData SDK 完整能力验证 (按开发手册)")
    print("="*70)
    
    results = {}
    
    def record(category, name, success, count=0, msg="", sample=None):
        key = f"{category}.{name}"
        results[key] = {"success": success, "count": count, "category": category}
        status = "OK" if success else "FAIL"
        count_str = f"({count}条)" if count > 0 else ""
        msg_str = f" - {msg}" if msg else ""
        print(f"  [{status}] {name:25} {count_str}{msg_str}")
        if sample and success:
            sample_str = str(sample)[:100]
            print(f"       样本: {sample_str}")
    
    import AmazingData as ad
    
    # ========== 登录 ==========
    print("\n[0] 登录 API")
    print("-" * 50)
    try:
        result = ad.login(
            username="212200038719",
            password="212200038719@2025",
            host="101.230.159.234",
            port=8600
        )
        if result == 0 or result is True:
            print("  [OK] 登录成功")
        else:
            print(f"  [FAIL] 登录失败: {result}")
            return
    except Exception as e:
        print(f"  [FAIL] 登录异常: {e}")
        return
    
    # ========== BaseData 基础数据 ==========
    print("\n[1] BaseData 基础数据")
    print("-" * 50)
    
    base = ad.BaseData()
    calendar = None
    code_list = None
    
    # 交易日历
    try:
        calendar = base.get_calendar()
        if calendar and len(calendar) > 0:
            record("BaseData", "get_calendar", True, len(calendar), sample=calendar[:3])
        else:
            record("BaseData", "get_calendar", False, msg="无数据")
    except Exception as e:
        record("BaseData", "get_calendar", False, msg=str(e)[:40])
    
    # A股代码列表
    try:
        code_list = base.get_code_list(security_type='EXTRA_STOCK_A')
        if code_list and len(code_list) > 0:
            record("BaseData", "get_code_list(A股)", True, len(code_list), sample=code_list[:3])
        else:
            record("BaseData", "get_code_list(A股)", False, msg="无数据")
    except Exception as e:
        record("BaseData", "get_code_list(A股)", False, msg=str(e)[:40])
    
    # 股票基本信息
    try:
        code_info = base.get_code_info(security_type='EXTRA_STOCK_A')
        if code_info is not None and len(code_info) > 0:
            record("BaseData", "get_code_info", True, len(code_info))
        else:
            record("BaseData", "get_code_info", False, msg="无数据")
    except Exception as e:
        record("BaseData", "get_code_info", False, msg=str(e)[:40])
    
    # ETF申赎清单 - 按手册: get_etf_pcf(code_list) 返回 (etf_pcf_info, etf_pcf_constituent)
    try:
        etf_pcf_info, etf_pcf_constituent = base.get_etf_pcf(["510300.SH"])
        if etf_pcf_info is not None and len(etf_pcf_info) > 0:
            record("BaseData", "get_etf_pcf(ETF清单)", True, len(etf_pcf_info))
        else:
            record("BaseData", "get_etf_pcf(ETF清单)", False, msg="无数据")
    except Exception as e:
        record("BaseData", "get_etf_pcf(ETF清单)", False, msg=str(e)[:40])
    
    # 期权代码列表
    try:
        option_list = base.get_option_code_list()
        if option_list and len(option_list) > 0:
            record("BaseData", "get_option_code_list", True, len(option_list))
        else:
            record("BaseData", "get_option_code_list", False, msg="无数据")
    except Exception as e:
        record("BaseData", "get_option_code_list", False, msg=str(e)[:40])
    
    # 期货代码列表
    try:
        future_list = base.get_future_code_list()
        if future_list and len(future_list) > 0:
            record("BaseData", "get_future_code_list", True, len(future_list))
        else:
            record("BaseData", "get_future_code_list", False, msg="无数据")
    except Exception as e:
        record("BaseData", "get_future_code_list", False, msg=str(e)[:40])
    
    # ========== MarketData 历史行情 ==========
    print("\n[2] MarketData 历史行情")
    print("-" * 50)
    
    if calendar is None:
        print("  [SKIP] 无交易日历，跳过MarketData测试")
    else:
        try:
            market = ad.MarketData(calendar)
            print("  [INFO] MarketData 实例创建成功")
            
            # 历史K线 - 按Period枚举: day=10008
            try:
                kline = market.query_kline(
                    code_list=["000001.SZ"],
                    begin_date=20241201,
                    end_date=20241213,
                    period=10008  # Period.day.value = 10008
                )
                if kline and "000001.SZ" in kline:
                    data = kline["000001.SZ"]
                    count = len(data) if hasattr(data, '__len__') else 1
                    record("MarketData", "query_kline(日K)", True, count)
                else:
                    record("MarketData", "query_kline(日K)", False, msg="无数据")
            except Exception as e:
                record("MarketData", "query_kline(日K)", False, msg=str(e)[:50])
            
            # 分钟K线 - 按Period枚举: min1=10000
            try:
                kline_min = market.query_kline(
                    code_list=["000001.SZ"],
                    begin_date=20241213,
                    end_date=20241213,
                    period=10000  # Period.min1.value = 10000
                )
                if kline_min and "000001.SZ" in kline_min:
                    data = kline_min["000001.SZ"]
                    count = len(data) if hasattr(data, '__len__') else 1
                    record("MarketData", "query_kline(1分钟)", True, count)
                else:
                    record("MarketData", "query_kline(1分钟)", False, msg="无数据")
            except Exception as e:
                record("MarketData", "query_kline(1分钟)", False, msg=str(e)[:50])
            
            # 历史快照 - 按手册: query_snapshot(code_list, begin_date, end_date)
            # 使用最近的交易日
            from datetime import datetime
            today = int(datetime.now().strftime("%Y%m%d"))
            try:
                snapshot = market.query_snapshot(
                    code_list=["000001.SZ"],
                    begin_date=today,
                    end_date=today
                )
                if snapshot:
                    # 检查返回的key
                    keys = list(snapshot.keys())[:3] if snapshot else []
                    if "000001.SZ" in snapshot:
                        data = snapshot["000001.SZ"]
                        count = len(data) if hasattr(data, '__len__') else 1
                        record("MarketData", "query_snapshot", True, count)
                    elif keys:
                        # 尝试使用返回的第一个key
                        first_key = keys[0]
                        data = snapshot[first_key]
                        count = len(data) if hasattr(data, '__len__') else 1
                        record("MarketData", "query_snapshot", True, count, sample=keys)
                    else:
                        record("MarketData", "query_snapshot", False, msg="无数据")
                else:
                    record("MarketData", "query_snapshot", False, msg="返回空")
            except Exception as e:
                record("MarketData", "query_snapshot", False, msg=str(e)[:50])
                
        except Exception as e:
            record("MarketData", "实例创建", False, msg=str(e)[:50])
    
    # ========== InfoData 财务/股东/交易数据 ==========
    print("\n[3] InfoData 财务/股东数据")
    print("-" * 50)
    
    try:
        info = ad.InfoData()
        local_path = "D://AmazingData_local_data//"
        test_codes = ["000001.SZ"]
        
        # 资产负债表
        try:
            balance = info.get_balance_sheet(test_codes, local_path=local_path, is_local=False)
            if balance and len(balance) > 0:
                record("InfoData", "get_balance_sheet", True, len(balance))
            else:
                record("InfoData", "get_balance_sheet", False, msg="无数据")
        except Exception as e:
            record("InfoData", "get_balance_sheet", False, msg=str(e)[:40])
        
        # 利润表
        try:
            income = info.get_income(test_codes, local_path=local_path, is_local=False)
            if income and len(income) > 0:
                record("InfoData", "get_income", True, len(income))
            else:
                record("InfoData", "get_income", False, msg="无数据")
        except Exception as e:
            record("InfoData", "get_income", False, msg=str(e)[:40])
        
        # 十大股东 - 使用DataFrame安全判断
        try:
            import pandas as pd
            holder = info.get_share_holder(test_codes, local_path=local_path, is_local=False)
            if isinstance(holder, pd.DataFrame):
                if not holder.empty:
                    record("InfoData", "get_share_holder", True, len(holder))
                else:
                    record("InfoData", "get_share_holder", False, msg="空DataFrame")
            elif holder and len(holder) > 0:
                record("InfoData", "get_share_holder", True, len(holder))
            else:
                record("InfoData", "get_share_holder", False, msg="无数据")
        except Exception as e:
            record("InfoData", "get_share_holder", False, msg=str(e)[:40])
        
        # 龙虎榜 - 按手册: get_long_hu_bang(code_list, local_path, is_local=True, begin_date, end_date)
        # 使用全市场股票列表 + 指定日期范围
        try:
            # 获取最近30天的日期范围
            from datetime import datetime, timedelta
            end_dt = datetime.now()
            begin_dt = end_dt - timedelta(days=30)
            begin_date = int(begin_dt.strftime("%Y%m%d"))
            end_date = int(end_dt.strftime("%Y%m%d"))
            
            # 使用少量股票进行测试，避免全市场查询过慢
            lhb_test_codes = ["000001.SZ", "600519.SH", "000002.SZ"]
            lhb = info.get_long_hu_bang(
                lhb_test_codes, 
                local_path=local_path,
                begin_date=begin_date,
                end_date=end_date
            )
            if isinstance(lhb, pd.DataFrame):
                if not lhb.empty:
                    record("InfoData", "get_long_hu_bang", True, len(lhb))
                else:
                    record("InfoData", "get_long_hu_bang", False, msg="无上榜记录(正常)")
            elif lhb and len(lhb) > 0:
                record("InfoData", "get_long_hu_bang", True, len(lhb))
            else:
                record("InfoData", "get_long_hu_bang", False, msg="无上榜记录(正常)")
        except Exception as e:
            record("InfoData", "get_long_hu_bang", False, msg=str(e)[:40])
        
        # 大宗交易 - 使用DataFrame安全判断
        try:
            block = info.get_block_trading(test_codes, local_path=local_path, is_local=False)
            if isinstance(block, pd.DataFrame):
                if not block.empty:
                    record("InfoData", "get_block_trading", True, len(block))
                else:
                    record("InfoData", "get_block_trading", False, msg="无数据")
            elif block and len(block) > 0:
                record("InfoData", "get_block_trading", True, len(block))
            else:
                record("InfoData", "get_block_trading", False, msg="无数据")
        except Exception as e:
            record("InfoData", "get_block_trading", False, msg=str(e)[:40])
        
        # 融资融券明细
        try:
            margin = info.get_margin_detail(test_codes, local_path=local_path, is_local=False)
            if margin and len(margin) > 0:
                record("InfoData", "get_margin_detail", True, len(margin))
            else:
                record("InfoData", "get_margin_detail", False, msg="无数据")
        except Exception as e:
            record("InfoData", "get_margin_detail", False, msg=str(e)[:40])
        
        # 指数成分
        try:
            idx = info.get_index_constituent(["000300.SH"], local_path=local_path, is_local=False)
            if idx and "000300.SH" in idx:
                record("InfoData", "get_index_constituent", True, len(idx["000300.SH"]))
            else:
                record("InfoData", "get_index_constituent", False, msg="无数据")
        except Exception as e:
            record("InfoData", "get_index_constituent", False, msg=str(e)[:40])
            
    except Exception as e:
        record("InfoData", "实例创建", False, msg=str(e)[:50])
    
    # 登出
    try:
        ad.logout("212200038719")
        print("\n  [INFO] 已登出")
    except:
        pass
    
    # ========== 结果汇总 ==========
    print("\n" + "="*70)
    print("测试结果汇总")
    print("="*70)
    
    categories = {}
    for key, r in results.items():
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"pass": 0, "total": 0}
        categories[cat]["total"] += 1
        if r["success"]:
            categories[cat]["pass"] += 1
    
    total_pass = sum(c["pass"] for c in categories.values())
    total_all = sum(c["total"] for c in categories.values())
    
    print(f"\n总体: {total_pass}/{total_all} 项通过")
    print()
    for cat, stats in categories.items():
        print(f"  {cat:15} : {stats['pass']}/{stats['total']}")
    
    print("\n详细结果:")
    for key, r in results.items():
        status = "OK" if r["success"] else "FAIL"
        count = r.get("count", 0)
        count_str = f"({count}条)" if count > 0 else ""
        print(f"  {status:4} | {key:35} {count_str}")


if __name__ == "__main__":
    verify_amazingdata_complete()
