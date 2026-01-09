# encoding:utf-8
"""
AmazingData 枚举类型扩展

本文件定义了基于官方文档附录的额外枚举类型
可以直接导入使用，无需修改原有的 amazingdata_types.py
"""

from enum import Enum


class AmazingDataTradingPhase(Enum):
    """交易阶段代码

    根据 AmazingData 官方文档 4.1.5
    包含上市现货和深交所的交易阶段状态码
    """

    # 上市现货连续竞价交易状态
    BEFORE_OPENING = "S"  # 启动（开市前）
    OPENING_CALL_AUCTION_UNCLOSED = "O"  # 开盘集合竞价
    OPENING_CALL_AUCTION_CLOSED = "0"  # 开盘集合竞价（已闭市）
    CONTINUOUS_TRADING_NOT_TRADABLE = "T"  # 连续竞价（开市未可交易）
    CONTINUOUS_TRADING_SUSPENDED = "1"  # 连续竞价成交不可交易（未可交易，停牌）
    CONTINUOUS_TRADING = "2"  # 连续竞价
    CLOSING_CALL_AUCTION = "3"  # 收盘集合竞价
    POST_TRADING_TRANSFER = "E"  # 盘后固定价格交易
    CLOSED = "C"  # 闭市
    MARKET_CLOSED = "P"  # 停牌
    VOLATILITY_INTERRUPTION = "U"  # 波动性中断

    # 深交所现货连续竞价交易状态（部分特殊状态）
    SZ_CLOSING = "B"  # 盘中收盘集合竞价
    SZ_VOLATILITY_INTERRUPTION = "V"  # 波动性中断


class AmazingDataReportPeriod(Enum):
    """报告期名称

    根据 AmazingData 官方文档 4.1.7
    """

    Q1 = 1  # 3月
    Q2 = 2  # 6月
    Q3 = 3  # 9月
    ANNUAL = 4  # 12月


