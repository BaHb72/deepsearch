"""QMT 行情模型别名，实现与数据源模块的解耦。"""

from __future__ import annotations

from deepsearch.infrastructure.providers.datafeed.qmt.models.tick import (
    OrderBook,
    OrderBookLevel,
    TickData,
)

__all__ = ["OrderBookLevel", "OrderBook", "TickData"]
