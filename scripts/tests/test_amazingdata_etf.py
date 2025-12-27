# encoding:utf-8
"""
AmazingData ETF数据 API 测试脚本
测试 etf 模块的所有接口

使用真实数据进行测试，每个API只测试少量标的以避免数据源限额
"""

import asyncio
import sys
from datetime import datetime
from typing import Callable

# 添加项目路径
sys.path.insert(0, "d:/Stock/code/deepsearch")

from deepsearch.webui.api.endpoints.amazingdata.base import get_amazingdata_provider


class TestResult:
    """测试结果类"""

    def __init__(
        self, api_name: str, success: bool, data_count: int, error: str = "", elapsed: float = 0
    ):
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

        if result is None:
            print("状态: 返回None")
            return TestResult(api_name, False, 0, "返回None", elapsed)

        if hasattr(result, "to_dict"):
            data_count = len(result)
            print("状态: 成功")
            print(f"数据条数: {data_count}")
            print(f"耗时: {elapsed:.2f}秒")
            return TestResult(api_name, True, data_count, "", elapsed)

        elif isinstance(result, tuple) and len(result) == 2:
            # ETF PCF 返回 (etf_pcf_info, etf_pcf_constituent)
            etf_pcf_info, etf_pcf_constituent = result
            info_count = len(etf_pcf_info) if hasattr(etf_pcf_info, "__len__") else 0
            constituent_count = (
                len(etf_pcf_constituent) if isinstance(etf_pcf_constituent, dict) else 0
            )
            print("状态: 成功")
            print(f"ETF数量: {info_count}")
            print(f"成分股组数: {constituent_count}")
            print(f"耗时: {elapsed:.2f}秒")
            return TestResult(api_name, True, info_count, "", elapsed)

        elif isinstance(result, dict):
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
        print("状态: 异常")
        print(f"错误: {str(e)}")
        return TestResult(api_name, False, 0, str(e), elapsed)


async def run_etf_tests():
    """运行ETF数据API测试"""
    print("\n" + "=" * 70)
    print("AmazingData ETF数据 API 测试")
    print("=" * 70)

    results = []

    try:
        provider = await get_amazingdata_provider()
    except Exception as e:
        print(f"[错误] 无法获取AmazingData提供者: {e}")
        return results

    # ETF代码 (沪深300ETF, 创业板ETF)
    etf_codes = ["510300.SH", "159919.SZ"]

    # ==================== 1. get_etf_pcf ====================
    async def test_get_etf_pcf():
        data = await provider.get_etf_pcf(code_list=etf_codes)
        return data

    results.append(await test_api("get_etf_pcf (ETF每日申赎数据)", test_get_etf_pcf))

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
    asyncio.run(run_etf_tests())
