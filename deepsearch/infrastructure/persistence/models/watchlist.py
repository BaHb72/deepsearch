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

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # 最新状态
    last_price: Mapped[Optional[float]] = mapped_column(nullable=True)
    last_signal: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_signal_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    success_rate: Mapped[Optional[float]] = mapped_column(nullable=True)

    # 配置
    alert_enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 仓位配置（新增）
    total_value: Mapped[Optional[float]] = mapped_column(nullable=True)  # 用户输入的总市值
    grid_levels: Mapped[int] = mapped_column(nullable=False, default=5)  # 网格层数
    trading_ratio: Mapped[float] = mapped_column(nullable=False, default=50.0)  # 做T仓位比例%

    # 时间戳
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
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

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "high" or "low"

    # 信号发出时的信息
    signal_time: Mapped[datetime] = mapped_column(nullable=False, index=True)
    signal_price: Mapped[float] = mapped_column(nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.5)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 验证结果（盘后填充）
    close_price: Mapped[Optional[float]] = mapped_column(nullable=True)
    actual_high: Mapped[Optional[float]] = mapped_column(nullable=True)
    actual_low: Mapped[Optional[float]] = mapped_column(nullable=True)
    is_success: Mapped[Optional[bool]] = mapped_column(nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

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

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # 入场信息
    entry_time: Mapped[datetime] = mapped_column(nullable=False, index=True)
    entry_price: Mapped[float] = mapped_column(nullable=False)
    entry_signal: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # 触发信号类型

    # 出场信息（平仓后填充）
    exit_time: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    exit_price: Mapped[Optional[float]] = mapped_column(nullable=True)
    exit_signal: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # 交易详情
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # "buy_first" / "sell_first"
    quantity: Mapped[int] = mapped_column(nullable=False)  # 股数

    # 收益（平仓时自动计算）
    pnl: Mapped[Optional[float]] = mapped_column(nullable=True)  # 绝对收益
    pnl_ratio: Mapped[Optional[float]] = mapped_column(nullable=True)  # 收益率%
    trading_cost: Mapped[Optional[float]] = mapped_column(nullable=True)  # 交易成本
    is_success: Mapped[Optional[bool]] = mapped_column(nullable=True)  # 是否盈利

    # 状态
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")  # open / closed

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

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

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(8), nullable=False, default="A")  # A/HK/US

    # 持仓信息
    quantity: Mapped[int] = mapped_column(nullable=False, default=0)  # 持有数量
    cost_price: Mapped[float] = mapped_column(nullable=False, default=0.0)  # 成本价

    # T+1 规则（仅A股生效）
    available_qty: Mapped[int] = mapped_column(nullable=False, default=0)  # 可卖数量
    frozen_qty: Mapped[int] = mapped_column(nullable=False, default=0)  # 冻结数量（当日买入）
    last_buy_date: Mapped[Optional[datetime]] = mapped_column(nullable=True)  # 最近买入日期

    # 分类
    position_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="trading"
    )  # base/trading

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
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
