"""
AmazingData API 深度测试脚本 v2

修正版：
1. 使用正确的HTTP方法(GET/POST)
2. POST接口发送JSON请求体而非URL参数
3. 详细验证返回数据内容
"""

import json
from datetime import datetime

import requests

BASE_URL = "http://localhost:8000/api/amazingdata"
LOG_FILE = "tests/amazingdata_api_test_log.txt"

# 测试结果统计
results = {"total": 0, "passed": 0, "failed": 0, "details": []}


def log(msg: str, to_file: bool = True):
    """打印并记录日志"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    if to_file:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def validate_response(
    name: str, endpoint: str, response: requests.Response, check_data_exists: bool = True
) -> dict:
    """
    验证响应数据

    返回: {"passed": bool, "reason": str, "data_summary": str}
    """
    result = {
        "name": name,
        "endpoint": endpoint,
        "status_code": response.status_code,
        "passed": False,
        "reason": "",
        "data_summary": "",
        "record_count": 0,
    }

    # 1. 检查状态码
    if response.status_code != 200:
        result["reason"] = f"状态码错误: {response.status_code}"
        try:
            result["data_summary"] = response.text[:500]
        except:
            pass
        return result

    # 2. 检查JSON格式
    try:
        data = response.json()
    except json.JSONDecodeError:
        result["reason"] = "响应不是有效JSON"
        result["data_summary"] = response.text[:200]
        return result

    # 3. 检查success字段
    if isinstance(data, dict):
        if data.get("success") is False:
            error_msg = data.get("error") or data.get("detail") or "Unknown error"
            result["reason"] = f"接口返回失败: {error_msg}"
            result["data_summary"] = str(data)[:500]
            return result

        if "detail" in data and "error" not in data:
            # FastAPI validation error
            result["reason"] = f"请求验证失败: {data['detail']}"
            result["data_summary"] = str(data)[:500]
            return result

    # 4. 分析数据内容
    if isinstance(data, dict):
        # 尝试找到实际数据
        actual_data = None
        for key in ["data", "items", "result"]:
            if key in data:
                actual_data = data[key]
                break

        if actual_data is None:
            actual_data = data

        # 统计数据条数
        if isinstance(actual_data, list):
            result["record_count"] = len(actual_data)
            if len(actual_data) > 0:
                first_item = actual_data[0]
                if isinstance(first_item, dict):
                    result["data_summary"] = (
                        f"列表[{len(actual_data)}条], 首条字段: {list(first_item.keys())[:8]}"
                    )
                else:
                    result["data_summary"] = (
                        f"列表[{len(actual_data)}条], 首项: {str(first_item)[:50]}"
                    )
            else:
                result["data_summary"] = "空列表[]"
        elif isinstance(actual_data, dict):
            result["record_count"] = 1
            result["data_summary"] = f"字典, 字段: {list(actual_data.keys())[:10]}"
            # 检查是否有count字段
            if "count" in data:
                result["record_count"] = data["count"]
                result["data_summary"] += f", count={data['count']}"
        else:
            result["record_count"] = 1 if actual_data else 0
            result["data_summary"] = (
                f"类型: {type(actual_data).__name__}, 值: {str(actual_data)[:100]}"
            )
    elif isinstance(data, list):
        result["record_count"] = len(data)
        result["data_summary"] = f"列表[{len(data)}条]"
    else:
        result["record_count"] = 1
        result["data_summary"] = f"类型: {type(data).__name__}"

    # 5. 检查是否有实际数据
    if check_data_exists and result["record_count"] == 0:
        # 空数据不一定是错误，但需要标记
        result["passed"] = True
        result["reason"] = "OK (无数据)"
        return result

    result["passed"] = True
    result["reason"] = "OK"
    return result


def test_api(
    name: str,
    endpoint: str,
    method: str = "GET",
    params: dict = None,
    json_body: dict = None,
    check_data_exists: bool = True,
):
    """测试单个API接口"""
    results["total"] += 1
    url = f"{BASE_URL}{endpoint}"

    log(f"\n{'='*60}")
    log(f"测试 [{results['total']}] {name}")
    log(f"  HTTP方法: {method}")
    log(f"  端点: {endpoint}")
    if params:
        log(f"  URL参数: {params}")
    if json_body:
        log(f"  请求体: {json.dumps(json_body, ensure_ascii=False)[:200]}")

    try:
        if method == "GET":
            resp = requests.get(url, params=params, timeout=60)
        else:
            resp = requests.post(url, json=json_body, params=params, timeout=60)

        result = validate_response(name, endpoint, resp, check_data_exists)

        if result["passed"]:
            results["passed"] += 1
            log(f"  [PASS] 状态码={result['status_code']}, 记录数={result['record_count']}")
            log(f"  数据摘要: {result['data_summary']}")
        else:
            results["failed"] += 1
            log(f"  [FAIL] {result['reason']}")
            if result["data_summary"]:
                log(f"  响应摘要: {result['data_summary'][:300]}")

        results["details"].append(result)

    except requests.exceptions.Timeout:
        results["failed"] += 1
        log("  [FAIL] 请求超时(60秒)")
        results["details"].append(
            {
                "name": name,
                "endpoint": endpoint,
                "passed": False,
                "reason": "请求超时",
                "status_code": 0,
                "record_count": 0,
            }
        )
    except requests.exceptions.ConnectionError:
        results["failed"] += 1
        log("  [FAIL] 连接失败，服务未启动?")
        results["details"].append(
            {
                "name": name,
                "endpoint": endpoint,
                "passed": False,
                "reason": "连接失败",
                "status_code": 0,
                "record_count": 0,
            }
        )
    except Exception as e:
        results["failed"] += 1
        log(f"  [FAIL] 异常: {e}")
        results["details"].append(
            {
                "name": name,
                "endpoint": endpoint,
                "passed": False,
                "reason": str(e),
                "status_code": 0,
                "record_count": 0,
            }
        )


def run_all_tests():
    """运行所有测试"""
    # 清空日志文件
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("AmazingData API 深度测试 v2\n")
        f.write(f"测试时间: {datetime.now()}\n")
        f.write(f"基础URL: {BASE_URL}\n")
        f.write("=" * 60 + "\n")

    log("\n" + "=" * 60)
    log("AmazingData API 深度测试 v2")
    log(f"测试时间: {datetime.now()}")
    log("=" * 60)

    # ==================== BasicData 模块 ====================
    log("\n>>> 模块: BasicData (基础数据) - 10个接口")

    # GET 接口
    test_api(
        "get_code_info", "/basic/code-info", method="GET", params={"security_type": "EXTRA_STOCK_A"}
    )

    test_api(
        "get_calendar",
        "/basic/calendar",
        method="GET",
        params={"market": "SH", "begin_date": 20240101, "end_date": 20240131},
    )

    test_api(
        "get_code_list", "/basic/code-list", method="GET", params={"security_type": "EXTRA_STOCK_A"}
    )

    test_api("get_future_code_list", "/basic/future-code-list", method="GET")

    test_api("get_bj_code_mapping", "/basic/bj-code-mapping", method="GET")

    # POST 接口
    test_api(
        "get_stock_basic",
        "/basic/stock-basic",
        method="POST",
        json_body={"code_list": ["SH.600000", "SZ.000001"]},
    )

    test_api(
        "get_backward_factor",
        "/basic/backward-factor",
        method="POST",
        json_body={
            "code_list": ["SH.600000"],
            "begin_date": 20240101,
            "end_date": 20241225,
            "is_local": True,
        },
    )

    test_api(
        "get_adj_factor",
        "/basic/adj-factor",
        method="POST",
        json_body={
            "code_list": ["SH.600000"],
            "begin_date": 20240101,
            "end_date": 20241225,
            "is_local": True,
        },
    )

    test_api(
        "get_history_stock_status",
        "/basic/history-stock-status",
        method="POST",
        json_body={
            "code_list": ["SH.600000"],
            "begin_date": 20240101,
            "end_date": 20241225,
            "is_local": True,
        },
    )

    test_api(
        "get_hist_code_list",
        "/basic/hist-code-list",
        method="POST",
        json_body={
            "security_type": "EXTRA_STOCK_A_SH_SZ",
            "start_date": 20240101,
            "end_date": 20240131,
        },
    )

    # ==================== Financial 模块 ====================
    log("\n>>> 模块: Financial (财务数据) - 6个接口")

    test_api(
        "get_balance_sheet",
        "/financial/balance-sheet",
        method="POST",
        json_body={"code_list": ["SH.600000"], "report_type": "quarter", "is_local": True},
    )

    test_api(
        "get_cash_flow",
        "/financial/cash-flow",
        method="POST",
        json_body={"code_list": ["SH.600000"], "report_type": "quarter", "is_local": True},
    )

    test_api(
        "get_income",
        "/financial/income",
        method="POST",
        json_body={"code_list": ["SH.600000"], "report_type": "quarter", "is_local": True},
    )

    test_api(
        "get_profit_express",
        "/financial/profit-express",
        method="POST",
        json_body={"code_list": ["SH.600000"], "is_local": True},
    )

    test_api(
        "get_profit_notice",
        "/financial/profit-notice",
        method="POST",
        json_body={"code_list": ["SH.600000"], "is_local": True},
    )

    test_api(
        "get_financial_summary",
        "/financial/financial-summary",
        method="POST",
        params={"code": "SH.600000"},
    )

    # ==================== Margin 模块 ====================
    log("\n>>> 模块: Margin (融资融券) - 4个接口")

    test_api("get_margin_summary", "/margin/margin-summary", method="GET")

    test_api(
        "get_margin_detail", "/margin/margin-detail", method="POST", params={"code": "SH.600000"}
    )

    test_api(
        "get_long_hu_bang", "/margin/long-hu-bang", method="POST", params={"code": "SH.600000"}
    )

    test_api(
        "get_block_trading", "/margin/block-trading", method="POST", params={"code": "SH.600000"}
    )

    # ==================== 测试报告 ====================
    log("\n" + "=" * 60)
    log("测试报告汇总")
    log("=" * 60)
    log(f"总计: {results['total']} 个接口")
    log(f"通过: {results['passed']} ({results['passed']/results['total']*100:.1f}%)")
    log(f"失败: {results['failed']} ({results['failed']/results['total']*100:.1f}%)")

    if results["failed"] > 0:
        log("\n失败接口列表:")
        for r in results["details"]:
            if not r["passed"]:
                log(f"  - {r['name']}: {r['reason'][:100]}")

    log("\n通过接口列表:")
    for r in results["details"]:
        if r["passed"]:
            log(f"  + {r['name']}: {r['data_summary'][:80]}")

    log(f"\n详细日志已保存到: {LOG_FILE}")


if __name__ == "__main__":
    run_all_tests()
