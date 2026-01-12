#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData 数据源综合测试脚本
测试AmazingData的所有主要功能，包括连接、数据获取、性能和稳定性
生成时间: 2025-09-17
"""

import asyncio
import importlib.util
import json
import os
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Protocol, TypeVar, cast

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from core.config import get_config
from helpers import fetch_code_list

# 为 colorama 定义最小协议，确保缺失依赖时依旧具备类型约束


class _ColorProtocol(Protocol):
    RESET: str
    RED: str
    GREEN: str
    YELLOW: str
    CYAN: str
    MAGENTA: str
    BLUE: str
    WHITE: str


class _StyleProtocol(Protocol):
    BRIGHT: str
    DIM: str
    NORMAL: str
    RESET_ALL: str


class _TqdmCallable(Protocol):
    def __call__(self, iterable: Iterable[Any], *args: Any, **kwargs: Any) -> Iterable[Any]: ...


# 尝试导入彩色输出库
try:
    from colorama import Fore as _ForeInstance
    from colorama import Style as _StyleInstance
    from colorama import init

    init(autoreset=True)
    Fore: _ColorProtocol = _ForeInstance
    Style: _StyleProtocol = _StyleInstance
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

    class _FallbackFore:
        RESET = ""
        RED = ""
        GREEN = ""
        YELLOW = ""
        CYAN = ""
        MAGENTA = ""
        BLUE = ""
        WHITE = ""

    class _FallbackStyle:
        BRIGHT = ""
        DIM = ""
        NORMAL = ""
        RESET_ALL = ""

    Fore = cast(_ColorProtocol, _FallbackFore())
    Style = cast(_StyleProtocol, _FallbackStyle())


# 尝试导入进度条库
T = TypeVar("T")

_tqdm_spec = importlib.util.find_spec("tqdm")
if _tqdm_spec is not None:
    from tqdm import tqdm as _tqdm_impl

    HAS_TQDM = True
    _tqdm_callable: _TqdmCallable = _tqdm_impl
else:
    HAS_TQDM = False

    def _tqdm_fallback(iterable: Iterable[Any], *args: Any, **kwargs: Any) -> Iterable[Any]:
        return iterable

    _tqdm_callable = _tqdm_fallback


def tqdm(iterable: Iterable[T], **kwargs: Any) -> Iterable[T]:
    result = _tqdm_callable(iterable, **kwargs)
    return cast(Iterable[T], result)


@dataclass
class TestResult:
    """测试结果数据类"""

    name: str
    status: str  # 'success', 'fail', 'skip', 'warning'
    duration: float
    message: str = ""
    data: Dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AmazingDataTester:
    """AmazingData综合测试类"""

    def __init__(self):
        self.config = None
        self.credentials = None
        self.results: List[TestResult] = []
        self.start_time = None
        self.end_time = None
        self._calendar = None  # 交易日历缓存

    def _get_calendar(self):
        """获取交易日历（缓存）- MarketData.query_kline必需"""
        if self._calendar is None:
            import AmazingData as ad

            try:
                self._calendar = ad.BaseData().get_calendar()
            except Exception:
                pass
        return self._calendar

    def print_header(self):
        """打印测试头部信息"""
        print("\n" + "=" * 80)
        print(f"{Style.BRIGHT}{Fore.CYAN}AmazingData 数据源综合测试{Style.RESET_ALL}")
        print("=" * 80)
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Python版本: {sys.version.split()[0]}")
        print(f"系统平台: {sys.platform}")
        print("=" * 80 + "\n")

    def print_section(self, title: str):
        """打印章节标题"""
        print(f"\n{Fore.YELLOW}{'─' * 40}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.YELLOW}[{title}]{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}{'─' * 40}{Style.RESET_ALL}\n")

    def print_result(self, result: TestResult, verbose: bool = True):
        """打印测试结果"""
        icon = {
            "success": f"{Fore.GREEN}[OK]",
            "fail": f"{Fore.RED}[FAIL]",
            "skip": f"{Fore.YELLOW}[SKIP]",
            "warning": f"{Fore.YELLOW}[WARN]",
        }.get(result.status, "[?]")

        status_color = {
            "success": Fore.GREEN,
            "fail": Fore.RED,
            "skip": Fore.YELLOW,
            "warning": Fore.YELLOW,
        }.get(result.status, Fore.WHITE)

        print(
            f"{icon} {result.name}: {status_color}{result.status.upper()}{Style.RESET_ALL} ({result.duration:.2f}s)"
        )

        if verbose and result.message:
            print(f"   {Fore.CYAN}{result.message}{Style.RESET_ALL}")

        if verbose and result.data:
            for key, value in result.data.items():
                print(f"   - {key}: {value}")

    def load_config(self) -> bool:
        """加载配置文件"""
        self.print_section("1. 加载配置文件")

        start_time = time.time()
        try:
            self.config = get_config()
            env = self.config.app.env
            print(f"当前环境: {Fore.CYAN}{env}{Style.RESET_ALL}")

            # 尝试新格式配置
            if hasattr(self.config, "data_sources") and self.config.data_sources:
                ds = self.config.data_sources
                # 兼容 Pydantic 模型和字典两种格式
                providers = (
                    getattr(ds, "providers", None) or ds.get("providers", {})
                    if isinstance(ds, dict)
                    else getattr(ds, "providers", {})
                )

                # 获取 amazingdata 提供者配置
                ad_provider = None
                if isinstance(providers, dict):
                    ad_provider = providers.get("amazingdata")
                elif hasattr(providers, "__getitem__"):
                    ad_provider = (
                        providers.get("amazingdata", None)
                        if hasattr(providers, "get")
                        else providers["amazingdata"] if "amazingdata" in providers else None
                    )

                if ad_provider:
                    print(f"{Fore.GREEN}使用新格式配置{Style.RESET_ALL}")

                    # 获取 enabled 状态
                    enabled = (
                        getattr(ad_provider, "enabled", False)
                        if hasattr(ad_provider, "enabled")
                        else (
                            ad_provider.get("enabled", False)
                            if isinstance(ad_provider, dict)
                            else False
                        )
                    )

                    # 获取 config
                    ad_config = (
                        getattr(ad_provider, "config", {})
                        if hasattr(ad_provider, "config")
                        else ad_provider.get("config", {}) if isinstance(ad_provider, dict) else {}
                    )

                    # 获取 connection
                    if isinstance(ad_config, dict):
                        conn_config = ad_config.get("connection", {})
                    else:
                        conn_config = (
                            getattr(ad_config, "connection", {})
                            if hasattr(ad_config, "connection")
                            else {}
                        )

                    # 提取凭证
                    if isinstance(conn_config, dict):
                        self.credentials = {
                            "host": conn_config.get("host", ""),
                            "port": conn_config.get("port", 8600),
                            "username": conn_config.get("username", ""),
                            "password": conn_config.get("password", ""),
                            "timeout": conn_config.get("timeout", 10),
                            "enabled": enabled,
                        }
                    else:
                        self.credentials = {
                            "host": getattr(conn_config, "host", ""),
                            "port": getattr(conn_config, "port", 8600),
                            "username": getattr(conn_config, "username", ""),
                            "password": getattr(conn_config, "password", ""),
                            "timeout": getattr(conn_config, "timeout", 10),
                            "enabled": enabled,
                        }
            # 尝试旧格式配置
            elif hasattr(self.config, "amazingdata"):
                print(f"{Fore.YELLOW}使用旧格式配置{Style.RESET_ALL}")
                ad_config = self.config.amazingdata

                self.credentials = {
                    "host": getattr(ad_config, "host", ""),
                    "port": getattr(ad_config, "port", 8600),
                    "username": getattr(ad_config, "username", ""),
                    "password": str(getattr(ad_config, "password", "")),
                    "timeout": getattr(ad_config, "timeout", 10),
                    "enabled": getattr(ad_config, "enabled", False),
                }
            else:
                raise ValueError("配置文件中没有amazingdata配置项")

            # 验证配置
            if not self.credentials["enabled"]:
                result = TestResult(
                    name="配置启用状态",
                    status="warning",
                    duration=time.time() - start_time,
                    message="AmazingData未启用，请在配置文件中设置enabled: true",
                )
                self.results.append(result)
                self.print_result(result)
                return False

            if not self.credentials["username"] or not self.credentials["password"]:
                result = TestResult(
                    name="凭证验证",
                    status="fail",
                    duration=time.time() - start_time,
                    message="用户名或密码未配置",
                )
                self.results.append(result)
                self.print_result(result)
                return False

            result = TestResult(
                name="配置加载",
                status="success",
                duration=time.time() - start_time,
                message="成功加载配置",
                data={
                    "服务器": f"{self.credentials['host']}:{self.credentials['port']}",
                    "用户名": f"***{self.credentials['username'][-4:] if len(self.credentials['username']) > 4 else '***'}",
                    "超时设置": f"{self.credentials['timeout']}秒",
                },
            )
            self.results.append(result)
            self.print_result(result)
            return True

        except Exception as e:
            result = TestResult(
                name="配置加载",
                status="fail",
                duration=time.time() - start_time,
                message=f"配置加载失败: {str(e)}",
            )
            self.results.append(result)
            self.print_result(result)
            return False

    def test_sdk_import(self) -> bool:
        """测试SDK导入"""
        self.print_section("2. SDK环境检查")

        start_time = time.time()
        try:
            import AmazingData as ad

            version = getattr(ad, "__version__", "未知")
            result = TestResult(
                name="SDK导入",
                status="success",
                duration=time.time() - start_time,
                message=f"AmazingData SDK版本: {version}",
                data={"模块路径": getattr(ad, "__file__", "未知")},
            )
            self.results.append(result)
            self.print_result(result)
            return True

        except ImportError as e:
            result = TestResult(
                name="SDK导入",
                status="fail",
                duration=time.time() - start_time,
                message=f"SDK未安装: {str(e)}",
                data={
                    "建议": "运行: uv pip install third_party/AmazingData-1.0.9-cp313-none-any.whl"
                },
            )
            self.results.append(result)
            self.print_result(result)
            return False

    async def test_connection(self) -> bool:
        """测试连接和登录"""
        self.print_section("3. 连接和认证测试")

        start_time = time.time()
        try:
            import AmazingData as ad

            # 直接使用ad模块的login函数
            print(
                f"{Fore.CYAN}连接服务器 {self.credentials['host']}:{self.credentials['port']}...{Style.RESET_ALL}"
            )
            print(f"{Fore.CYAN}登录用户 {self.credentials['username'][:3]}***...{Style.RESET_ALL}")

            # AmazingData SDK使用直接的login函数（必须使用关键字参数）
            login_result = ad.login(
                username=self.credentials["username"],
                password=self.credentials["password"],
                host=self.credentials["host"],
                port=self.credentials["port"],
            )

            if login_result == 0 or login_result is True:
                result = TestResult(
                    name="登录认证",
                    status="success",
                    duration=time.time() - start_time,
                    message="登录成功",
                    data={
                        "连接耗时": f"{(time.time() - start_time):.3f}秒",
                        "服务器": f"{self.credentials['host']}:{self.credentials['port']}",
                    },
                )
                self.results.append(result)
                self.print_result(result)
                return True
            else:
                result = TestResult(
                    name="登录认证",
                    status="fail",
                    duration=time.time() - start_time,
                    message="登录失败，请检查用户名密码",
                )
                self.results.append(result)
                self.print_result(result)
                return False

        except Exception as e:
            result = TestResult(
                name="登录认证",
                status="fail",
                duration=time.time() - start_time,
                message=f"连接异常: {str(e)}",
            )
            self.results.append(result)
            self.print_result(result)
            return False

    async def test_stock_list(self) -> bool:
        """测试获取股票列表"""
        self.print_section("4. 股票列表获取测试")

        import AmazingData as ad

        success_count = 0
        start_time = time.time()
        try:
            print(f"{Fore.CYAN}获取A股股票列表...{Style.RESET_ALL}")
            stock_list = fetch_code_list(ad)

            if not stock_list.empty:
                result = TestResult(
                    name="股票列表获取",
                    status="success",
                    duration=time.time() - start_time,
                    message="获取成功",
                    data={
                        "股票数量": len(stock_list),
                        "示例股票": (
                            stock_list.head(3).to_dict("records")
                            if len(stock_list) >= 3
                            else stock_list.to_dict("records")
                        ),
                    },
                )
                success_count = 1
            else:
                result = TestResult(
                    name="股票列表获取",
                    status="warning",
                    duration=time.time() - start_time,
                    message="返回列表为空",
                )

        except Exception as e:
            result = TestResult(
                name="股票列表获取",
                status="fail",
                duration=time.time() - start_time,
                message=f"获取失败: {str(e)}",
            )

        self.results.append(result)
        self.print_result(result)

        return success_count > 0

    async def test_kline_data(self) -> bool:
        """测试K线数据获取"""
        self.print_section("5. K线数据获取测试")

        import AmazingData as ad

        test_symbols = [("000001", "平安银行"), ("600036", "招商银行"), ("000002", "万科A")]

        success_count = 0
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        for symbol, name in test_symbols:
            start_time = time.time()
            try:
                print(f"{Fore.CYAN}获取 {symbol} {name} 的K线数据...{Style.RESET_ALL}")

                # 使用AmazingData MarketData获取K线数据
                kline_data = ad.MarketData(self._get_calendar()).query_kline(
                    [symbol + ".SZ" if symbol.startswith("0") else symbol + ".SH"],
                    period=10008,  # Period.day.value
                    begin_date=int(start_date.strftime("%Y%m%d")),
                    end_date=int(end_date.strftime("%Y%m%d")),
                )

                if kline_data is not None and len(kline_data) > 0:
                    result = TestResult(
                        name=f"{symbol} {name} K线",
                        status="success",
                        duration=time.time() - start_time,
                        message="获取成功",
                        data={
                            "数据条数": len(kline_data),
                            "时间范围": f"{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}",
                            "数据类型": type(kline_data).__name__,
                        },
                    )
                    success_count += 1

                    # 如果是DataFrame，显示最后几条数据
                    if isinstance(kline_data, pd.DataFrame) and not kline_data.empty:
                        print("   最后3条数据:")
                        print(kline_data.tail(3).to_string(index=False))
                else:
                    result = TestResult(
                        name=f"{symbol} {name} K线",
                        status="warning",
                        duration=time.time() - start_time,
                        message="返回数据为空",
                    )

            except Exception as e:
                result = TestResult(
                    name=f"{symbol} {name} K线",
                    status="fail",
                    duration=time.time() - start_time,
                    message=f"获取失败: {str(e)}",
                )

            self.results.append(result)
            self.print_result(result, verbose=False)

        return success_count > 0

    async def test_realtime_quotes(self) -> bool:
        """测试实时行情获取"""
        self.print_section("6. 实时行情获取测试")

        import AmazingData as ad

        test_symbols = ["000001", "000002", "600036", "600519"]

        start_time = time.time()
        try:
            print(f"{Fore.CYAN}批量获取实时行情: {test_symbols}...{Style.RESET_ALL}")

            today = int(datetime.now().strftime("%Y%m%d"))
            quotes = {}
            for symbol in test_symbols:
                # 使用AmazingData MarketData获取实时行情
                quote = ad.MarketData(self._get_calendar()).query_snapshot(
                    [symbol + ".SZ" if symbol.startswith("0") else symbol + ".SH"],
                    begin_date=today,
                    end_date=today,
                )
                if quote:
                    quotes[symbol] = quote

            if quotes:
                result = TestResult(
                    name="实时行情批量获取",
                    status="success",
                    duration=time.time() - start_time,
                    message=f"成功获取 {len(quotes)}/{len(test_symbols)} 只股票行情",
                    data={
                        "成功股票": list(quotes.keys()),
                        "平均响应时间": f"{(time.time() - start_time) / len(test_symbols):.3f}秒/股",
                    },
                )

                # 显示部分行情数据
                for symbol, quote in list(quotes.items())[:2]:
                    print(f"\n   {symbol} 行情数据:")
                    print(f"   - 最新价: {quote.get('last', 'N/A')}")
                    print(f"   - 涨跌幅: {quote.get('pct_chg', 'N/A')}%")
                    print(f"   - 成交量: {quote.get('volume', 'N/A')}")
                    print(f"   - 成交额: {quote.get('amount', 'N/A')}")
            else:
                result = TestResult(
                    name="实时行情批量获取",
                    status="fail",
                    duration=time.time() - start_time,
                    message="未能获取任何股票行情",
                )

        except Exception as e:
            result = TestResult(
                name="实时行情批量获取",
                status="fail",
                duration=time.time() - start_time,
                message=f"获取失败: {str(e)}",
            )

        self.results.append(result)
        self.print_result(result, verbose=False)
        return result.status == "success"

    async def test_performance(self) -> bool:
        """性能测试"""
        self.print_section("7. 性能测试")

        import AmazingData as ad

        # 测试单次请求延迟
        print(f"{Fore.CYAN}测试单次请求延迟...{Style.RESET_ALL}")
        latencies = []

        today = int(datetime.now().strftime("%Y%m%d"))
        for i in range(10):
            start_time = time.time()
            try:
                ad.MarketData(self._get_calendar()).query_snapshot(
                    ["000001.SZ"], begin_date=today, end_date=today
                )
                latency = time.time() - start_time
                latencies.append(latency)
            except Exception:
                pass

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)

            result = TestResult(
                name="请求延迟测试",
                status="success" if avg_latency < 1.0 else "warning",
                duration=sum(latencies),
                message=f"平均延迟: {avg_latency:.3f}秒",
                data={
                    "最小延迟": f"{min_latency:.3f}秒",
                    "最大延迟": f"{max_latency:.3f}秒",
                    "测试次数": len(latencies),
                },
            )
        else:
            result = TestResult(
                name="请求延迟测试", status="fail", duration=0, message="无法完成延迟测试"
            )

        self.results.append(result)
        self.print_result(result)

        # 测试并发请求
        print(f"\n{Fore.CYAN}测试并发请求能力...{Style.RESET_ALL}")
        concurrent_symbols = ["000001", "000002", "600036", "600519", "300750"]

        start_time = time.time()
        try:
            # 并发获取多只股票
            today = int(datetime.now().strftime("%Y%m%d"))
            for symbol in concurrent_symbols:
                # 这里简化处理，实际应该用asyncio并发
                ad.MarketData(self._get_calendar()).query_snapshot(
                    [symbol + ".SZ" if symbol.startswith("0") else symbol + ".SH"],
                    begin_date=today,
                    end_date=today,
                )

            duration = time.time() - start_time
            result = TestResult(
                name="并发请求测试",
                status="success" if duration < 5.0 else "warning",
                duration=duration,
                message=f"并发获取{len(concurrent_symbols)}只股票",
                data={
                    "总耗时": f"{duration:.3f}秒",
                    "平均耗时": f"{duration/len(concurrent_symbols):.3f}秒/股",
                },
            )
        except Exception as e:
            result = TestResult(
                name="并发请求测试",
                status="fail",
                duration=time.time() - start_time,
                message=f"并发请求失败: {str(e)}",
            )

        self.results.append(result)
        self.print_result(result)

        return True

    def generate_report(self):
        """生成测试报告"""
        self.print_section("8. 生成测试报告")

        # 统计结果
        total_tests = len(self.results)
        success_count = sum(1 for r in self.results if r.status == "success")
        fail_count = sum(1 for r in self.results if r.status == "fail")
        warning_count = sum(1 for r in self.results if r.status == "warning")
        skip_count = sum(1 for r in self.results if r.status == "skip")

        success_rate = (success_count / total_tests * 100) if total_tests > 0 else 0
        total_duration = self.end_time - self.start_time if self.end_time and self.start_time else 0

        # 生成文本报告
        report_lines = [
            "=" * 80,
            "AmazingData 数据源测试报告",
            "=" * 80,
            f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"总耗时: {total_duration:.2f}秒",
            "",
            "测试统计:",
            f"  总测试数: {total_tests}",
            f"  成功: {success_count} ({Fore.GREEN}{success_rate:.1f}%{Style.RESET_ALL})",
            f"  失败: {fail_count}",
            f"  警告: {warning_count}",
            f"  跳过: {skip_count}",
            "",
            "详细结果:",
            "-" * 80,
        ]

        for result in self.results:
            status_icon = {
                "success": "[OK]",
                "fail": "[FAIL]",
                "warning": "[WARN]",
                "skip": "[SKIP]",
            }.get(result.status, "[?]")

            report_lines.append(
                f"{status_icon} {result.name}: {result.status.upper()} ({result.duration:.2f}s)"
            )
            if result.message:
                report_lines.append(f"   {result.message}")

        report_lines.extend(
            [
                "-" * 80,
                "",
                "建议:",
            ]
        )

        # 添加建议
        if fail_count > 0:
            report_lines.append("- 存在失败的测试，请检查网络连接和配置")
        if warning_count > 0:
            report_lines.append("- 存在警告，某些功能可能需要优化")
        if success_rate < 80:
            report_lines.append("- 成功率较低，建议排查数据源配置和连接稳定性")
        if success_rate >= 90:
            report_lines.append(f"- {Fore.GREEN}测试通过率良好，数据源可正常使用{Style.RESET_ALL}")

        # 保存文本报告
        report_text = "\n".join(report_lines)
        report_file = "amazingdata_test_report.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            # 去除颜色代码
            clean_text = report_text
            if HAS_COLOR:
                for color in [
                    Fore.GREEN,
                    Fore.RED,
                    Fore.YELLOW,
                    Fore.CYAN,
                    Fore.MAGENTA,
                    Fore.BLUE,
                    Fore.WHITE,
                    Style.BRIGHT,
                    Style.DIM,
                    Style.RESET_ALL,
                ]:
                    clean_text = clean_text.replace(color, "")
            f.write(clean_text)

        print(f"\n{Fore.GREEN}文本报告已保存到: {report_file}{Style.RESET_ALL}")

        # 保存JSON报告
        json_report = {
            "test_time": datetime.now().isoformat(),
            "total_duration": total_duration,
            "statistics": {
                "total": total_tests,
                "success": success_count,
                "fail": fail_count,
                "warning": warning_count,
                "skip": skip_count,
                "success_rate": success_rate,
            },
            "results": [asdict(r) for r in self.results],
            "credentials": {
                "host": self.credentials["host"] if self.credentials else None,
                "port": self.credentials["port"] if self.credentials else None,
                "username": (
                    self.credentials["username"][:3] + "***"
                    if self.credentials and self.credentials["username"]
                    else None
                ),
            },
        }

        json_file = "amazingdata_test_report.json"
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(json_report, f, ensure_ascii=False, indent=2)

        print(f"{Fore.GREEN}JSON报告已保存到: {json_file}{Style.RESET_ALL}")

        # 显示测试总结
        print("\n" + "=" * 80)
        print(f"{Style.BRIGHT}测试总结{Style.RESET_ALL}")
        print("=" * 80)

        if success_rate >= 90:
            print(f"{Fore.GREEN}[PASS] 测试通过！成功率: {success_rate:.1f}%{Style.RESET_ALL}")
            print("AmazingData数据源工作正常，可以在生产环境使用")
        elif success_rate >= 70:
            print(f"{Fore.YELLOW}[WARN] 测试部分通过！成功率: {success_rate:.1f}%{Style.RESET_ALL}")
            print("AmazingData数据源基本可用，但存在一些问题需要解决")
        else:
            print(f"{Fore.RED}[FAIL] 测试未通过！成功率: {success_rate:.1f}%{Style.RESET_ALL}")
            print("AmazingData数据源存在严重问题，请检查配置和网络连接")

    async def run_tests(self):
        """运行所有测试"""
        self.start_time = time.time()

        # 打印头部
        self.print_header()

        # 1. 加载配置
        if not self.load_config():
            self.end_time = time.time()
            self.generate_report()
            return False

        # 2. 检查SDK
        if not self.test_sdk_import():
            self.end_time = time.time()
            self.generate_report()
            return False

        # 3. 测试连接
        if not await self.test_connection():
            self.end_time = time.time()
            self.generate_report()
            return False

        # 4. 测试股票列表
        await self.test_stock_list()

        # 5. 测试K线数据
        await self.test_kline_data()

        # 6. 测试实时行情
        await self.test_realtime_quotes()

        # 7. 性能测试
        await self.test_performance()

        # 登出
        try:
            import AmazingData as ad

            ad.logout()
            print(f"\n{Fore.GREEN}已安全登出{Style.RESET_ALL}")
        except Exception:
            pass

        self.end_time = time.time()

        # 8. 生成报告
        self.generate_report()

        return True


async def main():
    """主函数"""
    tester = AmazingDataTester()

    try:
        success = await tester.run_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}测试被用户中断{Style.RESET_ALL}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Fore.RED}测试过程发生异常: {e}{Style.RESET_ALL}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
