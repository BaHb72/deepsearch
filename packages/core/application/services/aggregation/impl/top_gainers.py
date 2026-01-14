"""
涨幅榜聚合。

从全市场行情中计算涨幅最大的股票。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, List

from aiocache import cached
from core.ports.data.requests import RealtimeQuoteRequest, StockListRequest
from core.ports.data.semantic_types import AssetSpec
from loguru import logger

from ..base import BaseAggregation
from ..registry import register_aggregation

if TYPE_CHECKING:
    from core.infrastructure.providers.binder import UnifiedDataFeed


@register_aggregation("top_gainers")
class TopGainersAggregation(BaseAggregation):
    """涨幅榜聚合。"""

    interval = 60  # 每分钟刷新
    BATCH_SIZE = 500  # 每批处理股票数
    MAX_CONCURRENT = 5  # 最大并发批次数

    @cached(ttl=60, key="market:top_gainers")
    async def compute(self, feed: "UnifiedDataFeed") -> List[dict]:
        """
        计算涨幅榜。

        使用 Cache-Aside + Pipelining 策略：
        1. 获取全市场股票列表（缓存5分钟）
        2. 分批并发获取实时行情（每批500只，最多5个并发）
        3. 计算涨跌幅并排序
        4. 缓存结果60秒
        """
        try:
            # 1. 获取全市场股票列表
            symbols = await self._get_all_symbols(feed)
            if not symbols:
                logger.warning("未获取到股票列表")
                return []

            logger.debug(f"获取到 {len(symbols)} 只股票")

            # 2. 分批并发获取行情
            quotes = await self._batch_get_quotes(feed, symbols)
            if not quotes:
                logger.warning("未获取到任何行情数据")
                return []

            logger.debug(f"获取到 {len(quotes)} 条行情数据")

            # 3. 计算涨跌幅并排序
            sorted_quotes = sorted(
                quotes,
                key=lambda q: q.get("change_pct", 0),
                reverse=True,
            )

            # 4. 返回 Top 20
            return sorted_quotes[:20]

        except Exception as e:
            logger.error(f"计算涨幅榜失败: {e}")
            # 返回空列表而不是抛出异常，确保服务可用性
            return []

    @cached(ttl=300, key="market:all_symbols")
    async def _get_all_symbols(self, feed: "UnifiedDataFeed") -> List[str]:
        """
        获取全市场股票列表。

        缓存5分钟，减少对数据源的压力。
        """
        try:
            request = StockListRequest(
                market=None,  # 全市场
                include_delisted=False,  # 不包含退市
                limit=None,  # 不限制数量
            )
            response = await feed.list_instruments(request)

            if not response or not response.instruments:
                logger.warning("股票列表为空")
                return []

            # 提取股票代码（格式：000001.SZ）
            symbols = [inst.code for inst in response.instruments]
            logger.info(f"缓存全市场股票列表: {len(symbols)} 只")
            return symbols

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return []

    async def _batch_get_quotes(
        self,
        feed: "UnifiedDataFeed",
        symbols: List[str],
    ) -> List[dict]:
        """
        批量获取实时行情。

        使用 asyncio.Semaphore 限制并发数，避免打爆数据源。
        """
        # 分批
        batches = [
            symbols[i : i + self.BATCH_SIZE] for i in range(0, len(symbols), self.BATCH_SIZE)
        ]
        logger.debug(f"分为 {len(batches)} 批，每批 {self.BATCH_SIZE} 只")

        # 并发控制
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)

        async def fetch_batch(batch: List[str]) -> List[dict]:
            """获取单批行情"""
            async with semaphore:
                try:
                    # 转换为 AssetSpec
                    assets = [AssetSpec.from_code(symbol) for symbol in batch]

                    # 创建批量请求
                    request = RealtimeQuoteRequest(assets=assets)

                    # 查询数据
                    response = await feed.get_realtime(request)

                    if not response or not response.quotes:
                        return []

                    # 转换为字典格式
                    result = []
                    for quote in response.quotes:
                        result.append(
                            {
                                "symbol": quote.asset.to_standard(),
                                "name": getattr(quote, "name", ""),
                                "current": quote.last_price,
                                "change": quote.change,
                                "change_pct": quote.change_pct,
                                "volume": quote.volume,
                                "amount": quote.amount,
                                "timestamp": quote.timestamp.isoformat() + "Z",
                            }
                        )
                    return result

                except Exception as e:
                    logger.warning(f"获取批次行情失败: {e}")
                    return []

        # 并发执行所有批次
        results = await asyncio.gather(*[fetch_batch(batch) for batch in batches])

        # 扁平化结果
        all_quotes = [quote for batch_result in results for quote in batch_result]
        return all_quotes


__all__ = ["TopGainersAggregation"]
