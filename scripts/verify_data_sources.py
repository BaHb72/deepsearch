#!/usr/bin/env python
"""
数据源能力全面验证脚本
直接测试各个Provider的能力
"""
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import Any, Dict

from loguru import logger

# 配置日志级别
logger.remove()
logger.add(
    lambda msg: print(msg, end=""),
    format="<level>{level: <8}</level> | {message}",
    level="DEBUG",
)


async def test_akshare_direct_provider():
    """测试 AKShare 直连 Provider"""
    print("\n" + "=" * 60)
    print("测试 AKShareDirectProvider")
    print("=" * 60 + "\n")

    try:
        from deepsearch.infrastructure.providers.implementations.akshare.akshare_direct import (
            AKShareDirectProvider,
        )
    except ImportError as e:
        print(f"[ERROR] 无法导入 AKShareDirectProvider: {e}")
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    provider = AKShareDirectProvider()
    await provider.initialize()

    # 测试列表
    tests = [
        ("get_stock_list", lambda: provider.get_stock_list(limit=10)),
        ("get_stock_info", lambda: provider.get_stock_info("000001")),
        ("get_realtime_quote", lambda: provider.get_realtime_quote("000001")),
        ("get_realtime_quotes", lambda: provider.get_realtime_quotes(["000001", "000002"])),
        (
            "get_kline_data",
            lambda: provider.get_kline_data(
                symbol="000001",
                period="1d",
                start_date=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d"),
                limit=30,
            ),
        ),
        ("get_concept_sectors", lambda: provider.get_concept_sectors()),
        ("get_industry_sectors", lambda: provider.get_industry_sectors()),
        (
            "get_sector_stocks",
            lambda: provider.get_sector_stocks(sector_name="融资融券", sector_type="concept"),
        ),
        (
            "get_individual_capital_flow",
            lambda: provider.get_individual_capital_flow("600519", market="sh"),
        ),
        ("get_sector_capital_flow_rank", lambda: provider.get_sector_capital_flow_rank()),
        (
            "get_margin_trading",
            lambda: provider.get_margin_trading(
                start_date=(datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
            ),
        ),
        (
            "get_block_trades",
            lambda: provider.get_block_trades(
                start_date=(datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
                end_date=datetime.now().strftime("%Y%m%d"),
            ),
        ),
        ("get_northbound_flow_hist", lambda: provider.get_northbound_flow_hist()),
        (
            "get_limit_up_pool",
            lambda: provider.get_limit_up_pool(date=datetime.now().strftime("%Y%m%d")),
        ),
        (
            "get_limit_down_pool",
            lambda: provider.get_limit_down_pool(date=datetime.now().strftime("%Y%m%d")),
        ),
        (
            "get_financial_report",
            lambda: provider.get_financial_report(date="20240930"),
        ),
    ]

    for test_name, test_fn in tests:
        print(f"\n--- 测试 {test_name} ---")
        try:
            result = await test_fn()
            if result:
                count = len(result) if hasattr(result, "__len__") else 1
                sample = None
                if isinstance(result, list) and result:
                    sample = result[0]
                elif isinstance(result, dict):
                    sample = {k: v for k, v in list(result.items())[:5]}
                results[test_name] = {"success": True, "count": count, "sample": sample}
                print(f"[OK] {test_name}: 成功, 数据量={count}")
                if sample:
                    print(f"     样本: {str(sample)[:200]}...")
            else:
                results[test_name] = {"success": False, "error": "返回空数据"}
                print(f"[FAIL] {test_name}: 返回空数据")
        except Exception as e:
            results[test_name] = {"success": False, "error": str(e)}
            print(f"[ERROR] {test_name}: {e}")
            traceback.print_exc()

    await provider.close()
    return results


async def test_data_source_manager():
    """测试 DataSourceManager"""
    print("\n" + "=" * 60)
    print("测试 DataSourceManager")
    print("=" * 60 + "\n")

    try:
        from deepsearch.infrastructure.providers.managers.data_source_manager import (
            DataSourceManager,
        )
    except ImportError as e:
        print(f"[ERROR] 无法导入 DataSourceManager: {e}")
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    manager = DataSourceManager.get_instance()
    await manager.initialize()

    print(f"可用数据源: {manager.get_available_sources()}")

    # 测试列表
    tests = [
        ("get_stock_list", lambda: manager.get_stock_list(limit=10)),
        ("fetch_stock_info", lambda: manager.fetch_stock_info("000001")),
        ("get_realtime_quote", lambda: manager.get_realtime_quote("000001")),
        ("get_realtime_quotes", lambda: manager.get_realtime_quotes(["000001", "000002"])),
        (
            "get_kline_data",
            lambda: manager.get_kline_data(
                symbol="000001",
                period="1d",
                start_date=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d"),
                limit=30,
            ),
        ),
    ]

    for test_name, test_fn in tests:
        print(f"\n--- 测试 {test_name} ---")
        try:
            result = await test_fn()
            if result:
                count = len(result) if hasattr(result, "__len__") else 1
                results[test_name] = {"success": True, "count": count}
                print(f"[OK] {test_name}: 成功, 数据量={count}")
            else:
                results[test_name] = {"success": False, "error": "返回空数据"}
                print(f"[FAIL] {test_name}: 返回空数据")
        except Exception as e:
            results[test_name] = {"success": False, "error": str(e)}
            print(f"[ERROR] {test_name}: {e}")
            traceback.print_exc()

    return results


async def main():
    """主函数"""
    print("=" * 60)
    print("数据源能力全面验证")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 测试 AKShare 直连
    akshare_results = await test_akshare_direct_provider()

    # 测试 DataSourceManager
    manager_results = await test_data_source_manager()

    # 生成汇总报告
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    print("\n=== AKShareDirectProvider ===")
    success_count = sum(1 for r in akshare_results.values() if r.get("success"))
    total_count = len(akshare_results)
    print(
        f"成功率: {success_count}/{total_count} ({success_count / total_count * 100:.1f}%)"
        if total_count > 0
        else "无测试结果"
    )
    for test_name, result in akshare_results.items():
        status = "[PASS]" if result.get("success") else "[FAIL]"
        error = result.get("error", "")
        print(f"  {status} {test_name}: {error if error else 'OK'}")

    print("\n=== DataSourceManager ===")
    success_count = sum(1 for r in manager_results.values() if r.get("success"))
    total_count = len(manager_results)
    print(
        f"成功率: {success_count}/{total_count} ({success_count / total_count * 100:.1f}%)"
        if total_count > 0
        else "无测试结果"
    )
    for test_name, result in manager_results.items():
        status = "[PASS]" if result.get("success") else "[FAIL]"
        error = result.get("error", "")
        print(f"  {status} {test_name}: {error if error else 'OK'}")


if __name__ == "__main__":
    asyncio.run(main())
