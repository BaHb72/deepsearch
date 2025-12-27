"""股票实体定义，提供仓储与接口层共享的数据结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping


class StockMarket(str, Enum):
    """股票市场枚举，覆盖常见交易所。"""

    CN = "CN"
    HK = "HK"
    US = "US"
    OTHER = "OTHER"


class StockStatus(str, Enum):
    """股票交易状态枚举。"""

    TRADING = "TRADING"
    HALTED = "HALTED"
    DELISTED = "DELISTED"


@dataclass(slots=True)
class StockEntity:
    """仓储层使用的股票实体。"""

    symbol: str
    name: str
    market: StockMarket = StockMarket.CN
    status: StockStatus = StockStatus.TRADING
    industry: str | None = None
    listing_date: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    current_price: Decimal | None = None
    prev_close: Decimal | None = None
    open_price: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    amount: Decimal | None = None
    market_cap: Decimal | None = None
    pe_ratio: Decimal | None = None
    pb_ratio: Decimal | None = None
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化的字典结构。"""

        return {
            "symbol": self.symbol,
            "name": self.name,
            "market": self.market.value,
            "status": self.status.value,
            "industry": self.industry,
            "listing_date": self.listing_date.isoformat() if self.listing_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "current_price": str(self.current_price) if self.current_price is not None else None,
            "prev_close": str(self.prev_close) if self.prev_close is not None else None,
            "open_price": str(self.open_price) if self.open_price is not None else None,
            "high": str(self.high) if self.high is not None else None,
            "low": str(self.low) if self.low is not None else None,
            "amount": str(self.amount) if self.amount is not None else None,
            "market_cap": str(self.market_cap) if self.market_cap is not None else None,
            "pe_ratio": str(self.pe_ratio) if self.pe_ratio is not None else None,
            "pb_ratio": str(self.pb_ratio) if self.pb_ratio is not None else None,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "StockEntity":
        """根据字典数据构造实体，负责规范化枚举与数值类型。"""

        normalized: dict[str, Any] = dict(data)
        market_value = normalized.get("market")
        if market_value is not None and not isinstance(market_value, StockMarket):
            normalized["market"] = StockMarket(str(market_value))
        status_value = normalized.get("status")
        if status_value is not None and not isinstance(status_value, StockStatus):
            normalized["status"] = StockStatus(str(status_value))

        for field_name in (
            "current_price",
            "prev_close",
            "open_price",
            "high",
            "low",
            "amount",
            "market_cap",
            "pe_ratio",
            "pb_ratio",
        ):
            value = normalized.get(field_name)
            if value is None or isinstance(value, Decimal):
                continue
            normalized[field_name] = Decimal(str(value))

        for field_name in ("listing_date", "created_at", "updated_at"):
            value = normalized.get(field_name)
            if isinstance(value, str):
                try:
                    normalized[field_name] = datetime.fromisoformat(value)
                except ValueError:
                    normalized[field_name] = None

        return cls(**normalized)
