"""简化版股票实体，满足单元测试的核心行为。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from .price import Price


@dataclass(slots=True)
class Stock:
    """描述股票基础信息与交易状态。"""

    symbol: Any  # 可以是str或Symbol对象
    name: str
    market: str = ""
    industry: Optional[str] = None
    sector: Optional[str] = None
    is_trading: bool = True
    halt_reason: Optional[str] = None
    current_price: Optional[Price] = None
    last_updated: Optional[datetime] = None
    # 以下属性用于兼容 stock_repository.py
    previous_close: Optional[Price] = None
    open_price: Optional[Price] = None
    high_price: Optional[Price] = None
    low_price: Optional[Price] = None
    volume: int = 0
    turnover: Any = None  # 可能是Decimal或None
    market_cap: Any = None
    pe_ratio: Any = None
    pb_ratio: Any = None
    updated_at: Optional[datetime] = None

    # 向后兼容的私有属性访问器
    @property
    def _turnover(self) -> Any:
        return self.turnover

    @property
    def _market_cap(self) -> Any:
        return self.market_cap

    @property
    def _pe_ratio(self) -> Any:
        return self.pe_ratio

    @property
    def _pb_ratio(self) -> Any:
        return self.pb_ratio

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
        # symbol可能是str或有value属性的对象
        my_symbol = getattr(self.symbol, "value", self.symbol)
        other_symbol = getattr(other.symbol, "value", other.symbol)
        return bool(str(my_symbol) == str(other_symbol))

    def __hash__(self) -> int:
        symbol_value = getattr(self.symbol, "value", self.symbol)
        return hash(str(symbol_value))
