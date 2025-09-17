# encoding:utf-8
"""
AmazingData 数据类型定义
定义 AmazingData 相关的数据结构和枚举类型
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


class AmazingDataPeriod(Enum):
    """AmazingData 周期类型"""
    TICK = "tick"  # 逐笔
    SNAPSHOT = "snapshot"  # 快照
    M1 = "1m"  # 1分钟
    M5 = "5m"  # 5分钟
    M15 = "15m"  # 15分钟
    M30 = "30m"  # 30分钟
    M60 = "60m"  # 60分钟
    DAY = "1d"  # 日线
    WEEK = "1w"  # 周线
    MONTH = "1M"  # 月线
    QUARTER = "1Q"  # 季线
    YEAR = "1Y"  # 年线


class AmazingDataAdjust(Enum):
    """复权类型"""
    NONE = "none"  # 不复权
    FORWARD = "qfq"  # 前复权
    BACKWARD = "hfq"  # 后复权


class AmazingDataMarket(Enum):
    """市场类型"""
    SH = "SH"  # 上海
    SZ = "SZ"  # 深圳
    BJ = "BJ"  # 北京
    HK = "HK"  # 香港
    US = "US"  # 美股


class AmazingDataSecurityType(Enum):
    """证券类型"""
    STOCK_A = "EXTRA_STOCK_A"  # A股
    ETF = "EXTRA_ETF"  # ETF
    KZZ = "EXTRA_KZZ"  # 可转债
    HKT = "EXTRA_HKT"  # 港股通
    INDEX = "EXTRA_INDEX"  # 指数
    FUTURE = "EXTRA_FUTURE"  # 期货
    OPTION = "EXTRA_OPTION"  # 期权


class AmazingDataReportType(Enum):
    """财务报表类型"""
    BALANCE_SHEET = "balance_sheet"  # 资产负债表
    INCOME_STATEMENT = "income_statement"  # 利润表
    CASH_FLOW = "cash_flow"  # 现金流量表
    KEY_INDICATORS = "key_indicators"  # 主要指标


@dataclass
class StockInfo:
    """股票基础信息"""
    symbol: str  # 股票代码
    name: str  # 股票名称
    market: AmazingDataMarket  # 市场
    security_type: AmazingDataSecurityType  # 证券类型
    list_date: Optional[str] = None  # 上市日期
    delist_date: Optional[str] = None  # 退市日期
    status: str = "normal"  # 状态


@dataclass
class KlineData:
    """K线数据"""
    datetime: datetime  # 时间
    open: float  # 开盘价
    high: float  # 最高价
    low: float  # 最低价
    close: float  # 收盘价
    volume: float  # 成交量
    amount: float  # 成交额
    adjust_factor: Optional[float] = None  # 复权因子
    turnover_rate: Optional[float] = None  # 换手率
    change: Optional[float] = None  # 涨跌额
    change_percent: Optional[float] = None  # 涨跌幅


@dataclass
class SnapshotData:
    """实时快照数据"""
    symbol: str  # 股票代码
    name: str  # 股票名称
    time: str  # 时间
    last_price: float  # 最新价
    open: float  # 开盘价
    high: float  # 最高价
    low: float  # 最低价
    prev_close: float  # 昨收价
    volume: float  # 成交量
    amount: float  # 成交额

    # 买卖盘
    bid_prices: List[float] = None  # 买价列表
    bid_volumes: List[float] = None  # 买量列表
    ask_prices: List[float] = None  # 卖价列表
    ask_volumes: List[float] = None  # 卖量列表

    # 涨跌信息
    change: float = 0  # 涨跌额
    change_percent: float = 0  # 涨跌幅
    amplitude: float = 0  # 振幅
    turnover_rate: float = 0  # 换手率

    # 其他
    status: str = "normal"  # 状态
    limit_up: Optional[float] = None  # 涨停价
    limit_down: Optional[float] = None  # 跌停价


@dataclass
class TickData:
    """逐笔成交数据"""
    symbol: str  # 股票代码
    time: str  # 时间
    price: float  # 成交价
    volume: int  # 成交量
    amount: float  # 成交额
    direction: str  # 方向 (B买/S卖/N中性)
    order_type: str  # 订单类型


@dataclass
class OrderData:
    """逐笔委托数据（Level2）"""
    symbol: str  # 股票代码
    time: str  # 时间
    order_id: str  # 委托号
    price: float  # 委托价
    volume: int  # 委托量
    direction: str  # 方向 (B买/S卖)
    order_type: str  # 委托类型


@dataclass
class QueueData:
    """委托队列数据（Level2）"""
    symbol: str  # 股票代码
    time: str  # 时间
    bid_queue: List[int]  # 买方队列
    ask_queue: List[int]  # 卖方队列
    bid_total: int  # 买方总量
    ask_total: int  # 卖方总量


@dataclass
class FinancialData:
    """财务数据基类"""
    symbol: str  # 股票代码
    report_date: str  # 报告期
    announce_date: str  # 公告日期
    data: Dict[str, Any]  # 具体数据


@dataclass
class ShareholderData:
    """股东数据"""
    symbol: str  # 股票代码
    report_date: str  # 报告期
    shareholder_count: int  # 股东总数
    avg_holding: float  # 户均持股
    top10_holders: List[Dict[str, Any]]  # 前十大股东
    top10_tradable: List[Dict[str, Any]]  # 前十大流通股东
    institution_holding: float  # 机构持股比例


@dataclass
class DragonTigerData:
    """龙虎榜数据"""
    symbol: str  # 股票代码
    trade_date: str  # 交易日期
    reason: str  # 上榜原因
    buy_amount: float  # 买入金额
    sell_amount: float  # 卖出金额
    net_amount: float  # 净买入
    buy_list: List[Dict[str, Any]]  # 买入席位
    sell_list: List[Dict[str, Any]]  # 卖出席位


@dataclass
class MarginTradingData:
    """融资融券数据"""
    symbol: str  # 股票代码
    trade_date: str  # 交易日期
    margin_balance: float  # 融资余额
    margin_buy: float  # 融资买入
    margin_repay: float  # 融资偿还
    short_balance: float  # 融券余额
    short_sell: float  # 融券卖出
    short_repay: float  # 融券偿还
    margin_ratio: float  # 融资融券比例


@dataclass
class NorthFlowData:
    """北向资金数据"""
    trade_date: str  # 交易日期
    sh_buy: float  # 沪股通买入
    sh_sell: float  # 沪股通卖出
    sh_net: float  # 沪股通净买入
    sz_buy: float  # 深股通买入
    sz_sell: float  # 深股通卖出
    sz_net: float  # 深股通净买入
    total_net: float  # 合计净买入
    accumulated_net: float  # 累计净买入


# 数据字段映射
FIELD_MAPPING = {
    # K线字段映射
    'kline': {
        'time': 'datetime',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'close': 'close',
        'volume': 'volume',
        'amount': 'amount',
        'turnover': 'turnover_rate',
        'change': 'change',
        'change_rate': 'change_percent'
    },
    # 快照字段映射
    'snapshot': {
        'code': 'symbol',
        'name': 'name',
        'time': 'time',
        'last': 'last_price',
        'open': 'open',
        'high': 'high',
        'low': 'low',
        'pre_close': 'prev_close',
        'volume': 'volume',
        'amount': 'amount',
        'bid1': 'bid1',
        'bid1_volume': 'bid1_volume',
        'ask1': 'ask1',
        'ask1_volume': 'ask1_volume'
    }
}


def convert_period(period: str) -> str:
    """
    转换周期格式
    
    Args:
        period: 系统周期格式
        
    Returns:
        AmazingData 周期格式
    """
    period_map = {
        '1m': AmazingDataPeriod.M1.value,
        '5m': AmazingDataPeriod.M5.value,
        '15m': AmazingDataPeriod.M15.value,
        '30m': AmazingDataPeriod.M30.value,
        '60m': AmazingDataPeriod.M60.value,
        '1d': AmazingDataPeriod.DAY.value,
        '1w': AmazingDataPeriod.WEEK.value,
        '1M': AmazingDataPeriod.MONTH.value
    }
    return period_map.get(period, period)


def convert_adjust(adjust: str) -> str:
    """
    转换复权类型
    
    Args:
        adjust: 系统复权类型
        
    Returns:
        AmazingData 复权类型
    """
    adjust_map = {
        'none': AmazingDataAdjust.NONE.value,
        'qfq': AmazingDataAdjust.FORWARD.value,
        'hfq': AmazingDataAdjust.BACKWARD.value
    }
    return adjust_map.get(adjust, adjust)


def parse_symbol(symbol: str) -> tuple:
    """
    解析股票代码
    
    Args:
        symbol: 股票代码 (如 '000001.SZ')
        
    Returns:
        (code, market) 元组
    """
    if '.' in symbol:
        code, market = symbol.split('.')
        return code, market
    else:
        # 根据代码判断市场
        if symbol.startswith('60') or symbol.startswith('68'):
            return symbol, 'SH'
        elif symbol.startswith('00') or symbol.startswith('30'):
            return symbol, 'SZ'
        elif symbol.startswith('8') or symbol.startswith('4'):
            return symbol, 'BJ'
        else:
            return symbol, 'SZ'  # 默认深圳


def format_symbol(code: str, market: str = None) -> str:
    """
    格式化股票代码
    
    Args:
        code: 股票代码
        market: 市场
        
    Returns:
        格式化的股票代码
    """
    if market:
        return f"{code}.{market}"
    else:
        _, market = parse_symbol(code)
        return f"{code}.{market}"