class AmazingDataStatementType(Enum):
    """报表类型代码

    根据 AmazingData 官方文档 4.1.8
    定义了36种主要报表类型
    """

    # 1-5: 合并报表
    CONSOLIDATED_INCOME = 1  # 合并报表
    CONSOLIDATED_BALANCE_SHEET = 2  # 合并报表（母子公司）
    PARENT_INCOME = 3  # 母公司报表（母子）
    CONSOLIDATED_REPORT = 4  # 合并报表（母益）
    PARENT_BALANCE_SHEET_PROFIT = 5  # 母公司报表（资正别）

    # 6-7: 现金流量表
    CONSOLIDATED_CASH_FLOW = 6  # 母公司母报表
    PARENT_CASH_FLOW = 7  # 母公司母报表（资本母义）

    # 8-10: 利润表等
    CONSOLIDATED_PROFIT_PARENT = 8  # 母公司母报表（母母度母期）
    CONSOLIDATED_PROFIT = 9  # 母公司母报表（票验）
    CONSOLIDATED_BALANCE_SHEET_PERIOD = 10  # 母公司母报表（不过母公司）

    # 11-18: 其他报表类型
    CONSOLIDATED_REPORT_11 = 11  # 合并报表（本股公司）
    PARENT_REPORT_12 = 12  # 母公司报表（母股）
    CONSOLIDATED_REPORT_13 = 13  # 合并报表（母股本公司）
    PARENT_REPORT_14 = 14  # 母公司报表（本不本股本公司）
    CONSOLIDATED_REPORT_15 = 15  # 母公司母报表（本公司）
    CONSOLIDATED_REPORT_16 = 16  # 母公司母报表（资本股母股）
    PARENT_REPORT_17 = 17  # 母公司母报表（资资股母资资股公司股本）
    PARENT_REPORT_18 = 18  # 母公司母报表（资不本股资张母资母公司股本）

    # 19-22: 准备金相关
    RESERVE_REPORT_19 = 19  # 合并报表（准益）
    SPECIAL_REPORT_20 = 20  # 母报表
    RESERVE_REPORT_21 = 21  # 母公司报表（母本股）
    RESERVE_REPORT_22 = 22  # 母公司报表（母本股度股）

    # 23-26: 股东权益相关
    EQUITY_REPORT_23 = 23  # 母公司母报表（股产）
    EQUITY_REPORT_24 = 24  # 母公司母报表（资股益）
    EQUITY_REPORT_25 = 25  # 母公司母报表（股母股母本）
    EQUITY_REPORT_26 = 26  # 母公司母报表（股母股母本季度调整）

    # 27-30: 正式报告
    OFFICIAL_REPORT_27 = 27  # 合并报表（复收正）
    OFFICIAL_REPORT_28 = 28  # 合并报表（复收正一次更正）
    OFFICIAL_REPORT_29 = 29  # 合并报告（复次更正）
    OFFICIAL_REPORT_30 = 30  # 合并报表（母不本股月本股式母公司报表不管）

    # 31-36: 更正报告
    CORRECTED_REPORT_31 = 31  # 合并财报（复次更正）
    CORRECTED_REPORT_32 = 32  # 母公司母报表（不更正，母公司母股母次更正）
    CORRECTED_REPORT_33 = 33  # 母公司母调查（不更正，母公司调整母次更正）
    CORRECTED_REPORT_34 = 34  # 母公司母报表（不更正，母公司股本数母次更正）
    CORRECTED_REPORT_35 = 35  # 母公司母报表（不更改，母公司股本数母一次更正）
    CORRECTED_REPORT_36 = 36  # 合并报表（复次更正）

    # 37-50: 更多报表类型
    STATEMENT_37 = 37  # 合并报表（复次更正）
    STATEMENT_38 = 38  # 母公司母报表（不更正，母公司股本数次更正）
    STATEMENT_39 = 39  # 母公司母调查（不更正，母公司调整母次更正）
    STATEMENT_40 = 40  # 母公司母报表（集团分股前本股公司之母公司母报表母股权按）
    STATEMENT_41 = 41  # 合并报表（已被调味股一种类型数据类（满外政情等项））
    STATEMENT_42 = 42  # 合并报表（复一次合并更新报）
    STATEMENT_43 = 43  # 合并报表（复二次合并更新报）
    STATEMENT_44 = 44  # 合并报表（复三次合并更新报）
    STATEMENT_45 = 45  # 合并报表（不更改正报，合并报表母类可及更正）
    STATEMENT_46 = 46  # 合并报表（不更改正报，合并更新母类可及更正）
    STATEMENT_47 = 47  # 母公司母报表（不更改正报，母公司股本股母次更正）
    STATEMENT_48 = 48  # 母公司母调查（不更改正报，母公司调整股母次更正）
    STATEMENT_50 = (
        50  # 合并报表（改正允许母组，诉导合并视表（剥离）母已记录数据还复号母母母本补表（报告））
    )
    STATEMENT_51 = 51  # 合并报表（下年半年报股母本）

    # 60-91: 特殊报表类型
    STATEMENT_60 = 60  # 母公司母调查（经改正母公司母并本半母公司一半同股份限按令表数据类，益先母一次没补母股数组母母本数据类）
    STATEMENT_70 = 70  # 合并报表（在股在在本上市时可股数完制的股公司母报表母记）
    STATEMENT_80 = 80  # 合并报表（预制） REITS中含合市任股以本平年股的纲限等半被投数成
    STATEMENT_81 = 81  # 合并报表（营业报前制）
    STATEMENT_90 = (
        90  # 现目货产投本 由公司货产等现目组中一频以货本投，用于股验采股投本的母公平年股型号列
    )
    STATEMENT_91 = 91  # 合并报表（E巨矩平）


class AmazingDataDivProgress(Enum):
    """股票分红进度代码

    根据 AmazingData 官方文档 4.1.9
    """

    DECLARED = 1  # 董事会预案
    SHAREHOLDER_APPROVED = 2  # 股东大会通过
    IMPLEMENTATION = 3  # 实施
    COMPLETED = 4  # 实施完成
    STOP_IMPLEMENTATION = 12  # 停止实施
    SHAREHOLDER_REJECTED = 17  # 股东大会否决
    DECLARED_NOT_IMPLEMENTATION = 19  # 董事会预案不实施


class AmazingDataProgress(Enum):
    """股票配股进度代码

    根据 AmazingData 官方文档 4.1.10
    """

    DECLARED = 1  # 董事会预案
    SHAREHOLDER_APPROVED = 2  # 股东大会通过
    IMPLEMENTATION = 3  # 实施
    COMPLETED = 4  # 实施完成
    REGULATORY_APPROVED = 5  # 证监会核准
    ISSUANCE_APPROVED = 6  # 发审委批准
    EXCHANGE_APPROVED = 7  # 交易所批准
    NDRC_APPROVED = 8  # 国家发改批准
    CSRC_APPROVED = 9  # 证券会批准
    FILING = 10  # 备案
    SUSPENSION_REVIEW = 11  # 暂缓审批
    TERMINATE = 12  # 停止实施
    REGULATORY_REJECTED = 13  # 证监会否决
    TERMINATED = 14  # 终止
    EXCHANGE_REJECTED = 15  # 交易所否决
    SHAREHOLDER_REJECTED = 16  # 股东大会否决
    SHAREHOLDER_POSTPONED = 17  # 股东大会延期
    EXCHANGE_TERMINATED = 18  # 交易所终止
    DECLARED_NOT_IMPLEMENTATION = 19  # 董事会预案不实施
    SUSPENSION_REORGANIZATION = 20  # 被暂停审批调整
    CSRC_REJECTED = 21  # 发审委否决
    SHAREHOLDER_POSTPONED_2 = 22  # 股东大会公告延迟
    REGULATORY_FILING = 23  # 证监会批准
    EXCHANGE_FILING = 24  # 交易所公告备案
    CSRC_FILING = 25  # 预发布
    RECEIVED_NOTICE = 26  # 接受注册


