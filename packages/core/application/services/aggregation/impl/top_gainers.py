"""
涨幅榜聚合。

从全市场行情中计算涨幅最大的股票。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List

from loguru import logger

from ..base import BaseAggregation
from ..registry import register_aggregation

if TYPE_CHECKING:
    from core.infrastructure.providers.binder import UnifiedDataFeed


@register_aggregation("top_gainers")
class TopGainersAggregation(BaseAggregation):
    """涨幅榜聚合。"""

    interval = 60  # 每分钟刷新

    async def compute(self, feed: "UnifiedDataFeed") -> List[dict]:
        """
        计算涨幅榜。

        注意：目前返回示例数据，待 Provider 支持全市场行情后实现真实计算。
        """
        # TODO: 实现真实的全市场行情获取和排序
        # 目前返回示例数据，与原 stub 保持一致
        logger.debug("计算涨幅榜（示例数据）")

        return [
            {
                "symbol": "300001",
                "name": "示例科创",
                "current": 28.53,
                "change": 1.92,
                "change_pct": 7.22,
                "volume": 1_520_000,
                "amount": 43_100_000,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
            {
                "symbol": "600002",
                "name": "示例制造",
                "current": 15.87,
                "change": 0.83,
                "change_pct": 5.52,
                "volume": 3_260_000,
                "amount": 51_800_000,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
            {
                "symbol": "000003",
                "name": "示例消费",
                "current": 9.45,
                "change": 0.39,
                "change_pct": 4.31,
                "volume": 4_120_000,
                "amount": 38_600_000,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        ]


__all__ = ["TopGainersAggregation"]
