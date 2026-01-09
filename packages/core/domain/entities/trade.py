"""基础交易与订单实体，满足测试所需的最小功能。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Optional, Union

Numeric = Union[int, float, Decimal]


def _to_decimal(value: Numeric) -> Decimal:
    return Decimal(value)


def _to_optional_decimal(value: Optional[Numeric]) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(value)


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"


class OrderStatus(str, Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"


@dataclass(slots=True)
class Trade:
    """成交记录。"""

    symbol: str
    price: Decimal
    volume: int
    trade_type: str = "BUY"
    id: Optional[str] = None
    timestamp: datetime | None = None
    commission: Optional[Decimal] = None

    def __post_init__(self) -> None:
        try:
            self.price = _to_decimal(self.price)
        except (InvalidOperation, ValueError) as exc:  # pragma: no cover - 防御性分支
            raise ValueError("Price must be numeric") from exc

        if self.volume <= 0:
            raise ValueError("Volume must be positive")

        self.commission = _to_optional_decimal(self.commission)

        if self.timestamp is None:
            self.timestamp = datetime.now()

    @property
    def total_value(self) -> Decimal:
        return (self.price * self.volume).quantize(Decimal("0.01"))

    @property
    def net_value(self) -> Decimal:
        commission = self.commission or Decimal("0")
        if self.trade_type.upper() == "BUY":
            return self.total_value + commission
        return self.total_value - commission


@dataclass(slots=True)
class Order:
    """委托订单。"""

    symbol: str
    order_type: OrderType
    price: Optional[Decimal] = None
    volume: int = 0
    side: str = "BUY"
    status: OrderStatus = OrderStatus.PENDING
    id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    filled_volume: int = 0

    def __post_init__(self) -> None:
        if self.volume <= 0:
            raise ValueError("Order volume must be positive")

        if self.price is not None:
            try:
                self.price = _to_decimal(self.price)
            except (InvalidOperation, ValueError) as exc:  # pragma: no cover - 防御性分支
                raise ValueError("Order price must be numeric") from exc

    def fill(self, filled_price: Numeric, filled_volume: int) -> None:
        if filled_volume <= 0:
            raise ValueError("Filled volume must be positive")

        self.filled_volume += filled_volume
        try:
            self.price = _to_decimal(filled_price)
        except (InvalidOperation, ValueError) as exc:  # pragma: no cover - 防御性分支
            raise ValueError("Filled price must be numeric") from exc

        if self.filled_volume >= self.volume:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED

    def cancel(self) -> None:
        self.status = OrderStatus.CANCELLED
