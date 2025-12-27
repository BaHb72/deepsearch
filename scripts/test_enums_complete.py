#!/usr/bin/env python
# encoding:utf-8
"""
测试 AmazingData 枚举类型扩展（完整版）

测试所有枚举类型：
- AmazingDataTradingPhase (交易阶段代码)
- AmazingDataReportPeriod (报告期)
- AmazingDataStatementType (报表类型) - 扩展到91个
- AmazingDataDivProgress (股票分红进度)
- AmazingDataProgress (股票配股进度)
"""

import sys
from pathlib import Path

# 获取项目根目录
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# 导入路径
enum_file = (
    project_root
    / "deepsearch"
    / "infrastructure"
    / "providers"
    / "implementations"
    / "amazingdata"
    / "amazingdata_enums_extended.py"
)

# 加载模块
import importlib.util

spec = importlib.util.spec_from_file_location("amazingdata_enums_extended", enum_file)
enums_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(enums_mod)

# 从模块中获取需要的类和函数
AmazingDataTradingPhase = enums_mod.AmazingDataTradingPhase
AmazingDataReportPeriod = enums_mod.AmazingDataReportPeriod
AmazingDataStatementType = enums_mod.AmazingDataStatementType
AmazingDataDivProgress = enums_mod.AmazingDataDivProgress
AmazingDataProgress = enums_mod.AmazingDataProgress

get_trading_phase_name = enums_mod.get_trading_phase_name
get_report_period_name = enums_mod.get_report_period_name
get_statement_type_name = enums_mod.get_statement_type_name
get_div_progress_name = enums_mod.get_div_progress_name
get_progress_name = enums_mod.get_progress_name


def test_div_progress_enum():
    """测试股票分红进度枚举"""
    print("=" * 60)
    print("测试1: 股票分红进度枚举 (DIV_PROGRESS)")
    print("=" * 60)

    div_progresses = [
        AmazingDataDivProgress.DECLARED,
        AmazingDataDivProgress.SHAREHOLDER_APPROVED,
        AmazingDataDivProgress.IMPLEMENTATION,
        AmazingDataDivProgress.COMPLETED,
        AmazingDataDivProgress.STOP_IMPLEMENTATION,
        AmazingDataDivProgress.SHAREHOLDER_REJECTED,
        AmazingDataDivProgress.DECLARED_NOT_IMPLEMENTATION,
    ]

    for prog in div_progresses:
        print(
            f"枚举: {prog.name:35s} 数值: {prog.value:2d} 说明: {get_div_progress_name(prog.value)}"
        )

    print()


def test_progress_enum():
    """测试股票配股进度枚举"""
    print("=" * 60)
    print("测试2: 股票配股进度枚举 (PROGRESS)")
    print("=" * 60)

    progresses = [
        AmazingDataProgress.DECLARED,
        AmazingDataProgress.SHAREHOLDER_APPROVED,
        AmazingDataProgress.IMPLEMENTATION,
        AmazingDataProgress.COMPLETED,
        AmazingDataProgress.REGULATORY_APPROVED,
        AmazingDataProgress.ISSUANCE_APPROVED,
        AmazingDataProgress.FILING,
        AmazingDataProgress.SUSPENSION_REVIEW,
        AmazingDataProgress.TERMINATE,
        AmazingDataProgress.REGULATORY_REJECTED,
        AmazingDataProgress.TERMINATED,
        AmazingDataProgress.EXCHANGE_REJECTED,
        AmazingDataProgress.SHAREHOLDER_REJECTED,
        AmazingDataProgress.RECEIVED_NOTICE,
    ]

    for prog in progresses:
        print(f"枚举: {prog.name:35s} 数值: {prog.value:2d} 说明: {get_progress_name(prog.value)}")

    print()


def test_extended_statement_types():
    """测试扩展的报表类型（37-91）"""
    print("=" * 60)
    print("测试3: 扩展的报表类型（37-91）")
    print("=" * 60)

    # 测试几个扩展的报表类型
    statement_types = [
        AmazingDataStatementType.STATEMENT_37,
        AmazingDataStatementType.STATEMENT_40,
        AmazingDataStatementType.STATEMENT_50,
        AmazingDataStatementType.STATEMENT_60,
        AmazingDataStatementType.STATEMENT_70,
        AmazingDataStatementType.STATEMENT_80,
        AmazingDataStatementType.STATEMENT_90,
        AmazingDataStatementType.STATEMENT_91,
    ]

    for stmt_type in statement_types:
        print(
            f"枚举: {stmt_type.name:20s} 数值: {stmt_type.value:2d} 说明: {get_statement_type_name(stmt_type.value)}"
        )

    print()


