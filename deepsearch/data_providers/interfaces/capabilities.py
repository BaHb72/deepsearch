"""
数据源能力映射

定义每个数据源支持的API能力，用于智能路由和数据源选择。
"""
from enum import Enum
from typing import Dict, List, Optional


class DataCapability(Enum):
    """数据能力枚举"""
    # 市场数据
    MARKET_OVERVIEW = "market_overview"  # 市场概览
    MARKET_BREADTH = "market_breadth"  # 市场宽度
    CAPITAL_FLOW = "capital_flow"  # 资金流向
    SECTOR_DATA = "sector_data"  # 板块数据
    ANOMALY_DETECTION = "anomaly_detection"  # 异动监控

    # 行情数据
    REALTIME_QUOTES = "realtime_quotes"  # 实时行情
    KLINE_DATA = "kline_data"  # K线数据
    TICK_DATA = "tick_data"  # 逐笔数据
    MINUTE_DATA = "minute_data"  # 分钟数据

    # 深度数据
    ORDER_BOOK = "order_book"  # 盘口数据
    LEVEL2_DATA = "level2_data"  # Level2数据
    TRANSACTION_DATA = "transaction_data"  # 成交明细

    # 特色数据
    CHIP_DISTRIBUTION = "chip_distribution"  # 筹码分布
    DRAGON_TIGER = "dragon_tiger"  # 龙虎榜
    BLOCK_TRADE = "block_trade"  # 大宗交易

    # 基础信息
    STOCK_INFO = "stock_info"  # 股票基本信息
    FINANCIAL_DATA = "financial_data"  # 财务数据
    ANNOUNCEMENT = "announcement"  # 公告数据
    
    # AmazingData独有数据
    MARGIN_TRADING = "margin_trading"  # 融资融券数据
    NORTH_FLOW = "north_flow"  # 北向资金流
    KEY_INDICATORS = "key_indicators"  # 关键财务指标
    SHAREHOLDER_INFO = "shareholder_info"  # 股东信息
    TRADING_CALENDAR = "trading_calendar"  # 交易日历
    ADJUSTMENT_FACTOR = "adjustment_factor"  # 复权因子
    
    # 实时订阅
    SUBSCRIPTION = "subscription"  # 实时数据订阅


