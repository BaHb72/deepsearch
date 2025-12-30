"""
Strategy Center Data Models

Pydantic models for Strategy Center functionality:
- Strategy metadata and registration
- Composite strategies (weighted ensemble)
- Screening results
- Trading signals
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# ============================================
# Enums
# ============================================


class StrategyCategory(str, Enum):
    """策略分类"""

    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    COMPOSITE = "composite"
    CUSTOM = "custom"


class SignalDirection(str, Enum):
    """信号方向"""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class AggregationMethod(str, Enum):
    """组合策略聚合方式"""

    WEIGHTED_AVG = "weighted_avg"  # 加权平均
    VOTE = "vote"  # 投票
    UNANIMOUS = "unanimous"  # 一致性


class StrategyStatus(str, Enum):
    """策略运行状态"""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


# ============================================
# Strategy Parameter Definition
# ============================================


class StrategyParamDef(BaseModel):
    """策略参数定义"""

    type: Literal["int", "float", "bool", "str", "list"] = "int"
    default: Any
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None
    label: Optional[str] = None
    description: Optional[str] = None
    choices: Optional[List[Any]] = None  # For enum-like params


# ============================================
# Strategy Metadata
# ============================================


class StrategyMeta(BaseModel):
    """策略元数据"""

    id: str
    file: str
    class_name: str = Field(alias="class")
    name: str
    description: Optional[str] = None
    category: StrategyCategory = StrategyCategory.CUSTOM
    tags: List[str] = Field(default_factory=list)
    params: Dict[str, StrategyParamDef] = Field(default_factory=dict)
    enabled: bool = True
    version: str = "1.0.0"
    author: str = "user"

    class Config:
        populate_by_name = True


class StrategyListResponse(BaseModel):
    """策略列表响应"""

    strategies: List[StrategyMeta]
    total: int
    categories: Dict[str, int]  # category -> count


# ============================================
# Composite Strategy (组合策略)
# ============================================


class StrategyWeight(BaseModel):
    """策略权重配置"""

    strategy_id: str
    weight: float = Field(ge=0.0, le=1.0, default=0.5)
    enabled: bool = True
    params: Dict[str, Any] = Field(default_factory=dict)  # Override params


class CompositeStrategy(BaseModel):
    """组合策略"""

    id: str
    name: str
    description: Optional[str] = None

    # 子策略配置
    components: List[StrategyWeight] = Field(default_factory=list)

    # 聚合方式
    aggregation: AggregationMethod = AggregationMethod.WEIGHTED_AVG

    # 信号阈值（聚合信号超过此值才触发）
    signal_threshold: float = Field(ge=0.0, le=1.0, default=0.5)

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    author: str = "user"
    tags: List[str] = Field(default_factory=list)


class CompositeSignal(BaseModel):
    """组合策略输出信号"""

    composite_id: str
    symbol: str
    timestamp: datetime = Field(default_factory=datetime.now)

    # 各子策略信号
    component_signals: Dict[str, float] = Field(default_factory=dict)

    # 聚合后的信号
    aggregated_signal: float = Field(ge=-1.0, le=1.0)
    direction: SignalDirection = SignalDirection.HOLD
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


# ============================================
# Stock Screening (智能选股)
# ============================================


class ScreeningRequest(BaseModel):
    """选股请求"""

    composite_id: Optional[str] = None  # 使用组合策略
    strategy_ids: List[str] = Field(default_factory=list)  # 或指定策略列表
    stock_pool: List[str] = Field(default_factory=list)  # 股票池 (空=全市场)
    limit: int = Field(ge=1, le=500, default=50)


class ScreeningResult(BaseModel):
    """单只股票的选股结果"""

    symbol: str
    name: Optional[str] = None
    score: float  # 综合评分 [-1.0, 1.0]
    direction: SignalDirection
    component_signals: Dict[str, float] = Field(default_factory=dict)
    rank: int = 0


class ScreeningResponse(BaseModel):
    """选股响应"""

    request_id: str
    composite_id: Optional[str] = None
    strategy_ids: List[str]
    results: List[ScreeningResult]
    total_scanned: int
    total_matched: int
    executed_at: datetime = Field(default_factory=datetime.now)
    duration_ms: int = 0


# ============================================
# T-Trading (做T) Models
# ============================================


class TTradingConfig(BaseModel):
    """做T策略配置"""

    id: str
    name: str
    symbol: str

    # 基础参数
    base_position_ratio: float = Field(ge=0, le=100, default=50.0)  # 底仓比例%
    trading_position_ratio: float = Field(ge=0, le=100, default=50.0)  # 交易仓比例%

    # 网格参数
    grid_enabled: bool = True
    grid_base_price: Optional[float] = None  # 网格基准价（None=自动）
    grid_step_ratio: float = Field(ge=0.5, le=10.0, default=2.0)  # 网格步长%
    grid_levels: int = Field(ge=1, le=10, default=5)  # 网格层数

    # 技术指标参数
    ma_periods: List[int] = Field(default_factory=lambda: [5, 10, 20])
    rsi_period: int = 14
    boll_period: int = 20
    boll_std: float = 2.0

    # 分时分析参数
    intraday_ma_period: int = 20  # 分时均线周期
    volume_ratio_threshold: float = 1.5  # 量比阈值

    # 风控参数
    max_daily_trades: int = Field(ge=1, le=50, default=10)
    stop_loss_ratio: float = Field(ge=0.5, le=10.0, default=3.0)  # 止损比例%
    take_profit_ratio: float = Field(ge=0.5, le=10.0, default=2.0)  # 止盈比例%

    # 自适应参数
    adaptive_enabled: bool = True
    lookback_days: int = Field(ge=5, le=60, default=20)
    min_success_rate: float = Field(ge=0.3, le=0.9, default=0.6)


class IntradayAnalysis(BaseModel):
    """分时分析结果"""

    symbol: str
    date: str
    time: str

    # 价格指标
    current_price: float
    open_price: float
    high_price: float
    low_price: float
    vwap: float  # 成交量加权平均价

    # 分时均线
    intraday_ma: float
    price_deviation: float  # 价格偏离度%

    # 量价分析
    volume_ratio: float
    buy_volume_ratio: float = 0.5
    large_order_ratio: float = 0.0

    # 支撑阻力
    support_levels: List[float] = Field(default_factory=list)
    resistance_levels: List[float] = Field(default_factory=list)
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None

    # 形态识别
    pattern: Optional[str] = None
    trend: Literal["up", "down", "sideways"] = "sideways"

    # 信号强度
    buy_signal_strength: float = Field(ge=0, le=1, default=0)
    sell_signal_strength: float = Field(ge=0, le=1, default=0)


class TTradingSignal(BaseModel):
    """做T信号"""

    id: str
    strategy_id: str
    symbol: str
    timestamp: datetime = Field(default_factory=datetime.now)

    signal_type: str  # ma_deviation, support_resistance, volume_price, grid
    direction: SignalDirection
    price: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None

    confidence: float = Field(ge=0, le=1, default=0.5)
    reason: str = ""


class TTradingRecord(BaseModel):
    """做T交易记录（用于成功率分析）"""

    id: str
    strategy_id: str
    symbol: str

    # 交易信息
    entry_time: datetime
    entry_price: float
    entry_signal: str

    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_signal: Optional[str] = None

    # 结果
    direction: Literal["buy_first", "sell_first"]
    quantity: int
    pnl: Optional[float] = None
    pnl_ratio: Optional[float] = None
    is_success: Optional[bool] = None

    # 上下文
    market_condition: Dict[str, Any] = Field(default_factory=dict)
    intraday_analysis: Dict[str, Any] = Field(default_factory=dict)


class TTradingStats(BaseModel):
    """做T成功率统计"""

    strategy_id: str
    symbol: str
    period: Literal["7d", "30d", "90d", "all"] = "30d"
    updated_at: datetime = Field(default_factory=datetime.now)

    # 基础统计
    total_trades: int = 0
    successful_trades: int = 0
    success_rate: float = 0.0

    # 收益统计
    total_pnl: float = 0.0
    avg_pnl_per_trade: float = 0.0
    max_single_pnl: float = 0.0
    max_single_loss: float = 0.0
    profit_factor: float = 0.0

    # 信号分析
    signal_accuracy: Dict[str, float] = Field(default_factory=dict)
    best_entry_time: Optional[str] = None
    worst_entry_time: Optional[str] = None

    # 市况分析
    success_by_trend: Dict[str, float] = Field(default_factory=dict)
    success_by_volatility: Dict[str, float] = Field(default_factory=dict)


# ============================================
# Trading Cost Configuration
# ============================================


class TradingCostConfig(BaseModel):
    """交易费用配置（用户可在页面自定义）"""

    # 佣金
    commission_rate: float = Field(ge=0, le=0.01, default=0.0002)  # 万二
    min_commission: float = Field(ge=0, default=5.0)  # 最低5元
    commission_exempt_min: bool = False  # 是否免五

    # 印花税（仅卖出）
    stamp_tax_rate: float = Field(ge=0, le=0.01, default=0.001)  # 千分之一

    # 过户费
    transfer_fee_rate: float = Field(ge=0, le=0.001, default=0.00001)  # 十万分之一

    # 滑点（日级策略暂不模拟）
    slippage: float = Field(ge=0, le=0.1, default=0.0)

    def calc_buy_cost(self, amount: float) -> float:
        """计算买入成本"""
        commission = max(
            amount * self.commission_rate,
            0 if self.commission_exempt_min else self.min_commission,
        )
        transfer_fee = amount * self.transfer_fee_rate
        return commission + transfer_fee

    def calc_sell_cost(self, amount: float) -> float:
        """计算卖出成本"""
        commission = max(
            amount * self.commission_rate,
            0 if self.commission_exempt_min else self.min_commission,
        )
        stamp_tax = amount * self.stamp_tax_rate
        transfer_fee = amount * self.transfer_fee_rate
        return commission + stamp_tax + transfer_fee


# ============================================
# Signal Tracking (信号追踪)
# ============================================


class SignalHistory(BaseModel):
    """信号历史记录（用于成功率计算）

    成功率定义：
    - 卖出信号成功：当日收盘价 < 信号发出时的价格
    - 买入信号成功：当日收盘价 > 信号发出时的价格
    """

    id: str
    symbol: str
    signal_type: Literal["high", "low"]  # high=卖点 low=买点

    # 信号发出时的信息
    signal_time: datetime
    signal_price: float
    confidence: float = Field(ge=0, le=1, default=0.5)
    reason: Optional[str] = None

    # 验证结果（盘后填充）
    close_price: Optional[float] = None  # 当日收盘价
    actual_high: Optional[float] = None  # 信号后最高价
    actual_low: Optional[float] = None  # 信号后最低价
    is_success: Optional[bool] = None  # 是否成功

    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    verified_at: Optional[datetime] = None


class SignalHistoryStats(BaseModel):
    """信号成功率统计"""

    symbol: str
    period_days: int = 30

    # 卖出信号统计
    sell_total: int = 0
    sell_success: int = 0
    sell_success_rate: float = 0.0

    # 买入信号统计
    buy_total: int = 0
    buy_success: int = 0
    buy_success_rate: float = 0.0

    # 总体统计
    total_signals: int = 0
    overall_success_rate: float = 0.0

    updated_at: datetime = Field(default_factory=datetime.now)


# ============================================
# Watchlist (监控列表)
# ============================================


class WatchlistItem(BaseModel):
    """监控列表项"""

    symbol: str
    name: Optional[str] = None
    added_at: datetime = Field(default_factory=datetime.now)

    # 最新状态
    last_price: Optional[float] = None
    last_signal: Optional[str] = None
    last_signal_time: Optional[datetime] = None
    success_rate: Optional[float] = None

    # 配置
    alert_enabled: bool = True
    notes: Optional[str] = None


class WatchlistResponse(BaseModel):
    """监控列表响应"""

    items: List[WatchlistItem]
    total: int
