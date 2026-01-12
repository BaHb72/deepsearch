"""
Unit of Work pattern implementation for transaction management.
"""

from typing import Optional

import asyncpg
from core.infrastructure.repositories.stock_repository import PostgreSQLStockRepository
from core.observability import get_logger

logger = get_logger(__name__)


class PostgreSQLUnitOfWork:
    """
    PostgreSQL implementation of Unit of Work pattern.
    Manages database transactions across multiple repositories.
    """

    def __init__(self, connection_pool: asyncpg.Pool):
        self._pool = connection_pool
        self._connection: Optional[asyncpg.Connection] = None
        self._transaction: Optional[asyncpg.Transaction] = None
        self._stock_repository: Optional[PostgreSQLStockRepository] = None

    @property
    def stocks(self) -> PostgreSQLStockRepository:
        """Get stock repository."""
        if not self._stock_repository:
            raise RuntimeError("Unit of Work not started. Use 'async with' context.")
        return self._stock_repository

    async def __aenter__(self):
        """Begin transaction."""
        self._connection = await self._pool.acquire()
        self._transaction = self._connection.transaction()
        await self._transaction.start()

        # Initialize repositories with the transaction connection
        self._stock_repository = PostgreSQLStockRepository(self._connection)

        logger.debug("Transaction started")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """End transaction (commit or rollback)."""
        try:
            if exc_type is None:
                await self.commit()
            else:
                await self.rollback()
        finally:
            if self._connection:
                await self._pool.release(self._connection)
                self._connection = None
                self._transaction = None
                self._stock_repository = None

    async def commit(self) -> None:
        """Commit the transaction."""
        if self._transaction:
            await self._transaction.commit()
            logger.debug("Transaction committed")

    async def rollback(self) -> None:
        """Rollback the transaction."""
        if self._transaction:
            await self._transaction.rollback()
            logger.debug("Transaction rolled back")
