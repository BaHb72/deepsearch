# deepsearch/trader/core/constant.py
from enum import Enum

# ----------------------------------------------------------------------
# 事件类型（字符串）
# ----------------------------------------------------------------------
EVENT_TICK: str = "TICK"  # 行情 Tick
EVENT_ORDER: str = "ORDER"  # 订单状态
EVENT_TRADE: str = "TRADE"  # 成交回报
EVENT_TIMER: str = "TIMER"  # 系统计时器
EVENT_ERROR: str = "ERROR"  # 错误信息


# EVENT_ACCOUNT = "ACCOUNT"
# EVENT_POSITION = "POSITION"
EVENT_LOG = "LOG"

# ----------------------------------------------------------------------
# 业务枚举
# ----------------------------------------------------------------------

class Status(Enum):
    """
    Order status.
    """
    SUBMITTING = "提交中"
    NOTTRADED = "未成交"
    PARTTRADED = "部分成交"
    ALLTRADED = "全部成交"
    CANCELLED = "已撤销"
    REJECTED = "拒单"


class Exchange(Enum):
    """
    用于表示各交易所枚举类。

    该类定义了多种中国及全球范围内的交易所，以简化在代码中对交易所及其代码的管理和引用。

    :ivar CFFEX: 中国金融期货交易所
    :type CFFEX: str
    :ivar SHFE: 上海期货交易所
    :type SHFE: str
    :ivar CZCE: 郑州商品交易所
    :type CZCE: str
    :ivar DCE: 大连商品交易所
    :type DCE: str
    :ivar INE: 上海国际能源交易中心
    :type INE: str
    :ivar GFEX: 广州期货交易所
    :type GFEX: str
    :ivar SSE: 上海证券交易所
    :type SSE: str
    :ivar SZSE: 深圳证券交易所
    :type SZSE: str
    :ivar BSE: 北京证券交易所
    :type BSE: str
    :ivar SHHK: 沪港通
    :type SHHK: str
    :ivar SZHK: 深港通
    :type SZHK: str
    :ivar SGE: 上海黄金交易所
    :type SGE: str
    :ivar WXE: 无锡不锈钢电子交易中心
    :type WXE: str
    :ivar CFETS: 中国外汇交易中心债券市场做市交易系统
    :type CFETS: str
    :ivar XBOND: 中国外汇交易中心X-债券匿名交易系统
    :type XBOND: str
    :ivar SMART: 美国股票智能路由
    :type SMART: str
    :ivar NYSE: 纽约证券交易所
    :type NYSE: str
    :ivar NASDAQ: 纳斯达克交易所
    :type NASDAQ: str
    :ivar ARCA: ARCA交易所
    :type ARCA: str
    :ivar EDGEA: Direct Edge交易所
    :type EDGEA: str
    :ivar ISLAND: 纳斯达克Island ECN
    :type ISLAND: str
    :ivar BATS: Bats全球市场交易所
    :type BATS: str
    :ivar IEX: Investors 交易所
    :type IEX: str
    :ivar AMEX: 美国证券交易所
    :type AMEX: str
    :ivar TSE: 多伦多证券交易所
    :type TSE: str
    :ivar NYMEX: 纽约商品交易所
    :type NYMEX: str
    :ivar COMEX: CME集团的COMEX交易所
    :type COMEX: str
    :ivar GLOBEX: CME集团的Globex系统
    :type GLOBEX: str
    :ivar IDEALPRO: Interactive Brokers的外汇ECN
    :type IDEALPRO: str
    :ivar CME: 芝加哥商品交易所
    :type CME: str
    :ivar ICE: 洲际交易所
    :type ICE: str
    :ivar SEHK: 香港联合交易所
    :type SEHK: str
    :ivar HKFE: 香港期货交易所
    :type HKFE: str
    :ivar SGX: 新加坡全球交易所
    :type SGX: str
    :ivar CBOT: 芝加哥交易所
    :type CBOT: str
    :ivar CBOE: 芝加哥期权交易所
    :type CBOE: str
    :ivar CFE: CBOE期货交易所
    :type CFE: str
    :ivar DME: 迪拜商品交易所
    :type DME: str
    :ivar EUREX: 欧洲期货交易所
    :type EUREX: str
    :ivar APEX: 亚太交易所
    :type APEX: str
    :ivar LME: 伦敦金属交易所
    :type LME: str
    :ivar BMD: 马来西亚衍生品交易所
    :type BMD: str
    :ivar TOCOM: 东京商品交易所
    :type TOCOM: str
    :ivar EUNX: 欧洲交易所
    :type EUNX: str
    :ivar KRX: 韩国交易所
    :type KRX: str
    :ivar OTC: 场外市场（外汇/CFD/粉单市场）
    :type OTC: str
    :ivar IBKRATS: IB的模拟交易所
    :type IBKRATS: str
    :ivar LOCAL: 本地生成数据的特殊用途
    :type LOCAL: str
    :ivar GLOBAL: 不支持交易所的统一定义
    :type GLOBAL: str
    """
    # Chinese
    CFFEX = "CFFEX"  # China Financial Futures Exchange
    SHFE = "SHFE"  # Shanghai Futures Exchange
    CZCE = "CZCE"  # Zhengzhou Commodity Exchange
    DCE = "DCE"  # Dalian Commodity Exchange
    INE = "INE"  # Shanghai International Energy Exchange
    GFEX = "GFEX"  # Guangzhou Futures Exchange
    SSE = "SSE"  # Shanghai Stock Exchange
    SZSE = "SZSE"  # Shenzhen Stock Exchange
    BSE = "BSE"  # Beijing Stock Exchange
    SHHK = "SHHK"  # Shanghai-HK Stock Connect
    SZHK = "SZHK"  # Shenzhen-HK Stock Connect
    SGE = "SGE"  # Shanghai Gold Exchange
    WXE = "WXE"  # Wuxi Steel Exchange
    CFETS = "CFETS"  # CFETS Bond Market Maker Trading System
    XBOND = "XBOND"  # CFETS X-Bond Anonymous Trading System

    # Global
    SMART = "SMART"  # Smart Router for US stocks
    NYSE = "NYSE"  # New York Stock Exchnage
    NASDAQ = "NASDAQ"  # Nasdaq Exchange
    ARCA = "ARCA"  # ARCA Exchange
    EDGEA = "EDGEA"  # Direct Edge Exchange
    ISLAND = "ISLAND"  # Nasdaq Island ECN
    BATS = "BATS"  # Bats Global Markets
    IEX = "IEX"  # The Investors Exchange
    AMEX = "AMEX"  # American Stock Exchange
    TSE = "TSE"  # Toronto Stock Exchange
    NYMEX = "NYMEX"  # New York Mercantile Exchange
    COMEX = "COMEX"  # COMEX of CME
    GLOBEX = "GLOBEX"  # Globex of CME
    IDEALPRO = "IDEALPRO"  # Forex ECN of Interactive Brokers
    CME = "CME"  # Chicago Mercantile Exchange
    ICE = "ICE"  # Intercontinental Exchange
    SEHK = "SEHK"  # Stock Exchange of Hong Kong
    HKFE = "HKFE"  # Hong Kong Futures Exchange
    SGX = "SGX"  # Singapore Global Exchange
    CBOT = "CBOT"  # Chicago Board of Trade
    CBOE = "CBOE"  # Chicago Board Options Exchange
    CFE = "CFE"  # CBOE Futures Exchange
    DME = "DME"  # Dubai Mercantile Exchange
    EUREX = "EUX"  # Eurex Exchange
    APEX = "APEX"  # Asia Pacific Exchange
    LME = "LME"  # London Metal Exchange
    BMD = "BMD"  # Bursa Malaysia Derivatives
    TOCOM = "TOCOM"  # Tokyo Commodity Exchange
    EUNX = "EUNX"  # Euronext Exchange
    KRX = "KRX"  # Korean Exchange
    OTC = "OTC"  # OTC Product (Forex/CFD/Pink Sheet Equity)
    IBKRATS = "IBKRATS"  # Paper Trading Exchange of IB

    # Special Function
    LOCAL = "LOCAL"  # For local generated data
    GLOBAL = "GLOBAL"  # For those exchanges not supported yet
