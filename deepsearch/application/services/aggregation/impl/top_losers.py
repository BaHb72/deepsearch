"""
跌幅榜聚合。

从全市场行情中计算跌幅最大的股票。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List

from loguru import logger

from ..base import BaseAggregation
from ..registry import register_aggregation

if TYPE_CHECKING:
    from deepsearch.infrastructure.providers.binder import UnifiedDataFeed


@register_aggregation("top_losers")
class TopLosersAggregation(BaseAggregation):
    """跌幅榜聚合。"""

    interval = 60  # 每分钟刷新

    async def compute(self, feed: "UnifiedDataFeed") -> List[dict]:
        """
        计算跌幅榜。

        注意：目前返回示例数据，待 Provider 支持全市场行情后实现真实计算。
        """
        logger.debug("计算跌幅榜（示例数据）")

        return [
            {
                "symbol": "300099",
                "name": "示例医疗",
                "current": 21.37,
                "change": -1.86,
                "change_pct": -8.01,
                "volume": 2_430_000,
                "amount": 52_400_000,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
            {
                "symbol": "600188",
                "name": "示例材料",
                "current": 12.68,
                "change": -0.84,
                "change_pct": -6.21,
                "volume": 3_980_000,
                "amount": 48_900_000,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
            {
                "symbol": "000777",
                "name": "示例环保",
                "current": 7.92,
                "change": -0.42,
                "change_pct": -5.04,
                "volume": 2_760_000,
                "amount": 21_900_000,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        ]


__all__ = ["TopLosersAggregation"]
