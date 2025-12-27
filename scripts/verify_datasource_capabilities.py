#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据源能力验证脚本

验证各数据源接口的实际可用性，每个接口测试一个标的
"""

import asyncio
import sys
from datetime import datetime, timedelta
from typing import Any, Dict

# 添加项目路径
sys.path.insert(0, "d:/Stock/code/deepsearch")


class CapabilityTester:
    """数据源能力测试器"""

    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}
        self.test_symbol = "000001"  # 平安银行
        self.test_index = "000300"  # 沪深300

    def _record(
        self,
        source: str,
        capability: str,
        success: bool,
        data_count: int = 0,
        message: str = "",
        sample: Any = None,
    ):
        """记录测试结果"""
        if source not in self.results:
            self.results[source] = {}

        self.results[source][capability] = {
            "success": success,
            "data_count": data_count,
            "message": message,
            "sample": sample,
            "time": datetime.now().isoformat(),
        }

        status = "OK" if success else "FAIL"
        count_str = f"({data_count}条)" if data_count > 0 else ""
        print(f"  [{status}] {capability} {count_str} {message}")

    async def test_akshare(self):
        """测试 AKShare 数据源"""
        print("\n" + "=" * 60)
        print("测试 AKShare 数据源")
        print("=" * 60)

        try:
            from deepsearch.infrastructure.providers.implementations.akshare.akshare_direct import (
                AKShareDirectProvider,
            )

            provider = AKShareDirectProvider()
            await provider.initialize()

            # 1. 股票列表
            print("\n[1] 基础数据能力")
            try:
                result = await provider.fetch_stock_list()
                if result and len(result) > 0:
                    self._record(
                        "akshare",
                        "STOCK_LIST",
                        True,
                        len(result),
                        sample=result[0] if result else None,
                    )
                else:
                    self._record("akshare", "STOCK_LIST", False, message="无数据")
            except Exception as e:
                self._record("akshare", "STOCK_LIST", False, message=str(e)[:50])

            # 2. 实时行情
            try:
                result = await provider.get_realtime_quote(self.test_symbol)
                if result and not result.get("error"):
                    self._record("akshare", "REALTIME_QUOTE", True, 1, sample=result)
                else:
                    self._record(
                        "akshare",
                        "REALTIME_QUOTE",
                        False,
                        message=result.get("error", "无数据")[:50] if result else "无数据",
                    )
            except Exception as e:
                self._record("akshare", "REALTIME_QUOTE", False, message=str(e)[:50])

            # 3. 批量行情
            try:
                result = await provider.get_realtime_quotes([self.test_symbol, "000002"])
                if result and len(result) > 0:
                    valid = [r for r in result if not r.get("error")]
                    self._record("akshare", "REALTIME_QUOTES", len(valid) > 0, len(valid))
                else:
                    self._record("akshare", "REALTIME_QUOTES", False, message="无数据")
            except Exception as e:
                self._record("akshare", "REALTIME_QUOTES", False, message=str(e)[:50])

            # 4. K线数据
            try:
                end_date = datetime.now().strftime("%Y%m%d")
                start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
                result = await provider.get_stock_hist(
                    self.test_symbol, period="daily", start_date=start_date, end_date=end_date
                )
                if result and result.get("data"):
                    self._record("akshare", "KLINE_DATA", True, len(result["data"]))
                elif isinstance(result, dict) and not result.get("error"):
                    self._record("akshare", "KLINE_DATA", True, 1, sample=result)
                else:
                    self._record(
                        "akshare",
                        "KLINE_DATA",
                        False,
                        message=result.get("error", "无数据")[:50] if result else "无数据",
                    )
            except Exception as e:
                self._record("akshare", "KLINE_DATA", False, message=str(e)[:50])

            # 5. 股票信息
            try:
                result = await provider.get_stock_info(self.test_symbol)
                if result and not result.get("error"):
                    self._record("akshare", "STOCK_INFO", True, 1, sample=result)
                else:
                    self._record(
                        "akshare",
                        "STOCK_INFO",
                        False,
                        message=result.get("error", "无数据")[:50] if result else "无数据",
                    )
            except Exception as e:
                self._record("akshare", "STOCK_INFO", False, message=str(e)[:50])

            # 6. 特色数据
            print("\n[2] 特色数据能力")

            # 龙虎榜
            try:
                if hasattr(provider, "get_dragon_tiger"):
                    result = await provider.get_dragon_tiger(
                        start_date=(datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
                        end_date=datetime.now().strftime("%Y%m%d"),
                    )
                    if result and len(result) > 0:
                        self._record("akshare", "DRAGON_TIGER", True, len(result))
                    else:
                        self._record("akshare", "DRAGON_TIGER", False, message="无数据")
                else:
                    self._record("akshare", "DRAGON_TIGER", False, message="方法不存在")
            except Exception as e:
                self._record("akshare", "DRAGON_TIGER", False, message=str(e)[:50])

            # 融资融券
            try:
                if hasattr(provider, "get_margin_trading"):
                    result = await provider.get_margin_trading(self.test_symbol)
                    if result and len(result) > 0:
                        self._record("akshare", "MARGIN_TRADING", True, len(result))
                    else:
                        self._record("akshare", "MARGIN_TRADING", False, message="无数据")
                else:
                    self._record("akshare", "MARGIN_TRADING", False, message="方法不存在")
            except Exception as e:
                self._record("akshare", "MARGIN_TRADING", False, message=str(e)[:50])

            # 大宗交易
            try:
                if hasattr(provider, "get_block_trades"):
                    result = await provider.get_block_trades(
                        start_date=(datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
                        end_date=datetime.now().strftime("%Y%m%d"),
                    )
                    if result and len(result) > 0:
                        self._record("akshare", "BLOCK_TRADE", True, len(result))
                    else:
                        self._record("akshare", "BLOCK_TRADE", False, message="无数据")
                else:
                    self._record("akshare", "BLOCK_TRADE", False, message="方法不存在")
            except Exception as e:
                self._record("akshare", "BLOCK_TRADE", False, message=str(e)[:50])

            # 北向资金
            try:
                if hasattr(provider, "get_northbound_holdings"):
                    result = await provider.get_northbound_holdings(self.test_symbol)
                    if result and len(result) > 0:
                        self._record("akshare", "NORTH_FLOW", True, len(result))
                    else:
                        self._record("akshare", "NORTH_FLOW", False, message="无数据")
                else:
                    self._record("akshare", "NORTH_FLOW", False, message="方法不存在")
            except Exception as e:
                self._record("akshare", "NORTH_FLOW", False, message=str(e)[:50])

            # 7. 市场数据
            print("\n[3] 市场数据能力")

            # 资金流向
            try:
                if hasattr(provider, "get_capital_flow"):
                    result = await provider.get_capital_flow(self.test_symbol)
                    if result and len(result) > 0:
                        self._record("akshare", "CAPITAL_FLOW", True, len(result))
                    else:
                        self._record("akshare", "CAPITAL_FLOW", False, message="无数据")
                else:
                    self._record("akshare", "CAPITAL_FLOW", False, message="方法不存在")
            except Exception as e:
                self._record("akshare", "CAPITAL_FLOW", False, message=str(e)[:50])

            # 交易日历
            try:
                if hasattr(provider, "get_trading_calendar"):
                    result = await provider.get_trading_calendar(
                        start_date=(datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
                        end_date=datetime.now().strftime("%Y%m%d"),
                    )
                    if result and len(result) > 0:
                        self._record("akshare", "TRADING_CALENDAR", True, len(result))
                    else:
                        self._record("akshare", "TRADING_CALENDAR", False, message="无数据")
                else:
                    self._record("akshare", "TRADING_CALENDAR", False, message="方法不存在")
            except Exception as e:
                self._record("akshare", "TRADING_CALENDAR", False, message=str(e)[:50])

        except ImportError as e:
            print(f"  [SKIP] AKShare 导入失败: {e}")
        except Exception as e:
            print(f"  [ERROR] AKShare 测试异常: {e}")

    async def test_miniqmt(self):
        """测试 MiniQMT 数据源"""
        print("\n" + "=" * 60)
        print("测试 MiniQMT 数据源")
        print("=" * 60)

        try:
            from deepsearch.infrastructure.providers.implementations.qmt.unified_qmt_provider import (
                QMTMode,
                UnifiedQMTProvider,
            )

            provider = UnifiedQMTProvider(mode=QMTMode.MINI)

            # 尝试初始化
            try:
                success = await provider.initialize()
                if not success:
                    print("  [SKIP] MiniQMT 初始化失败 (需要xtquant SDK)")
                    self._record("miniqmt", "INIT", False, message="初始化失败")
                    return
            except Exception as e:
                print(f"  [SKIP] MiniQMT 初始化异常: {e}")
                self._record("miniqmt", "INIT", False, message=str(e)[:50])
                return

            print("\n[1] 行情数据能力")

            # K线数据
            try:
                result = await provider.get_kline(self.test_symbol + ".SZ", period="1d", count=10)
                if result is not None and not result.empty:
                    self._record("miniqmt", "KLINE_DATA", True, len(result))
                else:
                    self._record("miniqmt", "KLINE_DATA", False, message="无数据")
            except Exception as e:
                self._record("miniqmt", "KLINE_DATA", False, message=str(e)[:50])

            # 实时行情
            try:
                result = await provider.get_realtime_quote([self.test_symbol + ".SZ"])
                if result and len(result) > 0:
                    self._record("miniqmt", "REALTIME_QUOTE", True, len(result))
                else:
                    self._record("miniqmt", "REALTIME_QUOTE", False, message="无数据")
            except Exception as e:
                self._record("miniqmt", "REALTIME_QUOTE", False, message=str(e)[:50])

        except ImportError as e:
            print(f"  [SKIP] MiniQMT 导入失败: {e}")
        except Exception as e:
            print(f"  [ERROR] MiniQMT 测试异常: {e}")

    async def test_amazingdata(self):
        """测试 AmazingData 数据源"""
        print("\n" + "=" * 60)
        print("测试 AmazingData 数据源")
        print("=" * 60)

        try:
            from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
                AmazingDataProvider,
            )
            from deepsearch.infrastructure.providers.implementations.amazingdata.config import (
                AmazingDataConfig,
            )

            # 尝试加载配置
            try:
                import yaml

                config_path = "d:/Stock/code/deepsearch/config/settings.development.yaml"
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                ad_config = config.get("data_providers", {}).get("amazingdata", {})
                if not ad_config.get("enabled", False):
                    print("  [SKIP] AmazingData 未启用")
                    return

                provider = AmazingDataProvider(ad_config)
            except Exception as e:
                print(f"  [SKIP] AmazingData 配置加载失败: {e}")
                return

            # 尝试初始化
            try:
                success = await provider.initialize()
                if not success:
                    print("  [SKIP] AmazingData 初始化失败 (需要SDK和凭证)")
                    return
            except Exception as e:
                print(f"  [SKIP] AmazingData 初始化异常: {e}")
                return

            print("\n[1] 基础数据能力")

            # K线数据
            try:
                result = await provider.get_kline(self.test_symbol, period="1d", count=10)
                if result is not None and not result.empty:
                    self._record("amazingdata", "KLINE_DATA", True, len(result))
                else:
                    self._record("amazingdata", "KLINE_DATA", False, message="无数据")
            except Exception as e:
                self._record("amazingdata", "KLINE_DATA", False, message=str(e)[:50])

            # 关键指标
            try:
                result = await provider.get_key_indicators(self.test_symbol)
                if result is not None and not result.empty:
                    self._record("amazingdata", "KEY_INDICATORS", True, len(result))
                else:
                    self._record("amazingdata", "KEY_INDICATORS", False, message="无数据")
            except Exception as e:
                self._record("amazingdata", "KEY_INDICATORS", False, message=str(e)[:50])

            # 股东信息
            try:
                result = await provider.get_shareholder_info(self.test_symbol)
                if result:
                    self._record("amazingdata", "SHAREHOLDER_INFO", True, 1)
                else:
                    self._record("amazingdata", "SHAREHOLDER_INFO", False, message="无数据")
            except Exception as e:
                self._record("amazingdata", "SHAREHOLDER_INFO", False, message=str(e)[:50])

            # 龙虎榜
            try:
                result = await provider.get_dragon_tiger(
                    self.test_symbol,
                    start_date=(datetime.now() - timedelta(days=90)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"),
                )
                if result and len(result) > 0:
                    self._record("amazingdata", "DRAGON_TIGER", True, len(result))
                else:
                    self._record("amazingdata", "DRAGON_TIGER", False, message="无数据")
            except Exception as e:
                self._record("amazingdata", "DRAGON_TIGER", False, message=str(e)[:50])

        except ImportError as e:
            print(f"  [SKIP] AmazingData 导入失败: {e}")
        except Exception as e:
            print(f"  [ERROR] AmazingData 测试异常: {e}")

    def print_summary(self):
        """打印测试汇总"""
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)

        for source, capabilities in self.results.items():
            success_count = sum(1 for c in capabilities.values() if c["success"])
            total_count = len(capabilities)
            print(f"\n[{source.upper()}] {success_count}/{total_count} 项通过")

            for cap_name, result in capabilities.items():
                status = "OK" if result["success"] else "FAIL"
                count = result["data_count"]
                msg = result["message"]
                count_str = f"({count}条)" if count > 0 else ""
                msg_str = f" - {msg}" if msg else ""
                print(f"  {status:4} | {cap_name:20} {count_str}{msg_str}")

    async def run_all(self):
        """运行所有测试"""
        print("=" * 60)
        print("数据源能力验证测试")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"测试标的: {self.test_symbol}")
        print("=" * 60)

        await self.test_akshare()
        await self.test_miniqmt()
        await self.test_amazingdata()

        self.print_summary()


async def main():
    tester = CapabilityTester()
    await tester.run_all()


if __name__ == "__main__":
    asyncio.run(main())
