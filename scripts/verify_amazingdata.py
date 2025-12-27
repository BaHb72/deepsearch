#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData 数据源能力验证脚本
"""

import asyncio
import sys
from datetime import datetime, timedelta
from typing import Any, Dict

sys.path.insert(0, "d:/Stock/code/deepsearch")


class AmazingDataTester:
    """AmazingData 能力测试器"""

    def __init__(self):
        self.results: Dict[str, Dict[str, Any]] = {}
        self.test_symbol = "000001"  # 平安银行

    def _record(
        self,
        capability: str,
        success: bool,
        data_count: int = 0,
        message: str = "",
        sample: Any = None,
    ):
        """记录测试结果"""
        self.results[capability] = {
            "success": success,
            "data_count": data_count,
            "message": message,
        }

        status = "OK" if success else "FAIL"
        count_str = f"({data_count}条)" if data_count > 0 else ""
        print(f"  [{status}] {capability} {count_str} {message}")

    async def test_amazingdata(self):
        """测试 AmazingData 数据源"""
        print("=" * 60)
        print("测试 AmazingData 数据源")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"测试标的: {self.test_symbol}")
        print("=" * 60)

        try:
            from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata import (
                AmazingDataProvider,
            )

            # 直接使用提供的凭证
            config = {
                "name": "amazingdata",
                "enabled": True,
                "username": "212200038719",
                "password": "212200038719@2025",
                "host": "101.230.159.234",
                "port": 8600,
                "timeout": 30,
                "subscription_enabled": False,
            }

            print("\n[0] 初始化连接...")
            provider = AmazingDataProvider(config)

            try:
                success = await provider.initialize()
                if not success:
                    print("  [FAIL] 初始化失败")
                    return
                print("  [OK] 初始化成功")
            except Exception as e:
                print(f"  [FAIL] 初始化异常: {e}")
                return

            print("\n[1] 基础行情能力")

            # K线数据
            try:
                result = await provider.get_kline(self.test_symbol, period="1d", count=10)
                if result is not None and not result.empty:
                    self._record("KLINE_DATA", True, len(result))
                else:
                    self._record("KLINE_DATA", False, message="无数据")
            except Exception as e:
                self._record("KLINE_DATA", False, message=str(e)[:60])

            print("\n[2] 财务数据能力")

            # 关键指标
            try:
                result = await provider.get_key_indicators(self.test_symbol)
                if result is not None and not result.empty:
                    self._record("KEY_INDICATORS", True, len(result))
                else:
                    self._record("KEY_INDICATORS", False, message="无数据")
            except Exception as e:
                self._record("KEY_INDICATORS", False, message=str(e)[:60])

            # 股东信息
            try:
                result = await provider.get_shareholder_info(self.test_symbol)
                if result:
                    self._record("SHAREHOLDER_INFO", True, 1)
                else:
                    self._record("SHAREHOLDER_INFO", False, message="无数据")
            except Exception as e:
                self._record("SHAREHOLDER_INFO", False, message=str(e)[:60])

            print("\n[3] 特色数据能力")

            # 龙虎榜
            try:
                result = await provider.get_dragon_tiger(
                    self.test_symbol,
                    start_date=(datetime.now() - timedelta(days=90)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d"),
                )
                if result and len(result) > 0:
                    self._record("DRAGON_TIGER", True, len(result))
                else:
                    self._record("DRAGON_TIGER", False, message="无数据")
            except Exception as e:
                self._record("DRAGON_TIGER", False, message=str(e)[:60])

            # 停止provider
            try:
                await provider.stop_async()
            except Exception:
                pass

        except ImportError as e:
            print(f"  [SKIP] AmazingData 导入失败: {e}")
        except Exception as e:
            print(f"  [ERROR] AmazingData 测试异常: {e}")

    def print_summary(self):
        """打印测试汇总"""
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)

        success_count = sum(1 for c in self.results.values() if c["success"])
        total_count = len(self.results)
        print(f"\n[AMAZINGDATA] {success_count}/{total_count} 项通过")

        for cap_name, result in self.results.items():
            status = "OK" if result["success"] else "FAIL"
            count = result["data_count"]
            msg = result["message"]
            count_str = f"({count}条)" if count > 0 else ""
            msg_str = f" - {msg}" if msg else ""
            print(f"  {status:4} | {cap_name:20} {count_str}{msg_str}")

    async def run(self):
        """运行测试"""
        await self.test_amazingdata()
        self.print_summary()


async def main():
    tester = AmazingDataTester()
    await tester.run()


if __name__ == "__main__":
    asyncio.run(main())
