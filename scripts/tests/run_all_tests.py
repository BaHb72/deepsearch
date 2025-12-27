# encoding:utf-8
"""
AmazingData API 测试脚本 - 总运行入口
运行所有模块的测试

使用方式:
    uv run python scripts/tests/run_all_tests.py

    或运行单个模块:
    uv run python scripts/tests/test_amazingdata_basic_data.py
    uv run python scripts/tests/test_amazingdata_financial.py
    uv run python scripts/tests/test_amazingdata_history.py
    uv run python scripts/tests/test_amazingdata_shareholder.py
    uv run python scripts/tests/test_amazingdata_margin.py
    uv run python scripts/tests/test_amazingdata_option.py
    uv run python scripts/tests/test_amazingdata_etf.py
"""

import asyncio
import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, "d:/Stock/code/deepsearch")


async def run_all_tests():
    """运行所有AmazingData API测试"""
    print("=" * 80)
    print("AmazingData API 完整测试")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    all_results = {}
    total_start = datetime.now()

    # 1. 基础数据测试
    print("\n\n" + "#" * 80)
    print("# 1. 基础数据 API 测试")
    print("#" * 80)
    try:
        from test_amazingdata_basic_data import run_basic_data_tests

        results = await run_basic_data_tests()
        all_results["基础数据"] = results
    except Exception as e:
        print(f"[错误] 基础数据测试失败: {e}")
        all_results["基础数据"] = []

    # 2. 财务数据测试
    print("\n\n" + "#" * 80)
    print("# 2. 财务数据 API 测试")
    print("#" * 80)
    try:
        from test_amazingdata_financial import run_financial_tests

        results = await run_financial_tests()
        all_results["财务数据"] = results
    except Exception as e:
        print(f"[错误] 财务数据测试失败: {e}")
        all_results["财务数据"] = []

    # 3. 历史行情测试
    print("\n\n" + "#" * 80)
    print("# 3. 历史行情 API 测试")
    print("#" * 80)
    try:
        from test_amazingdata_history import run_history_tests

        results = await run_history_tests()
        all_results["历史行情"] = results
    except Exception as e:
        print(f"[错误] 历史行情测试失败: {e}")
        all_results["历史行情"] = []

    # 4. 股东数据测试
    print("\n\n" + "#" * 80)
    print("# 4. 股东数据 API 测试")
    print("#" * 80)
    try:
        from test_amazingdata_shareholder import run_shareholder_tests

        results = await run_shareholder_tests()
        all_results["股东数据"] = results
    except Exception as e:
        print(f"[错误] 股东数据测试失败: {e}")
        all_results["股东数据"] = []

    # 5. 融资融券测试
    print("\n\n" + "#" * 80)
    print("# 5. 融资融券 API 测试")
    print("#" * 80)
    try:
        from test_amazingdata_margin import run_margin_tests

        results = await run_margin_tests()
        all_results["融资融券"] = results
    except Exception as e:
        print(f"[错误] 融资融券测试失败: {e}")
        all_results["融资融券"] = []

    # 6. 期权数据测试
    print("\n\n" + "#" * 80)
    print("# 6. 期权数据 API 测试")
    print("#" * 80)
    try:
        from test_amazingdata_option import run_option_tests

        results = await run_option_tests()
        all_results["期权数据"] = results
    except Exception as e:
        print(f"[错误] 期权数据测试失败: {e}")
        all_results["期权数据"] = []

    # 7. ETF数据测试
    print("\n\n" + "#" * 80)
    print("# 7. ETF数据 API 测试")
    print("#" * 80)
    try:
        from test_amazingdata_etf import run_etf_tests

        results = await run_etf_tests()
        all_results["ETF数据"] = results
    except Exception as e:
        print(f"[错误] ETF数据测试失败: {e}")
        all_results["ETF数据"] = []

    # 生成总体报告
    total_elapsed = (datetime.now() - total_start).total_seconds()
    print_final_report(all_results, total_elapsed)


def print_final_report(all_results: dict, total_elapsed: float):
    """打印最终汇总报告"""
    print("\n\n")
    print("=" * 80)
    print("AmazingData API 测试汇总报告")
    print("=" * 80)

    total_tests = 0
    total_passed = 0
    total_failed = 0

    print("\n模块汇总:")
    print("-" * 80)
    print(f"{'模块名称':<20} {'总计':<10} {'通过':<10} {'失败':<10} {'通过率':<10}")
    print("-" * 80)

    for module_name, results in all_results.items():
        module_total = len(results)
        module_passed = sum(1 for r in results if r.success)
        module_failed = module_total - module_passed
        pass_rate = f"{module_passed/module_total*100:.1f}%" if module_total > 0 else "N/A"

        print(
            f"{module_name:<20} {module_total:<10} {module_passed:<10} {module_failed:<10} {pass_rate:<10}"
        )

        total_tests += module_total
        total_passed += module_passed
        total_failed += module_failed

    print("-" * 80)
    overall_rate = f"{total_passed/total_tests*100:.1f}%" if total_tests > 0 else "N/A"
    print(
        f"{'总计':<20} {total_tests:<10} {total_passed:<10} {total_failed:<10} {overall_rate:<10}"
    )
    print("-" * 80)

    print(f"\n总耗时: {total_elapsed:.2f} 秒")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 列出失败的测试
    failed_tests = []
    for module_name, results in all_results.items():
        for r in results:
            if not r.success:
                failed_tests.append((module_name, r.api_name, r.error))

    if failed_tests:
        print("\n\n失败的测试详情:")
        print("-" * 80)
        for module, api, error in failed_tests:
            print(f"  [{module}] {api}")
            print(f"    错误: {error}")
        print("-" * 80)
    else:
        print("\n所有测试均通过!")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
