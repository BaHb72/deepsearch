# encoding:utf-8
"""
AmazingData 基础数据 API 测试脚本
测试 basic_data 模块的所有接口

使用真实数据进行测试，每个API只测试少量标的以避免数据源限额
"""

import asyncio
import sys
from datetime import datetime
from typing import Any, Callable

# 添加项目路径
sys.path.insert(0, "d:/Stock/code/deepsearch")

from deepsearch.webui.api.endpoints.amazingdata.base import get_amazingdata_provider


class TestResult:
    """测试结果类"""

    def __init__(self, api_name: str, success: bool, data_count: int, error: str = "", elapsed: float = 0):
        self.api_name = api_name
        self.success = success
        self.data_count = data_count
        self.error = error
        self.elapsed = elapsed


async def test_api(api_name: str, func: Callable, *args, **kwargs) -> TestResult:
    """通用API测试函数"""
    print(f"\n{'='*60}")
    print(f"测试: {api_name}")
    print(f"{'='*60}")

    start = datetime.now()
    try:
        result = await func(*args, **kwargs)
        elapsed = (datetime.now() - start).total_seconds()

        # 解析结果
        if isinstance(result, dict):
            success = result.get("success", False)
            data = result.get("data")
            error = result.get("error", "")

            if data is None:
                data_count = 0
            elif isinstance(data, list):
                data_count = len(data)
            elif isinstance(data, dict):
                data_count = len(data)
            else:
                data_count = 1

            print(f"状态: {'成功' if success else '失败'}")
            print(f"数据条数: {data_count}")
            print(f"耗时: {elapsed:.2f}秒")

            if error:
                print(f"错误信息: {error}")

            if data and data_count > 0:
                # 显示部分数据
                if isinstance(data, list):
                    print(f"数据样例: {data[:2]}")
                elif isinstance(data, dict) and len(data) > 0:
                    keys = list(data.keys())[:3]
                    print(f"数据键: {keys}")

            return TestResult(api_name, success, data_count, error, elapsed)
        else:
            print(f"返回值类型: {type(result)}")
            print(f"返回值: {result}")
            return TestResult(api_name, result is not None, 1 if result else 0, "", elapsed)

    except Exception as e:
        elapsed = (datetime.now() - start).total_seconds()
        print(f"状态: 异常")
        print(f"错误: {str(e)}")
        return TestResult(api_name, False, 0, str(e), elapsed)


async def run_basic_data_tests():
    """运行基础数据API测试"""
    print("\n" + "=" * 70)
    print("AmazingData 基础数据 API 测试")
    print("=" * 70)

    results = []

    try:
        provider = await get_amazingdata_provider()
    except Exception as e:
        print(f"[错误] 无法获取AmazingData提供者: {e}")
        return results

    # 测试用股票代码
    test_codes = ["SH.600000", "SZ.000001"]
    test_code_single = "SH.600000"

    # ==================== 1. get_code_info ====================
    async def test_get_code_info():
        data = await provider.get_code_info(security_type="EXTRA_STOCK_A")
        return {"success": data is not None, "data": data.to_dict("records") if hasattr(data, "to_dict") else data}

    results.append(await test_api("get_code_info (每日最新证券信息)", test_get_code_info))

    # ==================== 2. get_code_list ====================
    async def test_get_code_list():
        data = await provider.get_code_list(security_type="EXTRA_STOCK_A")
        return {"success": data is not None, "data": data if isinstance(data, list) else [data]}

    results.append(await test_api("get_code_list (每日最新代码列表)", test_get_code_list))

    # ==================== 3. get_future_code_list ====================
    async def test_get_future_code_list():
        data = await provider.get_future_code_list(security_type="EXTRA__FUTURE")
        return {"success": data is not None, "data": data if isinstance(data, list) else [data]}

    results.append(await test_api("get_future_code_list (期货代码列表)", test_get_future_code_list))

    # ==================== 4. get_calendar ====================
    async def test_get_calendar():
        data = await provider.get_calendar(market="SH")
        return {"success": data is not None, "data": data if isinstance(data, list) else [data]}

    results.append(await test_api("get_calendar (交易日历)", test_get_calendar))

    # ==================== 5. get_stock_basic ====================
    async def test_get_stock_basic():
        data = await provider.get_stock_basic(test_codes)
        return {"success": data is not None, "data": data.to_dict("records") if hasattr(data, "to_dict") else data}

    results.append(await test_api("get_stock_basic (证券基础信息)", test_get_stock_basic))

    # ==================== 6. get_backward_factor ====================
    async def test_get_backward_factor():
        data = await provider.get_backward_factor(
            code_list=test_codes, begin_date=20241201, end_date=20241210
        )
        return {"success": data is not None, "data": data.to_dict("records") if hasattr(data, "to_dict") else data}

    results.append(await test_api("get_backward_factor (后复权因子)", test_get_backward_factor))

    # ==================== 7. get_adj_factor ====================
    async def test_get_adj_factor():
        data = await provider.get_adj_factor(
            code_list=test_codes, begin_date=20241201, end_date=20241210
        )
        return {"success": data is not None, "data": data.to_dict("records") if hasattr(data, "to_dict") else data}

    results.append(await test_api("get_adj_factor (前复权因子)", test_get_adj_factor))

    # ==================== 8. get_history_stock_status ====================
    async def test_get_history_stock_status():
        data = await provider.get_history_stock_status(
            code_list=test_codes, begin_date=20241201, end_date=20241210
        )
        return {"success": data is not None, "data": data.to_dict("records") if hasattr(data, "to_dict") else data}

    results.append(await test_api("get_history_stock_status (历史证券状态)", test_get_history_stock_status))

    # ==================== 9. get_hist_code_list ====================
    async def test_get_hist_code_list():
        data = await provider.get_hist_code_list(
            security_type="EXTRA_STOCK_A_SH_SZ", start_date=20241201, end_date=20241210
        )
        return {"success": data is not None, "data": data if isinstance(data, list) else [data]}

    results.append(await test_api("get_hist_code_list (历史代码列表)", test_get_hist_code_list))

    # ==================== 10. get_bj_code_mapping ====================
    async def test_get_bj_code_mapping():
        data = await provider.get_bj_code_mapping()
        return {"success": data is not None, "data": data.to_dict("records") if hasattr(data, "to_dict") else data}

    results.append(await test_api("get_bj_code_mapping (北交所代码映射)", test_get_bj_code_mapping))

    # 生成测试报告
    print_report(results)

    return results


def print_report(results: list[TestResult]):
    """打印测试报告"""
    print("\n" + "=" * 70)
    print("测试报告")
    print("=" * 70)

    total = len(results)
    passed = sum(1 for r in results if r.success)
    failed = total - passed

    print(f"\n总计: {total} | 通过: {passed} | 失败: {failed}")
    print(f"通过率: {passed/total*100:.1f}%\n")

    print("-" * 70)
    print(f"{'API名称':<40} {'状态':<8} {'数据条数':<10} {'耗时(秒)':<10}")
    print("-" * 70)

    for r in results:
        status = "通过" if r.success else "失败"
        print(f"{r.api_name[:38]:<40} {status:<8} {r.data_count:<10} {r.elapsed:.2f}")

    print("-" * 70)

    if failed > 0:
        print("\n失败的测试:")
        for r in results:
            if not r.success:
                print(f"  - {r.api_name}: {r.error}")


if __name__ == "__main__":
    asyncio.run(run_basic_data_tests())