# 数据源能力矩阵
DATA_SOURCE_CAPABILITIES: Dict[str, Dict[DataCapability, bool]] = {
    "amazingdata": {
        # AmazingData支持的功能
        DataCapability.MARKET_OVERVIEW: True,
        DataCapability.MARKET_BREADTH: True,
        DataCapability.CAPITAL_FLOW: True,
        DataCapability.SECTOR_DATA: True,
        DataCapability.ANOMALY_DETECTION: True,
        DataCapability.REALTIME_QUOTES: True,
        DataCapability.KLINE_DATA: True,
        DataCapability.TICK_DATA: True,
        DataCapability.MINUTE_DATA: True,
        DataCapability.ORDER_BOOK: True,
        DataCapability.LEVEL2_DATA: True,
        DataCapability.TRANSACTION_DATA: True,
        DataCapability.CHIP_DISTRIBUTION: True,
        DataCapability.DRAGON_TIGER: True,
        DataCapability.BLOCK_TRADE: True,
        DataCapability.STOCK_INFO: True,
        DataCapability.FINANCIAL_DATA: True,
        DataCapability.ANNOUNCEMENT: True,
        DataCapability.MARGIN_TRADING: True,  # 融资融券
        DataCapability.NORTH_FLOW: True,  # 北向资金
        DataCapability.KEY_INDICATORS: True,  # 关键指标
        DataCapability.SHAREHOLDER_INFO: True,  # 股东信息
        DataCapability.TRADING_CALENDAR: True,  # 交易日历
        DataCapability.ADJUSTMENT_FACTOR: True,  # 复权因子
        DataCapability.SUBSCRIPTION: True,  # 支持实时订阅
    },
    "qmt": {
        # QMT支持全部功能
        DataCapability.MARKET_OVERVIEW: True,
        DataCapability.MARKET_BREADTH: True,
        DataCapability.CAPITAL_FLOW: True,
        DataCapability.SECTOR_DATA: True,
        DataCapability.ANOMALY_DETECTION: True,
        DataCapability.REALTIME_QUOTES: True,
        DataCapability.KLINE_DATA: True,
        DataCapability.TICK_DATA: True,
        DataCapability.MINUTE_DATA: True,
        DataCapability.ORDER_BOOK: True,
        DataCapability.LEVEL2_DATA: True,
        DataCapability.TRANSACTION_DATA: True,
        DataCapability.CHIP_DISTRIBUTION: True,
        DataCapability.DRAGON_TIGER: True,
        DataCapability.BLOCK_TRADE: True,
        DataCapability.STOCK_INFO: True,
        DataCapability.FINANCIAL_DATA: True,
        DataCapability.ANNOUNCEMENT: True,
        # AmazingData独有功能（QMT不支持）
        DataCapability.MARGIN_TRADING: False,
        DataCapability.NORTH_FLOW: False,
        DataCapability.KEY_INDICATORS: False,
        DataCapability.SHAREHOLDER_INFO: False,
        DataCapability.TRADING_CALENDAR: True,  # QMT支持交易日历
        DataCapability.ADJUSTMENT_FACTOR: True,  # QMT支持复权因子
        DataCapability.SUBSCRIPTION: True,  # QMT支持实时订阅
    },
    "miniqmt": {
        # MiniQMT支持大部分功能
        DataCapability.MARKET_OVERVIEW: True,
        DataCapability.MARKET_BREADTH: True,
        DataCapability.CAPITAL_FLOW: False,  # 不支持资金流向
        DataCapability.SECTOR_DATA: True,
        DataCapability.ANOMALY_DETECTION: True,
        DataCapability.REALTIME_QUOTES: True,
        DataCapability.KLINE_DATA: True,
        DataCapability.TICK_DATA: False,  # 不支持逐笔
        DataCapability.MINUTE_DATA: True,
        DataCapability.ORDER_BOOK: True,
        DataCapability.LEVEL2_DATA: False,  # 不支持Level2
        DataCapability.TRANSACTION_DATA: False,
        DataCapability.CHIP_DISTRIBUTION: True,
        DataCapability.DRAGON_TIGER: True,
        DataCapability.BLOCK_TRADE: False,
        DataCapability.STOCK_INFO: True,
        DataCapability.FINANCIAL_DATA: True,
        DataCapability.ANNOUNCEMENT: False,
        # AmazingData独有功能（MiniQMT不支持）
        DataCapability.MARGIN_TRADING: False,
        DataCapability.NORTH_FLOW: False,
        DataCapability.KEY_INDICATORS: False,
        DataCapability.SHAREHOLDER_INFO: False,
        DataCapability.TRADING_CALENDAR: True,  # MiniQMT支持交易日历
        DataCapability.ADJUSTMENT_FACTOR: True,  # MiniQMT支持复权因子
        DataCapability.SUBSCRIPTION: True,  # MiniQMT支持实时订阅
    },
    "akshare": {
        # AkShare支持基础功能
        DataCapability.MARKET_OVERVIEW: True,  # stock_zh_index_spot_em
        DataCapability.MARKET_BREADTH: True,  # stock_zh_a_spot_em
        DataCapability.CAPITAL_FLOW: True,  # stock_em_hsgt_north_net_flow_in
        DataCapability.SECTOR_DATA: True,  # stock_sector_spot
        DataCapability.ANOMALY_DETECTION: False,  # 需要自行计算
        DataCapability.REALTIME_QUOTES: True,  # stock_zh_a_spot_em
        DataCapability.KLINE_DATA: True,  # stock_zh_a_hist
        DataCapability.TICK_DATA: False,  # 不支持
        DataCapability.MINUTE_DATA: True,  # stock_zh_a_hist_min_em
        DataCapability.ORDER_BOOK: False,  # 不支持实时盘口
        DataCapability.LEVEL2_DATA: False,  # 不支持
        DataCapability.TRANSACTION_DATA: False,  # 不支持
        DataCapability.CHIP_DISTRIBUTION: False,  # 不支持
        DataCapability.DRAGON_TIGER: True,  # stock_lhb_detail_daily_sina
        DataCapability.BLOCK_TRADE: True,  # stock_dzjy_sctj
        DataCapability.STOCK_INFO: True,  # stock_info_a_code_name
        DataCapability.FINANCIAL_DATA: True,  # stock_financial_report_sina
        DataCapability.ANNOUNCEMENT: True,  # stock_notice_report
        # AmazingData独有功能（AkShare部分支持）
        DataCapability.MARGIN_TRADING: True,  # AkShare支持融资融券
        DataCapability.NORTH_FLOW: True,  # AkShare支持北向资金
        DataCapability.KEY_INDICATORS: False,  # 不支持关键指标
        DataCapability.SHAREHOLDER_INFO: True,  # AkShare支持股东信息
        DataCapability.TRADING_CALENDAR: True,  # AkShare支持交易日历
        DataCapability.ADJUSTMENT_FACTOR: True,  # AkShare支持复权因子
        DataCapability.SUBSCRIPTION: False,  # AkShare不支持实时订阅
    }
}

