#!/usr/bin/env python
# encoding:utf-8
"""
AmazingData 枚举使用示例

展示如何在实际应用中使用枚举类型
"""

import sys
from pathlib import Path

# 获取项目根目录
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# 导入枚举（使用importlib避免SDK依赖）
import importlib.util
enum_file = project_root / "deepsearch" / "infrastructure" / "providers" / "implementations" / "amazingdata" / "amazingdata_enums_extended.py"
spec = importlib.util.spec_from_file_location("amazingdata_enums_extended", enum_file)
enums_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(enums_mod)

AmazingDataTradingPhase = enums_mod.AmazingDataTradingPhase
AmazingDataProgress = enums_mod.AmazingDataProgress
AmazingDataDivProgress = enums_mod.AmazingDataDivProgress
AmazingDataReportPeriod = enums_mod.AmazingDataReportPeriod
AmazingDataStatementType = enums_mod.AmazingDataStatementType

get_trading_phase_name = enums_mod.get_trading_phase_name
get_progress_name = enums_mod.get_progress_name
get_div_progress_name = enums_mod.get_div_progress_name
get_report_period_name = enums_mod.get_report_period_name
get_statement_type_name = enums_mod.get_statement_type_name


def example_1_trading_phase():
    """示例1: 使用交易阶段枚举"""
    print("=" * 80)
    print("示例1: 交易阶段代码解析")
    print("=" * 80)
    
    # 模拟快照数据
    mock_snapshots = [
        {"code": "000001.SZ", "last": 10.5, "trading_phase_code": "2"},
        {"code": "600000.SH", "last": 8.8, "trading_phase_code": "P"},  
        {"code": "600016.SH", "last": 5.2, "trading_phase_code": "3"},
    ]
    
    print("\n快照数据交易状态解析:")
    for snapshot in mock_snapshots:
        phase = snapshot['trading_phase_code']
        phase_name = get_trading_phase_name(phase)
        
        # 判断是否可交易
        tradable = phase == AmazingDataTradingPhase.CONTINUOUS_TRADING.value
        status = "✓ 可交易" if tradable else "✗ 不可交易"
        
        print(f"  {snapshot['code']}: {phase_name} ({phase}) - {status}")
    
    print()


def example_2_right_issue_progress():
    """示例2: 配股进度分析"""
    print("=" * 80)
    print("示例2: 配股数据进度分析")
    print("=" * 80)
    
    # 模拟配股数据
    mock_right_issues = [
        {"code": "000001.SZ", "PROGRESS": 4, "PRICE": 10.5},  # 已完成
        {"code": "000002.SZ", "PROGRESS": 5, "PRICE": 8.8},   # 证监会核准
        {"code": "600000.SH", "PROGRESS": 2, "PRICE": 6.6},   # 股东大会通过
        {"code": "600016.SH", "PROGRESS": 13, "PRICE": 5.2},  # 证监会否决
    ]
    
    print("\n配股数据进度解析:")
    for issue in mock_right_issues:
        progress = issue['PROGRESS']
        progress_name = get_progress_name(progress)
        print(f"  {issue['code']}: {progress_name} (代码:{progress})")
    
    # 筛选已完成的配股
    print("\n已完成的配股:")
    completed = [
        issue for issue in mock_right_issues
        if issue['PROGRESS'] == AmazingDataProgress.COMPLETED.value
    ]
    for issue in completed:
        print(f"  {issue['code']}: 配股价={issue['PRICE']}元")
    
    # 筛选获得监管审批的配股
    print("\n已获监管审批的配股:")
    approved_stages = {5, 6, 7, 8, 9}
    approved = [
        issue for issue in mock_right_issues
        if issue['PROGRESS'] in approved_stages
    ]
    for issue in approved:
        print(f"  {issue['code']}: {get_progress_name(issue['PROGRESS'])}")
    
    print()


