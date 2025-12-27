"""轻量级价格值对象，配合单元测试验证基本行为。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional, Union

Numeric = Union[int, float, Decimal]


@dataclass(slots=True, frozen=True)
class PriceChange:
    """描述价格变动结果的辅助对象。"""

    amount: Decimal
    percentage: Decimal
    is_up: bool
    is_down: bool
    is_unchanged: bool


def _to_decimal(value: Optional[Numeric]) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(value)


@dataclass(slots=True)
class Price:
    """封装行情价格及成交数据的值对象。"""

    current: Decimal
    previous_close: Optional[Decimal] = None
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    volume: int = 0
    turnover: Optional[Decimal] = None

    def __post_init__(self) -> None:
        try:
            self.current = Decimal(self.current)
        except (InvalidOperation, ValueError) as exc:  # pragma: no cover - 防御性分支
            raise ValueError("Current price must be numeric") from exc

        if self.current <= Decimal("0"):
            raise ValueError("Current price must be positive")

        if self.volume < 0:
            raise ValueError("Volume must be non-negative")

        self.previous_close = _to_decimal(self.previous_close)
        self.open = _to_decimal(self.open)
        self.high = _to_decimal(self.high)
        self.low = _to_decimal(self.low)
        self.turnover = _to_decimal(self.turnover)

    @property
    def value(self) -> Decimal:
        """向后兼容别名：返回current价格值。"""
        return self.current

    def calculate_change(self) -> PriceChange:
        """根据昨收价计算涨跌幅。"""

        previous = self.previous_close or Decimal("0")
        amount = self.current - previous
        if previous == 0:
            percentage = Decimal("0.00")
        else:
            percentage = (amount / previous * Decimal("100")).quantize(Decimal("0.01"))

        amount_quantized = amount.quantize(Decimal("0.01"))
        is_up = amount > 0
        is_down = amount < 0
        is_unchanged = amount == 0

        return PriceChange(
            amount=amount_quantized,
            percentage=percentage,
            is_up=is_up,
            is_down=is_down,
            is_unchanged=is_unchanged,
        )