# AkShare API映射表（用于具体实现）
AKSHARE_API_MAPPING = {
    DataCapability.MARKET_OVERVIEW: "stock_zh_index_spot_em",
    DataCapability.MARKET_BREADTH: "stock_zh_a_spot_em",
    DataCapability.CAPITAL_FLOW: "stock_em_hsgt_north_net_flow_in",
    DataCapability.SECTOR_DATA: "stock_sector_spot",
    DataCapability.REALTIME_QUOTES: "stock_zh_a_spot_em",
    DataCapability.KLINE_DATA: "stock_zh_a_hist",
    DataCapability.MINUTE_DATA: "stock_zh_a_hist_min_em",
    DataCapability.DRAGON_TIGER: "stock_lhb_detail_daily_sina",
    DataCapability.BLOCK_TRADE: "stock_dzjy_sctj",
    DataCapability.STOCK_INFO: "stock_info_a_code_name",
    DataCapability.FINANCIAL_DATA: "stock_financial_report_sina",
    DataCapability.ANNOUNCEMENT: "stock_notice_report",
}


def get_capable_providers(capability: DataCapability) -> List[str]:
    """
    获取支持指定能力的数据源列表
    
    Args:
        capability: 数据能力
        
    Returns:
        支持该能力的数据源名称列表（按优先级排序）
    """
    capable_providers = []

    # 按优先级顺序检查（AmazingData优先级最高）
    priority_order = ["amazingdata", "qmt", "miniqmt", "akshare"]

    for provider_name in priority_order:
        capabilities = DATA_SOURCE_CAPABILITIES.get(provider_name, {})
        if capabilities.get(capability, False):
            capable_providers.append(provider_name)

    return capable_providers


def check_provider_capability(provider_name: str, capability: DataCapability) -> bool:
    """
    检查指定数据源是否支持某个能力
    
    Args:
        provider_name: 数据源名称
        capability: 数据能力
        
    Returns:
        是否支持
    """
    capabilities = DATA_SOURCE_CAPABILITIES.get(provider_name, {})
    return capabilities.get(capability, False)


def get_akshare_api(capability: DataCapability) -> Optional[str]:
    """
    获取AkShare对应的API名称
    
    Args:
        capability: 数据能力
        
    Returns:
        AkShare API名称，如果不支持返回None
    """
    return AKSHARE_API_MAPPING.get(capability)