def example_3_dividend_progress():
    """示例3: 分红进度分析"""
    print("=" * 80)
    print("示例3: 分红数据进度分析")
    print("=" * 80)
    
    # 模拟分红数据
    mock_dividends = [
        {"code": "000001.SZ", "DIV_PROGRESS": 4, "ratio": 0.5},   # 已完成
        {"code": "000002.SZ", "DIV_PROGRESS": 3, "ratio": 0.3},   # 实施中
        {"code": "600000.SH", "DIV_PROGRESS": 12, "ratio": 0.2},  # 停止实施
        {"code": "600016.SH", "DIV_PROGRESS": 2, "ratio": 0.4},   # 股东大会通过
    ]
    
    print("\n分红数据进度解析:")
    for div in mock_dividends:
        progress = div['DIV_PROGRESS']
        progress_name = get_div_progress_name(progress)
        print(f"  {div['code']}: {progress_name} (代码:{progress})")
    
    # 筛选已完成的分红
    print("\n已完成的分红:")
    completed = [
        div for div in mock_dividends
        if div['DIV_PROGRESS'] == AmazingDataDivProgress.COMPLETED.value
    ]
    for div in completed:
        print(f"  {div['code']}: 分红比例={div['ratio']}")
    
    # 筛选进行中的分红
    print("\n进行中的分红:")
    in_progress_stages = {1, 2, 3}
    in_progress = [
        div for div in mock_dividends
        if div['DIV_PROGRESS'] in in_progress_stages
    ]
    for div in in_progress:
        print(f"  {div['code']}: {get_div_progress_name(div['DIV_PROGRESS'])}")
    
    print()


def example_4_financial_reports():
    """示例4: 财务报表筛选"""
    print("=" * 80)
    print("示例4: 财务报表类型筛选")
    print("=" * 80)
    
    # 模拟财务报表数据
    mock_statements = [
        {"code": "000001.SZ", "REPORT_PERIOD": 1, "STATEMENT_TYPE": 1},
        {"code": "000001.SZ", "REPORT_PERIOD": 2, "STATEMENT_TYPE": 1},
        {"code": "000001.SZ", "REPORT_PERIOD": 4, "STATEMENT_TYPE": 1},
        {"code": "600000.SH", "REPORT_PERIOD": 4, "STATEMENT_TYPE": 2},
    ]
    
    print("\n报表数据解析:")
    for stmt in mock_statements:
        period_name = get_report_period_name(stmt['REPORT_PERIOD'])
        type_name = get_statement_type_name(stmt['STATEMENT_TYPE'])
        print(f"  {stmt['code']}: {period_name} - {type_name}")
    
    # 筛选年报
    print("\n年报数据:")
    annual = [
        stmt for stmt in mock_statements
        if stmt['REPORT_PERIOD'] == AmazingDataReportPeriod.ANNUAL.value
    ]
    for stmt in annual:
        print(f"  {stmt['code']}: {get_statement_type_name(stmt['STATEMENT_TYPE'])}")
    
    # 筛选合并报表
    print("\n合并报表:")
    consolidated = [
        stmt for stmt in mock_statements
        if stmt['STATEMENT_TYPE'] == AmazingDataStatementType.CONSOLIDATED_INCOME.value
    ]
    for stmt in consolidated:
        print(f"  {stmt['code']}: {get_report_period_name(stmt['REPORT_PERIOD'])}")
    
    print()


def example_5_comprehensive_analysis():
    """示例5: 综合分析"""
    print("=" * 80)
    print("示例5: 综合股票状态分析")
    print("=" * 80)
    
    # 模拟股票综合数据
    stock_data = {
        "code": "000001.SZ",
        "name": "平安银行",
        "trading_phase": "2",
        "right_issue_progress": 5,
        "div_progress": 3,
    }
    
    print(f"\n股票: {stock_data['name']} ({stock_data['code']})")
    print("-" * 60)
    
    # 交易状态
    phase_name = get_trading_phase_name(stock_data['trading_phase'])
    print(f"交易状态: {phase_name}")
    
    # 配股进度
    if stock_data.get('right_issue_progress'):
        progress_name = get_progress_name(stock_data['right_issue_progress'])
        print(f"配股进度: {progress_name}")
        
        if stock_data['right_issue_progress'] in {5, 6, 7, 8, 9}:
            print("  → 已获监管机构审批，进入实施阶段")
    
    # 分红进度
    if stock_data.get('div_progress'):
        div_progress_name = get_div_progress_name(stock_data['div_progress'])
        print(f"分红进度: {div_progress_name}")
        
        if stock_data['div_progress'] == 3:
            print("  → 分红正在实施中")
    
    print()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("AmazingData 枚举使用示例")
    print("=" * 80 + "\n")
    
    try:
        example_1_trading_phase()
        example_2_right_issue_progress()
        example_3_dividend_progress()
        example_4_financial_reports()
        example_5_comprehensive_analysis()
        
        print("=" * 80)
        print("所有示例运行完成!")
        print("=" * 80)
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
