"""
快速验证AkShare核心API接口
测试最常用的API确保基本功能正常
"""

import json
import time
from datetime import datetime

import pandas as pd

try:
    import akshare as ak

    version = getattr(ak, "__version__", "unknown")
    print(f"AkShare version: {version}")
except ImportError:
    print("AkShare not installed!")
    exit(1)


def test_api(func_name, params=None):
    """测试单个API"""
    if params is None:
        params = {}

    result = {
        "function": func_name,
        "params": params,
        "status": "unknown",
        "error": None,
        "response_time": None,
        "data_shape": None,
    }

    try:
        func = getattr(ak, func_name)
        start = time.time()
        data = func(**params)
        response_time = time.time() - start

        result["response_time"] = round(response_time, 3)

        if isinstance(data, pd.DataFrame):
            result["status"] = "success"
            result["data_shape"] = list(data.shape)
            print(f"[OK] {func_name}: Success ({data.shape[0]} rows, {response_time:.2f}s)")
        elif data is not None:
            result["status"] = "success"
            result["data_shape"] = type(data).__name__
            print(f"[OK] {func_name}: Success ({type(data).__name__}, {response_time:.2f}s)")
        else:
            result["status"] = "empty"
            print(f"[EMPTY] {func_name}: Empty response")
    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)[:200]
        print(f"[FAIL] {func_name}: Failed - {str(e)[:100]}")

    return result


def main():
    print("=" * 60)
    print("AkShare Core API Validation")
    print("=" * 60)

    # 核心API测试列表
    test_cases = [
        # 实时行情
        ("stock_zh_a_spot_em", {}),  # A股实时行情
        ("stock_zh_index_spot_em", {}),  # 指数实时行情
        # 历史数据
        (
            "stock_zh_a_hist",
            {
                "symbol": "000001",
                "period": "daily",
                "start_date": "20240101",
                "end_date": "20240131",
                "adjust": "",
            },
        ),
        # 分钟数据
        (
            "stock_zh_a_hist_min_em",
            {
                "symbol": "000001",
                "start_date": "2024-01-01 09:30:00",
                "end_date": "2024-01-01 15:00:00",
                "period": "5",
                "adjust": "",
            },
        ),
        # 个股信息
        ("stock_individual_info_em", {"symbol": "000001"}),
        # 板块数据
        ("stock_board_industry_name_em", {}),
        ("stock_board_concept_name_em", {}),
        # 涨跌停数据
        ("stock_zt_pool_em", {"date": None}),  # 涨停板
        ("stock_zt_pool_dtgc_em", {"date": None}),  # 跌停板
        # 筹码分布
        ("stock_cyq_em", {"symbol": "000001", "adjust": "qfq"}),
        # 指数成分股
        ("index_stock_cons", {"symbol": "000300"}),
        # 基金数据
        ("fund_etf_spot_em", {}),  # ETF实时行情
        # 宏观数据
        ("macro_china_lpr", {}),  # LPR利率
        ("macro_china_cpi_yearly", {}),  # CPI年度数据
    ]

    results = []

    print(f"\nTesting {len(test_cases)} core APIs...\n")

    for func_name, params in test_cases:
        result = test_api(func_name, params)
        results.append(result)
        time.sleep(0.5)  # 避免请求过快

    # 统计结果
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    empty = sum(1 for r in results if r["status"] == "empty")

    print(f"Total: {len(results)}")
    print(f"Success: {success} ({success/len(results)*100:.1f}%)")
    print(f"Failed: {failed}")
    print(f"Empty: {empty}")

    # 保存结果
    output_file = f"akshare_sample_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "test_time": datetime.now().isoformat(),
                "summary": {
                    "total": len(results),
                    "success": success,
                    "failed": failed,
                    "empty": empty,
                    "success_rate": f"{success/len(results)*100:.1f}%",
                },
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\nResults saved to: {output_file}")

    # 显示失败的API
    if failed > 0:
        print("\nFailed APIs:")
        for r in results:
            if r["status"] == "failed":
                print(f"  - {r['function']}: {r['error'][:100]}")


if __name__ == "__main__":
    main()
