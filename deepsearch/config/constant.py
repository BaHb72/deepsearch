"""
Business constants and enumerations for the DeepSearch trading system.
"""
from __future__ import annotations

from enum import Enum


# ==============================================================================
# Trading Status Enumeration
# ==============================================================================

class Status(Enum):
    """
    Order status enumeration.
    
    Defines all possible states an order can be in during its lifecycle.
    """
    SUBMITTING = "提交中"  # Order is being submitted
    NOTTRADED = "未成交"  # Order submitted but not traded
    PARTTRADED = "部分成交"  # Order partially filled
    ALLTRADED = "全部成交"  # Order completely filled
    CANCELLED = "已撤销"  # Order cancelled
    REJECTED = "拒单"  # Order rejected by exchange


# ==============================================================================
# Exchange Enumeration
# ==============================================================================


class Exchange(Enum):
    """
    Exchange enumeration for global trading venues.
    
    Defines exchange codes for major trading venues worldwide, organized by region.
    """
    # --------------------------------------------------------------------------
    # Chinese Exchanges
    # --------------------------------------------------------------------------

    # Futures Exchanges
    CFFEX = "CFFEX"  # 中国金融期货交易所 (China Financial Futures Exchange)
    SHFE = "SHFE"  # 上海期货交易所 (Shanghai Futures Exchange)
    CZCE = "CZCE"  # 郑州商品交易所 (Zhengzhou Commodity Exchange)
    DCE = "DCE"  # 大连商品交易所 (Dalian Commodity Exchange)
    INE = "INE"  # 上海国际能源交易中心 (Shanghai International Energy Exchange)
    GFEX = "GFEX"  # 广州期货交易所 (Guangzhou Futures Exchange)

    # Stock Exchanges
    SSE = "SSE"  # 上海证券交易所 (Shanghai Stock Exchange)
    SZSE = "SZSE"  # 深圳证券交易所 (Shenzhen Stock Exchange)
    BSE = "BSE"  # 北京证券交易所 (Beijing Stock Exchange)

    # Stock Connect Programs
    SHHK = "SHHK"  # 沪港通 (Shanghai-HK Stock Connect)
    SZHK = "SZHK"  # 深港通 (Shenzhen-HK Stock Connect)

    # Other Chinese Exchanges
    SGE = "SGE"  # 上海黄金交易所 (Shanghai Gold Exchange)
    WXE = "WXE"  # 无锡不锈钢电子交易中心 (Wuxi Steel Exchange)
    CFETS = "CFETS"  # 中国外汇交易中心债券市场做市交易系统 (CFETS Bond Market Maker Trading System)
    XBOND = "XBOND"  # 中国外汇交易中心X-债券匿名交易系统 (CFETS X-Bond Anonymous Trading System)

    # --------------------------------------------------------------------------
    # North American Exchanges
    # --------------------------------------------------------------------------

    # US Stock Exchanges
    SMART = "SMART"  # Smart Router for US stocks
    NYSE = "NYSE"  # New York Stock Exchange
    NASDAQ = "NASDAQ"  # Nasdaq Exchange
    ARCA = "ARCA"  # ARCA Exchange
    EDGEA = "EDGEA"  # Direct Edge Exchange
    ISLAND = "ISLAND"  # Nasdaq Island ECN
    BATS = "BATS"  # Bats Global Markets
    IEX = "IEX"  # The Investors Exchange
    AMEX = "AMEX"  # American Stock Exchange

    # US Derivatives Exchanges
    CME = "CME"  # Chicago Mercantile Exchange
    CBOT = "CBOT"  # Chicago Board of Trade
    CBOE = "CBOE"  # Chicago Board Options Exchange
    CFE = "CFE"  # CBOE Futures Exchange
    NYMEX = "NYMEX"  # New York Mercantile Exchange
    COMEX = "COMEX"  # COMEX of CME
    GLOBEX = "GLOBEX"  # Globex of CME
    ICE = "ICE"  # Intercontinental Exchange

    # Canadian Exchanges
    TSE = "TSE"  # Toronto Stock Exchange

    # --------------------------------------------------------------------------
    # Asian Exchanges (Non-Chinese)
    # --------------------------------------------------------------------------

    SEHK = "SEHK"  # 香港联合交易所 (Stock Exchange of Hong Kong)
    HKFE = "HKFE"  # 香港期货交易所 (Hong Kong Futures Exchange)
    SGX = "SGX"  # Singapore Exchange
    TOCOM = "TOCOM"  # Tokyo Commodity Exchange
    KRX = "KRX"  # Korean Exchange
    BMD = "BMD"  # Bursa Malaysia Derivatives
    APEX = "APEX"  # Asia Pacific Exchange

    # --------------------------------------------------------------------------
    # European Exchanges
    # --------------------------------------------------------------------------
    
    EUREX = "EUX"  # Eurex Exchange
    EUNX = "EUNX"  # Euronext Exchange
    LME = "LME"  # London Metal Exchange

    # --------------------------------------------------------------------------
    # Other Exchanges
    # --------------------------------------------------------------------------

    DME = "DME"  # Dubai Mercantile Exchange
    IDEALPRO = "IDEALPRO"  # Forex ECN of Interactive Brokers
    OTC = "OTC"  # OTC Product (Forex/CFD/Pink Sheet Equity)

    # --------------------------------------------------------------------------
    # Special Purpose
    # --------------------------------------------------------------------------
    
    IBKRATS = "IBKRATS"  # Paper Trading Exchange of IB
    LOCAL = "LOCAL"  # For locally generated data
    GLOBAL = "GLOBAL"  # For exchanges not yet supported


# ==============================================================================
# Module Summary
# ==============================================================================
"""
This module defines business constants and enumerations for the trading system.

Key Components:
1. Status: Order status enumeration
   - Tracks the complete lifecycle of an order
   - From submission through execution or cancellation

2. Exchange: Global exchange enumeration
   - Comprehensive list of trading venues
   - Organized by geographic region
   - Includes futures, stocks, options, and OTC markets

Usage:
    from deepsearch.config.constant import Status, Exchange
    
    # Check order status
    if order.status == Status.ALLTRADED:
        print("Order fully executed")
    
    # Set exchange
    order.exchange = Exchange.SSE
"""
