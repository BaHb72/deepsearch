# encoding:utf-8
"""
AmazingData 历史行情 API 测试脚本
测试 history 模块的所有接口

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
        if result is None:
            print(f"状态: 返回None")
            return TestResult(api_name, False, 0, "返回None", elapsed)

        if hasattr(result, "to_dict"):
            # DataFrame
            data_count = len(result)
            print(f"状态: 成功")
            print(f"数据条数: {data_count}")
            print(f"耗时: {elapsed:.2f}秒")
            return TestResult(api_name, True, data_count, "", elapsed)

        elif isinstance(result, dict):
            # 可能是 {code: DataFrame} 的格式
            if all(hasattr(v, "to_dict") for v in result.values() if v is not None):
                total_rows = sum(len(v) for v in result.values() if v is not None)
                print(f"状态: 成功")
                print(f"股票数: {len(result)}")
                print(f"总数据行数: {total_rows}")
                print(f"耗时: {elapsed:.2f}秒")
                return TestResult(api_name, True, total_rows, "", elapsed)

            success = result.get("success", True)
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

            return TestResult(api_name, success, data_count, error, elapsed)
        else:
            print(f"返回值类型: {type(result)}")
            return TestResult(api_name, result is not None, 1, "", elapsed)

    except Exception as e:
        elapsed = (datetime.now() - start).total_seconds()
        print(f"状态: 异常")
        print(f"错误: {str(e)}")
        return TestResult(api_name, False, 0, str(e), elapsed)


async def run_history_tests():
    """运行历史行情API测试"""
    print("\n" + "=" * 70)
    print("AmazingData 历史行情 API 测试")
    print("=" * 70)

    results = []

    try:
        provider = await get_amazingdata_provider()
    except Exception as e:
        print(f"[错误] 无法获取AmazingData提供者: {e}")
        return results

    # 测试用股票代码 (只用1-2个以减少负载)
    test_codes = ["SH.600000"]

    # 日期范围 (只取最近10天)
    begin_date = 20241201
    end_date = 20241210

    # ==================== 1. query_snapshot ====================
    async def test_query_snapshot():
        data = await provider.query_snapshot(
            code_list=test_codes,
            begin_date=begin_date,
            end_date=end_date,
        )
        return data

    results.append(await test_api("query_snapshot (历史快照)", test_query_snapshot))

    # ==================== 2. query_kline (日线) ====================
    async def test_query_kline_daily():
        data = await provider.query_kline(
            code_list=test_codes,
            begin_date=begin_date,
            end_date=end_date,
            period="daily",
        )
        return data

    results.append(await test_api("query_kline 日线 (历史K线)", test_query_kline_daily))

    # ==================== 3. query_kline (5分钟线) ====================
    async def test_query_kline_5min():
        # 5分钟线数据量大，只取1天
        data = await provider.query_kline(
            code_list=test_codes,
            begin_date=20241210,
            end_date=20241210,
            period="5min",
        )
        return data

    results.append(await test_api("query_kline 5分钟 (历史K线)", test_query_kline_5min))

    # ==================== 4. query_kline (周线) ====================
    async def test_query_kline_weekly():
        data = await provider.query_kline(
            code_list=test_codes,
            begin_date=20241101,
            end_date=20241210,
            period="weekly",
        )
        return data

    results.append(await test_api("query_kline 周线 (历史K线)", test_query_kline_weekly))

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
    asyncio.run(run_history_tests())
