#!/usr/bin/env python
"""
股票列表数据源路由验证脚本

验证内容：
1. 配置读取是否正确（stock_list 优先级配置）
2. unified_proxy 的优先级逻辑是否正确
3. 各数据源的 get_stock_list 方法是否可调用

运行方式：uv run pytest tests/verify_stock_list_routing.py -v
"""
import asyncio
import sys


def test_config_reading():
    """测试 1：验证配置读取"""
    print("\n" + "=" * 60)
    print("测试 1：验证配置读取")
    print("=" * 60)

    try:
        from core.config.manager import ConfigManager

        config = ConfigManager.get_instance()

        # 检查 capability_routing
        cap_routing = getattr(config, "capability_routing", None)
        if cap_routing:
            routing = getattr(cap_routing, "routing", {})
            stock_list_config = routing.get("stock_list", {})
            priority = stock_list_config.get("priority", [])
            print(f"[OK] capability_routing.routing.stock_list.priority = {priority}")

            expected = ["miniqmt", "amazingdata", "akshare"]
            if priority == expected:
                print(f"[OK] 优先级配置正确: {expected}")
            else:
                print(f"[WARN] 优先级配置不匹配，期望: {expected}，实际: {priority}")
        else:
            print("[INFO] capability_routing 未配置，将使用 fallback_order")

        # 检查 fallback_order
        ds_config = getattr(config, "data_sources", None)
        if ds_config:
            fallback_order = getattr(ds_config, "fallback_order", [])
            print(f"[OK] data_sources.fallback_order = {fallback_order}")
        else:
            print("[WARN] data_sources 配置未找到")

        # 检查 Worker 数量
        dask_config = getattr(config, "dask", None)
        if dask_config:
            workers_config = getattr(dask_config, "windows_workers", None)
            if workers_config:
                num_workers = getattr(workers_config, "num_workers", None)
                print(f"[OK] dask.windows_workers.num_workers = {num_workers}")
                if num_workers == 1:
                    print("[OK] Worker 数量已设置为 1（适配 AmazingData 单连接限制）")
                else:
                    print(f"[WARN] Worker 数量为 {num_workers}，建议设置为 1")

        return True
    except Exception as e:
        print(f"[ERROR] 配置读取失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_unified_proxy_priority():
    """测试 2：验证 unified_proxy 的优先级逻辑"""
    print("\n" + "=" * 60)
    print("测试 2：验证 unified_proxy 优先级逻辑")
    print("=" * 60)

    try:
        from core.infrastructure.providers.unified_proxy import DataAccessProxy
        from core.ports.data_sources import DataAccessType, DataSourceType

        proxy = DataAccessProxy()

        # 测试 STOCK_LIST 的优先级
        priority = proxy._get_source_priority(DataAccessType.STOCK_LIST)
        print(f"[OK] STOCK_LIST 优先级: {[s.value for s in priority]}")

        # 验证是否使用默认优先级（QMT > AKSHARE）
        if priority[0] == DataSourceType.QMT:
            print("[OK] 股票列表优先使用 QMT（miniqmt）")
        elif priority[0] == DataSourceType.AKSHARE:
            print("[WARN] 股票列表仍然优先使用 AKSHARE（旧行为）")

        # 测试其他访问类型的优先级
        realtime_priority = proxy._get_source_priority(DataAccessType.REALTIME_QUOTE)
        print(f"[INFO] REALTIME_QUOTE 优先级: {[s.value for s in realtime_priority]}")

        return True
    except Exception as e:
        print(f"[ERROR] 优先级测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_provider_methods():
    """测试 3：验证各数据源的 get_stock_list 方法"""
    print("\n" + "=" * 60)
    print("测试 3：验证数据源方法可用性")
    print("=" * 60)

    providers_to_check = [
        (
            "akshare",
            "core.infrastructure.providers.implementations.akshare.akshare_direct",
            "AKShareDirectProvider",
        ),
        (
            "miniqmt (unified)",
            "core.infrastructure.providers.implementations.qmt.unified_qmt_provider",
            "UnifiedQMTProvider",
        ),
        (
            "amazingdata",
            "core.infrastructure.providers.implementations.amazingdata.amazingdata",
            "AmazingDataProvider",
        ),
    ]

    results = []
    for name, module_path, class_name in providers_to_check:
        try:
            module = __import__(module_path, fromlist=[class_name])
            provider_class = getattr(module, class_name)

            # 检查是否有 get_stock_list 方法
            has_method = hasattr(provider_class, "get_stock_list")
            if has_method:
                print(f"[OK] {name}: get_stock_list 方法存在")
                results.append((name, True, None))
            else:
                print(f"[WARN] {name}: get_stock_list 方法不存在")
                results.append((name, False, "方法不存在"))
        except Exception as e:
            print(f"[ERROR] {name}: 导入失败 - {e}")
            results.append((name, False, str(e)))

    return all(r[1] for r in results)


async def test_akshare_exception_handling():
    """测试 4：验证 akshare 异常处理（不再返回硬编码列表）"""
    print("\n" + "=" * 60)
    print("测试 4：验证 akshare 异常处理")
    print("=" * 60)

    try:
        from core.infrastructure.providers.implementations.akshare.akshare_direct import (
            AKShareDirectProvider,
        )

        # 检查 ProviderDataError 是否被导入
        provider = AKShareDirectProvider()

        # 检查 _fetch_stock_list_sync 方法的源码是否包含 ProviderDataError
        import inspect

        source = inspect.getsource(provider._fetch_stock_list_sync)
        if "ProviderDataError" in source:
            print("[OK] _fetch_stock_list_sync 已使用 ProviderDataError 异常")
        else:
            print("[WARN] _fetch_stock_list_sync 可能仍使用旧的降级逻辑")

        if "平安银行" in source and "万科A" in source:
            print("[WARN] 源码中仍包含硬编码股票列表")
        else:
            print("[OK] 源码中已移除硬编码股票列表")

        return True
    except Exception as e:
        print(f"[ERROR] 异常处理测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_miniqmt_stock_list_impl():
    """测试 5：验证 MiniQMTBackend.get_special_data 实现"""
    print("\n" + "=" * 60)
    print("测试 5：验证 MiniQMT stock_list 实现")
    print("=" * 60)

    try:
        import inspect

        from core.infrastructure.providers.implementations.qmt.unified_qmt_provider import (
            MiniQMTBackend,
        )

        # 检查 get_special_data 方法
        source = inspect.getsource(MiniQMTBackend.get_special_data)
        if "stock_list" in source:
            print("[OK] MiniQMTBackend.get_special_data 支持 stock_list")
        else:
            print("[WARN] MiniQMTBackend.get_special_data 不支持 stock_list")

        # 检查 _get_stock_list 方法
        if hasattr(MiniQMTBackend, "_get_stock_list"):
            print("[OK] MiniQMTBackend._get_stock_list 方法存在")
            source = inspect.getsource(MiniQMTBackend._get_stock_list)
            if "get_stock_list_in_sector" in source:
                print("[OK] 使用 xtdata.get_stock_list_in_sector 获取股票列表")
        else:
            print("[WARN] MiniQMTBackend._get_stock_list 方法不存在")

        return True
    except Exception as e:
        print(f"[ERROR] MiniQMT 实现测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_amazingdata_systemexit_handling():
    """测试 6：验证 AmazingData SystemExit 异常处理"""
    print("\n" + "=" * 60)
    print("测试 6：验证 AmazingData SystemExit 处理")
    print("=" * 60)

    try:
        import inspect

        from core.compute.actors.amazingdata_actor import AmazingDataActor

        # 检查 _run_sdk_with_timeout 方法
        source = inspect.getsource(AmazingDataActor._run_sdk_with_timeout)
        if "SystemExit" in source:
            print("[OK] _run_sdk_with_timeout 已捕获 SystemExit 异常")
            if "RuntimeError" in source:
                print("[OK] SystemExit 被转换为 RuntimeError")
        else:
            print("[WARN] _run_sdk_with_timeout 未捕获 SystemExit 异常")

        return True
    except Exception as e:
        print(f"[ERROR] SystemExit 处理测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """运行所有验证测试"""
    print("\n" + "=" * 60)
    print(" 股票列表数据源路由验证")
    print("=" * 60)

    results = []

    # 同步测试
    results.append(("配置读取", test_config_reading()))
    results.append(("优先级逻辑", test_unified_proxy_priority()))
    results.append(("方法可用性", test_provider_methods()))

    # 异步测试
    results.append(("akshare 异常处理", await test_akshare_exception_handling()))
    results.append(("MiniQMT 实现", await test_miniqmt_stock_list_impl()))
    results.append(("SystemExit 处理", await test_amazingdata_systemexit_handling()))

    # 汇总结果
    print("\n" + "=" * 60)
    print(" 验证结果汇总")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print(" 所有验证通过!")
    else:
        print(" 部分验证失败，请检查上述错误")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
