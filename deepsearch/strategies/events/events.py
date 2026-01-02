"""
Strategy Event Types

Defines all strategy-related events for the event-driven system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class StrategyEventType(Enum):
    """Strategy event type enumeration"""

    # Strategy lifecycle events
    STRATEGY_STARTED = "STRATEGY_STARTED"
    STRATEGY_STOPPED = "STRATEGY_STOPPED"
    STRATEGY_PAUSED = "STRATEGY_PAUSED"
    STRATEGY_RESUMED = "STRATEGY_RESUMED"
    STRATEGY_ERROR = "STRATEGY_ERROR"

    # Signal events
    STRATEGY_SIGNAL = "STRATEGY_SIGNAL"
    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    SIGNAL_VALIDATED = "SIGNAL_VALIDATED"
    SIGNAL_REJECTED = "SIGNAL_REJECTED"

    # Order events
    STRATEGY_ORDER_SUBMIT = "STRATEGY_ORDER_SUBMIT"
    STRATEGY_ORDER_CANCEL = "STRATEGY_ORDER_CANCEL"
    STRATEGY_ORDER_MODIFY = "STRATEGY_ORDER_MODIFY"

    # Position events
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    POSITION_UPDATED = "POSITION_UPDATED"

    # Risk events
    RISK_LIMIT_EXCEEDED = "RISK_LIMIT_EXCEEDED"
    DRAWDOWN_WARNING = "DRAWDOWN_WARNING"
    STOP_LOSS_TRIGGERED = "STOP_LOSS_TRIGGERED"

    # Performance events
    PERFORMANCE_UPDATE = "PERFORMANCE_UPDATE"
    METRICS_CALCULATED = "METRICS_CALCULATED"


@dataclass
class StrategyEvent:
    """Base strategy event class"""

    event_type: StrategyEventType
    strategy_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "event_type": self.event_type.value,
            "strategy_id": self.strategy_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


@dataclass
class SignalEvent(StrategyEvent):
    """Trading signal event"""

    symbol: str = ""
    signal_type: str = ""
    strength: int = 0
    price: float = 0.0
    indicators: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def __post_init__(self):
        """Initialize event type"""
        self.event_type = StrategyEventType.STRATEGY_SIGNAL
        self.data = {
            "symbol": self.symbol,
            "signal_type": self.signal_type,
            "strength": self.strength,
            "price": self.price,
            "indicators": self.indicators,
            "reason": self.reason,
        }


@dataclass
class OrderEvent(StrategyEvent):
    """Order event"""

    order_id: str = ""
    symbol: str = ""
    side: str = ""  # BUY/SELL
    size: float = 0.0
    price: Optional[float] = None
    order_type: str = "MARKET"
    status: str = "PENDING"

    def __post_init__(self):
        """Initialize event type"""
        self.event_type = StrategyEventType.STRATEGY_ORDER_SUBMIT
        self.data = {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "size": self.size,
            "price": self.price,
            "order_type": self.order_type,
            "status": self.status,
        }


@dataclass
class PositionEvent(StrategyEvent):
    """Position event"""

    symbol: str = ""
    position_size: float = 0.0
    avg_cost: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    def __post_init__(self):
        """Initialize event type"""
        self.event_type = StrategyEventType.POSITION_UPDATED
        self.data = {
            "symbol": self.symbol,
            "position_size": self.position_size,
            "avg_cost": self.avg_cost,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
        }


@dataclass
class RiskEvent(StrategyEvent):
    """Risk management event"""

    risk_type: str = ""  # DRAWDOWN, POSITION_LIMIT, LOSS_LIMIT
    current_value: float = 0.0
    limit_value: float = 0.0
    action: str = ""  # WARNING, STOP, REDUCE
    message: str = ""

    def __post_init__(self):
        """Initialize event type"""
        self.event_type = StrategyEventType.RISK_LIMIT_EXCEEDED
        self.data = {
            "risk_type": self.risk_type,
            "current_value": self.current_value,
            "limit_value": self.limit_value,
            "action": self.action,
            "message": self.message,
        }


@dataclass
class PerformanceEvent(StrategyEvent):
    """Performance update event"""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0

    def __post_init__(self):
        """Initialize event type"""
        self.event_type = StrategyEventType.PERFORMANCE_UPDATE
        self.data = {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl": self.total_pnl,
            "win_rate": self.win_rate,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
        }


class StrategyEventFactory:
    """Factory for creating strategy events"""

    @staticmethod
    def create_signal_event(
        strategy_id: str, symbol: str, signal_type: str, **kwargs
    ) -> SignalEvent:
        """Create signal event"""
        return SignalEvent(
            event_type=StrategyEventType.STRATEGY_SIGNAL,
            strategy_id=strategy_id,
            symbol=symbol,
            signal_type=signal_type,
            **kwargs,
        )

    @staticmethod
    def create_order_event(
        strategy_id: str, order_id: str, symbol: str, side: str, size: float, **kwargs
    ) -> OrderEvent:
        """Create order event"""
        return OrderEvent(
            event_type=StrategyEventType.STRATEGY_ORDER_SUBMIT,
            strategy_id=strategy_id,
            order_id=order_id,
            symbol=symbol,
            side=side,
            size=size,
            **kwargs,
        )

    @staticmethod
    def create_position_event(
        strategy_id: str, symbol: str, position_size: float, **kwargs
    ) -> PositionEvent:
        """Create position event"""
        return PositionEvent(
            event_type=StrategyEventType.POSITION_UPDATED,
            strategy_id=strategy_id,
            symbol=symbol,
            position_size=position_size,
            **kwargs,
        )

    @staticmethod
    def create_risk_event(
        strategy_id: str, risk_type: str, current_value: float, limit_value: float, **kwargs
    ) -> RiskEvent:
        """Create risk event"""
        return RiskEvent(
            event_type=StrategyEventType.RISK_LIMIT_EXCEEDED,
            strategy_id=strategy_id,
            risk_type=risk_type,
            current_value=current_value,
            limit_value=limit_value,
            **kwargs,
        )

    @staticmethod
    def create_performance_event(strategy_id: str, **metrics) -> PerformanceEvent:
        """Create performance event"""
        return PerformanceEvent(
            event_type=StrategyEventType.PERFORMANCE_UPDATE, strategy_id=strategy_id, **metrics
        )

    @staticmethod
    def create_lifecycle_event(
        event_type: StrategyEventType, strategy_id: str, **data
    ) -> StrategyEvent:
        """Create lifecycle event"""
        return StrategyEvent(event_type=event_type, strategy_id=strategy_id, data=data)
