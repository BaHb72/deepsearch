#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AmazingData SDK 全接口最小探针测试

目的: 使用最小数据量逐一测试 SDK 全部非订阅接口，检测版本更新后的兼容性问题。
策略: 每个接口仅请求 1 只股票 / 极短日期范围，减少流量消耗。

用法:
    cd D:\\Stock\\code\\deepsearch
    python tests/integration/amazingdata/test_amazingdata_api_probe.py
"""

from __future__ import annotations

import inspect
import os
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# --- 路径设置 ---
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "packages"))

# --- 测试常量 (最小化) ---
TEST_STOCK = "000001.SZ"  # 平安银行 - 沪深市场最稳定的测试股
TEST_SH_STOCK = "600036.SH"  # 招商银行
TEST_CODE_LIST = [TEST_STOCK]
TEST_DATE_END = int(datetime.now().strftime("%Y%m%d"))
TEST_DATE_START = int((datetime.now() - timedelta(days=7)).strftime("%Y%m%d"))
# 用较远的日期范围保证有数据 (财务报表按季度发布)
FIN_DATE_START = int((datetime.now() - timedelta(days=365)).strftime("%Y%m%d"))
LOCAL_CACHE_PATH = os.path.join(_PROJECT_ROOT, ".cache", "amazingdata_test")


@dataclass
class ProbeResult:
    """单接口探针结果"""

    module: str
    method: str
    status: str  # OK / FAIL / WARN / SKIP
    elapsed: float = 0.0
    message: str = ""
    data_type: str = ""
    data_size: int = 0
    error_detail: str = ""


@dataclass
class ProbeReport:
    """探针报告"""

    results: list[ProbeResult] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    def add(self, r: ProbeResult) -> None:
        self.results.append(r)

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"OK": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
        for r in self.results:
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts


def _describe(data: object) -> tuple[str, int]:
    """返回 (数据类型描述, 大小)"""
    if data is None:
        return "None", 0
    try:
        import pandas as pd

        if isinstance(data, pd.DataFrame):
            return f"DataFrame({data.shape[0]}x{data.shape[1]})", data.shape[0]
    except ImportError:
        pass
    if isinstance(data, dict):
        return f"dict(keys={len(data)})", len(data)
    if isinstance(data, (list, tuple)):
        return f"{type(data).__name__}(len={len(data)})", len(data)
    return type(data).__name__, 1


def _safe_probe(
    module_name: str,
    method_name: str,
    call_fn,
    *,
    expect_nonempty: bool = True,
) -> ProbeResult:
    """安全执行一次探针调用"""
    t0 = time.time()
    try:
        result = call_fn()
        elapsed = time.time() - t0
        dtype, dsize = _describe(result)

        if result is None and expect_nonempty:
            return ProbeResult(
                module=module_name,
                method=method_name,
                status="WARN",
                elapsed=elapsed,
                message="返回 None",
                data_type=dtype,
                data_size=dsize,
            )

        # 检查 DataFrame 是否为空
        try:
            import pandas as pd

            if isinstance(result, pd.DataFrame) and result.empty and expect_nonempty:
                return ProbeResult(
                    module=module_name,
                    method=method_name,
                    status="WARN",
                    elapsed=elapsed,
                    message="返回空 DataFrame",
                    data_type=dtype,
                    data_size=0,
                )
        except ImportError:
            pass

        return ProbeResult(
            module=module_name,
            method=method_name,
            status="OK",
            elapsed=elapsed,
            message="",
            data_type=dtype,
            data_size=dsize,
        )
    except Exception as e:
        elapsed = time.time() - t0
        tb = traceback.format_exc()
        return ProbeResult(
            module=module_name,
            method=method_name,
            status="FAIL",
            elapsed=elapsed,
            message=str(e),
            error_detail=tb,
        )


# ========================================================================
#  加载配置
# ========================================================================


def load_credentials() -> dict:
    """从项目 Settings 加载 AmazingData 凭证"""
    from core.config import get_config

    config = get_config()
    ds = config.data_sources
    if ds is None:
        raise RuntimeError("data_sources 配置不存在")

    ad_provider = ds.get_provider("amazingdata")
    if ad_provider is None or not ad_provider.enabled:
        raise RuntimeError("AmazingData 未启用")

    cfg = ad_provider.config
    if isinstance(cfg, dict):
        conn = cfg.get("connection", {})
    else:
        conn = getattr(cfg, "connection", {})
        if not isinstance(conn, dict):
            conn = conn.__dict__ if hasattr(conn, "__dict__") else {}

    return {
        "username": conn.get("username", ""),
        "password": conn.get("password", ""),
        "host": conn.get("host", "101.230.159.234"),
        "port": conn.get("port", 8600),
    }


# ========================================================================
#  主测试逻辑
# ========================================================================


def run_all_probes() -> ProbeReport:
    """执行全部接口探针"""
    report = ProbeReport(start_time=time.time())

    # ---- 0. 加载配置 ----
    print("=" * 72)
    print("AmazingData SDK 全接口探针测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 72)

    try:
        creds = load_credentials()
        print(f"  服务器: {creds['host']}:{creds['port']}")
        print(f"  用户名: ***{creds['username'][-4:]}")
    except Exception as e:
        print(f"  [FAIL] 配置加载失败: {e}")
        return report

    # ---- 1. SDK 导入 ----
    print("\n--- SDK 导入 ---")
    try:
        import AmazingData as ad

        ver = getattr(ad, "__version__", "unknown")
        print(f"  SDK 版本: {ver}")
        print(f"  SDK 路径: {getattr(ad, '__file__', 'unknown')}")
    except ImportError as e:
        print(f"  [FAIL] SDK 未安装: {e}")
        return report

    # 应用 SDK v1.0.4 bug 修复补丁
    try:
        from core.infrastructure.providers.implementations.amazingdata.sdk_patches import (
            apply_sdk_patches,
        )

        patches = apply_sdk_patches()
        if patches:
            print(f"  SDK 补丁已应用: {', '.join(patches)}")
    except Exception as e:
        print(f"  [WARN] SDK 补丁加载失败: {e}")

    # ---- 2. 登录 ----
    print("\n--- 登录 ---")
    r = _safe_probe(
        "SDK",
        "login",
        lambda: ad.login(
            username=creds["username"],
            password=creds["password"],
            host=creds["host"],
            port=creds["port"],
        ),
    )
    report.add(r)
    _print_probe(r)

    if r.status == "FAIL":
        print("  登录失败，终止测试")
        report.end_time = time.time()
        return report

    # ---- 3. BaseData ----
    print("\n--- BaseData ---")
    base = ad.BaseData()

    # get_calendar (无参数)
    calendar = None
    r = _safe_probe("BaseData", "get_calendar", lambda: base.get_calendar())
    report.add(r)
    _print_probe(r)
    if r.status == "OK":
        # 缓存日历供后续 MarketData 使用
        calendar = base.get_calendar()

    # get_code_list
    r = _safe_probe(
        "BaseData", "get_code_list", lambda: base.get_code_list(security_type="EXTRA_STOCK_A")
    )
    report.add(r)
    _print_probe(r)

    # get_code_info
    r = _safe_probe(
        "BaseData", "get_code_info", lambda: base.get_code_info(security_type="EXTRA_STOCK_A")
    )
    report.add(r)
    _print_probe(r)

    # get_backward_factor (1 只股票)
    r = _safe_probe(
        "BaseData",
        "get_backward_factor",
        lambda: base.get_backward_factor(code_list=TEST_CODE_LIST),
    )
    report.add(r)
    _print_probe(r)

    # get_adj_factor - SDK v1.0.4 已移除
    r = ProbeResult(
        module="BaseData", method="get_adj_factor", status="SKIP", message="SDK v1.0.4 已移除此方法"
    )
    report.add(r)
    _print_probe(r)

    # get_hist_code_list (短日期范围)
    os.makedirs(LOCAL_CACHE_PATH, exist_ok=True)
    r = _safe_probe(
        "BaseData",
        "get_hist_code_list",
        lambda: base.get_hist_code_list(
            security_type="EXTRA_STOCK_A_SH_SZ",
            start_date=TEST_DATE_START,
            end_date=TEST_DATE_END,
            local_path=LOCAL_CACHE_PATH,
        ),
    )
    report.add(r)
    _print_probe(r)

    # get_future_code_list - SDK v1.0.4 已移除
    r = ProbeResult(
        module="BaseData",
        method="get_future_code_list",
        status="SKIP",
        message="SDK v1.0.4 已移除此方法",
    )
    report.add(r)
    _print_probe(r)

    # get_option_code_list - SDK v1.0.4 已移除
    r = ProbeResult(
        module="BaseData",
        method="get_option_code_list",
        status="SKIP",
        message="SDK v1.0.4 已移除此方法",
    )
    report.add(r)
    _print_probe(r)

    # ---- 4. MarketData ----
    print("\n--- MarketData ---")
    try:
        mkt = ad.MarketData(calendar) if calendar else ad.MarketData()
    except Exception as e:
        print(f"  [FAIL] MarketData 初始化失败: {e}")
        mkt = None

    if mkt is not None:
        # query_snapshot (1 只股票, 1 天)
        r = _safe_probe(
            "MarketData",
            "query_snapshot",
            lambda: mkt.query_snapshot(
                TEST_CODE_LIST, begin_date=TEST_DATE_END, end_date=TEST_DATE_END
            ),
        )
        report.add(r)
        _print_probe(r)

        # query_kline (1 只股票, 7 天, 日K)
        # SDK v1.0.4: period 参数改为整数枚举，10008=day
        r = _safe_probe(
            "MarketData",
            "query_kline",
            lambda: mkt.query_kline(
                TEST_CODE_LIST, begin_date=TEST_DATE_START, end_date=TEST_DATE_END, period=10008
            ),
        )
        report.add(r)
        _print_probe(r)

    # ---- 5. InfoData ----
    print("\n--- InfoData ---")
    info = ad.InfoData()

    # 反射检查 InfoData 实际方法签名，以确定每个接口的参数
    def _call_info(method_name: str, **kwargs):
        func = getattr(info, method_name)
        return func(**kwargs)

    # --- 5.1 基础信息 ---
    # get_stock_basic - SDK v1.0.4 已移除
    r = ProbeResult(
        module="InfoData",
        method="get_stock_basic",
        status="SKIP",
        message="SDK v1.0.4 已移除此方法",
    )
    report.add(r)
    _print_probe(r)

    info_basic_tests = [
        ("get_history_stock_status", {"code_list": TEST_CODE_LIST}),
        ("get_bj_code_mapping", {}),
    ]

    for method_name, kwargs in info_basic_tests:
        if not hasattr(info, method_name):
            report.add(
                ProbeResult(
                    module="InfoData", method=method_name, status="SKIP", message="方法不存在"
                )
            )
            _print_probe(report.results[-1])
            continue
        r = _safe_probe("InfoData", method_name, lambda m=method_name, k=kwargs: _call_info(m, **k))
        report.add(r)
        _print_probe(r)

    # --- 5.2 财务报表 (local_path + is_local 模式) ---
    finance_tests = [
        "get_balance_sheet",
        "get_cash_flow",
        "get_income",
    ]

    for method_name in finance_tests:
        if not hasattr(info, method_name):
            report.add(
                ProbeResult(
                    module="InfoData", method=method_name, status="SKIP", message="方法不存在"
                )
            )
            _print_probe(report.results[-1])
            continue
        r = _safe_probe(
            "InfoData", method_name, lambda m=method_name: _call_info(m, code_list=TEST_CODE_LIST)
        )
        report.add(r)
        _print_probe(r)

    # --- 5.3 业绩 ---
    # SDK v1.0.4: begin_date/end_date 参数已移除，改为 (code_list, local_path, is_local)
    perf_tests = [
        "get_profit_express",
        "get_profit_notice",
    ]

    for method_name in perf_tests:
        if not hasattr(info, method_name):
            report.add(
                ProbeResult(
                    module="InfoData", method=method_name, status="SKIP", message="方法不存在"
                )
            )
            _print_probe(report.results[-1])
            continue
        r = _safe_probe(
            "InfoData", method_name, lambda m=method_name: _call_info(m, code_list=TEST_CODE_LIST)
        )
        report.add(r)
        _print_probe(r)

    # --- 5.4 股东/股权 ---
    shareholder_tests = [
        "get_share_holder",
        "get_holder_num",
        "get_equity_structure",
        "get_equity_pledge_freeze",
        "get_equity_restricted",
    ]

    for method_name in shareholder_tests:
        if not hasattr(info, method_name):
            report.add(
                ProbeResult(
                    module="InfoData", method=method_name, status="SKIP", message="方法不存在"
                )
            )
            _print_probe(report.results[-1])
            continue
        r = _safe_probe(
            "InfoData", method_name, lambda m=method_name: _call_info(m, code_list=TEST_CODE_LIST)
        )
        report.add(r)
        _print_probe(r)

    # --- 5.5 交易异动 ---
    # SDK v1.0.4: 签名统一改为 (code_list, local_path, is_local)
    # get_margin_summary 特殊: 无 code_list 参数，签名为 (local_path, is_local)
    trading_tests = [
        ("get_dividend", {"code_list": TEST_CODE_LIST}),
        ("get_margin_summary", {}),  # 无 code_list
        ("get_long_hu_bang", {"code_list": TEST_CODE_LIST}),
        ("get_block_trading", {"code_list": TEST_CODE_LIST}),
    ]

    for method_name, kwargs in trading_tests:
        if not hasattr(info, method_name):
            report.add(
                ProbeResult(
                    module="InfoData", method=method_name, status="SKIP", message="方法不存在"
                )
            )
            _print_probe(report.results[-1])
            continue
        r = _safe_probe("InfoData", method_name, lambda m=method_name, k=kwargs: _call_info(m, **k))
        report.add(r)
        _print_probe(r)

    # --- 5.6 已通过 sdk_patches.py monkey-patch 修复的接口 ---
    # get_right_issue: SDK v1.0.4 bug (列名 KeyError) 已修复 -> 正常测试
    if hasattr(info, "get_right_issue"):
        r = _safe_probe(
            "InfoData",
            "get_right_issue",
            lambda: _call_info("get_right_issue", code_list=TEST_CODE_LIST),
        )
    else:
        r = ProbeResult(
            module="InfoData", method="get_right_issue", status="SKIP", message="方法不存在"
        )
    report.add(r)
    _print_probe(r)

    # get_margin_detail: SDK v1.0.4 bug (大小写+路径) 已修复 -> 正常测试
    if hasattr(info, "get_margin_detail"):
        r = _safe_probe(
            "InfoData",
            "get_margin_detail",
            lambda: _call_info("get_margin_detail", code_list=TEST_CODE_LIST),
        )
    else:
        r = ProbeResult(
            module="InfoData", method="get_margin_detail", status="SKIP", message="方法不存在"
        )
    report.add(r)
    _print_probe(r)

    # ---- 6. 方法发现：列出 SDK 对象的全部公开方法 ----
    print("\n--- SDK 方法发现 ---")
    _discover_methods("BaseData", base)
    if mkt is not None:
        _discover_methods("MarketData", mkt)
    _discover_methods("InfoData", info)

    # ---- 7. 登出 ----
    print("\n--- 登出 ---")
    try:
        ad.logout()
        print("  [OK] 已登出")
    except Exception as e:
        print(f"  [WARN] 登出异常: {e}")

    report.end_time = time.time()
    return report


def _discover_methods(name: str, obj: object) -> None:
    """列出 SDK 对象的全部公开方法"""
    methods = sorted(
        m for m in dir(obj) if not m.startswith("_") and callable(getattr(obj, m, None))
    )
    print(f"  {name}: {len(methods)} 个方法")
    for m in methods:
        func = getattr(obj, m)
        try:
            sig = inspect.signature(func)
            params = ", ".join(str(p) for p in sig.parameters.values())
        except (ValueError, TypeError):
            params = "?"
        print(f"    - {m}({params})")


def _print_probe(r: ProbeResult) -> None:
    """打印单条探针结果"""
    icon = {"OK": "[OK]  ", "FAIL": "[FAIL]", "WARN": "[WARN]", "SKIP": "[SKIP]"}
    tag = icon.get(r.status, "[?]   ")
    timing = f"{r.elapsed:.2f}s" if r.elapsed > 0 else ""
    detail = ""
    if r.data_type:
        detail = f" -> {r.data_type}"
    if r.message:
        detail += f" | {r.message}"
    print(f"  {tag} {r.module}.{r.method} {timing}{detail}")


def print_final_report(report: ProbeReport) -> None:
    """打印最终汇总报告"""
    print("\n" + "=" * 72)
    print("汇总报告")
    print("=" * 72)

    total_time = report.end_time - report.start_time
    counts = report.summary()
    total = len(report.results)

    print(f"  总耗时: {total_time:.1f}s")
    print(f"  接口总数: {total}")
    print(f"  OK:   {counts['OK']}")
    print(f"  FAIL: {counts['FAIL']}")
    print(f"  WARN: {counts['WARN']}")
    print(f"  SKIP: {counts['SKIP']}")

    if counts["OK"] > 0:
        rate = counts["OK"] / max(total - counts["SKIP"], 1) * 100
        print(f"  通过率: {rate:.0f}%")

    # 打印失败详情
    failures = [r for r in report.results if r.status == "FAIL"]
    if failures:
        print(f"\n--- 失败详情 ({len(failures)} 个) ---")
        for r in failures:
            print(f"\n  [{r.module}.{r.method}]")
            print(f"    错误: {r.message}")
            if r.error_detail:
                # 只打印最后 5 行 traceback
                lines = r.error_detail.strip().split("\n")
                for line in lines[-5:]:
                    print(f"    {line}")

    # 打印警告详情
    warnings = [r for r in report.results if r.status == "WARN"]
    if warnings:
        print(f"\n--- 警告详情 ({len(warnings)} 个) ---")
        for r in warnings:
            print(f"  [{r.module}.{r.method}] {r.message}")

    print("\n" + "=" * 72)


if __name__ == "__main__":
    report = run_all_probes()
    print_final_report(report)
