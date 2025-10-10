"""简化版股票实体，满足单元测试的核心行为。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .price import Price


@dataclass(slots=True)
class Stock:
    """描述股票基础信息与交易状态。"""

    symbol: str
    name: str
    market: str = ""
    industry: Optional[str] = None
    sector: Optional[str] = None
    is_trading: bool = True
    halt_reason: Optional[str] = None
    current_price: Optional[Price] = None
    last_updated: Optional[datetime] = None

    def halt_trading(self, reason: Optional[str] = None) -> None:
        """标记股票停牌并记录原因。"""

        self.is_trading = False
        self.halt_reason = reason

    def resume_trading(self) -> None:
        """恢复交易状态。"""

        self.is_trading = True
        self.halt_reason = None

    def update_price(self, price: Price) -> None:
        """更新最新价格并记录更新时间。"""

        self.current_price = price
        self.last_updated = datetime.now()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Stock):
            return NotImplemented
        return self.symbol == other.symbol

    def __hash__(self) -> int:
        return hash(self.symbol)
