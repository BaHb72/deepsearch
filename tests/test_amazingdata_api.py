"""
AmazingData API 后端测试脚本
测试8000端口全部接口是否正常响应
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000/api/amazingdata"

# 测试结果记录
results = {
    "tested": 0,
    "passed": 0,
    "failed": 0,
    "errors": []
}

def test_endpoint(method: str, path: str, params: dict = None, json_data: dict = None, description: str = ""):
    """测试单个端点"""
    url = f"{BASE_URL}{path}"
    results["tested"] += 1
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, params=params, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=json_data, timeout=10)
        else:
            raise ValueError(f"不支持的HTTP方法: {method}")
        
        if response.status_code == 200:
            results["passed"] += 1
            data = response.json()
            record_count = len(data.get("data", [])) if isinstance(data.get("data"), list) else "N/A"
            print(f"[PASS] {description}: {path} (状态码: 200, 记录数: {record_count})")
            return True, data
        else:
            results["failed"] += 1
            results["errors"].append({
                "path": path,
                "description": description,
                "status_code": response.status_code,
                "error": response.text[:200]
            })
            print(f"[FAIL] {description}: {path} (状态码: {response.status_code})")
            return False, None
            
    except requests.exceptions.ConnectionError:
        results["failed"] += 1
        results["errors"].append({
            "path": path,
            "description": description,
            "error": "连接失败 - 请确认后端服务器运行在8000端口"
        })
        print(f"[ERROR] {description}: {path} (连接失败)")
        return False, None
    except Exception as e:
        results["failed"] += 1
        results["errors"].append({
            "path": path,
            "description": description,
            "error": str(e)
        })
        print(f"[ERROR] {description}: {path} ({str(e)})")
        return False, None

def main():
    print("=" * 60)
    print("AmazingData API 后端接口测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"基础URL: {BASE_URL}")
    print("=" * 60)
    
    # 1. 测试根路径API信息
    print("\n>>> 1. API 根信息")
    test_endpoint("GET", "/", description="API根信息")
    
    # 2. 测试 basic_data 模块
    print("\n>>> 2. Basic Data 模块 (BaseData)")
    
    # GET 请求接口
    test_endpoint("GET", "/basic/code-info", 
                  params={"security_type": "EXTRA_STOCK_A"}, 
                  description="get_code_info")
    
    test_endpoint("GET", "/basic/calendar", 
                  params={"market": "SH", "data_type": "str"}, 
                  description="get_calendar")
    
    test_endpoint("GET", "/basic/code-list", 
                  params={"security_type": "EXTRA_STOCK_A"}, 
                  description="get_code_list")
    
    test_endpoint("GET", "/basic/future-code-list", 
                  params={"security_type": "EXTRA_FUTURE"}, 
                  description="get_future_code_list")
    
    test_endpoint("GET", "/basic/bj-code-mapping", 
                  description="get_bj_code_mapping")
    
    # POST 请求接口
    test_endpoint("POST", "/basic/stock-basic", 
                  json_data={"code_list": ["SH.600000"]}, 
                  description="get_stock_basic")
    
    test_endpoint("POST", "/basic/backward-factor", 
                  json_data={
                      "code_list": ["SH.600000"],
                      "begin_date": 20241201,
                      "end_date": 20241225,
                      "is_local": True
                  }, 
                  description="get_backward_factor")
    
    test_endpoint("POST", "/basic/adj-factor", 
                  json_data={
                      "code_list": ["SH.600000"],
                      "begin_date": 20241201,
                      "end_date": 20241225,
                      "is_local": True
                  }, 
                  description="get_adj_factor")
    
    test_endpoint("POST", "/basic/history-stock-status", 
                  json_data={
                      "code_list": ["SH.600000"],
                      "begin_date": 20241201,
                      "end_date": 20241225,
                      "is_local": True
                  }, 
                  description="get_history_stock_status")
    
    test_endpoint("POST", "/basic/hist-code-list", 
                  json_data={
                      "security_type": "EXTRA_STOCK_A_SH_SZ",
                      "start_date": 20241201,
                      "end_date": 20241225
                  }, 
                  description="get_hist_code_list")
    
    # 3. 测试 financial 模块 (InfoData - 财务相关)
    print("\n>>> 3. Financial 模块 (InfoData财务)")
    
    test_endpoint("POST", "/financial/balance-sheet", 
                  json_data={
                      "code_list": ["SH.600000"],
                      "report_type": "quarter",
                      "is_local": True
                  }, 
                  description="get_balance_sheet")
    
    test_endpoint("POST", "/financial/cash-flow", 
                  json_data={
                      "code_list": ["SH.600000"],
                      "report_type": "quarter",
                      "is_local": True
                  }, 
                  description="get_cash_flow")
    
    test_endpoint("POST", "/financial/income", 
                  json_data={
                      "code_list": ["SH.600000"],
                      "report_type": "quarter",
                      "is_local": True
                  }, 
                  description="get_income")
    
    test_endpoint("POST", "/financial/profit-express", 
                  json_data={
                      "code_list": ["SH.600000"],
                      "is_local": True
                  }, 
                  description="get_profit_express")
    
    test_endpoint("POST", "/financial/profit-notice", 
                  json_data={
                      "code_list": ["SH.600000"],
                      "is_local": True
                  }, 
                  description="get_profit_notice")
    
    # 4. 测试 margin 模块 (InfoData - 融资融券)
    print("\n>>> 4. Margin 模块 (InfoData融资融券)")
    
    test_endpoint("GET", "/margin/summary", 
                  params={"code": "SH.600000"}, 
                  description="get_margin_summary")
    
    test_endpoint("GET", "/margin/detail", 
                  params={"code": "SH.600000"}, 
                  description="get_margin_detail")
    
    test_endpoint("GET", "/margin/long-hu-bang", 
                  params={"limit": 10}, 
                  description="get_long_hu_bang")
    
    test_endpoint("GET", "/margin/block-trading", 
                  params={"limit": 10}, 
                  description="get_block_trading")
    
    # 5. 测试 shareholder 模块 (InfoData - 股东股本)
    print("\n>>> 5. Shareholder 模块 (InfoData股东股本)")
    
    test_endpoint("POST", "/shareholder/share-holder", 
                  json_data={"code_list": ["SH.600000"]}, 
                  description="get_share_holder")
    
    test_endpoint("POST", "/shareholder/holder-num", 
                  json_data={"code_list": ["SH.600000"]}, 
                  description="get_holder_num")
    
    test_endpoint("POST", "/shareholder/equity-structure", 
                  json_data={"code_list": ["SH.600000"]}, 
                  description="get_equity_structure")
    
    test_endpoint("POST", "/shareholder/equity-pledge-freeze", 
                  json_data={"code_list": ["SH.600000"]}, 
                  description="get_equity_pledge_freeze")
    
    test_endpoint("POST", "/shareholder/equity-restricted", 
                  json_data={"code_list": ["SH.600000"]}, 
                  description="get_equity_restricted")
    
    test_endpoint("POST", "/shareholder/dividend", 
                  json_data={"code_list": ["SH.600000"]}, 
                  description="get_dividend")
    
    test_endpoint("POST", "/shareholder/right-issue", 
                  json_data={"code_list": ["SH.600000"]}, 
                  description="get_right_issue")
    
    # 6. 测试 realtime 模块 (MarketData)
    print("\n>>> 6. Realtime 模块 (MarketData)")
    
    test_endpoint("GET", "/realtime/snapshot", 
                  params={"codes": "SH.600000"}, 
                  description="query_snapshot")
    
    # 7. 测试 history 模块 (MarketData)
    print("\n>>> 7. History 模块 (MarketData)")
    
    test_endpoint("GET", "/history/kline", 
                  params={
                      "code": "SH.600000",
                      "period": "day",
                      "start_date": "20241201",
                      "end_date": "20241225"
                  }, 
                  description="query_kline")
    
    # 打印测试总结
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"总测试数: {results['tested']}")
    print(f"通过: {results['passed']}")
    print(f"失败: {results['failed']}")
    print(f"成功率: {results['passed']/results['tested']*100:.1f}%" if results['tested'] > 0 else "N/A")
    
    if results["errors"]:
        print("\n失败详情:")
        for i, err in enumerate(results["errors"], 1):
            print(f"  {i}. {err['description']} ({err['path']})")
            print(f"     错误: {err.get('error', 'Unknown')[:100]}")
    
    return results

if __name__ == "__main__":
    main()
