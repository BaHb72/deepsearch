"""持仓管理服务。

提供统一的持仓操作入口，支持 T+1/T+0 规则、盈亏计算。
参考 Vn.py portfolio_manager 设计。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from deepsearch.infrastructure.persistence.watchlist_repository import PositionRepository
from deepsearch.observability.logger import logger


@dataclass
class PositionDTO:
    """持仓数据传输对象。"""

    id: int
    symbol: str
    market: str
    quantity: int
    cost_price: float
    available_qty: int
    frozen_qty: int
    last_buy_date: Optional[datetime]
    position_type: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PositionDTO":
        """从字典创建 DTO。"""
        return cls(
            id=data["id"],
            symbol=data["symbol"],
            market=data["market"],
            quantity=data["quantity"],
            cost_price=data["cost_price"],
            available_qty=data["available_qty"],
            frozen_qty=data["frozen_qty"],
            last_buy_date=data.get("last_buy_date"),
            position_type=data["position_type"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
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


@dataclass
class PnLResult:
    """盈亏计算结果。"""

    symbol: str
    quantity: int
    cost_price: float
    current_price: float
    market_value: float  # 市值
    cost_value: float  # 成本
    unrealized_pnl: float  # 浮动盈亏
    pnl_ratio: float  # 盈亏比例 %


@dataclass
class PortfolioSummary:
    """持仓汇总。"""

    total_positions: int
    total_market_value: float
    total_cost_value: float
    total_unrealized_pnl: float
    total_pnl_ratio: float


class PositionService:
    """通用持仓管理服务。

    特性：
    - 统一的 buy/sell 操作入口
    - 自动处理 T+1 规则（A股）和 T+0（港美股）
    - 盈亏计算
    - 事件通知（可选）

    参考 Vn.py portfolio_manager 设计。
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PositionRepository(session)
        self.logger = logger.bind(module="PositionService")
        self._change_handlers: List[Callable] = []

    # ===========================================
    # 读取操作
    # ===========================================

    async def get_all(self) -> List[PositionDTO]:
        """获取所有持仓。"""
        positions = await self.repo.get_all()
        return [PositionDTO.from_dict(p) for p in positions]

    async def get_by_symbol(self, symbol: str) -> Optional[PositionDTO]:
        """获取单只股票持仓。"""
        position = await self.repo.get_by_symbol(symbol)
        if position is None:
            return None
        return PositionDTO.from_dict(position)

    # ===========================================
    # 交易操作（核心）
    # ===========================================

    async def create(
        self,
        symbol: str,
        quantity: int,
        cost_price: float,
        market: str = "A",
        position_type: str = "trading",
    ) -> PositionDTO:
        """创建持仓（手动录入已有持仓）。"""
        result = await self.repo.create(
            symbol=symbol,
            quantity=quantity,
            cost_price=cost_price,
            market=market,
            position_type=position_type,
        )
        dto = PositionDTO.from_dict(result)
        await self._notify_change("create", dto)
        return dto

    async def buy(
        self,
        symbol: str,
        quantity: int,
        price: float,
        market: str = "A",
        source: str = "manual",
    ) -> PositionDTO:
        """买入股票。

        Args:
            symbol: 股票代码
            quantity: 数量
            price: 价格
            market: 市场 (A/HK/US)
            source: 来源 (manual/signal/strategy)

        Returns:
            更新后的持仓
        """
        self.logger.info(f"Buy: {symbol} +{quantity}@{price} source={source}")
        result = await self.repo.buy(
            symbol=symbol,
            quantity=quantity,
            price=price,
            market=market,
        )
        dto = PositionDTO.from_dict(result)
        await self._notify_change("buy", dto)
        return dto

    async def sell(
        self,
        symbol: str,
        quantity: int,
        price: float,
        source: str = "manual",
    ) -> PositionDTO:
        """卖出股票（T+1 规则校验）。

        Args:
            symbol: 股票代码
            quantity: 数量
            price: 价格
            source: 来源 (manual/signal/strategy)

        Returns:
            更新后的持仓

        Raises:
            ValueError: 可卖数量不足
        """
        self.logger.info(f"Sell: {symbol} -{quantity}@{price} source={source}")
        result = await self.repo.sell(
            symbol=symbol,
            quantity=quantity,
            price=price,
        )
        dto = PositionDTO.from_dict(result)
        await self._notify_change("sell", dto)
        return dto

    async def delete(self, symbol: str) -> bool:
        """删除持仓。"""
        deleted = await self.repo.delete(symbol)
        if deleted:
            await self._notify_change("delete", symbol)
        return deleted

    # ===========================================
    # 盈亏计算
    # ===========================================

    async def calc_pnl(
        self,
        symbol: str,
        current_price: float,
    ) -> Optional[PnLResult]:
        """计算单只股票盈亏。"""
        position = await self.get_by_symbol(symbol)
        if position is None or position.quantity == 0:
            return None

        market_value = position.quantity * current_price
        cost_value = position.quantity * position.cost_price
        unrealized_pnl = market_value - cost_value
        pnl_ratio = (unrealized_pnl / cost_value * 100) if cost_value > 0 else 0.0

        return PnLResult(
            symbol=symbol,
            quantity=position.quantity,
            cost_price=position.cost_price,
            current_price=current_price,
            market_value=market_value,
            cost_value=cost_value,
            unrealized_pnl=unrealized_pnl,
            pnl_ratio=pnl_ratio,
        )

    async def calc_portfolio_summary(
        self,
        prices: Dict[str, float],
    ) -> PortfolioSummary:
        """计算持仓汇总。

        Args:
            prices: 当前价格字典 {symbol: price}
        """
        positions = await self.get_all()

        total_market_value = 0.0
        total_cost_value = 0.0

        for pos in positions:
            current_price = prices.get(pos.symbol, pos.cost_price)
            total_market_value += pos.quantity * current_price
            total_cost_value += pos.quantity * pos.cost_price

        total_unrealized_pnl = total_market_value - total_cost_value
        total_pnl_ratio = (
            (total_unrealized_pnl / total_cost_value * 100) if total_cost_value > 0 else 0.0
        )

        return PortfolioSummary(
            total_positions=len(positions),
            total_market_value=total_market_value,
            total_cost_value=total_cost_value,
            total_unrealized_pnl=total_unrealized_pnl,
            total_pnl_ratio=total_pnl_ratio,
        )

    # ===========================================
    # T+1 结算
    # ===========================================

    async def daily_settlement(self) -> int:
        """每日结算：解冻 A股 T+1 可卖数量。"""
        count = await self.repo.daily_settlement()
        self.logger.info(f"Daily settlement: {count} positions unfrozen")
        return count

    # ===========================================
    # 实时盈亏计算
    # ===========================================

    async def _get_realtime_price(self, symbol: str) -> Optional[float]:
        """获取实时价格。

        尝试从 DataSourceManager 获取实时行情。
        """
        try:
            from deepsearch.infrastructure.providers.managers.data_source_manager import (
                get_data_source_manager,
            )

            manager = get_data_source_manager()
            result = await manager.execute_with_fallback("get_realtime_quote", symbol=symbol)
            if result and "latestPrice" in result:
                return float(result["latestPrice"])
            elif result and "price" in result:
                return float(result["price"])
            elif result and "close" in result:
                return float(result["close"])
            return None
        except Exception as e:
            self.logger.warning(f"Failed to get realtime price for {symbol}: {e}")
            return None

    async def calc_pnl_realtime(self, symbol: str) -> Optional[PnLResult]:
        """计算实时盈亏（自动获取当前价格）。"""
        position = await self.get_by_symbol(symbol)
        if position is None or position.quantity == 0:
            return None

        current_price = await self._get_realtime_price(symbol)
        if current_price is None:
            # 无法获取实时价格，使用成本价
            self.logger.warning(f"Using cost price for {symbol} (no realtime data)")
            current_price = position.cost_price

        return await self.calc_pnl(symbol, current_price)

    async def calc_portfolio_summary_realtime(self) -> PortfolioSummary:
        """计算实时持仓汇总（自动获取所有股票当前价格）。"""
        positions = await self.get_all()
        prices: Dict[str, float] = {}

        for pos in positions:
            price = await self._get_realtime_price(pos.symbol)
            if price is not None:
                prices[pos.symbol] = price
            else:
                prices[pos.symbol] = pos.cost_price

        return await self.calc_portfolio_summary(prices)

    async def get_all_with_pnl(self) -> List[Dict[str, Any]]:
        """获取所有持仓及其实时盈亏。"""
        positions = await self.get_all()
        results = []

        for pos in positions:
            price = await self._get_realtime_price(pos.symbol)
            if price is None:
                price = pos.cost_price

            market_value = pos.quantity * price
            cost_value = pos.quantity * pos.cost_price
            unrealized_pnl = market_value - cost_value
            pnl_ratio = (unrealized_pnl / cost_value * 100) if cost_value > 0 else 0.0

            result = pos.to_dict()
            result.update(
                {
                    "current_price": price,
                    "market_value": market_value,
                    "unrealized_pnl": unrealized_pnl,
                    "pnl_ratio": pnl_ratio,
                }
            )
            results.append(result)

        return results

    # ===========================================
    # 事件机制
    # ===========================================

    def on_position_changed(self, handler: Callable) -> None:
        """订阅持仓变更事件。

        handler(event_type: str, data: PositionDTO | str)
        """
        self._change_handlers.append(handler)

    async def _notify_change(self, event_type: str, data: Any) -> None:
        """通知持仓变更。"""
        for handler in self._change_handlers:
            try:
                if callable(handler):
                    handler(event_type, data)
            except Exception as e:
                self.logger.warning(f"Event handler error: {e}")


__all__ = [
    "PositionService",
    "PositionDTO",
    "PnLResult",
    "PortfolioSummary",
]
