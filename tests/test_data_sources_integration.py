#!/usr/bin/env python
"""
数据源集成测试套件
测试所有数据源的基本功能和性能
"""
import asyncio
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest
from loguru import logger

from deepsearch.infrastructure.providers.managers.data_source_manager import StockListFetchResult

# 配置日志
logger.add("test_data_sources.log", rotation="10 MB")


@dataclass
class TestResult:
    """测试结果"""

    source: str
    method: str
    success: bool
    error: Optional[str] = None
    response_time: float = 0.0
    data_count: int = 0
    data_sample: Optional[Any] = None


class DataSourceTestSuite:
    """数据源测试套件"""

    def __init__(self):
        self.results: List[TestResult] = []
        self.test_symbol = "000001"  # 测试股票代码（平安银行）
        self.manager = None

    async def setup(self):
        """初始化测试环境"""
        try:
            from deepsearch.infrastructure.providers.managers.data_source_manager import (
                DataSourceManager,
            )

            self.manager = DataSourceManager.get_instance()
            await self.manager.initialize()

            logger.info(f"初始化完成，可用数据源: {self.manager.get_available_sources()}")
            return True

        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    async def test_get_stock_list(self, source: str) -> TestResult:
        """测试获取股票列表"""
        start_time = time.time()

        try:
            self.manager.set_primary_source(source)

            stock_result = await self.manager.get_stock_list(limit=10)
            response_time = time.time() - start_time

            if isinstance(stock_result, StockListFetchResult):
                data_count = len(stock_result.records) or len(stock_result.legacy)
                sample = None
                if stock_result.legacy:
                    sample = stock_result.legacy[0]
                elif stock_result.records:
                    sample = dict(stock_result.records[0].as_mapping())
                if data_count:
                    return TestResult(
                        source=source,
                        method="get_stock_list",
                        success=True,
                        response_time=response_time,
                        data_count=data_count,
                        data_sample=sample,
                    )
                return TestResult(
                    source=source,
                    method="get_stock_list",
                    success=False,
                    error="返回为空",
                    response_time=response_time,
                )

            if stock_result:
                return TestResult(
                    source=source,
                    method="get_stock_list",
                    success=True,
                    response_time=response_time,
                    data_count=len(stock_result),
                    data_sample=stock_result[0] if stock_result else None,
                )

            return TestResult(
                source=source,
                method="get_stock_list",
                success=False,
                error="返回为空",
                response_time=response_time,
            )

        except Exception as e:
            return TestResult(
                source=source,
                method="get_stock_list",
                success=False,
                error=str(e),
                response_time=time.time() - start_time,
            )

    async def test_get_kline_data(self, source: str) -> TestResult:
        """测试获取K线数据"""
        start_time = time.time()

        try:
            # 切换数据源
            self.manager.set_primary_source(source)

            # 获取最近30天的日K线
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            klines = await self.manager.get_kline_data(
                symbol=self.test_symbol,
                period="1d",
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                limit=30,
            )

            response_time = time.time() - start_time

            if klines:
                return TestResult(
                    source=source,
                    method="get_kline_data",
                    success=True,
                    response_time=response_time,
                    data_count=len(klines),
                    data_sample=klines[-1] if klines else None,
                )
            else:
                return TestResult(
                    source=source,
                    method="get_kline_data",
                    success=False,
                    error="返回空数据",
                    response_time=response_time,
                )

        except Exception as e:
            return TestResult(
                source=source,
                method="get_kline_data",
                success=False,
                error=str(e),
                response_time=time.time() - start_time,
            )

    async def test_get_realtime_quotes(self, source: str) -> TestResult:
        """测试获取实时行情"""
        start_time = time.time()

        try:
            # 切换数据源
            self.manager.set_primary_source(source)

            # 获取实时行情
            quotes = await self.manager.get_realtime_quotes([self.test_symbol])

            response_time = time.time() - start_time

            if quotes:
                # quotes 可能是 dict 或 list，统一处理
                if isinstance(quotes, dict):
                    data_count = len(quotes)
                    data_sample = next(iter(quotes.values()), None)
                else:
                    data_count = len(quotes)
                    data_sample = quotes[0] if quotes else None

                return TestResult(
                    source=source,
                    method="get_realtime_quotes",
                    success=True,
                    response_time=response_time,
                    data_count=data_count,
                    data_sample=data_sample,
                )
            else:
                return TestResult(
                    source=source,
                    method="get_realtime_quotes",
                    success=False,
                    error="返回空数据",
                    response_time=response_time,
                )

        except Exception as e:
            return TestResult(
                source=source,
                method="get_realtime_quotes",
                success=False,
                error=str(e),
                response_time=time.time() - start_time,
            )

    async def test_get_stock_info(self, source: str) -> TestResult:
        """测试获取股票信息"""
        start_time = time.time()

        try:
            # 切换数据源
            self.manager.set_primary_source(source)

            # 获取股票信息
            info = await self.manager.get_stock_info(self.test_symbol)

            response_time = time.time() - start_time

            if info:
                return TestResult(
                    source=source,
                    method="get_stock_info",
                    success=True,
                    response_time=response_time,
                    data_count=1,
                    data_sample=info,
                )
            else:
                return TestResult(
                    source=source,
                    method="get_stock_info",
                    success=False,
                    error="返回空数据",
                    response_time=response_time,
                )

        except Exception as e:
            return TestResult(
                source=source,
                method="get_stock_info",
                success=False,
                error=str(e),
                response_time=time.time() - start_time,
            )

    async def test_all_sources(self):
        """测试所有数据源"""
        if not await self.setup():
            logger.error("初始化失败，无法进行测试")
            return

        # 获取所有可用数据源
        sources = self.manager.get_available_sources()

        if not sources:
            logger.error("没有可用的数据源")
            return

        logger.info(f"开始测试 {len(sources)} 个数据源: {sources}")

        # 测试方法列表
        test_methods = [
            self.test_get_stock_list,
            self.test_get_kline_data,
            self.test_get_realtime_quotes,
            self.test_get_stock_info,
        ]

        # 对每个数据源执行所有测试
        for source in sources:
            logger.info(f"\n{'=' * 50}")
            logger.info(f"测试数据源: {source}")
            logger.info(f"{'=' * 50}")

            for test_method in test_methods:
                result = await test_method(source)
                self.results.append(result)

                # 输出测试结果
                if result.success:
                    logger.success(
                        f"✅ {result.method}: 成功 "
                        f"(耗时: {result.response_time:.2f}s, "
                        f"数据量: {result.data_count})"
                    )
                    if result.data_sample:
                        logger.debug(
                            f"数据样例: {json.dumps(result.data_sample, ensure_ascii=False, indent=2)[:200]}..."
                        )
                else:
                    logger.error(
                        f"❌ {result.method}: 失败 "
                        f"(耗时: {result.response_time:.2f}s, "
                        f"错误: {result.error})"
                    )

                # 避免请求过快
                await asyncio.sleep(0.5)

    def generate_report(self) -> str:
        """生成测试报告"""
        if not self.results:
            return "没有测试结果"

        report = []
        report.append("\n" + "=" * 60)
        report.append("数据源测试报告")
        report.append(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 60)

        # 按数据源分组统计
        source_stats: Dict[str, Dict] = {}

        for result in self.results:
            if result.source not in source_stats:
                source_stats[result.source] = {
                    "total": 0,
                    "success": 0,
                    "failed": 0,
                    "total_time": 0,
                    "methods": {},
                }

            stats = source_stats[result.source]
            stats["total"] += 1
            stats["total_time"] += result.response_time

            if result.success:
                stats["success"] += 1
            else:
                stats["failed"] += 1

            stats["methods"][result.method] = {
                "success": result.success,
                "time": result.response_time,
                "error": result.error,
            }

        # 生成报告
        for source, stats in source_stats.items():
            success_rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
            avg_time = stats["total_time"] / stats["total"] if stats["total"] > 0 else 0

            report.append(f"\n📊 {source}")
            report.append(f"  成功率: {success_rate:.1f}% ({stats['success']}/{stats['total']})")
            report.append(f"  平均响应时间: {avg_time:.2f}秒")

            # 方法详情
            for method, method_stats in stats["methods"].items():
                status = "✅" if method_stats["success"] else "❌"
                report.append(f"    {status} {method}: {method_stats['time']:.2f}s")
                if method_stats["error"]:
                    report.append(f"       错误: {method_stats['error'][:50]}...")

        # 总体评分
        report.append("\n" + "=" * 60)
        report.append("总体评估:")

        total_tests = len(self.results)
        total_success = sum(1 for r in self.results if r.success)
        overall_rate = total_success / total_tests * 100 if total_tests > 0 else 0

        if overall_rate >= 90:
            grade = "A - 优秀"
        elif overall_rate >= 70:
            grade = "B - 良好"
        elif overall_rate >= 50:
            grade = "C - 及格"
        else:
            grade = "D - 需要改进"

        report.append(f"  总测试数: {total_tests}")
        report.append(f"  成功数: {total_success}")
        report.append(f"  总成功率: {overall_rate:.1f}%")
        report.append(f"  评级: {grade}")
        report.append("=" * 60)

        return "\n".join(report)

    async def run_tests(self):
        """运行所有测试"""
        await self.test_all_sources()
        report = self.generate_report()

        # 输出报告
        logger.info(report)

        # 保存报告到文件
        with open("data_source_test_report.txt", "w", encoding="utf-8") as f:
            f.write(report)

        logger.info("\n报告已保存到: data_source_test_report.txt")


# Pytest测试用例
@pytest.mark.asyncio
async def test_data_sources():
    """Pytest测试入口"""
    suite = DataSourceTestSuite()
    await suite.run_tests()

    # 验证至少有一个数据源工作
    assert len(suite.results) > 0, "没有测试结果"

    success_count = sum(1 for r in suite.results if r.success)
    assert success_count > 0, "所有测试都失败了"


def main():
    """主函数"""
    suite = DataSourceTestSuite()
    asyncio.run(suite.run_tests())


if __name__ == "__main__":
    main()
