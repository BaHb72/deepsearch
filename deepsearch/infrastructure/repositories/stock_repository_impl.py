"""
股票仓储实现
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from datetime import datetime
from decimal import Decimal
from typing import NotRequired, Optional, TypedDict, cast

from loguru import logger
from sqlalchemy import text

from deepsearch.core.utils.async_timeout import with_timeout
from deepsearch.core.utils.timeout_config import TimeoutCategory
from deepsearch.infrastructure.cache.cache_manager import CacheManager
from deepsearch.infrastructure.persistence.types import (
    DatabaseServiceProtocol,
    DatabaseSessionProtocol,
    RowDict,
)
from deepsearch.infrastructure.providers.entities.stock import StockEntity, StockMarket, StockStatus
from deepsearch.infrastructure.providers.interfaces.repositories.base import (
    IRepository,
    QueryOptions,
)


class StockRow(TypedDict, total=False):
    """数据库股票行的最小字段集合。"""

    symbol: str
    name: str
    market: str
    status: str
    industry: Optional[str]
    listing_date: datetime | str | None
    created_at: datetime | str | None
    updated_at: datetime | str | None
    current_price: Decimal | float | str | None
    prev_close: Decimal | float | str | None
    open_price: Decimal | float | str | None
    high: Decimal | float | str | None
    low: Decimal | float | str | None
    amount: Decimal | float | str | None
    market_cap: Decimal | float | str | None
    pe_ratio: Decimal | float | str | None
    pb_ratio: Decimal | float | str | None
    version: Optional[int]
    count: NotRequired[int]


class StockRepository(IRepository[StockEntity, str]):
    """
    股票仓储实现

    提供股票实体的持久化和查询功能
    """

    def __init__(self, db_service: DatabaseServiceProtocol, cache_manager: Optional[CacheManager] = None):
        """
        初始化股票仓储

        Args:
            db_service: 数据库服务
            cache_manager: 缓存管理器
        """
        self.db = db_service
        self.cache = cache_manager
        self.table_name = "stocks"
        self.cache_prefix = "stock:"
        self.cache_ttl = 300  # 5分钟缓存

    @with_timeout(TimeoutCategory.DB_QUERY)
    async def get_by_id(self, symbol: str) -> Optional[StockEntity]:
        """
        根据股票代码获取股票实体

        Args:
            symbol: 股票代码

        Returns:
            股票实体或None
        """
        # 尝试从缓存获取
        if self.cache:
            cache_key = f"{self.cache_prefix}{symbol}"
            cached = await self.cache.get(cache_key)
            if cached:
                logger.debug(f"从缓存获取股票: {symbol}")
                return StockEntity.from_dict(cached)

        # 从数据库查询
        query = f"SELECT * FROM {self.table_name} WHERE symbol = ?"
        raw_row = await self.db.fetch_one(query, [symbol])

        if raw_row is None:
            return None

        # 转换为实体
        entity = self._row_to_entity(raw_row)

        # 缓存结果
        if self.cache and entity:
            cache_key = f"{self.cache_prefix}{symbol}"
            await self.cache.set(cache_key, entity.to_dict(), ttl=self.cache_ttl)

        return entity

    @with_timeout(TimeoutCategory.DB_QUERY)
    async def get_all(self, options: Optional[QueryOptions] = None) -> list[StockEntity]:
        """
        获取所有股票

        Args:
            options: 查询选项

        Returns:
            股票列表
        """
        if options is None:
            options = QueryOptions()

        # 构建查询
        query = f"SELECT * FROM {self.table_name}"
        params: list[object] = []

        # 添加过滤条件
        if options.filters:
            conditions = []
            for key, value in options.filters.items():
                conditions.append(f"{key} = ?")
                params.append(value)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        # 添加排序
        if options.sort_by:
            order = "DESC" if options.sort_desc else "ASC"
            query += f" ORDER BY {options.sort_by} {order}"

        # 添加分页
        query += f" LIMIT {options.limit} OFFSET {options.skip}"

        # 执行查询
        rows = await self.db.fetch_all(query, params)

        # 转换为实体列表
        return [self._row_to_entity(row) for row in rows]

    @with_timeout(TimeoutCategory.DB_QUERY)
    async def find(self, criteria: Mapping[str, object]) -> list[StockEntity]:
        """
        根据条件查找股票

        Args:
            criteria: 查询条件

        Returns:
            股票列表
        """
        options = QueryOptions(filters=dict(criteria))
        results = await self.get_all(options)
        return results if results is not None else []

    @with_timeout(TimeoutCategory.DB_QUERY)
    async def find_one(self, criteria: Mapping[str, object]) -> Optional[StockEntity]:
        """
        根据条件查找单个股票

        Args:
            criteria: 查询条件

        Returns:
            股票实体或None
        """
        options = QueryOptions(filters=dict(criteria), limit=1)
        results = await self.get_all(options)
        if not results:
            return None
        return results[0]

    @with_timeout(TimeoutCategory.DB_QUERY)
    async def exists(self, symbol: str) -> bool:
        """
        检查股票是否存在

        Args:
            symbol: 股票代码

        Returns:
            是否存在
        """
        query = f"SELECT COUNT(*) as count FROM {self.table_name} WHERE symbol = ?"
        raw_row = await self.db.fetch_one(query, [symbol])
        if raw_row is None:
            return False

        count_value = self._parse_count(raw_row.get("count"))
        return bool(count_value and count_value > 0)

    @with_timeout(TimeoutCategory.DB_QUERY)
    async def count(self, criteria: Optional[Mapping[str, object]] = None) -> int:
        """
        统计股票数量

        Args:
            criteria: 查询条件

        Returns:
            股票数量
        """
        query = f"SELECT COUNT(*) as count FROM {self.table_name}"
        params: list[object] = []

        if criteria:
            conditions = []
            for key, value in criteria.items():
                conditions.append(f"{key} = ?")
                params.append(value)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        result = await self.db.fetch_one(query, params)
        if result is None:
            return 0

        count_value = self._parse_count(result.get("count"))
        return count_value if count_value is not None else 0

    @with_timeout(TimeoutCategory.DB_TRANSACTION)
    async def save(
        self, entity: StockEntity, session: DatabaseSessionProtocol | None = None
    ) -> StockEntity:
        """
        保存股票实体

        Args:
            entity: 股票实体

        Returns:
            保存后的实体
        """
        if session is None:
            async with self.db.transaction() as scoped_session:
                await self._save_with_session(scoped_session, entity)
        else:
            await self._save_with_session(session, entity)

        # 更新缓存
        if self.cache:
            cache_key = f"{self.cache_prefix}{entity.symbol}"
            await self.cache.set(cache_key, entity.to_dict(), ttl=self.cache_ttl)

        return entity

    @with_timeout(TimeoutCategory.DB_TRANSACTION)
    async def save_many(self, entities: list[StockEntity]) -> list[StockEntity]:
        """
        批量保存股票

        Args:
            entities: 股票列表

        Returns:
            保存后的股票列表
        """
        if not entities:
            return []

        saved_entities: list[StockEntity] = []

        # 使用事务批量保存
        async with self.db.transaction() as session:
            for entity in entities:
                saved_entities.append(await self.save(entity, session=session))

        return saved_entities

    @with_timeout(TimeoutCategory.DB_TRANSACTION)
    async def update(self, symbol: str, updates: Mapping[str, object]) -> Optional[StockEntity]:
        """
        更新股票

        Args:
            symbol: 股票代码
            updates: 更新字段

        Returns:
            更新后的实体或None
        """
        # 获取现有实体
        entity = await self.get_by_id(symbol)
        if not entity:
            return None

        # 应用更新
        for key, value in updates.items():
            if hasattr(entity, key):
                setattr(entity, key, value)

        # 更新时间戳和版本
        entity.updated_at = datetime.now()
        entity.version += 1

        # 保存
        return await self.save(entity)

    @with_timeout(TimeoutCategory.DB_TRANSACTION)
    async def delete(self, symbol: str) -> bool:
        """
        删除股票

        Args:
            symbol: 股票代码

        Returns:
            是否删除成功
        """
        query = f"DELETE FROM {self.table_name} WHERE symbol = ?"
        affected = await self.db.execute(query, [symbol])
        changed = affected if affected is not None else 0

        # �������
        if self.cache:
            cache_key = f"{self.cache_prefix}{symbol}"
            await self.cache.delete(cache_key)

        return changed > 0

    @with_timeout(TimeoutCategory.DB_TRANSACTION)
    async def delete_many(self, criteria: Mapping[str, object]) -> int:
        """
        批量删除股票

        Args:
            criteria: 删除条件

        Returns:
            删除的数量
        """
        # 先查询要删除的股票
        to_delete = await self.find(criteria)

        # 批量删除
        deleted_count = 0
        for entity in to_delete:
            if await self.delete(entity.symbol):
                deleted_count += 1

        return deleted_count

    async def _insert_entity(
        self, entity: StockEntity, session: DatabaseSessionProtocol | None = None
    ) -> None:
        """插入实体"""
        data = entity.to_dict()
        columns = list(data.keys())
        values = {column: data[column] for column in columns}
        placeholders = [f":{column}" for column in columns]

        query = f"""
            INSERT INTO {self.table_name} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """
        if session is None:
            await self.db.execute(query, values)
        else:
            await session.execute(text(query), values)

    async def _update_entity(
        self, entity: StockEntity, session: DatabaseSessionProtocol | None = None
    ) -> None:
        """更新实体"""
        data = entity.to_dict()
        symbol = data.pop("symbol")  # 移除主键

        set_clause = ", ".join([f"{k} = :{k}" for k in data.keys()])
        values = dict(data)
        values["symbol"] = symbol

        query = f"""
            UPDATE {self.table_name}
            SET {set_clause}
            WHERE symbol = :symbol
        """
        if session is None:
            await self.db.execute(query, values)
        else:
            await session.execute(text(query), values)

    async def _save_with_session(
        self, session: DatabaseSessionProtocol, entity: StockEntity
    ) -> None:
        """在给定会话中保存实体，自动选择插入或更新。"""
        exists_query = text(
            f"SELECT 1 FROM {self.table_name} WHERE symbol = :symbol LIMIT 1"
        )
        result = await session.execute(exists_query, {"symbol": entity.symbol})
        if result.first() is None:
            await self._insert_entity(entity, session=session)
        else:
            await self._update_entity(entity, session=session)

    def _row_to_entity(self, row: RowDict) -> StockEntity:
        """将数据库行转换为领域实体"""
        stock_row = cast(StockRow, row)
        data: MutableMapping[str, object] = dict(stock_row)

        market_value = data.get("market")
        if isinstance(market_value, StockMarket):
            data["market"] = market_value
        elif market_value is not None:
            data["market"] = StockMarket(str(market_value))

        status_value = data.get("status")
        if isinstance(status_value, StockStatus):
            data["status"] = status_value
        elif status_value is not None:
            data["status"] = StockStatus(str(status_value))

        for field in ("listing_date", "created_at", "updated_at"):
            value = data.get(field)
            if isinstance(value, str):
                try:
                    data[field] = datetime.fromisoformat(value)
                except ValueError:
                    pass

        decimal_fields = [
            "current_price",
            "prev_close",
            "open_price",
            "high",
            "low",
            "amount",
            "market_cap",
            "pe_ratio",
            "pb_ratio",
        ]
        for field in decimal_fields:
            value = data.get(field)
            if value is None:
                continue
            if isinstance(value, Decimal):
                continue
            data[field] = Decimal(str(value))

        return StockEntity(**data)

    @staticmethod
    def _parse_count(value: object | None) -> int | None:
        """将数据库 COUNT 结果转换为整数"""
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, Decimal):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None


class StockQueryService:
    """
    股票查询服务

    提供高级查询功能
    """

    def __init__(self, repository: StockRepository):
        """
        初始化查询服务

        Args:
            repository: 股票仓储
        """
        self.repo = repository

    async def find_by_market(self, market: StockMarket) -> list[StockEntity]:
        """
        按市场查找股票

        Args:
            market: 市场

        Returns:
            股票列表
        """
        results = await self.repo.find({"market": market.value})
        return results if results is not None else []

    async def find_by_status(self, status: StockStatus) -> list[StockEntity]:
        """
        按状态查找股票

        Args:
            status: 状态

        Returns:
            股票列表
        """
        results = await self.repo.find({"status": status.value})
        return results if results is not None else []

    async def find_by_industry(self, industry: str) -> list[StockEntity]:
        """
        按行业查找股票

        Args:
            industry: 行业

        Returns:
            股票列表
        """
        results = await self.repo.find({"industry": industry})
        return results if results is not None else []

    async def find_active_stocks(self) -> list[StockEntity]:
        """
        查找活跃股票（正在交易的）

        Returns:
            股票列表
        """
        return await self.find_by_status(StockStatus.TRADING)

    async def search_by_name(self, keyword: str) -> list[StockEntity]:
        """
        按名称搜索股票

        Args:
            keyword: 关键词

        Returns:
            股票列表
        """
        # 这里需要使用LIKE查询，暂时简化处理
        all_stocks = await self.repo.get_all()
        return [stock for stock in all_stocks if keyword.lower() in stock.name.lower()]
