"""T-Trading 监控列表、信号历史与交易记录 ORM 模型。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class WatchlistItemDB(Base):
    """T-Trading 监控列表项。

    存储用户添加的股票监控列表，支持持久化存储。
    """

    __tablename__ = "ttrading_watchlist"

    # 必填字段
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    # 可选字段（有默认值）
    name: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    last_price: Mapped[Optional[float]] = mapped_column(default=None)
    last_signal: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    last_signal_time: Mapped[Optional[datetime]] = mapped_column(default=None)
    success_rate: Mapped[Optional[float]] = mapped_column(default=None)
    alert_enabled: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    total_value: Mapped[Optional[float]] = mapped_column(default=None)
    grid_levels: Mapped[int] = mapped_column(default=5)
    trading_ratio: Mapped[float] = mapped_column(default=50.0)

    # 自动生成字段（init=False）
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    added_at: Mapped[datetime] = mapped_column(
        default_factory=lambda: datetime.now(timezone.utc),
        init=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        init=False,
    )

    def __repr__(self) -> str:
        return f"<WatchlistItemDB(symbol='{self.symbol}', name='{self.name}')>"

    def to_dict(self) -> dict[str, Any]:
        """转换为 Pydantic 模型兼容的字典。"""
        return {
            "symbol": self.symbol,
            "name": self.name,
            "added_at": self.added_at,
            "last_price": self.last_price,
            "last_signal": self.last_signal,
            "last_signal_time": self.last_signal_time,
            "success_rate": self.success_rate,
            "alert_enabled": self.alert_enabled,
            "notes": self.notes,
            "total_value": self.total_value,
            "grid_levels": self.grid_levels,
            "trading_ratio": self.trading_ratio,
        }


class SignalHistoryDB(Base):
    """T-Trading 信号历史记录。

    存储交易信号用于成功率计算和回溯分析。
    """

    __tablename__ = "ttrading_signal_history"

    # 必填字段（由调用方提供）
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    signal_type: Mapped[str] = mapped_column(String(16))  # "high" or "low"
    signal_time: Mapped[datetime] = mapped_column(index=True)
    signal_price: Mapped[float] = mapped_column()

    # 可选字段（有默认值）
    confidence: Mapped[float] = mapped_column(default=0.5)
    reason: Mapped[Optional[str]] = mapped_column(Text, default=None)
    close_price: Mapped[Optional[float]] = mapped_column(default=None)
    actual_high: Mapped[Optional[float]] = mapped_column(default=None)
    actual_low: Mapped[Optional[float]] = mapped_column(default=None)
    is_success: Mapped[Optional[bool]] = mapped_column(default=None)
    verified_at: Mapped[Optional[datetime]] = mapped_column(default=None)

    # 自动生成字段
    created_at: Mapped[datetime] = mapped_column(
        default_factory=lambda: datetime.now(timezone.utc),
        init=False,
    )

    def __repr__(self) -> str:
        return (
            f"<SignalHistoryDB(id='{self.id}', symbol='{self.symbol}', type='{self.signal_type}')>"
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为 Pydantic 模型兼容的字典。"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "signal_type": self.signal_type,
            "signal_time": self.signal_time,
            "signal_price": self.signal_price,
            "confidence": self.confidence,
            "reason": self.reason,
            "close_price": self.close_price,
            "actual_high": self.actual_high,
            "actual_low": self.actual_low,
            "is_success": self.is_success,
            "created_at": self.created_at,
            "verified_at": self.verified_at,
        }


class TTradingRecordDB(Base):
    """T-Trading 交易记录。

    记录每次买卖操作用于收益分析和统计。
    """

    __tablename__ = "ttrading_records"

    # 必填字段（由调用方提供）
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    entry_time: Mapped[datetime] = mapped_column(index=True)
    entry_price: Mapped[float] = mapped_column()
    direction: Mapped[str] = mapped_column(String(16))  # "buy_first" / "sell_first"
    quantity: Mapped[int] = mapped_column()

    # 可选字段（有默认值）
    entry_signal: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    exit_time: Mapped[Optional[datetime]] = mapped_column(default=None)
    exit_price: Mapped[Optional[float]] = mapped_column(default=None)
    exit_signal: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    pnl: Mapped[Optional[float]] = mapped_column(default=None)
    pnl_ratio: Mapped[Optional[float]] = mapped_column(default=None)
    trading_cost: Mapped[Optional[float]] = mapped_column(default=None)
    is_success: Mapped[Optional[bool]] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(String(16), default="open")
    closed_at: Mapped[Optional[datetime]] = mapped_column(default=None)

    # 自动生成字段
    created_at: Mapped[datetime] = mapped_column(
        default_factory=lambda: datetime.now(timezone.utc),
        init=False,
    )

    def __repr__(self) -> str:
        return f"<TTradingRecordDB(id='{self.id}', symbol='{self.symbol}', direction='{self.direction}')>"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "entry_time": self.entry_time,
            "entry_price": self.entry_price,
            "entry_signal": self.entry_signal,
            "exit_time": self.exit_time,
            "exit_price": self.exit_price,
            "exit_signal": self.exit_signal,
            "direction": self.direction,
            "quantity": self.quantity,
            "pnl": self.pnl,
            "pnl_ratio": self.pnl_ratio,
            "trading_cost": self.trading_cost,
            "is_success": self.is_success,
            "status": self.status,
            "created_at": self.created_at,
            "closed_at": self.closed_at,
        }


class PositionDB(Base):
    """T-Trading 持仓记录。

    追踪股票持仓状态，支持 T+1 规则（A股）和 T+0（港美股）。
    """

    __tablename__ = "ttrading_positions"

    # 必填字段
    symbol: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    # 可选字段（有默认值）
    market: Mapped[str] = mapped_column(String(8), default="A")  # A/HK/US
    quantity: Mapped[int] = mapped_column(default=0)
    cost_price: Mapped[float] = mapped_column(default=0.0)
    available_qty: Mapped[int] = mapped_column(default=0)
    frozen_qty: Mapped[int] = mapped_column(default=0)
    last_buy_date: Mapped[Optional[datetime]] = mapped_column(default=None)
    position_type: Mapped[str] = mapped_column(String(16), default="trading")

    # 自动生成字段（init=False）
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    created_at: Mapped[datetime] = mapped_column(
        default_factory=lambda: datetime.now(timezone.utc),
        init=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        init=False,
    )

    def __repr__(self) -> str:
        return f"<PositionDB(symbol='{self.symbol}', qty={self.quantity}, available={self.available_qty})>"

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "market": self.market,
            "quantity": self.quantity,
            "cost_price": self.cost_price,
            "available_qty": self.available_qty,
            "frozen_qty": self.frozen_qty,
            "last_buy_date": self.last_buy_date,
            "position_type": self.position_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def get_settlement_days(self) -> int:
        """获取结算周期 T+N"""
        return {"A": 1, "HK": 0, "US": 0}.get(self.market, 1)  # type: ignore[return-value]

    def can_sell(self, sell_qty: int) -> bool:
        """检查是否可卖出指定数量"""
        if self.get_settlement_days() == 0:  # T+0 市场
            return self.quantity >= sell_qty
        else:  # T+1 市场
            return self.available_qty >= sell_qty


__all__ = ["WatchlistItemDB", "SignalHistoryDB", "TTradingRecordDB", "PositionDB"]
