"""
股票仓储实现
"""
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal
from loguru import logger

from deepsearch.infrastructure.providers.interfaces.repositories.base import IRepository, QueryOptions
from deepsearch.infrastructure.providers.entities.stock import StockEntity, StockMarket, StockStatus
from deepsearch.infrastructure.persistence.database import DatabaseService
from deepsearch.infrastructure.cache.cache_manager import CacheManager
from deepsearch.core.utils.async_timeout import with_timeout
from deepsearch.core.utils.timeout_config import TimeoutCategory


class StockRepository(IRepository[StockEntity, str]):
    """
    股票仓储实现

    提供股票实体的持久化和查询功能
    """

    def __init__(
        self,
        db_service: DatabaseService,
        cache_manager: Optional[CacheManager] = None
    ):
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
        result = await self.db.fetch_one(query, [symbol])

        if not result:
            return None

        # 转换为实体
        entity = self._row_to_entity(result)

        # 缓存结果
        if self.cache and entity:
            cache_key = f"{self.cache_prefix}{symbol}"
            await self.cache.set(cache_key, entity.to_dict(), ttl=self.cache_ttl)

        return entity

    @with_timeout(TimeoutCategory.DB_QUERY)
    async def get_all(self, options: Optional[QueryOptions] = None) -> List[StockEntity]:
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
        params = []

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
        results = await self.db.fetch_all(query, params)

        # 转换为实体列表
        entities = [self._row_to_entity(row) for row in results]
        return entities

    @with_timeout(TimeoutCategory.DB_QUERY)
    async def find(self, criteria: Dict[str, Any]) -> List[StockEntity]:
        """
        根据条件查找股票

        Args:
            criteria: 查询条件

        Returns:
            股票列表
        """
        options = QueryOptions(filters=criteria)
        return await self.get_all(options)

    @with_timeout(TimeoutCategory.DB_QUERY)
    async def find_one(self, criteria: Dict[str, Any]) -> Optional[StockEntity]:
        """
        根据条件查找单个股票

        Args:
            criteria: 查询条件

        Returns:
            股票实体或None
        """
        options = QueryOptions(filters=criteria, limit=1)
        results = await self.get_all(options)
        return results[0] if results else None

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
        result = await self.db.fetch_one(query, [symbol])
        return result['count'] > 0 if result else False

    @with_timeout(TimeoutCategory.DB_QUERY)
    async def count(self, criteria: Optional[Dict[str, Any]] = None) -> int:
        """
        统计股票数量

        Args:
            criteria: 查询条件

        Returns:
            股票数量
        """
        query = f"SELECT COUNT(*) as count FROM {self.table_name}"
        params = []

        if criteria:
            conditions = []
            for key, value in criteria.items():
                conditions.append(f"{key} = ?")
                params.append(value)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        result = await self.db.fetch_one(query, params)
        return result['count'] if result else 0

    @with_timeout(TimeoutCategory.DB_TRANSACTION)
    async def save(self, entity: StockEntity) -> StockEntity:
        """
        保存股票实体

        Args:
            entity: 股票实体

        Returns:
            保存后的实体
        """
        # 检查是否存在
        exists = await self.exists(entity.symbol)

        if exists:
            # 更新
            await self._update_entity(entity)
        else:
            # 插入
            await self._insert_entity(entity)

        # 更新缓存
        if self.cache:
            cache_key = f"{self.cache_prefix}{entity.symbol}"
            await self.cache.set(cache_key, entity.to_dict(), ttl=self.cache_ttl)

        return entity

    @with_timeout(TimeoutCategory.DB_TRANSACTION)
    async def save_many(self, entities: List[StockEntity]) -> List[StockEntity]:
        """
        批量保存股票

        Args:
            entities: 股票列表

        Returns:
            保存后的股票列表
        """
        saved_entities = []

        # 使用事务批量保存
        async with self.db.transaction():
            for entity in entities:
                saved = await self.save(entity)
                saved_entities.append(saved)

        return saved_entities

    @with_timeout(TimeoutCategory.DB_TRANSACTION)
    async def update(self, symbol: str, updates: Dict[str, Any]) -> Optional[StockEntity]:
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
        result = await self.db.execute(query, [symbol])

        # 清除缓存
        if self.cache:
            cache_key = f"{self.cache_prefix}{symbol}"
            await self.cache.delete(cache_key)

        return result > 0

    @with_timeout(TimeoutCategory.DB_TRANSACTION)
    async def delete_many(self, criteria: Dict[str, Any]) -> int:
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

    async def _insert_entity(self, entity: StockEntity):
        """插入实体"""
        data = entity.to_dict()
        columns = list(data.keys())
        values = list(data.values())
        placeholders = ["?" for _ in columns]

        query = f"""
            INSERT INTO {self.table_name} ({', '.join(columns)})
            VALUES ({', '.join(placeholders)})
        """
        await self.db.execute(query, values)

    async def _update_entity(self, entity: StockEntity):
        """更新实体"""
        data = entity.to_dict()
        symbol = data.pop('symbol')  # 移除主键

        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values())
        values.append(symbol)  # 添加WHERE条件的值

        query = f"""
            UPDATE {self.table_name}
            SET {set_clause}
            WHERE symbol = ?
        """
        await self.db.execute(query, values)

    def _row_to_entity(self, row: Dict[str, Any]) -> StockEntity:
        """
        将数据库行转换为实体

        Args:
            row: 数据库行

        Returns:
            股票实体
        """
        # 处理市场枚举
        if 'market' in row:
            row['market'] = StockMarket(row['market'])

        # 处理状态枚举
        if 'status' in row:
            row['status'] = StockStatus(row['status'])

        # 处理日期
        date_fields = ['listing_date', 'created_at', 'updated_at']
        for field in date_fields:
            if field in row and row[field]:
                if isinstance(row[field], str):
                    row[field] = datetime.fromisoformat(row[field])

        # 处理Decimal
        decimal_fields = ['current_price', 'prev_close', 'open_price',
                         'high', 'low', 'amount', 'market_cap',
                         'pe_ratio', 'pb_ratio']
        for field in decimal_fields:
            if field in row and row[field] is not None:
                row[field] = Decimal(str(row[field]))

        return StockEntity(**row)


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

    async def find_by_market(self, market: StockMarket) -> List[StockEntity]:
        """
        按市场查找股票

        Args:
            market: 市场

        Returns:
            股票列表
        """
        return await self.repo.find({'market': market.value})

    async def find_by_status(self, status: StockStatus) -> List[StockEntity]:
        """
        按状态查找股票

        Args:
            status: 状态

        Returns:
            股票列表
        """
        return await self.repo.find({'status': status.value})

    async def find_by_industry(self, industry: str) -> List[StockEntity]:
        """
        按行业查找股票

        Args:
            industry: 行业

        Returns:
            股票列表
        """
        return await self.repo.find({'industry': industry})

    async def find_active_stocks(self) -> List[StockEntity]:
        """
        查找活跃股票（正在交易的）

        Returns:
            股票列表
        """
        return await self.find_by_status(StockStatus.TRADING)

    async def search_by_name(self, keyword: str) -> List[StockEntity]:
        """
        按名称搜索股票

        Args:
            keyword: 关键词

        Returns:
            股票列表
        """
        # 这里需要使用LIKE查询，暂时简化处理
        all_stocks = await self.repo.get_all()
        return [
            stock for stock in all_stocks
            if keyword.lower() in stock.name.lower()
        ]