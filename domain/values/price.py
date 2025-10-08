"""价格值对象的轻量级实现。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Union

Numeric = Union[int, float, Decimal]


@dataclass(frozen=True, slots=True)
class Price:
    """封装价格数值，提供统一的浮点表示。"""

    value: float

    def __init__(self, value: Numeric):
        object.__setattr__(self, "value", float(value))
