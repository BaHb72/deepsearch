"""
Stock repository implementation using PostgreSQL.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

import asyncpg
from core.domain.entities.stock_simple import Stock
from core.domain.interfaces.repository import IStockRepository, PageRequest, PageResult
from core.domain.value_objects import Price, Symbol
from core.observability import get_logger

logger = get_logger(__name__)


class PostgreSQLStockRepository(IStockRepository):
    """
    PostgreSQL implementation of stock repository.
    """

    def __init__(self, connection_pool: asyncpg.Pool):
        self._pool = connection_pool

    async def get_by_id(self, id: str) -> Optional[Stock]:
        """Get stock by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM stocks WHERE symbol = $1", id)
            if row:
                return self._map_to_entity(row)
            return None

    async def get_by_symbol(self, symbol: str) -> Optional[Stock]:
        """Get stock by symbol."""
        return await self.get_by_id(symbol)

    async def get_all(self) -> list[Stock]:
        """Get all stocks."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM stocks")
            return [self._map_to_entity(row) for row in rows]

    async def save(self, entity: Stock) -> None:
        """Save a stock entity."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO stocks (
                    symbol, name, current_price, previous_close,
                    open_price, high_price, low_price, volume,
                    turnover, market_cap, pe_ratio, pb_ratio,
                    is_trading, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                ON CONFLICT (symbol) DO UPDATE SET
                    name = EXCLUDED.name,
                    current_price = EXCLUDED.current_price,
                    previous_close = EXCLUDED.previous_close,
                    open_price = EXCLUDED.open_price,
                    high_price = EXCLUDED.high_price,
                    low_price = EXCLUDED.low_price,
                    volume = EXCLUDED.volume,
                    turnover = EXCLUDED.turnover,
                    market_cap = EXCLUDED.market_cap,
                    pe_ratio = EXCLUDED.pe_ratio,
                    pb_ratio = EXCLUDED.pb_ratio,
                    is_trading = EXCLUDED.is_trading,
                    updated_at = EXCLUDED.updated_at
            """,
                entity.symbol.value,
                entity.name,
                entity.current_price.value if entity.current_price else None,
                entity.previous_close.value if entity.previous_close else None,
                entity.open_price.value if entity.open_price else None,
                entity.high_price.value if entity.high_price else None,
                entity.low_price.value if entity.low_price else None,
                entity.volume,
                entity._turnover,
                entity._market_cap,
                entity._pe_ratio,
                entity._pb_ratio,
                entity.is_trading,
                entity.updated_at,
            )

    async def add(self, entity: Stock) -> None:
        """Add a new stock."""
        await self.save(entity)

    async def update(self, entity: Stock) -> None:
        """Update an existing stock."""
        await self.save(entity)

    async def delete(self, id: str) -> None:
        """Delete a stock by ID."""
        async with self._pool.acquire() as conn:
            await conn.execute("DELETE FROM stocks WHERE symbol = $1", id)

    async def exists(self, id: str) -> bool:
        """Check if stock exists."""
        async with self._pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM stocks WHERE symbol = $1)", id
            )
            return bool(result)

    async def get_by_market(self, market: str, page_request: PageRequest) -> PageResult[Stock]:
        """Get stocks by market."""
        async with self._pool.acquire() as conn:
            # Get total count
            total = await conn.fetchval("SELECT COUNT(*) FROM stocks WHERE market = $1", market)

            # Get paginated results
            rows = await conn.fetch(
                """
                SELECT * FROM stocks
                WHERE market = $1
                ORDER BY symbol
                LIMIT $2 OFFSET $3
            """,
                market,
                page_request.size,
                page_request.offset,
            )

            stocks = [self._map_to_entity(row) for row in rows]

            return PageResult(
                items=stocks, total=total, page=page_request.page, size=page_request.size
            )

    async def search(self, keyword: str, page_request: PageRequest) -> PageResult[Stock]:
        """Search stocks by keyword."""
        async with self._pool.acquire() as conn:
            search_pattern = f"%{keyword}%"

            # Get total count
            total = await conn.fetchval(
                """
                SELECT COUNT(*) FROM stocks
                WHERE symbol ILIKE $1 OR name ILIKE $1
            """,
                search_pattern,
            )

            # Get paginated results
            rows = await conn.fetch(
                """
                SELECT * FROM stocks
                WHERE symbol ILIKE $1 OR name ILIKE $1
                ORDER BY symbol
                LIMIT $2 OFFSET $3
            """,
                search_pattern,
                page_request.size,
                page_request.offset,
            )

            stocks = [self._map_to_entity(row) for row in rows]

            return PageResult(
                items=stocks, total=total, page=page_request.page, size=page_request.size
            )

    async def get_top_gainers(self, limit: int = 10, market: Optional[str] = None) -> list[Stock]:
        """Get top gaining stocks."""
        async with self._pool.acquire() as conn:
            query = """
                SELECT * FROM stocks
                WHERE current_price IS NOT NULL
                AND previous_close IS NOT NULL
                AND previous_close > 0
            """

            if market:
                query += f" AND market = '{market}'"

            query += """
                ORDER BY ((current_price - previous_close) / previous_close) DESC
                LIMIT $1
            """

            rows = await conn.fetch(query, limit)
            return [self._map_to_entity(row) for row in rows]

    async def get_top_losers(self, limit: int = 10, market: Optional[str] = None) -> list[Stock]:
        """Get top losing stocks."""
        async with self._pool.acquire() as conn:
            query = """
                SELECT * FROM stocks
                WHERE current_price IS NOT NULL
                AND previous_close IS NOT NULL
                AND previous_close > 0
            """

            if market:
                query += f" AND market = '{market}'"

            query += """
                ORDER BY ((current_price - previous_close) / previous_close) ASC
                LIMIT $1
            """

            rows = await conn.fetch(query, limit)
            return [self._map_to_entity(row) for row in rows]

    async def get_by_volume_threshold(
        self, threshold: int, page_request: PageRequest
    ) -> PageResult[Stock]:
        """Get stocks above volume threshold."""
        async with self._pool.acquire() as conn:
            # Get total count
            total = await conn.fetchval("SELECT COUNT(*) FROM stocks WHERE volume >= $1", threshold)

            # Get paginated results
            rows = await conn.fetch(
                """
                SELECT * FROM stocks
                WHERE volume >= $1
                ORDER BY volume DESC
                LIMIT $2 OFFSET $3
            """,
                threshold,
                page_request.size,
                page_request.offset,
            )

            stocks = [self._map_to_entity(row) for row in rows]

            return PageResult(
                items=stocks, total=total, page=page_request.page, size=page_request.size
            )

    def _map_to_entity(self, row: Any) -> Stock:
        """Map database row to Stock entity."""
        data = dict(row)
        symbol = Symbol(str(data["symbol"]))

        def _to_price(value: object) -> Optional[Price]:
            if value is None:
                return None
            if isinstance(value, Price):
                return value
            if isinstance(value, (int, float, Decimal)):
                return Price(Decimal(value))
            try:
                if isinstance(value, str):
                    numeric = float(value)
                    return Price(Decimal(numeric))
            except TypeError, ValueError:
                return None
            return None

        current_price = _to_price(data.get("current_price"))
        previous_close = _to_price(data.get("previous_close"))
        open_price = _to_price(data.get("open_price"))
        high_price = _to_price(data.get("high_price"))
        low_price = _to_price(data.get("low_price"))

        volume_raw = data.get("volume")
        if isinstance(volume_raw, (int, float, Decimal)):
            volume = int(volume_raw)
        elif isinstance(volume_raw, str) and volume_raw:
            try:
                volume = int(float(volume_raw))
            except ValueError:
                volume = 0
        else:
            volume = 0

        return Stock(
            symbol=symbol,
            name=str(data.get("name") or ""),
            current_price=current_price,
            previous_close=previous_close,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            volume=volume,
            turnover=data.get("turnover"),
            market_cap=data.get("market_cap"),
            pe_ratio=data.get("pe_ratio"),
            pb_ratio=data.get("pb_ratio"),
            is_trading=bool(data.get("is_trading")),
            updated_at=data.get("updated_at"),
        )