def test_usage_scenario():
    """测试实际使用场景"""
    print("=" * 60)
    print("测试4: 实际使用场景")
    print("=" * 60)

    # 场景1: 分红进度判断
    print("\n场景1: 判断分红是否已完成")
    div_progress = 4
    print(f"  分红进度: {div_progress} - {get_div_progress_name(div_progress)}")
    if div_progress == AmazingDataDivProgress.COMPLETED.value:
        print("  状态: 分红已完成")
    elif div_progress in {12, 17, 19}:
        print("  状态: 分红已停止或否决")
    else:
        print("  状态: 分红进行中")

    # 场景2: 配股进度判断
    print("\n场景2: 判断配股审批状态")
    progress = 5
    print(f"  配股进度: {progress} - {get_progress_name(progress)}")
    approved_stages = {5, 6, 7, 8, 9}  # 各类审批通过
    if progress in approved_stages:
        print("  状态: 已获得监管审批")
    elif progress == AmazingDataProgress.COMPLETED.value:
        print("  状态: 配股已完成")
    else:
        print("  状态: 等待审批或其他")

    # 场景3: 报表类型筛选
    print("\n场景3: 筛选特殊报表类型")
    statement_types = [1, 37, 60, 80, 91]
    for st in statement_types:
        print(f"  报表类型 {st}: {get_statement_type_name(st)}")

    print()


def test_all_enums_count():
    """统计所有枚举数量"""
    print("=" * 60)
    print("测试5: 枚举类型统计")
    print("=" * 60)

    print(f"\n交易阶段枚举数量: {len(AmazingDataTradingPhase)}")
    print(f"报告期枚举数量: {len(AmazingDataReportPeriod)}")
    print(f"报表类型枚举数量: {len(AmazingDataStatementType)}")
    print(f"股票分红进度枚举数量: {len(AmazingDataDivProgress)}")
    print(f"股票配股进度枚举数量: {len(AmazingDataProgress)}")

    total = (
        len(AmazingDataTradingPhase)
        + len(AmazingDataReportPeriod)
        + len(AmazingDataStatementType)
        + len(AmazingDataDivProgress)
        + len(AmazingDataProgress)
    )

    print(f"\n总枚举值数量: {total}")

    # 显示报表类型的数值范围
    all_statement_values = {stmt.value for stmt in AmazingDataStatementType}
    print(f"\n报表类型数值范围: {min(all_statement_values)} - {max(all_statement_values)}")
    print(f"包含的数值: {sorted(all_statement_values)}")

    # 显示配股进度的数值
    all_progress_values = {prog.value for prog in AmazingDataProgress}
    print(f"\n配股进度数值: {sorted(all_progress_values)}")

    print()


def test_progress_filtering():
    """测试进度筛选"""
    print("=" * 60)
    print("测试6: 进度状态筛选")
    print("=" * 60)

    # 模拟数据
    mock_dividends = [
        {"stock": "000001.SZ", "div_date": "2024-06-30", "progress": 4},
        {"stock": "000002.SZ", "div_date": "2024-06-30", "progress": 3},
        {"stock": "600000.SH", "div_date": "2024-06-30", "progress": 12},
        {"stock": "600016.SH", "div_date": "2024-06-30", "progress": 2},
    ]

    print("\n原始分红数据:")
    for div in mock_dividends:
        print(
            f"  {div['stock']}: 日期={div['div_date']}, "
            f"进度={div['progress']} ({get_div_progress_name(div['progress'])})"
        )

    # 筛选已完成的分红
    print("\n已完成的分红:")
    completed_divs = [
        div for div in mock_dividends if div["progress"] == AmazingDataDivProgress.COMPLETED.value
    ]
    for div in completed_divs:
        print(f"  {div['stock']}: {get_div_progress_name(div['progress'])}")

    # 筛选进行中的分红
    print("\n进行中的分红:")
    in_progress_divs = [
        div
        for div in mock_dividends
        if div["progress"]
        in {
            AmazingDataDivProgress.DECLARED.value,
            AmazingDataDivProgress.SHAREHOLDER_APPROVED.value,
            AmazingDataDivProgress.IMPLEMENTATION.value,
        }
    ]
    for div in in_progress_divs:
        print(f"  {div['stock']}: {get_div_progress_name(div['progress'])}")

    # 筛选已停止的分红
    print("\n已停止/否决的分红:")
    stopped_divs = [div for div in mock_dividends if div["progress"] in {12, 17, 19}]
    for div in stopped_divs:
        print(f"  {div['stock']}: {get_div_progress_name(div['progress'])}")

    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("AmazingData 枚举类型扩展测试（完整版）")
    print("=" * 60 + "\n")

    try:
        test_div_progress_enum()
        test_progress_enum()
        test_extended_statement_types()
        test_usage_scenario()
        test_all_enums_count()
        test_progress_filtering()

        print("=" * 60)
        print("所有测试完成!")
        print("=" * 60)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback

        traceback.print_exc()
