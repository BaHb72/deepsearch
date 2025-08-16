"""
DuckDB 分析数据模型

定义 DuckDB 中的数据结构和分析模型
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, List, Any


@dataclass
class KlineAnalytics:
    """K线分析数据"""
    symbol: str
    time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: Decimal

    # 技术指标
    ma5: Optional[Decimal] = None
    ma10: Optional[Decimal] = None
    ma20: Optional[Decimal] = None
    ma60: Optional[Decimal] = None

    rsi: Optional[Decimal] = None
    macd: Optional[Decimal] = None
    macd_signal: Optional[Decimal] = None
    macd_hist: Optional[Decimal] = None

    # 统计指标
    volatility: Optional[Decimal] = None  # 波动率
    return_rate: Optional[Decimal] = None  # 收益率
    volume_ratio: Optional[Decimal] = None  # 量比


@dataclass
class TickAnalytics:
    """Tick 分析数据"""
    symbol: str
    time: datetime
    last_price: Decimal
    volume: int
    amount: Decimal

    # 盘口数据
    bid_price1: Decimal
    ask_price1: Decimal
    bid_volume1: int
    ask_volume1: int

    # 微观结构指标
    spread: Optional[Decimal] = None  # 买卖价差
    mid_price: Optional[Decimal] = None  # 中间价
    imbalance: Optional[Decimal] = None  # 买卖不平衡度

    def calculate_microstructure(self):
        """计算微观结构指标"""
        self.spread = self.ask_price1 - self.bid_price1
        self.mid_price = (self.ask_price1 + self.bid_price1) / 2
        total_volume = self.bid_volume1 + self.ask_volume1
        if total_volume > 0:
            self.imbalance = (self.bid_volume1 - self.ask_volume1) / total_volume


@dataclass
class BacktestResult:
    """回测结果"""
    strategy_id: str
    run_time: datetime
    symbol: Optional[str]
    start_date: datetime
    end_date: datetime

    # 收益指标
    total_return: Decimal  # 总收益率
    annual_return: Decimal  # 年化收益率

    # 风险指标
    sharpe_ratio: Decimal  # 夏普比率
    max_drawdown: Decimal  # 最大回撤
    volatility: Decimal  # 波动率

    # 交易统计
    total_trades: int  # 总交易次数
    win_trades: int  # 盈利次数
    loss_trades: int  # 亏损次数
    win_rate: Decimal  # 胜率
    avg_win: Decimal  # 平均盈利
    avg_loss: Decimal  # 平均亏损
    profit_factor: Decimal  # 盈亏比

    # 详细数据
    trades: List[Dict[str, Any]]  # 交易明细
    metrics: Dict[str, Any]  # 其他指标


@dataclass
class MarketProfile:
    """市场概况分析"""
    date: datetime

    # 市场整体指标
    total_stocks: int  # 股票总数
    up_count: int  # 上涨家数
    down_count: int  # 下跌家数
    flat_count: int  # 平盘家数

    limit_up_count: int  # 涨停家数
    limit_down_count: int  # 跌停家数

    total_volume: int  # 总成交量
    total_amount: Decimal  # 总成交额

    # 行业分析
    sector_performance: Dict[str, Decimal]  # 各行业涨跌幅

    # 资金流向
    net_inflow: Decimal  # 净流入
    main_inflow: Decimal  # 主力流入
    retail_inflow: Decimal  # 散户流入


@dataclass
class TechnicalSignal:
    """技术信号"""
    symbol: str
    time: datetime
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    indicator: str  # 指标名称
    strength: Decimal  # 信号强度 (0-100)

    # 信号参数
    params: Dict[str, Any]

    # 信号描述
    description: str

    # 置信度
    confidence: Decimal  # 0-1


@dataclass
class SyncLog:
    """数据同步日志"""
    sync_id: str
    table_name: str
    sync_time: datetime
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    records_count: int
    status: str  # 'SUCCESS', 'FAILED', 'RUNNING'
    error_message: Optional[str] = None


# SQL 表创建语句
ANALYTICS_TABLES = {
    'kline_history': """
                     CREATE TABLE IF NOT EXISTS kline_history
                     (
                         symbol
                         VARCHAR
                         NOT
                         NULL,
                         time
                         TIMESTAMP
                         NOT
                         NULL,
                         open
                         DECIMAL
                     (
                         10,
                         2
                     ),
                         high DECIMAL
                     (
                         10,
                         2
                     ),
                         low DECIMAL
                     (
                         10,
                         2
                     ),
                         close DECIMAL
                     (
                         10,
                         2
                     ),
                         volume BIGINT,
                         amount DECIMAL
                     (
                         15,
                         2
                     ),
                         PRIMARY KEY
                     (
                         symbol,
                         time
                     )
                         )
                     """,

    'tick_archive': """
                    CREATE TABLE IF NOT EXISTS tick_archive
                    (
                        symbol
                        VARCHAR
                        NOT
                        NULL,
                        time
                        TIMESTAMP
                        NOT
                        NULL,
                        last_price
                        DECIMAL
                    (
                        10,
                        2
                    ),
                        volume BIGINT,
                        amount DECIMAL
                    (
                        15,
                        2
                    ),
                        bid_price1 DECIMAL
                    (
                        10,
                        2
                    ),
                        ask_price1 DECIMAL
                    (
                        10,
                        2
                    ),
                        bid_volume1 BIGINT,
                        ask_volume1 BIGINT,
                        spread DECIMAL
                    (
                        10,
                        4
                    ),
                        mid_price DECIMAL
                    (
                        10,
                        2
                    ),
                        imbalance DECIMAL
                    (
                        10,
                        4
                    ),
                        PRIMARY KEY
                    (
                        symbol,
                        time
                    )
                        )
                    """,

    'indicators': """
                  CREATE TABLE IF NOT EXISTS indicators
                  (
                      symbol
                      VARCHAR
                      NOT
                      NULL,
                      time
                      TIMESTAMP
                      NOT
                      NULL,
                      indicator_name
                      VARCHAR
                      NOT
                      NULL,
                      value
                      DECIMAL
                  (
                      20,
                      6
                  ),
                      params JSON,
                      PRIMARY KEY
                  (
                      symbol,
                      time,
                      indicator_name
                  )
                      )
                  """,

    'backtest_results': """
                        CREATE TABLE IF NOT EXISTS backtest_results
                        (
                            strategy_id
                            VARCHAR
                            NOT
                            NULL,
                            run_time
                            TIMESTAMP
                            NOT
                            NULL,
                            symbol
                            VARCHAR,
                            start_date
                            DATE,
                            end_date
                            DATE,
                            total_return
                            DECIMAL
                        (
                            10,
                            4
                        ),
                            annual_return DECIMAL
                        (
                            10,
                            4
                        ),
                            sharpe_ratio DECIMAL
                        (
                            10,
                            4
                        ),
                            max_drawdown DECIMAL
                        (
                            10,
                            4
                        ),
                            volatility DECIMAL
                        (
                            10,
                            4
                        ),
                            total_trades INTEGER,
                            win_trades INTEGER,
                            loss_trades INTEGER,
                            win_rate DECIMAL
                        (
                            10,
                            4
                        ),
                            avg_win DECIMAL
                        (
                            10,
                            4
                        ),
                            avg_loss DECIMAL
                        (
                            10,
                            4
                        ),
                            profit_factor DECIMAL
                        (
                            10,
                            4
                        ),
                            trades JSON,
                            metrics JSON,
                            PRIMARY KEY
                        (
                            strategy_id,
                            run_time
                        )
                            )
                        """,

    'market_profile': """
                      CREATE TABLE IF NOT EXISTS market_profile
                      (
                          date
                          DATE
                          PRIMARY
                          KEY,
                          total_stocks
                          INTEGER,
                          up_count
                          INTEGER,
                          down_count
                          INTEGER,
                          flat_count
                          INTEGER,
                          limit_up_count
                          INTEGER,
                          limit_down_count
                          INTEGER,
                          total_volume
                          BIGINT,
                          total_amount
                          DECIMAL
                      (
                          15,
                          2
                      ),
                          sector_performance JSON,
                          net_inflow DECIMAL
                      (
                          15,
                          2
                      ),
                          main_inflow DECIMAL
                      (
                          15,
                          2
                      ),
                          retail_inflow DECIMAL
                      (
                          15,
                          2
                      )
                          )
                      """,

    'technical_signals': """
                         CREATE TABLE IF NOT EXISTS technical_signals
                         (
                             symbol
                             VARCHAR
                             NOT
                             NULL,
                             time
                             TIMESTAMP
                             NOT
                             NULL,
                             signal_type
                             VARCHAR
                             NOT
                             NULL,
                             indicator
                             VARCHAR
                             NOT
                             NULL,
                             strength
                             DECIMAL
                         (
                             5,
                             2
                         ),
                             params JSON,
                             description TEXT,
                             confidence DECIMAL
                         (
                             3,
                             2
                         ),
                             PRIMARY KEY
                         (
                             symbol,
                             time,
                             indicator
                         )
                             )
                         """,

    'sync_log': """
                CREATE TABLE IF NOT EXISTS sync_log
                (
                    sync_id
                    VARCHAR
                    PRIMARY
                    KEY,
                    table_name
                    VARCHAR
                    NOT
                    NULL,
                    sync_time
                    TIMESTAMP
                    NOT
                    NULL,
                    start_time
                    TIMESTAMP,
                    end_time
                    TIMESTAMP,
                    records_count
                    BIGINT,
                    status
                    VARCHAR,
                    error_message
                    TEXT
                )
                """
}
