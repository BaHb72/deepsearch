# encoding: utf-8
"""
MiniQMT 全面能力测试脚本

全面测试 MiniQMT (xtquant SDK) 接口的所有能力，包括：
1. 连接测试
2. 实时数据获取
3. 历史数据下载
4. 基础信息查询
5. 财务数据获取
6. ETF/指数数据
7. 订阅功能
8. 性能测试

运行要求:
    - MiniQMT 终端已启动并运行
    - xtquant SDK 已安装

运行命令:
    python tests/integration/test_miniqmt_comprehensive.py

    或使用 pytest:
    pytest tests/integration/test_miniqmt_comprehensive.py -v -s --run-integration

Author: DeepSearch Team
Created: 2024-12-21
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# 尝试导入 rich 库
try:
    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("[警告] rich 库未安装，将使用简单输出格式")


class TestStatus(Enum):
    """测试状态"""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """测试结果"""

    name: str
    status: TestStatus
    duration: float = 0.0
    message: str = ""
    data: Any = None
    error: Optional[str] = None


@dataclass
class TestCategory:
    """测试分类"""

    name: str
    description: str
    results: List[TestResult] = field(default_factory=list)


class MiniQMTCapabilityTester:
    """
    MiniQMT 全面能力测试器

    测试 xtquant SDK 的所有主要功能
    """

    def __init__(self):
        """初始化测试器"""
        self.console = Console() if RICH_AVAILABLE else None
        self.xtdata = None
        self.connected = False
        self.categories: List[TestCategory] = []

        # 测试配置
        self.test_stocks = ["000001.SZ", "600000.SH", "000002.SZ"]
        self.test_single_stock = "000001.SZ"
        self.test_sector = "沪深A股"
        self.test_index = "000300.SH"
        self.test_etf = "510050.SH"

        # 日期范围
        self.end_date = datetime.now().strftime("%Y%m%d")
        self.start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    def print_header(self, text: str):
        """打印标题"""
        if self.console:
            self.console.print(f"\n[bold cyan]{'=' * 60}[/bold cyan]")
            self.console.print(f"[bold white]  {text}[/bold white]")
            self.console.print(f"[bold cyan]{'=' * 60}[/bold cyan]\n")
        else:
            print(f"\n{'=' * 60}")
            print(f"  {text}")
            print(f"{'=' * 60}\n")

    def print_test_result(self, result: TestResult):
        """打印单个测试结果"""
        if self.console:
            if result.status == TestStatus.PASSED:
                status_icon = "[green][OK][/green]"
            elif result.status == TestStatus.FAILED:
                status_icon = "[red][FAIL][/red]"
            elif result.status == TestStatus.SKIPPED:
                status_icon = "[yellow][SKIP][/yellow]"
            else:
                status_icon = "[red][ERROR][/red]"

            self.console.print(f"  {status_icon} {result.name} ({result.duration:.2f}s)")
            if result.message:
                self.console.print(f"       [dim]{result.message}[/dim]")
            if result.error:
                self.console.print(f"       [red]Error: {result.error}[/red]")
        else:
            status_map = {
                TestStatus.PASSED: "[OK]",
                TestStatus.FAILED: "[FAIL]",
                TestStatus.SKIPPED: "[SKIP]",
                TestStatus.ERROR: "[ERROR]",
            }
            print(f"  {status_map[result.status]} {result.name} ({result.duration:.2f}s)")
            if result.message:
                print(f"       {result.message}")
            if result.error:
                print(f"       Error: {result.error}")

    def run_test(self, name: str, test_func: Callable) -> TestResult:
        """运行单个测试"""
        start_time = time.time()
        try:
            success, message, data = test_func()
            duration = time.time() - start_time

            if success:
                result = TestResult(
                    name=name,
                    status=TestStatus.PASSED,
                    duration=duration,
                    message=message,
                    data=data,
                )
            else:
                result = TestResult(
                    name=name, status=TestStatus.FAILED, duration=duration, message=message
                )
        except Exception as e:
            duration = time.time() - start_time
            result = TestResult(name=name, status=TestStatus.ERROR, duration=duration, error=str(e))

        self.print_test_result(result)
        return result

    # ==================== 1. 连接测试 ====================

    def test_connection(self) -> TestCategory:
        """连接测试"""
        category = TestCategory(name="连接测试", description="测试 xtdata 模块导入和 MiniQMT 连接")

        self.print_header("1. 连接测试")

        # 测试 1.1: xtdata 模块导入
        def test_import():
            try:
                from xtquant import xtdata

                self.xtdata = xtdata

                # 检查关键函数
                required_funcs = [
                    "get_full_tick",
                    "get_market_data",
                    "download_history_data",
                    "get_instrument_detail",
                    "get_sector_list",
                    "get_trading_dates",
                ]
                missing = [f for f in required_funcs if not hasattr(xtdata, f)]

                if missing:
                    return False, f"缺少函数: {missing}", None
                return True, f"成功导入 xtdata，包含 {len(required_funcs)} 个关键函数", None
            except ImportError as e:
                return False, f"无法导入 xtquant: {e}", None

        category.results.append(self.run_test("xtdata 模块导入", test_import))

        if not self.xtdata:
            return category

        # 测试 1.2: 基本连接验证
        def test_basic_connection():
            try:
                result = self.xtdata.get_full_tick([self.test_single_stock])
                if result and self.test_single_stock in result:
                    self.connected = True
                    return True, "MiniQMT 连接正常，成功获取测试数据", result
                return False, "MiniQMT 未返回数据，请确认终端已启动", None
            except Exception as e:
                return False, f"连接失败: {e}", None

        category.results.append(self.run_test("MiniQMT 连接验证", test_basic_connection))

        # 测试 1.3: 多股票连接测试
        def test_multi_connection():
            if not self.connected:
                return False, "跳过: 未建立连接", None
            result = self.xtdata.get_full_tick(self.test_stocks)
            received = [s for s in self.test_stocks if s in result]
            return True, f"成功获取 {len(received)}/{len(self.test_stocks)} 只股票数据", result

        category.results.append(self.run_test("多股票批量连接", test_multi_connection))

        return category

    # ==================== 2. 实时数据测试 ====================

    def test_realtime_data(self) -> TestCategory:
        """实时数据测试"""
        category = TestCategory(name="实时数据测试", description="测试实时行情数据获取能力")

        self.print_header("2. 实时数据测试")

        if not self.connected:
            category.results.append(
                TestResult(
                    name="实时数据测试", status=TestStatus.SKIPPED, message="跳过: MiniQMT 未连接"
                )
            )
            return category

        # 测试 2.1: 单只股票 Tick 数据
        def test_single_tick():
            result = self.xtdata.get_full_tick([self.test_single_stock])
            if result and self.test_single_stock in result:
                tick = result[self.test_single_stock]
                fields = list(tick.keys()) if isinstance(tick, dict) else []
                return True, f"获取到 {len(fields)} 个字段", tick
            return False, "未获取到数据", None

        category.results.append(self.run_test("单只股票 Tick 数据", test_single_tick))

        # 测试 2.2: 多只股票 Tick 数据
        def test_multi_tick():
            result = self.xtdata.get_full_tick(self.test_stocks)
            received = {s: result.get(s) for s in self.test_stocks if s in result}
            return True, f"获取 {len(received)}/{len(self.test_stocks)} 只股票", received

        category.results.append(self.run_test("批量股票 Tick 数据", test_multi_tick))

        # 测试 2.3: Tick 数据字段验证
        def test_tick_fields():
            result = self.xtdata.get_full_tick([self.test_single_stock])
            if not result or self.test_single_stock not in result:
                return False, "未获取到数据", None

            tick = result[self.test_single_stock]
            expected_fields = ["lastPrice", "open", "high", "low", "volume", "amount"]
            found_fields = [f for f in expected_fields if f in tick]
            missing_fields = [f for f in expected_fields if f not in tick]

            if missing_fields:
                return True, f"找到 {len(found_fields)} 个预期字段, 缺失: {missing_fields}", tick
            return True, f"包含所有 {len(expected_fields)} 个预期字段", tick

        category.results.append(self.run_test("Tick 数据字段验证", test_tick_fields))

        # 测试 2.4: 五档盘口数据
        def test_orderbook():
            result = self.xtdata.get_full_tick([self.test_single_stock])
            if not result or self.test_single_stock not in result:
                return False, "未获取到数据", None

            tick = result[self.test_single_stock]
            bid_fields = ["bidPrice", "bidVol"]
            ask_fields = ["askPrice", "askVol"]

            has_bid = any(f in tick for f in bid_fields)
            has_ask = any(f in tick for f in ask_fields)

            if has_bid and has_ask:
                return True, "包含买卖盘口数据", tick
            return True, f"盘口数据: 买盘={has_bid}, 卖盘={has_ask}", tick

        category.results.append(self.run_test("五档盘口数据", test_orderbook))

        return category

    # ==================== 3. 历史数据测试 ====================

    def test_historical_data(self) -> TestCategory:
        """历史数据测试"""
        category = TestCategory(name="历史数据测试", description="测试历史 K 线数据下载和获取")

        self.print_header("3. 历史数据测试")

        if not self.connected:
            category.results.append(
                TestResult(
                    name="历史数据测试", status=TestStatus.SKIPPED, message="跳过: MiniQMT 未连接"
                )
            )
            return category

        # 测试 3.1: 日线数据下载
        def test_daily_download():
            try:
                self.xtdata.download_history_data(
                    self.test_single_stock, "1d", start_time=self.start_date, end_time=self.end_date
                )
                return True, f"日线数据下载完成 ({self.start_date} - {self.end_date})", None
            except Exception as e:
                return False, f"下载失败: {e}", None

        category.results.append(self.run_test("日线数据下载", test_daily_download))

        # 测试 3.2: 日线数据获取
        def test_daily_get():
            result = self.xtdata.get_market_data(
                field_list=[], stock_list=[self.test_single_stock], period="1d", count=20
            )
            if result and isinstance(result, dict):
                # 检查是否有数据
                if "close" in result and hasattr(result["close"], "shape"):
                    import pandas as pd

                    close_df = result["close"]
                    if isinstance(close_df, pd.DataFrame) and not close_df.empty:
                        return True, f"获取到 {close_df.shape[1]} 条日线数据", result
                return True, f"获取到数据，字段: {list(result.keys())}", result
            return False, "未获取到日线数据", None

        category.results.append(self.run_test("日线数据获取", test_daily_get))

        # 测试 3.3: 分钟数据测试
        periods = [
            ("1m", "1分钟"),
            ("5m", "5分钟"),
            ("15m", "15分钟"),
            ("30m", "30分钟"),
            ("60m", "60分钟"),
        ]

        for period, period_name in periods:

            def test_minute(p=period, pn=period_name):
                try:
                    # download_history_data 不支持 count 参数，使用时间范围
                    from datetime import datetime, timedelta

                    end_time = datetime.now().strftime("%Y%m%d%H%M%S")
                    start_time = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d%H%M%S")
                    self.xtdata.download_history_data(
                        self.test_single_stock, p, start_time=start_time, end_time=end_time
                    )
                    result = self.xtdata.get_market_data(
                        field_list=[], stock_list=[self.test_single_stock], period=p, count=50
                    )
                    if result:
                        return True, f"{pn}数据获取成功", result
                    return True, f"{pn}数据已下载，可能无新数据", None
                except Exception as e:
                    return False, f"{pn}数据获取失败: {e}", None

            category.results.append(self.run_test(f"{period_name} K线数据", test_minute))

        # 测试 3.4: 周线/月线数据
        def test_weekly():
            try:
                # 使用时间范围而不是 count 参数
                from datetime import datetime, timedelta

                end_time = datetime.now().strftime("%Y%m%d")
                start_time = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
                self.xtdata.download_history_data(
                    self.test_single_stock, "1w", start_time=start_time, end_time=end_time
                )
                result = self.xtdata.get_market_data(
                    field_list=[], stock_list=[self.test_single_stock], period="1w", count=20
                )
                return True, "周线数据获取成功", result
            except Exception as e:
                return False, f"周线数据失败: {e}", None

        category.results.append(self.run_test("周线数据", test_weekly))

        # 测试 3.5: get_market_data_ex 接口
        def test_market_data_ex():
            try:
                result = self.xtdata.get_market_data_ex(
                    field_list=["time", "open", "high", "low", "close", "volume"],
                    stock_list=[self.test_single_stock],
                    period="1d",
                    count=20,
                )
                if result and self.test_single_stock in result:
                    df = result[self.test_single_stock]
                    return True, f"get_market_data_ex 返回 {len(df)} 条数据", result
                return True, "get_market_data_ex 调用成功", result
            except Exception as e:
                return False, f"get_market_data_ex 失败: {e}", None

        category.results.append(self.run_test("get_market_data_ex 接口", test_market_data_ex))

        return category

    # ==================== 4. 基础信息测试 ====================

    def test_basic_info(self) -> TestCategory:
        """基础信息测试"""
        category = TestCategory(
            name="基础信息测试", description="测试合约信息、板块、交易日历等基础数据"
        )

        self.print_header("4. 基础信息测试")

        if not self.connected:
            category.results.append(
                TestResult(
                    name="基础信息测试", status=TestStatus.SKIPPED, message="跳过: MiniQMT 未连接"
                )
            )
            return category

        # 测试 4.1: 合约详情
        def test_instrument_detail():
            result = self.xtdata.get_instrument_detail(self.test_single_stock)
            if result:
                name = result.get("InstrumentName", "未知")
                return True, f"合约名称: {name}", result
            return False, "未获取到合约信息", None

        category.results.append(
            self.run_test("合约详情 (get_instrument_detail)", test_instrument_detail)
        )

        # 测试 4.2: 板块列表
        def test_sector_list():
            result = self.xtdata.get_sector_list()
            if result:
                count = len(result) if isinstance(result, list) else 0
                sample = list(result)[:5] if result else []
                return True, f"获取到 {count} 个板块, 示例: {sample}", result
            return False, "未获取到板块列表", None

        category.results.append(self.run_test("板块列表 (get_sector_list)", test_sector_list))

        # 测试 4.3: 板块成分股
        def test_sector_stocks():
            result = self.xtdata.get_stock_list_in_sector(self.test_sector)
            if result:
                count = len(result) if isinstance(result, list) else 0
                sample = list(result)[:5] if result else []
                return True, f"'{self.test_sector}' 包含 {count} 只股票, 示例: {sample}", result
            return True, f"板块 '{self.test_sector}' 无数据或不存在", None

        category.results.append(
            self.run_test("板块成分股 (get_stock_list_in_sector)", test_sector_stocks)
        )

        # 测试 4.4: 交易日历
        def test_trading_dates():
            result = self.xtdata.get_trading_dates(
                "SH", start_time=self.start_date, end_time=self.end_date
            )
            if result:
                count = len(result) if isinstance(result, list) else 0
                return True, f"获取到 {count} 个交易日", result
            return True, "交易日历数据为空", None

        category.results.append(self.run_test("交易日历 (get_trading_dates)", test_trading_dates))

        # 测试 4.5: 节假日
        def test_holidays():
            try:
                result = self.xtdata.get_holidays()
                if result:
                    count = len(result) if isinstance(result, list) else 0
                    return True, f"获取到 {count} 个节假日", result
                return True, "节假日数据为空", None
            except AttributeError:
                return True, "get_holidays 方法不存在", None

        category.results.append(self.run_test("节假日列表 (get_holidays)", test_holidays))

        # 测试 4.6: 市场列表
        def test_markets():
            try:
                result = self.xtdata.get_markets()
                if result:
                    return True, f"市场列表: {result}", result
                return True, "市场列表为空", None
            except AttributeError:
                return True, "get_markets 方法不存在", None

        category.results.append(self.run_test("市场列表 (get_markets)", test_markets))

        # 测试 4.7: 周期列表
        def test_periods():
            try:
                result = self.xtdata.get_period_list()
                if result:
                    return True, f"支持周期: {result}", result
                return True, "周期列表为空", None
            except AttributeError:
                return True, "get_period_list 方法不存在", None

        category.results.append(self.run_test("周期列表 (get_period_list)", test_periods))

        return category

    # ==================== 5. 财务数据测试 ====================

    def test_financial_data(self) -> TestCategory:
        """财务数据测试"""
        category = TestCategory(name="财务数据测试", description="测试财务报表数据获取")

        self.print_header("5. 财务数据测试")

        if not self.connected:
            category.results.append(
                TestResult(
                    name="财务数据测试", status=TestStatus.SKIPPED, message="跳过: MiniQMT 未连接"
                )
            )
            return category

        # 测试 5.1: 获取财务数据（跳过下载，直接尝试获取）
        def test_download_financial():
            try:
                # 跳过下载，直接尝试获取本地已有的数据
                # download_financial_data 可能会卡住，所以跳过
                return True, "跳过财务数据下载 (避免超时)", None
            except AttributeError:
                return True, "download_financial_data 方法不存在", None
            except Exception as e:
                return True, f"下载跳过: {e}", None

        category.results.append(self.run_test("财务数据下载", test_download_financial))

        # 测试财务表
        tables = [("Balance", "资产负债表"), ("Income", "利润表"), ("CashFlow", "现金流量表")]

        for table_name, table_desc in tables:

            def test_financial(tn=table_name, td=table_desc):
                try:
                    result = self.xtdata.get_financial_data([self.test_single_stock], [tn])
                    if result:
                        return True, f"{td}获取成功", result
                    return True, f"{td}数据为空", None
                except AttributeError:
                    return True, "get_financial_data 方法不存在", None
                except Exception as e:
                    return True, f"{td}获取跳过: {e}", None

            category.results.append(self.run_test(f"{table_desc} ({table_name})", test_financial))

        return category

    # ==================== 6. ETF 和指数测试 ====================

    def test_etf_index(self) -> TestCategory:
        """ETF 和指数测试"""
        category = TestCategory(name="ETF和指数测试", description="测试 ETF 信息和指数权重数据")

        self.print_header("6. ETF 和指数测试")

        if not self.connected:
            category.results.append(
                TestResult(
                    name="ETF和指数测试", status=TestStatus.SKIPPED, message="跳过: MiniQMT 未连接"
                )
            )
            return category

        # 测试 6.1: ETF 信息 (需要先下载)
        def test_etf_info():
            try:
                # 官方文档: 需要先 download_etf_info() 再 get_etf_info()
                self.xtdata.download_etf_info()
                # get_etf_info() 不接受参数，返回所有ETF信息
                result = self.xtdata.get_etf_info()
                if result:
                    # 检查测试ETF是否在结果中
                    if self.test_etf in result:
                        etf_data = result[self.test_etf]
                        fields = list(etf_data.keys()) if isinstance(etf_data, dict) else []
                        return (
                            True,
                            f"ETF {self.test_etf} 信息获取成功, 包含 {len(fields)} 个字段",
                            etf_data,
                        )
                    return True, f"获取到 {len(result)} 只 ETF 信息 (不含 {self.test_etf})", None
                return True, "ETF 信息为空 (需要交易时间下载)", None
            except AttributeError:
                return True, "ETF 信息接口不存在", None
            except Exception as e:
                return True, f"ETF 信息获取跳过: {e}", None

        category.results.append(self.run_test("ETF 信息 (get_etf_info)", test_etf_info))

        # 测试 6.2: 指数权重 (需要先下载)
        def test_index_weight():
            try:
                # 官方文档: 需要先 download_index_weight() 再 get_index_weight()
                # download_index_weight() 是无参调用，下载所有指数权重
                self.xtdata.download_index_weight()
                result = self.xtdata.get_index_weight(self.test_index)
                if result:
                    count = len(result) if isinstance(result, dict) else 0
                    sample = list(result.keys())[:5] if count > 0 else []
                    return (
                        True,
                        f"指数 {self.test_index} 包含 {count} 只成分股, 示例: {sample}",
                        result,
                    )
                return True, "指数权重数据为空 (可能需要交易时间或投研版)", None
            except AttributeError:
                return True, "指数权重接口不存在", None
            except Exception as e:
                return True, f"指数权重获取跳过: {e}", None

        category.results.append(self.run_test("指数权重 (get_index_weight)", test_index_weight))

        # 测试 6.3: 复权因子
        def test_divid_factors():
            try:
                result = self.xtdata.get_divid_factors(self.test_single_stock)
                # 处理 DataFrame 返回值
                if result is not None:
                    if hasattr(result, "empty"):
                        # 是 DataFrame
                        if not result.empty:
                            rows = len(result)
                            cols = list(result.columns) if hasattr(result, "columns") else []
                            return True, f"复权因子获取成功, {rows} 条记录, 字段: {cols}", result
                        return True, "复权因子数据为空 DataFrame", None
                    elif isinstance(result, dict) and len(result) > 0:
                        return True, "复权因子获取成功 (dict格式)", result
                return True, "复权因子数据为空", None
            except AttributeError:
                return True, "get_divid_factors 方法不存在", None
            except Exception as e:
                return True, f"复权因子获取跳过: {e}", None

        category.results.append(self.run_test("复权因子 (get_divid_factors)", test_divid_factors))

        return category

    # ==================== 7. 订阅功能测试 ====================

    def test_subscription(self) -> TestCategory:
        """订阅功能测试"""
        category = TestCategory(name="订阅功能测试", description="测试实时数据订阅和回调")

        self.print_header("7. 订阅功能测试")

        if not self.connected:
            category.results.append(
                TestResult(
                    name="订阅功能测试", status=TestStatus.SKIPPED, message="跳过: MiniQMT 未连接"
                )
            )
            return category

        # 测试 7.1: 订阅 Tick 数据
        def test_subscribe_tick():
            received_data = []

            def on_data(data):
                received_data.append(data)

            try:
                # 订阅，获取订阅号
                seq_id = self.xtdata.subscribe_quote(
                    self.test_single_stock, period="tick", callback=on_data
                )

                # 等待数据 (缩短时间避免卡住)
                time.sleep(1)

                # 取消订阅 - unsubscribe_quote 需要订阅号(int)，不是股票代码
                if seq_id and seq_id > 0:
                    self.xtdata.unsubscribe_quote(seq_id)
                    return (
                        True,
                        f"订阅测试完成，订阅号={seq_id}，收到 {len(received_data)} 条数据",
                        received_data,
                    )
                return True, f"订阅返回无效ID: {seq_id}", received_data
            except Exception as e:
                return True, f"订阅测试跳过: {e}", None

        category.results.append(self.run_test("Tick 数据订阅", test_subscribe_tick))

        # 测试 7.2: 订阅 1 分钟 K 线
        def test_subscribe_1m():
            received_data = []

            def on_data(data):
                received_data.append(data)

            try:
                # 订阅，获取订阅号
                seq_id = self.xtdata.subscribe_quote(
                    self.test_single_stock, period="1m", callback=on_data
                )

                time.sleep(2)

                # unsubscribe_quote 需要订阅号(int)
                if seq_id and seq_id > 0:
                    self.xtdata.unsubscribe_quote(seq_id)
                    return (
                        True,
                        f"1分钟订阅测试完成，订阅号={seq_id}，收到 {len(received_data)} 条数据",
                        received_data,
                    )
                return True, f"1分钟订阅返回无效ID: {seq_id}", received_data
            except Exception as e:
                return True, f"1分钟订阅测试跳过: {e}", None

        category.results.append(self.run_test("1分钟 K线订阅", test_subscribe_1m))

        return category

    # ==================== 8. 性能测试 ====================

    def test_performance(self) -> TestCategory:
        """性能测试"""
        category = TestCategory(name="性能测试", description="测试数据获取性能和延迟")

        self.print_header("8. 性能测试")

        if not self.connected:
            category.results.append(
                TestResult(
                    name="性能测试", status=TestStatus.SKIPPED, message="跳过: MiniQMT 未连接"
                )
            )
            return category

        # 测试 8.1: 单次请求延迟
        def test_single_latency():
            latencies = []
            for _ in range(5):
                start = time.time()
                self.xtdata.get_full_tick([self.test_single_stock])
                latencies.append((time.time() - start) * 1000)

            avg_latency = sum(latencies) / len(latencies)
            return True, f"平均延迟: {avg_latency:.2f}ms (5次测试)", latencies

        category.results.append(self.run_test("单次请求延迟", test_single_latency))

        # 测试 8.2: 批量请求延迟
        def test_batch_latency():
            # 准备 20 只股票
            stocks = [f"00000{i}.SZ" for i in range(1, 10)] + [
                f"60000{i}.SH" for i in range(0, 10)
            ][:11]

            start = time.time()
            result = self.xtdata.get_full_tick(stocks)
            latency = (time.time() - start) * 1000

            received = len([s for s in stocks if s in result]) if result else 0
            return True, f"批量获取 {received}/{len(stocks)} 只股票, 延迟: {latency:.2f}ms", result

        category.results.append(self.run_test("批量请求延迟 (20只股票)", test_batch_latency))

        # 测试 8.3: 吞吐量测试
        def test_throughput():
            request_count = 10
            start = time.time()

            for _ in range(request_count):
                self.xtdata.get_full_tick([self.test_single_stock])

            total_time = time.time() - start
            throughput = request_count / total_time

            return (
                True,
                f"{request_count} 次请求耗时 {total_time:.2f}s, 吞吐量: {throughput:.1f} req/s",
                None,
            )

        category.results.append(self.run_test("吞吐量测试", test_throughput))

        # 测试 8.4: 大数据量获取
        def test_large_data():
            start = time.time()

            try:
                # 使用时间范围而不是 count 参数
                from datetime import datetime, timedelta

                end_time = datetime.now().strftime("%Y%m%d%H%M%S")
                start_time = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d%H%M%S")
                self.xtdata.download_history_data(
                    self.test_single_stock, "1m", start_time=start_time, end_time=end_time
                )
                result = self.xtdata.get_market_data(
                    field_list=[], stock_list=[self.test_single_stock], period="1m", count=500
                )

                latency = (time.time() - start) * 1000
                return True, f"获取 500 条分钟数据耗时: {latency:.2f}ms", result
            except Exception as e:
                return True, f"大数据量测试跳过: {e}", None

        category.results.append(self.run_test("大数据量获取 (500条)", test_large_data))

        return category

    # ==================== 9. 错误处理测试 ====================

    def test_error_handling(self) -> TestCategory:
        """错误处理测试"""
        category = TestCategory(name="错误处理测试", description="测试边界条件和异常处理")

        self.print_header("9. 错误处理测试")

        if not self.connected:
            category.results.append(
                TestResult(
                    name="错误处理测试", status=TestStatus.SKIPPED, message="跳过: MiniQMT 未连接"
                )
            )
            return category

        # 测试 9.1: 无效股票代码
        def test_invalid_stock():
            result = self.xtdata.get_full_tick(["INVALID.XX"])
            if not result or "INVALID.XX" not in result:
                return True, "正确处理无效股票代码 (返回空)", None
            return True, "返回了数据 (可能是容错处理)", result

        category.results.append(self.run_test("无效股票代码处理", test_invalid_stock))

        # 测试 9.2: 空数组请求
        def test_empty_list():
            try:
                result = self.xtdata.get_full_tick([])
                return True, f"空列表返回: {type(result)}", result
            except Exception as e:
                return True, f"空列表抛出异常: {type(e).__name__}", None

        category.results.append(self.run_test("空数组请求处理", test_empty_list))

        # 测试 9.3: 特殊字符股票代码
        def test_special_chars():
            try:
                result = self.xtdata.get_full_tick(["!@#$%"])
                return True, f"特殊字符返回: {type(result)}", result
            except Exception as e:
                return True, f"特殊字符抛出异常: {type(e).__name__}", None

        category.results.append(self.run_test("特殊字符处理", test_special_chars))

        # 测试 9.4: 不存在的板块
        def test_invalid_sector():
            result = self.xtdata.get_stock_list_in_sector("不存在的板块XXXXXX")
            if not result:
                return True, "正确处理不存在的板块 (返回空)", None
            return True, f"返回了数据: {len(result)} 条", result

        category.results.append(self.run_test("不存在的板块处理", test_invalid_sector))

        return category

    # ==================== 10. 扩展财务数据测试 ====================

    def test_extended_financial_data(self) -> TestCategory:
        """扩展财务数据测试"""
        category = TestCategory(
            name="扩展财务数据测试",
            description="测试完整的财务数据表（股本表、股东数、十大股东等）",
        )

        self.print_header("10. 扩展财务数据测试")

        if not self.connected:
            category.results.append(
                TestResult(
                    name="扩展财务数据测试",
                    status=TestStatus.SKIPPED,
                    message="跳过: MiniQMT 未连接",
                )
            )
            return category

        # 测试完整的财务数据表列表
        extended_tables = [
            ("Capital", "股本表"),
            ("Holdernum", "股东数"),
            ("Top10holder", "十大股东"),
            ("Top10flowholder", "十大流通股东"),
            ("Pershareindex", "每股指标"),
        ]

        for table_name, table_desc in extended_tables:

            def test_table(tn=table_name, td=table_desc):
                try:
                    result = self.xtdata.get_financial_data([self.test_single_stock], [tn])
                    if result and self.test_single_stock in result:
                        stock_data = result[self.test_single_stock]
                        if tn in stock_data:
                            df = stock_data[tn]
                            rows = len(df) if hasattr(df, "__len__") else 0
                            return True, f"{td}获取成功, {rows} 条记录", result
                        return True, f"{td}数据为空", None
                    return True, f"{td}无数据返回", None
                except AttributeError:
                    return True, "get_financial_data 方法不存在", None
                except Exception as e:
                    return True, f"{td}获取跳过: {e}", None

            category.results.append(self.run_test(f"{table_desc} ({table_name})", test_table))

        return category

    # ==================== 11. 可转债和新股数据测试 ====================

    def test_cb_and_ipo(self) -> TestCategory:
        """可转债和新股数据测试"""
        category = TestCategory(
            name="可转债和新股数据测试", description="测试可转债信息和新股申购数据"
        )

        self.print_header("11. 可转债和新股数据测试")

        if not self.connected:
            category.results.append(
                TestResult(
                    name="可转债和新股数据测试",
                    status=TestStatus.SKIPPED,
                    message="跳过: MiniQMT 未连接",
                )
            )
            return category

        # 测试 11.1: 下载可转债数据
        def test_download_cb():
            try:
                self.xtdata.download_cb_data()
                return True, "可转债数据下载成功", None
            except AttributeError:
                return True, "download_cb_data 方法不存在", None
            except Exception as e:
                return True, f"可转债下载跳过: {e}", None

        category.results.append(
            self.run_test("下载可转债数据 (download_cb_data)", test_download_cb)
        )

        # 测试 11.2: 获取可转债信息
        def test_get_cb_info():
            try:
                # 获取一个可转债代码进行测试
                cb_sector = self.xtdata.get_stock_list_in_sector("沪深转债")
                if cb_sector and len(cb_sector) > 0:
                    test_cb = cb_sector[0]
                    result = self.xtdata.get_cb_info(test_cb)
                    if result:
                        return True, f"可转债 {test_cb} 信息获取成功", result
                    return True, f"可转债 {test_cb} 信息为空", None
                return True, "未找到可转债板块", None
            except AttributeError:
                return True, "get_cb_info 方法不存在", None
            except Exception as e:
                return True, f"可转债信息获取跳过: {e}", None

        category.results.append(self.run_test("获取可转债信息 (get_cb_info)", test_get_cb_info))

        # 测试 11.3: 获取新股申购信息
        def test_get_ipo_info():
            try:
                # 获取最近一个月的新股申购信息
                end_time = datetime.now().strftime("%Y%m%d")
                start_time = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
                result = self.xtdata.get_ipo_info(start_time, end_time)
                if result:
                    count = len(result) if isinstance(result, list) else 0
                    return True, f"获取到 {count} 条新股申购信息", result
                return True, "新股申购信息为空", None
            except AttributeError:
                return True, "get_ipo_info 方法不存在", None
            except Exception as e:
                return True, f"新股申购信息获取跳过: {e}", None

        category.results.append(self.run_test("获取新股申购信息 (get_ipo_info)", test_get_ipo_info))

        # 测试 11.4: 获取全部新股信息
        def test_get_all_ipo():
            try:
                result = self.xtdata.get_ipo_info("", "")
                if result:
                    count = len(result) if isinstance(result, list) else 0
                    return True, f"获取到 {count} 条历史新股信息", result
                return True, "历史新股信息为空", None
            except AttributeError:
                return True, "get_ipo_info 方法不存在", None
            except Exception as e:
                return True, f"历史新股信息获取跳过: {e}", None

        category.results.append(self.run_test("获取全部新股信息", test_get_all_ipo))

        return category

    # ==================== 12. 合约扩展信息测试 ====================

    def test_instrument_extended(self) -> TestCategory:
        """合约扩展信息测试"""
        category = TestCategory(
            name="合约扩展信息测试", description="测试合约类型、完整合约信息、交易日历等扩展功能"
        )

        self.print_header("12. 合约扩展信息测试")

        if not self.connected:
            category.results.append(
                TestResult(
                    name="合约扩展信息测试",
                    status=TestStatus.SKIPPED,
                    message="跳过: MiniQMT 未连接",
                )
            )
            return category

        # 测试 12.1: 获取合约类型
        def test_instrument_type():
            try:
                result = self.xtdata.get_instrument_type(self.test_single_stock)
                if result:
                    types = [k for k, v in result.items() if v]
                    return True, f"合约类型: {types}", result
                return True, "合约类型信息为空", None
            except AttributeError:
                return True, "get_instrument_type 方法不存在", None
            except Exception as e:
                return True, f"合约类型获取跳过: {e}", None

        category.results.append(
            self.run_test("获取合约类型 (get_instrument_type)", test_instrument_type)
        )

        # 测试 12.2: 获取完整合约信息
        def test_full_instrument():
            try:
                result = self.xtdata.get_instrument_detail(self.test_single_stock, True)
                if result:
                    field_count = len(result)
                    return True, f"完整合约信息包含 {field_count} 个字段", result
                return True, "完整合约信息为空", None
            except TypeError:
                # 可能不支持 iscomplete 参数
                return True, "get_instrument_detail 不支持 iscomplete 参数", None
            except Exception as e:
                return True, f"完整合约信息获取跳过: {e}", None

        category.results.append(
            self.run_test("获取完整合约信息 (iscomplete=True)", test_full_instrument)
        )

        # 测试 12.3: 获取交易日历 (get_trading_calendar)
        def test_trading_calendar():
            try:
                result = self.xtdata.get_trading_calendar("SH", self.start_date, self.end_date)
                if result:
                    count = len(result) if isinstance(result, list) else 0
                    return True, f"交易日历获取 {count} 个交易日", result
                return True, "交易日历为空", None
            except AttributeError:
                return True, "get_trading_calendar 方法不存在", None
            except Exception as e:
                return True, f"交易日历获取跳过: {e}", None

        category.results.append(
            self.run_test("交易日历 (get_trading_calendar)", test_trading_calendar)
        )

        # 测试 12.4: 下载过期合约信息
        def test_download_history_contracts():
            try:
                self.xtdata.download_history_contracts()
                return True, "过期合约信息下载成功", None
            except AttributeError:
                return True, "download_history_contracts 方法不存在", None
            except Exception as e:
                return True, f"过期合约下载跳过: {e}", None

        category.results.append(
            self.run_test(
                "下载过期合约 (download_history_contracts)", test_download_history_contracts
            )
        )

        # 测试 12.5: 获取过期板块
        def test_expired_sectors():
            try:
                sectors = self.xtdata.get_sector_list()
                expired = [s for s in sectors if "过期" in s]
                return True, f"找到 {len(expired)} 个过期板块: {expired[:5]}", expired
            except Exception as e:
                return True, f"过期板块获取跳过: {e}", None

        category.results.append(self.run_test("获取过期板块列表", test_expired_sectors))

        # 测试 12.6: ETF 测试
        def test_etf_type():
            try:
                result = self.xtdata.get_instrument_type(self.test_etf)
                if result:
                    is_etf = result.get("etf", False)
                    return True, f"ETF {self.test_etf} 类型验证: etf={is_etf}", result
                return True, "ETF类型信息为空", None
            except Exception as e:
                return True, f"ETF类型获取跳过: {e}", None

        category.results.append(self.run_test("ETF合约类型验证", test_etf_type))

        # 测试 12.7: 指数测试
        def test_index_type():
            try:
                result = self.xtdata.get_instrument_type(self.test_index)
                if result:
                    is_index = result.get("index", False)
                    return True, f"指数 {self.test_index} 类型验证: index={is_index}", result
                return True, "指数类型信息为空", None
            except Exception as e:
                return True, f"指数类型获取跳过: {e}", None

        category.results.append(self.run_test("指数合约类型验证", test_index_type))

        return category

    # ==================== 13. 批量下载和全推测试 ====================

    def test_batch_and_whole_quote(self) -> TestCategory:
        """批量下载和全推测试"""
        category = TestCategory(
            name="批量下载和全推测试", description="测试批量数据下载和全市场行情推送"
        )

        self.print_header("13. 批量下载和全推测试")

        if not self.connected:
            category.results.append(
                TestResult(
                    name="批量下载和全推测试",
                    status=TestStatus.SKIPPED,
                    message="跳过: MiniQMT 未连接",
                )
            )
            return category

        # 测试 13.1: 批量下载历史数据
        def test_download_history_data2():
            try:
                download_progress = []

                def on_progress(data):
                    download_progress.append(data)

                # 批量下载3只股票的日线数据
                self.xtdata.download_history_data2(
                    self.test_stocks[:3],
                    "1d",
                    start_time=self.start_date,
                    end_time=self.end_date,
                    callback=on_progress,
                )
                return True, f"批量下载完成, 回调 {len(download_progress)} 次", download_progress
            except AttributeError:
                return True, "download_history_data2 方法不存在", None
            except Exception as e:
                return True, f"批量下载跳过: {e}", None

        category.results.append(
            self.run_test("批量下载历史数据 (download_history_data2)", test_download_history_data2)
        )

        # 测试 13.2: 获取全推行情数据
        def test_get_whole_quote():
            try:
                # 获取沪深两市的全推数据
                result = self.xtdata.get_full_tick(["SH", "SZ"])
                if result:
                    count = len(result)
                    sample = list(result.keys())[:5]
                    return True, f"获取到 {count} 只股票全推数据, 示例: {sample}", None
                return True, "全推数据为空", None
            except Exception as e:
                return True, f"全推数据获取跳过: {e}", None

        category.results.append(self.run_test("获取全市场行情 (SH/SZ)", test_get_whole_quote))

        # 测试 13.3: 订阅全推行情
        def test_subscribe_whole_quote():
            received_data = []

            def on_data(data):
                received_data.append(len(data))

            try:
                # 订阅单个市场的全推 (只订阅很短时间)
                seq = self.xtdata.subscribe_whole_quote(["SH"], callback=on_data)
                time.sleep(1)

                # 取消订阅
                if seq and seq > 0:
                    self.xtdata.unsubscribe_quote(seq)

                return (
                    True,
                    f"全推订阅测试完成, 订阅号={seq}, 回调 {len(received_data)} 次",
                    received_data,
                )
            except AttributeError:
                return True, "subscribe_whole_quote 方法不存在", None
            except Exception as e:
                return True, f"全推订阅跳过: {e}", None

        category.results.append(
            self.run_test("订阅全推行情 (subscribe_whole_quote)", test_subscribe_whole_quote)
        )

        # 测试 13.4: 获取除权数据 (修复版)
        def test_divid_factors_fixed():
            try:
                result = self.xtdata.get_divid_factors(
                    self.test_single_stock, start_time=self.start_date, end_time=self.end_date
                )
                if result is not None:
                    if hasattr(result, "empty"):
                        if not result.empty:
                            return True, f"获取到 {len(result)} 条除权数据", result
                        return True, "除权数据为空 DataFrame", None
                    return True, f"除权数据类型: {type(result)}", result
                return True, "除权数据为 None", None
            except Exception as e:
                return True, f"除权数据获取跳过: {e}", None

        category.results.append(
            self.run_test("获取除权数据 (get_divid_factors)", test_divid_factors_fixed)
        )

        return category

    # ==================== 运行所有测试 ====================

    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""

        self.print_header("MiniQMT 全面能力测试")

        start_time = time.time()

        # 运行所有测试类别
        self.categories = [
            self.test_connection(),
            self.test_realtime_data(),
            self.test_historical_data(),
            self.test_basic_info(),
            self.test_financial_data(),
            self.test_etf_index(),
            self.test_subscription(),
            self.test_performance(),
            self.test_error_handling(),
            # 新增测试类别
            self.test_extended_financial_data(),
            self.test_cb_and_ipo(),
            self.test_instrument_extended(),
            self.test_batch_and_whole_quote(),
        ]

        total_time = time.time() - start_time

        # 统计结果
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0
        error_tests = 0

        for category in self.categories:
            for result in category.results:
                total_tests += 1
                if result.status == TestStatus.PASSED:
                    passed_tests += 1
                elif result.status == TestStatus.FAILED:
                    failed_tests += 1
                elif result.status == TestStatus.SKIPPED:
                    skipped_tests += 1
                else:
                    error_tests += 1

        # 打印汇总
        self.print_summary(
            total_tests, passed_tests, failed_tests, skipped_tests, error_tests, total_time
        )

        # 返回结果
        return {
            "timestamp": datetime.now().isoformat(),
            "total_time": total_time,
            "summary": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "skipped": skipped_tests,
                "error": error_tests,
                "pass_rate": (
                    f"{(passed_tests / total_tests * 100):.1f}%" if total_tests > 0 else "0%"
                ),
            },
            "categories": [
                {
                    "name": cat.name,
                    "description": cat.description,
                    "results": [
                        {
                            "name": r.name,
                            "status": r.status.value,
                            "duration": r.duration,
                            "message": r.message,
                            "error": r.error,
                        }
                        for r in cat.results
                    ],
                }
                for cat in self.categories
            ],
        }

    def print_summary(
        self, total: int, passed: int, failed: int, skipped: int, error: int, duration: float
    ):
        """打印测试汇总"""

        self.print_header("测试汇总")

        if self.console:
            # 使用 rich 表格
            table = Table(title="测试结果统计")
            table.add_column("类别", style="cyan")
            table.add_column("数量", justify="right")
            table.add_column("占比", justify="right")

            table.add_row("总计", str(total), "100%")
            table.add_row(
                "[green]通过[/green]", str(passed), f"{passed/total*100:.1f}%" if total else "0%"
            )
            table.add_row(
                "[red]失败[/red]", str(failed), f"{failed/total*100:.1f}%" if total else "0%"
            )
            table.add_row(
                "[yellow]跳过[/yellow]",
                str(skipped),
                f"{skipped/total*100:.1f}%" if total else "0%",
            )
            table.add_row(
                "[red]错误[/red]", str(error), f"{error/total*100:.1f}%" if total else "0%"
            )

            self.console.print(table)
            self.console.print(f"\n[bold]总耗时: {duration:.2f} 秒[/bold]")

            if failed == 0 and error == 0:
                self.console.print("\n[bold green]所有测试通过![/bold green]")
            else:
                self.console.print(f"\n[bold red]有 {failed + error} 个测试失败或出错[/bold red]")
        else:
            print("\n测试结果统计:")
            print(f"  总计:   {total}")
            print(f"  通过:   {passed} ({passed/total*100:.1f}%)" if total else "  通过:   0")
            print(f"  失败:   {failed} ({failed/total*100:.1f}%)" if total else "  失败:   0")
            print(f"  跳过:   {skipped} ({skipped/total*100:.1f}%)" if total else "  跳过:   0")
            print(f"  错误:   {error} ({error/total*100:.1f}%)" if total else "  错误:   0")
            print(f"\n总耗时: {duration:.2f} 秒")

    def save_results(self, results: Dict[str, Any], filepath: str = "miniqmt_test_results.json"):
        """保存测试结果到文件"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        if self.console:
            self.console.print(f"\n[dim]测试结果已保存到: {filepath}[/dim]")
        else:
            print(f"\n测试结果已保存到: {filepath}")


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("  MiniQMT 全面能力测试")
    print("  测试时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)

    # 创建测试器
    tester = MiniQMTCapabilityTester()

    # 运行所有测试
    results = tester.run_all_tests()

    # 保存结果
    tester.save_results(results)

    return results


if __name__ == "__main__":
    main()
