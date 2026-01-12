"""
数据能力定义
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Set


class DataCapability(Enum):
    """数据源能力枚举"""

    # 基础数据能力
    STOCK_LIST = "stock_list"
    REALTIME_QUOTE = "realtime_quote"
    REALTIME_QUOTES = "realtime_quotes"  # 批量实时行情
    KLINE_DATA = "kline_data"
    STOCK_INFO = "stock_info"
    ORDER_BOOK = "order_book"
    TRADE_DETAIL = "trade_detail"
    FINANCIAL_DATA = "financial_data"
    NEWS = "news"
    ANNOUNCEMENT = "announcement"

    # 市场数据能力
    MARKET_OVERVIEW = "market_overview"
    MARKET_BREADTH = "market_breadth"
    CAPITAL_FLOW = "capital_flow"
    SECTOR_DATA = "sector_data"
    ANOMALY_DETECTION = "anomaly_detection"

    # 高级行情能力
    TICK_DATA = "tick_data"
    MINUTE_DATA = "minute_data"
    LEVEL2_DATA = "level2_data"
    TRANSACTION_DATA = "transaction_data"

    # 特色数据能力
    CHIP_DISTRIBUTION = "chip_distribution"
    DRAGON_TIGER = "dragon_tiger"
    BLOCK_TRADE = "block_trade"
    MARGIN_TRADING = "margin_trading"
    NORTH_FLOW = "north_flow"

    # 基础信息能力
    KEY_INDICATORS = "key_indicators"
    SHAREHOLDER_INFO = "shareholder_info"
    TRADING_CALENDAR = "trading_calendar"
    ADJUSTMENT_FACTOR = "adjustment_factor"

    # 扩展数据能力
    INDEX_DATA = "index_data"  # 指数数据（成分股、权重）
    OPTION_DATA = "option_data"  # 期权数据
    ETF_DATA = "etf_data"  # ETF数据（申赎清单、份额）
    FUTURE_DATA = "future_data"  # 期货数据
    BOND_DATA = "bond_data"  # 债券/国债数据
    ORDER_FLOW = "order_flow"  # 订单流数据 (VIP)
    INDUSTRY_DATA = "industry_data"  # 行业分类数据


class DataProvider(ABC):
    """数据提供者基类"""

    @abstractmethod
    def get_capabilities(self) -> Set[DataCapability]:
        """获取数据源能力"""
        pass


class DataProviderConfig:
    """数据提供者配置"""

    pass


class DataRequest:
    """数据请求"""

    pass


class DataResponse:
    """数据响应"""

    pass


class DataProviderError(Exception):
    """数据提供者错误"""

    pass


def get_capable_providers(providers: Dict[str, Any], capability: DataCapability) -> List[str]:
    """获取支持指定能力的提供者"""
    result = []
    for name, provider in providers.items():
        if hasattr(provider, "get_capabilities"):
            if capability in provider.get_capabilities():
                result.append(name)
    return result


def check_provider_capability(provider: Any, capability: DataCapability) -> bool:
    """检查提供者是否支持指定能力"""
    if hasattr(provider, "get_capabilities"):
        return capability in provider.get_capabilities()
    return False
