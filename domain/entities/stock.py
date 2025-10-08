"""股票领域实体的最小占位实现，确保类型检查可用。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from domain.values.price import Price
from domain.values.symbol import Symbol


@dataclass(slots=True)
class Stock:
    """股票实体，聚合仓库访问所需的核心字段。"""

    symbol: Symbol
    name: str
    current_price: Optional[Price] = None
    previous_close: Optional[Price] = None
    open_price: Optional[Price] = None
    high_price: Optional[Price] = None
    low_price: Optional[Price] = None
    volume: int = 0
    turnover: Optional[float] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    is_trading: bool = True
    updated_at: Optional[datetime] = None