# 辅助函数：获取交易阶段说明
def get_trading_phase_name(code: str) -> str:
    """根据交易阶段代码获取说明

    Args:
        code: 交易阶段代码

    Returns:
        交易阶段说明
    """
    phase_map = {
        "S": "启动（开市前）",
        "O": "开盘集合竞价",
        "0": "开盘集合竞价（已闭市）",
        "T": "连续竞价（开市未可交易）",
        "1": "连续竞价成交不可交易（停牌）",
        "2": "连续竞价",
        "3": "收盘集合竞价",
        "E": "盘后固定价格交易",
        "C": "闭市/收盘处理",
        "P": "停牌",
        "U": "波动性中断/盘后交易",
        "B": "盘中收盘集合竞价",
        "V": "波动性中断（深交所）",
    }
    return phase_map.get(code, f"未知状态: {code}")


# 辅助函数：获取报告期说明
def get_report_period_name(period: int) -> str:
    """根据报告期数值获取说明

    Args:
        period: 报告期数值 (1-4)

    Returns:
        报告期说明
    """
    period_map = {
        1: "第一季度（3月）",
        2: "第二季度（6月）",
        3: "第三季度（9月）",
        4: "年报（12月）",
    }
    return period_map.get(period, f"未知报告期: {period}")


# 辅助函数：获取报表类型说明
def get_statement_type_name(statement_type: int) -> str:
    """根据报表类型数值获取说明

    Args:
        statement_type: 报表类型数值 (1-36)

    Returns:
        报表类型说明
    """
    type_map = {
        1: "合并报表",
        2: "合并报表（母子公司）",
        3: "母公司报表（母子）",
        4: "合并报表（母益）",
        5: "母公司报表（资正别）",
        6: "母公司母报表",
        7: "母公司母报表（资本母义）",
        8: "母公司母报表（母母度母期）",
        9: "母公司母报表（票验）",
        10: "母公司母报表（不过母公司）",
    }
    if statement_type in type_map:
        return type_map[statement_type]
    elif 11 <= statement_type <= 18:
        return f"其他报表类型 {statement_type}"
    elif 19 <= statement_type <= 22:
        return f"准备金相关报表 {statement_type}"
    elif 23 <= statement_type <= 26:
        return f"股东权益相关报表 {statement_type}"
    elif 27 <= statement_type <= 30:
        return f"正式报告 {statement_type}"
    elif 31 <= statement_type <= 51:
        return f"更正报告/特殊报表 {statement_type}"
    elif 60 <= statement_type <= 91:
        return f"特殊报表类型 {statement_type}"
    else:
        return f"未知报表类型: {statement_type}"


# 辅助函数：获取分红进度说明
def get_div_progress_name(progress: int) -> str:
    """根据分红进度数值获取说明

    Args:
        progress: 分红进度数值

    Returns:
        分红进度说明
    """
    progress_map = {
        1: "董事会预案",
        2: "股东大会通过",
        3: "实施",
        4: "实施完成",
        12: "停止实施",
        17: "股东大会否决",
        19: "董事会预案不实施",
    }
    return progress_map.get(progress, f"未知进度: {progress}")


# 辅助函数：获取配股进度说明
def get_progress_name(progress: int) -> str:
    """根据配股进度数值获取说明

    Args:
        progress: 配股进度数值

    Returns:
        配股进度说明
    """
    progress_map = {
        1: "董事会预案",
        2: "股东大会通过",
        3: "实施",
        4: "实施完成",
        5: "证监会核准",
        6: "发审委批准",
        7: "交易所批准",
        8: "国家发改批准",
        9: "证券会批准",
        10: "备案",
        11: "暂缓审批",
        12: "停止实施",
        13: "证监会否决",
        14: "终止",
        15: "交易所否决",
        16: "股东大会否决",
        17: "股东大会延期",
        18: "交易所终止",
        19: "董事会预案不实施",
        20: "被暂停审批调整",
        21: "发审委否决",
        22: "股东大会公告延迟",
        23: "证监会批准",
        24: "交易所公告备案",
        25: "预发布",
        26: "接受注册",
    }
    return progress_map.get(progress, f"未知进度: {progress}")
