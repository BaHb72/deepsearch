"""Compatibility exports for legacy domain.entities module."""

from __future__ import annotations

from deepsearch.domain.entities.price import Price, PriceChange
from deepsearch.domain.entities.stock_simple import Stock
from deepsearch.domain.entities.trade import Order, OrderStatus, OrderType, Trade

__all__ = [
    "Price",
    "PriceChange",
    "Stock",
    "Order",
    "OrderType",
    "OrderStatus",
    "Trade",
]
