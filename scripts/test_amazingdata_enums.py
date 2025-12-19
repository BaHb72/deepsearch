"""
测试 AmazingData 枚举类型扩展

演示如何使用新增的枚举类型：
- AmazingDataTradingPhase (交易阶段代码)
- AmazingDataReportPeriod (报告期)
- AmazingDataStatementType (报表类型)
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 直接导入枚举扩展模块（不依赖SDK）
from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_enums_extended import (
    AmazingDataTradingPhase,
    AmazingDataReportPeriod,
    AmazingDataStatementType,
    get_trading_phase_name,
    get_report_period_name,
    get_statement_type_name,
)



def test_trading_phase_enum():
    """测试交易阶段枚举"""
    print("=" * 60)
    print("测试1: 交易阶段代码枚举")
    print("=" * 60)
    
    # 测试所有交易阶段
    phases = [
        AmazingDataTradingPhase.BEFORE_OPENING,
        AmazingDataTradingPhase.OPENING_CALL_AUCTION_UNCLOSED,
        AmazingDataTradingPhase.CONTINUOUS_TRADING,
        AmazingDataTradingPhase.CLOSING_CALL_AUCTION,
        AmazingDataTradingPhase.CLOSED,
    ]
    
    for phase in phases:
        print(f"枚举: {phase.name:40s} 代码: {phase.value:3s} 说明: {get_trading_phase_name(phase.value)}")
    
    print("\n深交所特殊状态:")
    sz_phases = [
        AmazingDataTradingPhase.SZ_CLOSING,
        AmazingDataTradingPhase.SZ_VOLATILITY_INTERRUPTION,
    ]
    
    for phase in sz_phases:
        print(f"枚举: {phase.name:40s} 代码: {phase.value:3s} 说明: {get_trading_phase_name(phase.value)}")
    
    print()


def test_report_period_enum():
    """测试报告期枚举"""
    print("=" * 60)
    print("测试2: 报告期枚举")
    print("=" * 60)
    
    periods = [
        AmazingDataReportPeriod.Q1,
        AmazingDataReportPeriod.Q2,
        AmazingDataReportPeriod.Q3,
        AmazingDataReportPeriod.ANNUAL,
    ]
    
    for period in periods:
        print(f"枚举: {period.name:10s} 数值: {period.value} 说明: {get_report_period_name(period.value)}")
    
    print()


def test_statement_type_enum():
    """测试报表类型枚举"""
    print("=" * 60)
    print("测试3: 报表类型枚举（部分）")
    print("=" * 60)
    
    # 测试主要的报表类型
    statement_types = [
        AmazingDataStatementType.CONSOLIDATED_INCOME,
        AmazingDataStatementType.CONSOLIDATED_BALANCE_SHEET,
        AmazingDataStatementType.PARENT_INCOME,
        AmazingDataStatementType.CONSOLIDATED_CASH_FLOW,
        AmazingDataStatementType.PARENT_CASH_FLOW,
        AmazingDataStatementType.CONSOLIDATED_PROFIT,
        AmazingDataStatementType.EQUITY_REPORT_23,
        AmazingDataStatementType.OFFICIAL_REPORT_27,
        AmazingDataStatementType.CORRECTED_REPORT_31,
    ]
    
    for stmt_type in statement_types:
        print(f"枚举: {stmt_type.name:35s} 数值: {stmt_type.value:2d} 说明: {get_statement_type_name(stmt_type.value)}")
    
    print()


def test_enum_usage():
    """测试枚举的实际使用场景"""
    print("=" * 60)
    print("测试4: 枚举使用示例")
    print("=" * 60)
    
    # 示例1: 根据交易阶段代码判断市场状态
    phase_code = "2"  # 假设从API获取的交易阶段代码
    print(f"\n示例1: 解析交易阶段代码 '{phase_code}'")
    print(f"  状态说明: {get_trading_phase_name(phase_code)}")
    
    # 判断是否可交易
    trading_phases = {"2", "3"}  # 连续竞价和收盘集合竞价可交易
    if phase_code in trading_phases:
        print(f"  是否可交易: 是")
    else:
        print(f"  是否可交易: 否")
    
    # 示例2: 根据报告期数值判断財报类型
    report_period = 4  # 假设从API获取的报告期
    print(f"\n示例2: 解析报告期 {report_period}")
    print(f"  报告期说明: {get_report_period_name(report_period)}")
    
    # 判断是否是年报
    if report_period == AmazingDataReportPeriod.ANNUAL.value:
        print(f"  是否年报: 是")
    else:
        print(f"  是否年报: 否（季报）")
    
    # 示例3: 根据报表类型筛选合并报表
    statement_type = 1  # 假设从API获取的报表类型
    print(f"\n示例3: 解析报表类型 {statement_type}")
    print(f"  报表说明: {get_statement_type_name(statement_type)}")
    
    # 判断是否是合并报表
    consolidated_types = {1, 2, 4, 6, 8, 9, 10, 11, 13, 15, 16}
    if statement_type in consolidated_types:
        print(f"  是否合并报表: 是")
    else:
        print(f"  是否合并报表: 否（母公司报表）")
    
    print()


def test_enum_in_filter():
    """测试枚举在数据筛选中的应用"""
    print("=" * 60)
    print("测试5: 数据筛选应用示例")
    print("=" * 60)
    
    # 模拟从API获取的数据
    mock_quotes = [
        {"code": "000001.SZ", "last_price": 10.5, "trading_phase_code": "2"},
        {"code": "000002.SZ", "last_price": 15.3, "trading_phase_code": "P"},
        {"code": "600000.SH", "last_price": 8.7, "trading_phase_code": "2"},
        {"code": "600016.SH", "last_price": 12.1, "trading_phase_code": "1"},
    ]
    
    print("\n原始数据:")
    for quote in mock_quotes:
        print(f"  {quote['code']}: 价格={quote['last_price']}, 状态={quote['trading_phase_code']} ({get_trading_phase_name(quote['trading_phase_code'])})")
    
    # 筛选出正常交易的股票
    print("\n筛选正常交易的股票:")
    tradable_stocks = [
        quote for quote in mock_quotes
        if quote["trading_phase_code"] == AmazingDataTradingPhase.CONTINUOUS_TRADING.value
    ]
    
    for quote in tradable_stocks:
        print(f"  {quote['code']}: 价格={quote['last_price']}")
    
    # 筛选停牌的股票
    print("\n筛选停牌的股票:")
    suspended_stocks = [
        quote for quote in mock_quotes
        if quote["trading_phase_code"] in {
            AmazingDataTradingPhase.MARKET_CLOSED.value,
            AmazingDataTradingPhase.CONTINUOUS_TRADING_SUSPENDED.value
        }
    ]
    
    for quote in suspended_stocks:
        print(f"  {quote['code']}: {get_trading_phase_name(quote['trading_phase_code'])}")
    
    print()


def test_all_enums():
    """测试所有枚举值是否正确定义"""
    print("=" * 60)
    print("测试6: 验证所有枚举定义")
    print("=" * 60)
    
    # 验证交易阶段枚举
    print(f"\n交易阶段枚举总数: {len(AmazingDataTradingPhase)}")
    all_phase_codes = {phase.value for phase in AmazingDataTradingPhase}
    print(f"所有交易阶段代码: {sorted(all_phase_codes)}")
    
    # 验证报告期枚举
    print(f"\n报告期枚举总数: {len(AmazingDataReportPeriod)}")
    all_periods = {period.value for period in AmazingDataReportPeriod}
    print(f"所有报告期数值: {sorted(all_periods)}")
    
    # 验证报表类型枚举
    print(f"\n报表类型枚举总数: {len(AmazingDataStatementType)}")
    all_statement_types = {stmt.value for stmt in AmazingDataStatementType}
    print(f"报表类型数值范围: {min(all_statement_types)} - {max(all_statement_types)}")
    print(f"所有报表类型数值: {sorted(all_statement_types)}")
    
    print()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("AmazingData 枚举类型扩展测试")
    print("=" * 60 + "\n")
    
    test_trading_phase_enum()
    test_report_period_enum()
    test_statement_type_enum()
    test_enum_usage()
    test_enum_in_filter()
    test_all_enums()
    
    print("=" * 60)
    print("所有测试完成!")
    print("=" * 60)
