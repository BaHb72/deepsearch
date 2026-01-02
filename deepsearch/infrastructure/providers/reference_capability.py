"""
参考数据能力层。

提供股票列表、交易日历等参考数据的统一访问入口。
特点：
- 强缓存：启动时加载，显式刷新
- 语义标准化：统一代码格式和状态枚举
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Dict, Protocol, Sequence, runtime_checkable

from loguru import logger

from deepsearch.ports.data.requests import StockListRequest
from deepsearch.ports.data.responses import StockInfo, StockListResponse
from deepsearch.ports.data.semantic_types import InstrumentStatus
from deepsearch.ports.data_sources import DataSourceType

if TYPE_CHECKING:
    pass


@runtime_checkable
class IStockListProvider(Protocol):
    """股票列表能力接口"""

    async def query_stock_list(self, request: StockListRequest) -> StockListResponse:
        """查询股票列表"""
        ...


class ReferenceDataCapability:
    """
    参考数据能力层。

    带强缓存：
    - 首次调用时从 Provider 加载
    - 后续调用直接返回缓存
    - 可通过 refresh() 显式刷新
    """

    def __init__(self, providers: Sequence[IStockListProvider] | None = None):
        """
        初始化参考数据能力。

        Args:
            providers: 股票列表 Provider 列表（按优先级排序）
        """
        self._providers = list(providers or [])
        self._cache: Dict[str, StockInfo] = {}  # symbol -> info
        self._loaded_at: datetime | None = None
        self._source: DataSourceType | None = None

    @property
    def is_loaded(self) -> bool:
        """缓存是否已加载"""
        return self._loaded_at is not None

    @property
    def loaded_at(self) -> datetime | None:
        """缓存加载时间"""
        return self._loaded_at

    @property
    def cache_size(self) -> int:
        """缓存条目数"""
        return len(self._cache)

    def register_provider(self, provider: IStockListProvider) -> None:
        """注册 Provider"""
        self._providers.append(provider)

    async def list_instruments(self, request: StockListRequest) -> StockListResponse:
        """
        获取股票列表。

        优先从缓存返回，若缓存为空则从 Provider 加载。

        Args:
            request: 股票列表请求

        Returns:
            StockListResponse: 股票列表响应
        """
        # 缓存命中
        if self._cache:
            return self._from_cache(request)

        # 缓存未命中，从 Provider 加载
        return await self._load_from_provider(request)

    async def refresh(self) -> None:
        """
        显式刷新缓存。

        清空现有缓存，强制从 Provider 重新加载。
        """
        logger.info("刷新参考数据缓存...")
        self._cache.clear()
        self._loaded_at = None
        self._source = None

        # 预加载
        await self._load_from_provider(StockListRequest())
        logger.info(f"参考数据缓存刷新完成，共 {len(self._cache)} 条记录")

    def _from_cache(self, request: StockListRequest) -> StockListResponse:
        """从缓存构建响应"""
        stocks = list(self._cache.values())

        # 应用筛选
        if request.market:
            stocks = [s for s in stocks if s.asset.exchange.value == request.market]

        if not request.include_delisted:
            stocks = [s for s in stocks if s.status != InstrumentStatus.DELISTED]

        if request.limit:
            stocks = stocks[: request.limit]

        return StockListResponse(
            stocks=stocks,
            source=self._source or DataSourceType.UNKNOWN,
            latency_ms=0,  # 缓存命中，无延迟
        )

    async def _load_from_provider(self, request: StockListRequest) -> StockListResponse:
        """从 Provider 加载数据"""
        for provider in self._providers:
            try:
                response = await provider.query_stock_list(request)

                # 更新缓存
                for stock in response.stocks:
                    key = stock.asset.to_standard()
                    self._cache[key] = stock

                self._loaded_at = datetime.now()
                self._source = response.source

                logger.info(f"从 {response.source} 加载参考数据成功，共 {len(response.stocks)} 条")
                return response

            except Exception as e:
                logger.warning(f"从 Provider 加载股票列表失败: {e}")
                continue

        # 所有 Provider 都失败
        logger.error("所有 Provider 都无法提供股票列表")
        return StockListResponse(
            stocks=[],
            source=DataSourceType.UNKNOWN,
            latency_ms=0,
        )

    def get_instrument(self, symbol: str) -> StockInfo | None:
        """
        获取单个标的信息。

        Args:
            symbol: 标的代码（如 600000.SH）

        Returns:
            StockInfo 或 None
        """
        return self._cache.get(symbol)


__all__ = [
    "IStockListProvider",
    "ReferenceDataCapability",
]
