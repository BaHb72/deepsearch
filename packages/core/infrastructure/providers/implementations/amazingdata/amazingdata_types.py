# encoding:utf-8
"""
AmazingData 数据类型定义
定义 AmazingData 相关的数据结构和枚举类型
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, TypeAlias, TypedDict, Union


class AmazingDataStreamQuote(TypedDict, total=False):
    """Typed representation of AmazingData realtime quote payloads."""

    code: str
    symbol: str
    name: str
    exchange: str
    time: Union[str, int, float, datetime]
    price: Union[str, int, float]
    last: Union[str, int, float]
    last_price: Union[str, int, float]
    open: Union[str, int, float]
    high: Union[str, int, float]
    low: Union[str, int, float]
    pre_close: Union[str, int, float]
    prev_close: Union[str, int, float]
    amount: Union[str, int, float]
    volume: Union[str, int, float]
    num_trades: Union[str, int, float]
    trade_num: Union[str, int, float]
    bid: Sequence[Any]
    bid_prices: Sequence[Any]
    ask: Sequence[Any]
    ask_prices: Sequence[Any]
    bid_volume: Sequence[Any]
    bid_volumes: Sequence[Any]
    ask_volume: Sequence[Any]
    ask_volumes: Sequence[Any]
    high_limit: Union[str, int, float]
    upper_limit: Union[str, int, float]
    low_limit: Union[str, int, float]
    lower_limit: Union[str, int, float]
    trading_phase: str
    status: str


class AmazingDataStreamPayload(TypedDict, total=False):
    """Envelope emitted by AmazingData streaming handlers."""

    timestamp: datetime
    period: str
    data: AmazingDataStreamQuote


RealtimeQuoteMap: TypeAlias = Mapping[str, AmazingDataStreamQuote]


class AmazingDataPeriod(Enum):
    """AmazingData 数据周期"""

    TICK = "tick"
    SNAPSHOT = "snapshot"
    SNAPSHOT_FUTURE = "snapshot_future"
    SNAPSHOT_HKT = "snapshot_hkt"
    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M10 = "10m"
    M15 = "15m"
    M30 = "30m"
    M60 = "60m"
    M120 = "120m"
    DAY = "1d"
    WEEK = "1w"
    MONTH = "1M"
    QUARTER = "1Q"
    YEAR = "1Y"


class AmazingDataAdjust(Enum):
    """复权类型"""

    NONE = "none"  # 不复权
    FORWARD = "qfq"  # 前复权
    BACKWARD = "hfq"  # 后复权


class AmazingDataMarket(Enum):
    """市场类型 (SDK 4.1.4)"""

    # 股票市场
    SH = "SH"  # 上交所
    SZ = "SZ"  # 深交所
    BJ = "BJ"  # 北交所
    # 期货交易所
    SHF = "SHF"  # 上期所
    CFE = "CFE"  # 中金所
    DCE = "DCE"  # 大商所
    CZC = "CZC"  # 郑商所
    INE = "INE"  # 上海国际能源交易中心所
    # 港股通
    SHN = "SHN"  # 沪港通
    SZN = "SZN"  # 深港通
    HK = "HK"  # 港交所


class AmazingDataSecurityType(Enum):
    """证券类型 (SDK 4.1.1-4.1.3)"""

    # === 4.1.1 沪深北 A 股 ===
    # 单独市场 A 股
    SH_A = "SH_A"  # 上交所A股
    SZ_A = "SZ_A"  # 深交所A股
    BJ_A = "BJ_A"  # 北交所A股
    # 组合市场 A 股
    STOCK_A = "EXTRA_STOCK_A"  # 沪深北A股
    STOCK_A_SH_SZ = "EXTRA_STOCK_A_SH_SZ"  # 沪深A股（不含北交所）
    # 指数
    INDEX_A = "EXTRA_INDEX_A"  # 沪深北指数
    INDEX_A_SH_SZ = "EXTRA_INDEX_A_SH_SZ"  # 沪深指数
    SH_INDEX = "SH_INDEX"  # 上交所指数
    SZ_INDEX = "SZ_INDEX"  # 深交所指数
    BJ_INDEX = "BJ_INDEX"  # 北交所指数
    # ETF
    ETF = "EXTRA_ETF"  # 沪深ETF
    SH_ETF = "SH_ETF"  # 上交所ETF
    SZ_ETF = "SZ_ETF"  # 深交所ETF
    # 可转债
    KZZ = "EXTRA_KZZ"  # 沪深可转债
    SH_KZZ = "SH_KZZ"  # 上交所可转债
    SZ_KZZ = "SZ_KZZ"  # 深交所可转债
    # 港股通
    HKT = "EXTRA_HKT"  # 沪深港通
    SH_HKT = "SH_HKT"  # 沪港通
    SZ_HKT = "SZ_HKT"  # 深港通

    # === 4.1.2 期货交易所 ===
    FUTURE = "EXTRA_FUTURE"  # 全部期货（中金所/上期所/大商所/郑商所/能源中心）
    FUTURE_CFFEX = "ZJ_FUTURE"  # 中金所期货
    FUTURE_SHFE = "SQ_FUTURE"  # 上期所期货
    FUTURE_DCE = "DS_FUTURE"  # 大商所期货
    FUTURE_CZCE = "ZS_FUTURE"  # 郑商所期货
    FUTURE_INE = "SN_FUTURE"  # 能源中心期货

    # === 4.1.3 期权 ===
    OPTION = "EXTRA_ETF_OP"  # ETF期权（沪深）
    SH_OPTION = "SH_OPTION"  # 上交所ETF期权
    SZ_OPTION = "SZ_OPTION"  # 深交所ETF期权


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
    avg_price: Optional[float] = None  # 平均价
    turnover: Optional[float] = None  # 成交额
    iopv: Optional[float] = None  # ETF IOPV
    nav: Optional[float] = None  # ETF NAV
    premium_rate: Optional[float] = None  # ETF 溢价率
    pre_settle: Optional[float] = None  # 前结算价
    settle_price: Optional[float] = None  # 结算价
    pre_open_interest: Optional[float] = None  # 前持仓量
    open_interest: Optional[float] = None  # 持仓量
    open_interest_delta: Optional[float] = None  # 持仓变化
    trading_phase_code: Optional[str] = None  # 交易阶段

    # 买卖盘
    bid_prices: Optional[List[float]] = None  # 买价列表
    bid_volumes: Optional[List[float]] = None  # 买量列表
    ask_prices: Optional[List[float]] = None  # 卖价列表
    ask_volumes: Optional[List[float]] = None  # 卖量列表

    # 涨跌信息
    change: float = 0  # 涨跌额
    change_percent: float = 0  # 涨跌幅
    amplitude: float = 0  # 振幅
    turnover_rate: float = 0  # 换手率
    up_count: Optional[int] = None  # 上涨家数
    down_count: Optional[int] = None  # 下跌家数
    flat_count: Optional[int] = None  # 平盘家数

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

# Type helpers shared by AmazingData providers
RawDataMapping: TypeAlias = Mapping[str, object]
RawDataSequence: TypeAlias = Sequence[RawDataMapping]
SnapshotTimestamp: TypeAlias = Union[datetime, str]


class FiveLevelBook(TypedDict, total=False):
    """�������������"""

    ask_price1: float
    ask_price2: float
    ask_price3: float
    ask_price4: float
    ask_price5: float
    ask_volume1: int
    ask_volume2: int
    ask_volume3: int
    ask_volume4: int
    ask_volume5: int
    bid_price1: float
    bid_price2: float
    bid_price3: float
    bid_price4: float
    bid_price5: float
    bid_volume1: int
    bid_volume2: int
    bid_volume3: int
    bid_volume4: int
    bid_volume5: int


class SnapshotQuoteRequired(TypedDict):
    """Level-1 ����Ҫ�ֶΣ�Ӧ��文档 4.2.1"""

    code: str
    trade_time: SnapshotTimestamp
    pre_close: float
    last: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    num_trades: float
    high_limited: float
    low_limited: float


class SnapshotQuoteOptional(FiveLevelBook, TypedDict, total=False):
    """Level-1 ����ѡ�ֶ�"""

    iopv: float
    trading_phase_code: str
    name: str
    turnover: float
    turnover_rate: float
    change: float
    change_percent: float
    amplitude: float
    avg_price: float
    nav: float
    premium_rate: float
    pre_settle: float
    settle_price: float
    pre_open_interest: float
    open_interest: float
    open_interest_delta: float
    status: str
    error: str
    up_count: int
    down_count: int
    flat_count: int


class SnapshotQuote(SnapshotQuoteRequired, SnapshotQuoteOptional):
    """Level-1 �����ݽṹ"""


class SnapshotOptionRequired(TypedDict):
    """ETF ��Ȩ�����ݽṹ (文档 4.2.2)"""

    code: str
    trade_time: SnapshotTimestamp
    trading_phase_code: str
    total_long_position: int
    volume: float
    amount: float
    pre_close: float
    pre_settle: float
    auction_price: float
    auction_volume: int
    last: float
    open: float
    high: float
    low: float
    close: float
    settle: float
    high_limited: float
    low_limited: float
    contract_type: str
    expire_date: int
    underlying_security_code: str
    exercise_price: float


class SnapshotOptionOptional(FiveLevelBook, TypedDict, total=False):
    """ETF ��Ȩ����ѡ�ֶ�"""


class SnapshotOption(SnapshotOptionRequired, SnapshotOptionOptional):
    """ETF ��Ȩʵʱ���ݽṹ"""


class SnapshotFutureRequired(TypedDict):
    """�ڻ� Level-1 ���ݽṹ (文档 4.2.3)"""

    code: str
    trade_time: SnapshotTimestamp
    action_day: str
    trading_day: str
    pre_close: float
    pre_settle: float
    pre_open_interest: int
    open_interest: int
    last: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float
    high_limited: float
    low_limited: float
    average_price: float
    settle: float


class SnapshotFutureOptional(FiveLevelBook, TypedDict, total=False):
    """�ڻ� Level-1 ��ѡ�ֶ�"""


class SnapshotFuture(SnapshotFutureRequired, SnapshotFutureOptional):
    """�ڻ�ʵʱ���ݽṹ"""


class SnapshotIndex(TypedDict):
    """ָ�� Level-1 ���ݽṹ (文档 4.2.4)"""

    code: str
    trade_time: SnapshotTimestamp
    last: float
    pre_close: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float


class SnapshotHKTRequired(TypedDict):
    """���ͨʵʱ���ݽṹ (文档 4.2.5)"""

    code: str
    trade_time: SnapshotTimestamp
    pre_close: float
    last: float
    high: float
    low: float
    volume: float
    amount: float
    nominal_price: float
    ref_price: float
    bid_price_limit_up: float
    bid_price_limit_down: float
    offer_price_limit_up: float
    offer_price_limit_down: float
    high_limited: float
    low_limited: float
    trading_phase_code: str


class SnapshotHKTOptional(FiveLevelBook, TypedDict, total=False):
    """���ͨ Level-1 ��ѡ�ֶ�"""


class SnapshotHKT(SnapshotHKTRequired, SnapshotHKTOptional):
    """���ͨʵʱ���ݽṹ"""


class KlineRecord(TypedDict):
    """K �����ݽṹ (文档 4.2.6)"""

    code: str
    trade_time: SnapshotTimestamp
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


SnapshotPayload: TypeAlias = Union[
    SnapshotQuote,
    SnapshotOption,
    SnapshotFuture,
    SnapshotIndex,
    SnapshotHKT,
]


class OrderBookSnapshot(TypedDict):
    symbol: str
    time: str
    bid_queue: List[int]
    ask_queue: List[int]
    bid_prices: List[float]
    ask_prices: List[float]
    bid_volumes: List[int]
    ask_volumes: List[int]


class ShareholderSeat(TypedDict, total=False):
    name: str
    holding: float
    ratio: float
    change: float


class ShareholderSnapshot(TypedDict):
    symbol: str
    report_date: str
    shareholder_count: int
    avg_holding: float
    institution_ratio: float
    concentration: float
    top10_holders: List[ShareholderSeat]
    top10_tradable: List[ShareholderSeat]


class DragonTigerSeat(TypedDict, total=False):
    name: str
    amount: float
    ratio: float


class DragonTigerRecord(TypedDict):
    symbol: str
    trade_date: str
    reason: str
    buy_amount: float
    sell_amount: float
    net_amount: float
    turnover_rate: float
    buy_list: List[DragonTigerSeat]
    sell_list: List[DragonTigerSeat]


class KlineBarMessage(TypedDict, total=False):
    symbol: str
    period: str
    datetime: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    amount: float


class TickMessage(TypedDict, total=False):
    symbol: str
    time: str
    price: float
    volume: int
    direction: str


SubscriptionData: TypeAlias = Union[
    SnapshotPayload,
    KlineBarMessage,
    TickMessage,
    Mapping[str, object],
    object,
]


class SubscriptionMessageBase(TypedDict):
    type: str


class SubscriptionMessageOptional(TypedDict, total=False):
    timestamp: str
    data: Optional[SubscriptionData]
    error: str


class SubscriptionMessage(SubscriptionMessageBase, SubscriptionMessageOptional):
    pass


class StockListItem(TypedDict, total=False):
    symbol: str
    name: str
    exchange: str
    list_date: str
    delist_date: str
    board: str
    market: str
    security_type: str
    status: str
    is_listed: int
    company_id: str
    pinyin: str
    english_name: str
    short_name: str


FIELD_MAPPING = {
    # K线字段映射
    "kline": {
        "time": "datetime",
        "datetime": "datetime",
        "trade_time": "datetime",
        "trade_date": "datetime",
        "open": "open",
        "open_price": "open",
        "high": "high",
        "high_price": "high",
        "low": "low",
        "low_price": "low",
        "close": "close",
        "close_price": "close",
        "pre_close": "prev_close",
        "prev_close": "prev_close",
        "volume": "volume",
        "vol": "volume",
        "trade_volume": "volume",
        "amount": "amount",
        "trade_amount": "amount",
        "turnover_value": "amount",
        "turnover": "turnover",
        "turnover_rate": "turnover_rate",
        "change": "change",
        "change_rate": "change_percent",
        "change_percent": "change_percent",
        "amplitude": "amplitude",
    },
    # 快照字段映射
    "snapshot": {
        "code": "code",
        "symbol": "code",
        "market_code": "code",
        "name": "name",
        "security_name": "name",
        "time": "trade_time",
        "trade_time": "trade_time",
        "last": "last",
        "last_price": "last",
        "latest_price": "last",
        "open": "open",
        "open_price": "open",
        "high": "high",
        "high_price": "high",
        "low": "low",
        "low_price": "low",
        "close": "close",
        "close_price": "close",
        "pre_close": "pre_close",
        "prev_close": "pre_close",
        "avg_price": "avg_price",
        "average_price": "avg_price",
        "volume": "volume",
        "vol": "volume",
        "amount": "amount",
        "trade_amount": "amount",
        "turnover": "turnover",
        "turnover_value": "turnover",
        "turnover_rate": "turnover_rate",
        "amplitude": "amplitude",
        "change": "change",
        "change_rate": "change_percent",
        "change_percent": "change_percent",
        "num_trades": "num_trades",
        "trade_count": "num_trades",
        "trade_num": "num_trades",
        "iopv": "iopv",
        "nav": "nav",
        "premium_rate": "premium_rate",
        "pre_settle": "pre_settle",
        "settle_price": "settle_price",
        "pre_open_interest": "pre_open_interest",
        "open_interest": "open_interest",
        "open_interest_delta": "open_interest_delta",
        "trading_phase_code": "trading_phase_code",
        "limit_up": "high_limited",
        "high_limited": "high_limited",
        "limit_down": "low_limited",
        "low_limited": "low_limited",
        "up_count": "up_count",
        "down_count": "down_count",
        "flat_count": "flat_count",
        "status": "status",
        "bid1": "bid_price1",
        "bid_price1": "bid_price1",
        "bid1_volume": "bid_volume1",
        "bid_volume1": "bid_volume1",
        "bid2": "bid_price2",
        "bid_price2": "bid_price2",
        "bid2_volume": "bid_volume2",
        "bid_volume2": "bid_volume2",
        "bid3": "bid_price3",
        "bid_price3": "bid_price3",
        "bid3_volume": "bid_volume3",
        "bid_volume3": "bid_volume3",
        "bid4": "bid_price4",
        "bid_price4": "bid_price4",
        "bid4_volume": "bid_volume4",
        "bid_volume4": "bid_volume4",
        "bid5": "bid_price5",
        "bid_price5": "bid_price5",
        "bid5_volume": "bid_volume5",
        "bid_volume5": "bid_volume5",
        "ask1": "ask_price1",
        "ask_price1": "ask_price1",
        "ask1_volume": "ask_volume1",
        "ask_volume1": "ask_volume1",
        "ask2": "ask_price2",
        "ask_price2": "ask_price2",
        "ask2_volume": "ask_volume2",
        "ask_volume2": "ask_volume2",
        "ask3": "ask_price3",
        "ask_price3": "ask_price3",
        "ask3_volume": "ask_volume3",
        "ask_volume3": "ask_volume3",
        "ask4": "ask_price4",
        "ask_price4": "ask_price4",
        "ask4_volume": "ask_volume4",
        "ask_volume4": "ask_volume4",
        "ask5": "ask_price5",
        "ask_price5": "ask_price5",
        "ask5_volume": "ask_volume5",
        "ask_volume5": "ask_volume5",
    },
}


# SDK v1.0.4 Period 枚举的整数值（通过反编译 constant.pyc 确认）
PERIOD_TO_SDK_INT: dict[str, int] = {
    # SDK 原生名称
    "min1": 10000,
    "min3": 10001,
    "min5": 10002,
    "min10": 10003,
    "min15": 10004,
    "min30": 10005,
    "min60": 10006,
    "min120": 10007,
    "day": 10008,
    "week": 10009,
    "month": 10010,
    "season": 10011,
    "year": 10012,
    # API 端点别名
    "1min": 10000,
    "3min": 10001,
    "5min": 10002,
    "10min": 10003,
    "15min": 10004,
    "30min": 10005,
    "60min": 10006,
    "120min": 10007,
    "daily": 10008,
    "weekly": 10009,
    "monthly": 10010,
    "quarterly": 10011,
    "yearly": 10012,
    # convert_period 中间格式
    "1m": 10000,
    "3m": 10001,
    "5m": 10002,
    "10m": 10003,
    "15m": 10004,
    "30m": 10005,
    "60m": 10006,
    "120m": 10007,
    "1d": 10008,
    "1w": 10009,
    "1M": 10010,
    "1Q": 10011,
    "1Y": 10012,
}


def period_to_sdk_int(period: str | int | None) -> int:
    """将任意格式的 period 转为 SDK v1.0.4 需要的整数值

    SDK v1.0.4 的 Period 枚举值从字符串改为整数：
    - Period.day.value = 10008 (之前是 "day")
    - Period.min1.value = 10000 (之前是 "min1")

    Args:
        period: 周期值，支持字符串（多种格式）、整数或 None

    Returns:
        SDK 需要的整数 period 值

    Raises:
        ValueError: 未知的 period 值
    """
    if period is None:
        return 10008  # 默认日K
    if isinstance(period, int):
        return period  # 已经是整数
    result = PERIOD_TO_SDK_INT.get(period) or PERIOD_TO_SDK_INT.get(period.lower())
    if result is None:
        raise ValueError(f"未知的 period 值: {period!r}")
    return result


def convert_period(period: str) -> str:
    """
    转换周期格式

    Args:
        period: 系统周期格式

    Returns:
        AmazingData 周期格式
    """
    normalized = period.lower() if period else period
    period_map = {
        "tick": AmazingDataPeriod.TICK.value,
        "snapshot": AmazingDataPeriod.SNAPSHOT.value,
        "snapshot_future": AmazingDataPeriod.SNAPSHOT_FUTURE.value,
        "snapshot_hkt": AmazingDataPeriod.SNAPSHOT_HKT.value,
        "1m": AmazingDataPeriod.M1.value,
        "min1": AmazingDataPeriod.M1.value,
        "3m": AmazingDataPeriod.M3.value,
        "min3": AmazingDataPeriod.M3.value,
        "5m": AmazingDataPeriod.M5.value,
        "min5": AmazingDataPeriod.M5.value,
        "10m": AmazingDataPeriod.M10.value,
        "min10": AmazingDataPeriod.M10.value,
        "15m": AmazingDataPeriod.M15.value,
        "min15": AmazingDataPeriod.M15.value,
        "30m": AmazingDataPeriod.M30.value,
        "min30": AmazingDataPeriod.M30.value,
        "60m": AmazingDataPeriod.M60.value,
        "min60": AmazingDataPeriod.M60.value,
        "120m": AmazingDataPeriod.M120.value,
        "min120": AmazingDataPeriod.M120.value,
        "1d": AmazingDataPeriod.DAY.value,
        "day": AmazingDataPeriod.DAY.value,
        "1w": AmazingDataPeriod.WEEK.value,
        "week": AmazingDataPeriod.WEEK.value,
        "1mth": AmazingDataPeriod.MONTH.value,
        "1month": AmazingDataPeriod.MONTH.value,
        "month": AmazingDataPeriod.MONTH.value,
        "1M": AmazingDataPeriod.MONTH.value,
        "1q": AmazingDataPeriod.QUARTER.value,
        "1Q": AmazingDataPeriod.QUARTER.value,
        "quarter": AmazingDataPeriod.QUARTER.value,
        "1y": AmazingDataPeriod.YEAR.value,
        "1Y": AmazingDataPeriod.YEAR.value,
        "year": AmazingDataPeriod.YEAR.value,
    }
    return period_map.get(period, period_map.get(normalized, period))


def convert_adjust(adjust: str) -> str:
    """
    转换复权类型

    Args:
        adjust: 系统复权类型

    Returns:
        AmazingData 复权类型
    """
    adjust_map = {
        "none": AmazingDataAdjust.NONE.value,
        "qfq": AmazingDataAdjust.FORWARD.value,
        "hfq": AmazingDataAdjust.BACKWARD.value,
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
    if "." in symbol:
        code, market = symbol.split(".")
        return code, market
    else:
        # 根据代码判断市场
        if symbol.startswith("60") or symbol.startswith("68"):
            return symbol, "SH"
        elif symbol.startswith("00") or symbol.startswith("30"):
            return symbol, "SZ"
        elif symbol.startswith("8") or symbol.startswith("4"):
            return symbol, "BJ"
        else:
            return symbol, "SZ"  # 默认深圳


def format_symbol(code: str, market: Optional[str] = None) -> str:
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
