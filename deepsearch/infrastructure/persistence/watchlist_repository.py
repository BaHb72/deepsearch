"""T-Trading 监控列表、交易记录数据访问层。

提供监控列表、信号历史和交易记录的数据库 CRUD 操作。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from deepsearch.infrastructure.persistence.models.watchlist import (
    SignalHistoryDB,
    TTradingRecordDB,
    WatchlistItemDB,
)
from deepsearch.observability.logger import logger
from deepsearch.strategies.interfaces.models import (
    PositionCalcResult,
    SignalHistory,
    SignalHistoryStats,
    WatchlistItem,
)


class WatchlistRepository:
    """监控列表数据访问层。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = logger.bind(module="WatchlistRepository")

    async def get_all(self) -> list[WatchlistItem]:
        """获取所有监控列表项。"""
        stmt = select(WatchlistItemDB).order_by(WatchlistItemDB.added_at.desc())
        result = await self.session.execute(stmt)
        items = result.scalars().all()
        return [WatchlistItem(**item.to_dict()) for item in items]

    async def get_by_symbol(self, symbol: str) -> Optional[WatchlistItem]:
        """根据股票代码获取监控项。"""
        stmt = select(WatchlistItemDB).where(WatchlistItemDB.symbol == symbol)
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()
        if item is None:
            return None
        return WatchlistItem(**item.to_dict())

    async def exists(self, symbol: str) -> bool:
        """检查股票是否已在监控列表中。"""
        stmt = select(WatchlistItemDB.id).where(WatchlistItemDB.symbol == symbol)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add(
        self,
        symbol: str,
        name: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> WatchlistItem:
        """添加股票到监控列表。"""
        item = WatchlistItemDB(
            symbol=symbol,
            name=name,
            notes=notes,
            added_at=datetime.now(timezone.utc),
        )
        self.session.add(item)
        await self.session.flush()
        self.logger.info(f"Added to watchlist: {symbol}")
        return WatchlistItem(**item.to_dict())

    async def update(
        self,
        symbol: str,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        alert_enabled: Optional[bool] = None,
        last_price: Optional[float] = None,
        last_signal: Optional[str] = None,
        last_signal_time: Optional[datetime] = None,
        success_rate: Optional[float] = None,
        total_value: Optional[float] = None,
        grid_levels: Optional[int] = None,
        trading_ratio: Optional[float] = None,
    ) -> Optional[WatchlistItem]:
        """更新监控列表项。"""
        # 构建更新字段
        update_data: dict[str, Any] = {}
        if name is not None:
            update_data["name"] = name
        if notes is not None:
            update_data["notes"] = notes
        if alert_enabled is not None:
            update_data["alert_enabled"] = alert_enabled
        if last_price is not None:
            update_data["last_price"] = last_price
        if last_signal is not None:
            update_data["last_signal"] = last_signal
        if last_signal_time is not None:
            update_data["last_signal_time"] = last_signal_time
        if success_rate is not None:
            update_data["success_rate"] = success_rate
        if total_value is not None:
            update_data["total_value"] = total_value
        if grid_levels is not None:
            update_data["grid_levels"] = grid_levels
        if trading_ratio is not None:
            update_data["trading_ratio"] = trading_ratio

        if not update_data:
            return await self.get_by_symbol(symbol)

        stmt = (
            update(WatchlistItemDB)
            .where(WatchlistItemDB.symbol == symbol)
            .values(**update_data)
            .returning(WatchlistItemDB)
        )
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()
        if item is None:
            return None
        return WatchlistItem(**item.to_dict())

    async def delete(self, symbol: str) -> bool:
        """从监控列表移除股票。"""
        stmt = delete(WatchlistItemDB).where(WatchlistItemDB.symbol == symbol)
        result = await self.session.execute(stmt)
        deleted = (result.rowcount or 0) > 0
        if deleted:
            self.logger.info(f"Removed from watchlist: {symbol}")
        return deleted

    async def calc_position(
        self, symbol: str, current_price: float
    ) -> Optional[PositionCalcResult]:
        """计算仓位分配。"""
        item = await self.get_by_symbol(symbol)
        if item is None or item.total_value is None:
            return None

        total_value = item.total_value
        grid_levels = item.grid_levels
        trading_ratio = item.trading_ratio

        # 计算
        total_shares = int(total_value / current_price)
        base_ratio = (100 - trading_ratio) / 100
        trading_shares = int(total_shares * trading_ratio / 100)
        base_shares = int(total_shares * base_ratio)

        # 每层网格股数（向下取整到100股）
        per_level_shares = (trading_shares // grid_levels // 100) * 100

        return PositionCalcResult(
            symbol=symbol,
            current_price=current_price,
            total_value=total_value,
            total_shares=total_shares,
            base_shares=base_shares,
            trading_shares=trading_shares,
            per_level_shares=per_level_shares,
            grid_levels=grid_levels,
            trading_ratio=trading_ratio,
        )


class SignalHistoryRepository:
    """信号历史数据访问层。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = logger.bind(module="SignalHistoryRepository")

    async def save(
        self,
        symbol: str,
        signal_type: str,
        signal_price: float,
        confidence: float = 0.5,
        reason: Optional[str] = None,
    ) -> SignalHistory:
        """保存信号记录。"""
        signal_id = str(uuid4())
        signal = SignalHistoryDB(
            id=signal_id,
            symbol=symbol,
            signal_type=signal_type,
            signal_time=datetime.now(timezone.utc),
            signal_price=signal_price,
            confidence=confidence,
            reason=reason,
        )
        self.session.add(signal)
        await self.session.flush()
        self.logger.info(f"Signal saved: {symbol} {signal_type} @ {signal_price}")
        return SignalHistory(**signal.to_dict())

    async def get_by_symbol(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> list[SignalHistory]:
        """获取信号历史。"""
        stmt = select(SignalHistoryDB).order_by(SignalHistoryDB.signal_time.desc())
        if symbol:
            stmt = stmt.where(SignalHistoryDB.symbol == symbol)
        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        signals = result.scalars().all()
        return [SignalHistory(**s.to_dict()) for s in signals]

    async def get_by_id(self, signal_id: str) -> Optional[SignalHistoryDB]:
        """根据 ID 获取信号（返回 ORM 对象用于更新）。"""
        stmt = select(SignalHistoryDB).where(SignalHistoryDB.id == signal_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def verify(
        self,
        signal_id: str,
        close_price: float,
        actual_high: Optional[float] = None,
        actual_low: Optional[float] = None,
    ) -> Optional[dict[str, Any]]:
        """验证信号成功率（盘后调用）。"""
        signal = await self.get_by_id(signal_id)
        if signal is None:
            return None

        # 更新验证结果
        signal.close_price = close_price
        signal.actual_high = actual_high
        signal.actual_low = actual_low
        signal.verified_at = datetime.now(timezone.utc)

        # 计算是否成功
        if signal.signal_type == "high":  # 卖出信号：收盘价 < 信号价格 = 成功
            signal.is_success = close_price < signal.signal_price
        else:  # 买入信号：收盘价 > 信号价格 = 成功
            signal.is_success = close_price > signal.signal_price

        await self.session.flush()
        self.logger.info(
            f"Signal verified: {signal.symbol} {signal.signal_type} "
            f"is_success={signal.is_success}"
        )
        return {"success": True, "is_success": signal.is_success}

    async def get_stats(self, symbol: str, days: int = 30) -> SignalHistoryStats:
        """获取信号成功率统计。"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(SignalHistoryDB)
            .where(SignalHistoryDB.symbol == symbol)
            .where(SignalHistoryDB.signal_time >= cutoff)
        )
        result = await self.session.execute(stmt)
        signals = result.scalars().all()

        # 计算统计
        sell_signals = [s for s in signals if s.signal_type == "high"]
        buy_signals = [s for s in signals if s.signal_type == "low"]

        sell_success = sum(1 for s in sell_signals if s.is_success)
        buy_success = sum(1 for s in buy_signals if s.is_success)

        total = len(signals)
        total_success = sell_success + buy_success

        return SignalHistoryStats(
            symbol=symbol,
            period_days=days,
            sell_total=len(sell_signals),
            sell_success=sell_success,
            sell_success_rate=sell_success / len(sell_signals) if sell_signals else 0,
            buy_total=len(buy_signals),
            buy_success=buy_success,
            buy_success_rate=buy_success / len(buy_signals) if buy_signals else 0,
            total_signals=total,
            overall_success_rate=total_success / total if total else 0,
        )


class TTradingRecordRepository:
    """交易记录数据访问层。"""

    # 交易成本配置（万二 + 印花税千分之一）
    COMMISSION_RATE = 0.0002
    MIN_COMMISSION = 5.0
    STAMP_TAX_RATE = 0.001
    TRANSFER_FEE_RATE = 0.00001

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = logger.bind(module="TTradingRecordRepository")

    def _calc_trading_cost(self, amount: float, is_sell: bool = False) -> float:
        """计算交易成本。"""
        commission = max(amount * self.COMMISSION_RATE, self.MIN_COMMISSION)
        transfer_fee = amount * self.TRANSFER_FEE_RATE
        stamp_tax = amount * self.STAMP_TAX_RATE if is_sell else 0
        return commission + transfer_fee + stamp_tax

    async def create(
        self,
        symbol: str,
        entry_price: float,
        direction: Literal["buy_first", "sell_first"],
        quantity: int,
        entry_signal: Optional[str] = None,
    ) -> dict[str, Any]:
        """创建入场记录。"""
        record_id = str(uuid4())
        record = TTradingRecordDB(
            id=record_id,
            symbol=symbol,
            entry_time=datetime.now(timezone.utc),
            entry_price=entry_price,
            entry_signal=entry_signal,
            direction=direction,
            quantity=quantity,
            status="open",
        )
        self.session.add(record)
        await self.session.flush()
        self.logger.info(
            f"Trading record created: {symbol} {direction} " f"{quantity}股 @ {entry_price}"
        )
        return record.to_dict()

    async def close(
        self,
        record_id: str,
        exit_price: float,
        exit_signal: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """平仓并计算收益。"""
        stmt = select(TTradingRecordDB).where(TTradingRecordDB.id == record_id)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            return None

        if record.status == "closed":
            return {"error": "Record already closed"}

        # 计算收益
        entry_amount = record.entry_price * record.quantity
        exit_amount = exit_price * record.quantity

        # 计算交易成本
        is_sell_first = record.direction == "sell_first"
        entry_cost = self._calc_trading_cost(entry_amount, is_sell=is_sell_first)
        exit_cost = self._calc_trading_cost(exit_amount, is_sell=not is_sell_first)
        total_cost = entry_cost + exit_cost

        # 计算毛利润
        if record.direction == "buy_first":  # 先买后卖
            gross_pnl = (exit_price - record.entry_price) * record.quantity
        else:  # 先卖后买 (做T)
            gross_pnl = (record.entry_price - exit_price) * record.quantity

        # 净利润
        pnl = gross_pnl - total_cost
        pnl_ratio = (pnl / entry_amount) * 100

        # 更新记录
        record.exit_time = datetime.now(timezone.utc)
        record.exit_price = exit_price
        record.exit_signal = exit_signal
        record.pnl = pnl
        record.pnl_ratio = pnl_ratio
        record.trading_cost = total_cost
        record.is_success = pnl > 0
        record.status = "closed"
        record.closed_at = datetime.now(timezone.utc)

        await self.session.flush()
        self.logger.info(
            f"Trading record closed: {record.symbol} " f"pnl={pnl:.2f} ({pnl_ratio:.2f}%)"
        )
        return record.to_dict()

    async def get_by_symbol(
        self,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """获取交易记录。"""
        stmt = select(TTradingRecordDB).order_by(TTradingRecordDB.entry_time.desc())
        if symbol:
            stmt = stmt.where(TTradingRecordDB.symbol == symbol)
        if status:
            stmt = stmt.where(TTradingRecordDB.status == status)
        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        records = result.scalars().all()
        return [r.to_dict() for r in records]

    async def get_stats(self, symbol: str, days: int = 30) -> dict[str, Any]:
        """获取交易统计。"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(TTradingRecordDB)
            .where(TTradingRecordDB.symbol == symbol)
            .where(TTradingRecordDB.status == "closed")
            .where(TTradingRecordDB.closed_at >= cutoff)
        )
        result = await self.session.execute(stmt)
        records = list(result.scalars().all())

        if not records:
            return {
                "symbol": symbol,
                "period_days": days,
                "total_trades": 0,
                "success_trades": 0,
                "success_rate": 0,
                "total_pnl": 0,
                "avg_pnl": 0,
            }

        success_count = sum(1 for r in records if r.is_success)
        total_pnl = sum(r.pnl or 0 for r in records)

        return {
            "symbol": symbol,
            "period_days": days,
            "total_trades": len(records),
            "success_trades": success_count,
            "success_rate": success_count / len(records) if records else 0,
            "total_pnl": total_pnl,
            "avg_pnl": total_pnl / len(records) if records else 0,
        }

    async def delete(self, record_id: str) -> bool:
        """删除交易记录。"""
        stmt = delete(TTradingRecordDB).where(TTradingRecordDB.id == record_id)
        result = await self.session.execute(stmt)
        return (result.rowcount or 0) > 0


class PositionRepository:
    """持仓数据访问层。

    支持 T+1 规则（A股）和 T+0（港美股）。
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = logger.bind(module="PositionRepository")

    async def get_all(self) -> list[dict[str, Any]]:
        """获取所有持仓。"""
        from deepsearch.infrastructure.persistence.models.watchlist import PositionDB

        stmt = select(PositionDB).order_by(PositionDB.symbol)
        result = await self.session.execute(stmt)
        positions = result.scalars().all()
        return [p.to_dict() for p in positions]

    async def get_by_symbol(self, symbol: str) -> Optional[dict[str, Any]]:
        """根据股票代码获取持仓。"""
        from deepsearch.infrastructure.persistence.models.watchlist import PositionDB

        stmt = select(PositionDB).where(PositionDB.symbol == symbol)
        result = await self.session.execute(stmt)
        position = result.scalar_one_or_none()
        if position is None:
            return None
        return position.to_dict()

    async def _get_position_db(self, symbol: str):
        """获取 PositionDB ORM 对象。"""
        from deepsearch.infrastructure.persistence.models.watchlist import PositionDB

        stmt = select(PositionDB).where(PositionDB.symbol == symbol)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        symbol: str,
        quantity: int,
        cost_price: float,
        market: str = "A",
        position_type: str = "trading",
    ) -> dict[str, Any]:
        """创建持仓记录（手动录入已有持仓）。"""
        from deepsearch.infrastructure.persistence.models.watchlist import PositionDB

        today = datetime.now(timezone.utc)
        settlement_days = {"A": 1, "HK": 0, "US": 0}.get(market, 1)

        # 根据市场规则设置可卖数量
        available_qty = quantity if settlement_days == 0 else 0
        frozen_qty = 0 if settlement_days == 0 else quantity

        position = PositionDB(
            symbol=symbol,
            market=market,
            quantity=quantity,
            cost_price=cost_price,
            available_qty=available_qty,
            frozen_qty=frozen_qty,
            last_buy_date=today,
            position_type=position_type,
        )
        self.session.add(position)
        await self.session.flush()
        self.logger.info(f"Position created: {symbol} qty={quantity}")
        return position.to_dict()

    async def buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
        market: str = "A",
    ) -> dict[str, Any]:
        """买入股票（更新持仓）。

        A股 T+1 规则：
        - T日买入 → frozen_qty
        - T+1日：之前的 frozen 解冻到 available，新买的继续冻结
        """

        # A股用北京时间，港美股用 UTC
        if market == "A":
            from zoneinfo import ZoneInfo

            china_tz = ZoneInfo("Asia/Shanghai")
            today_date = datetime.now(china_tz).date()
        else:
            today_date = datetime.now(timezone.utc).date()

        today = datetime.now(timezone.utc)
        settlement_days = {"A": 1, "HK": 0, "US": 0}.get(market, 1)

        position = await self._get_position_db(symbol)
        if position is None:
            # 创建新持仓
            return await self.create(symbol, quantity, price, market)

        # A股：买入前先解冻之前的冻结（如果 last_buy_date 是昨天或更早）
        if settlement_days > 0 and position.last_buy_date:
            # 使用相同时区比较
            if market == "A":
                from zoneinfo import ZoneInfo

                china_tz = ZoneInfo("Asia/Shanghai")
                last_buy_local = position.last_buy_date.astimezone(china_tz).date()
            else:
                last_buy_local = position.last_buy_date.date()

            if last_buy_local < today_date and position.frozen_qty > 0:
                # 之前的冻结解冻到可卖
                position.available_qty += position.frozen_qty
                self.logger.info(
                    f"Auto unfreeze before buy: {symbol} +{position.frozen_qty} available"
                )
                position.frozen_qty = 0

        # 更新现有持仓
        old_qty = position.quantity
        old_cost = position.cost_price

        # 加权平均成本
        new_qty = old_qty + quantity
        new_cost = (old_qty * old_cost + quantity * price) / new_qty if new_qty > 0 else price

        position.quantity = new_qty
        position.cost_price = new_cost
        position.last_buy_date = today

        if settlement_days == 0:  # T+0 市场：买入即可卖
            position.available_qty += quantity
        else:  # T+1 市场：买入冻结
            position.frozen_qty += quantity

        await self.session.flush()
        await self.session.refresh(position)
        self.logger.info(f"Position buy: {symbol} +{quantity}@{price}")
        return position.to_dict()

    async def sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
    ) -> dict[str, Any]:
        """卖出股票（T+1 规则校验）。

        A股：卖出前先检查是否需要解冻（last_buy_date < today）。
        使用北京时间判断 A股交易日。
        """
        position = await self._get_position_db(symbol)
        if position is None:
            raise ValueError(f"No position for {symbol}")

        # 获取结算规则
        settlement_days = {"A": 1, "HK": 0, "US": 0}.get(position.market, 1)

        # A股用北京时间判断交易日
        if position.market == "A":
            from zoneinfo import ZoneInfo

            china_tz = ZoneInfo("Asia/Shanghai")
            today_date = datetime.now(china_tz).date()
        else:
            today_date = datetime.now(timezone.utc).date()

        # A股：卖出前先解冻之前的冻结（如果 last_buy_date 是昨天或更早）
        if settlement_days > 0 and position.last_buy_date:
            if position.market == "A":
                from zoneinfo import ZoneInfo

                china_tz = ZoneInfo("Asia/Shanghai")
                last_buy_local = position.last_buy_date.astimezone(china_tz).date()
            else:
                last_buy_local = position.last_buy_date.date()

            if last_buy_local < today_date and position.frozen_qty > 0:
                position.available_qty += position.frozen_qty
                self.logger.info(
                    f"Auto unfreeze before sell: {symbol} +{position.frozen_qty} available"
                )
                position.frozen_qty = 0

        # T+1/T+0 校验
        if settlement_days == 0:  # T+0: 检查总持仓
            can_sell_flag = position.quantity >= quantity
        else:  # T+1: 检查可卖数量
            can_sell_flag = position.available_qty >= quantity

        if not can_sell_flag:
            raise ValueError(
                f"可卖数量不足: available={position.available_qty}, requested={quantity}"
            )

        # 更新持仓
        position.quantity -= quantity
        position.available_qty -= quantity

        await self.session.flush()
        await self.session.refresh(position)
        self.logger.info(f"Position sell: {symbol} -{quantity}@{price}")
        return position.to_dict()

    async def daily_settlement(self) -> int:
        """每日结算：解冻 T+1 可卖数量（A股）。

        应在每个交易日开盘前调用。
        返回更新的持仓数量。
        """
        from deepsearch.infrastructure.persistence.models.watchlist import PositionDB

        today = datetime.now(timezone.utc).date()
        stmt = select(PositionDB).where(
            PositionDB.market == "A",
            PositionDB.frozen_qty > 0,
        )
        result = await self.session.execute(stmt)
        positions = result.scalars().all()

        count = 0
        for p in positions:
            if p.last_buy_date and p.last_buy_date.date() < today:
                # 解冻
                p.available_qty = p.quantity
                p.frozen_qty = 0
                count += 1

        await self.session.flush()
        self.logger.info(f"Daily settlement: {count} positions unfrozen")
        return count

    async def delete(self, symbol: str) -> bool:
        """删除持仓。"""
        from deepsearch.infrastructure.persistence.models.watchlist import PositionDB

        stmt = delete(PositionDB).where(PositionDB.symbol == symbol)
        result = await self.session.execute(stmt)
        return (result.rowcount or 0) > 0


__all__ = [
    "WatchlistRepository",
    "SignalHistoryRepository",
    "TTradingRecordRepository",
    "PositionRepository",
]
