from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import pytest
from core.domain.market_data import StockListRecord
from core.infrastructure.persistence.ingestion_records import DataSourceRecordPersistence
from core.infrastructure.persistence.models import Base
from core.infrastructure.persistence.types import (
    DatabaseServiceProtocol,
    DatabaseSessionProtocol,
    RowDict,
    SQLParams,
)
from core.ports.data_sources import DataAccessType, DataSourceType
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class SQLiteDatabaseService(DatabaseServiceProtocol):
    """Minimal async database service backed by an in-memory sqlite engine."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory

    async def fetch_one(self, query: str, params: SQLParams = None) -> RowDict | None:
        async with self._session_factory() as session:
            result = await session.execute(text(query), params or {})
            mapping = result.mappings().first()
            return mapping if mapping is None else dict(mapping)

    async def fetch_all(self, query: str, params: SQLParams = None) -> list[RowDict]:
        async with self._session_factory() as session:
            result = await session.execute(text(query), params or {})
            return [dict(row) for row in result.mappings().all()]

    async def execute(self, query: str, params: SQLParams = None) -> int:
        async with self._session_factory() as session:
            result = await session.execute(text(query), params or {})
            await session.commit()
            return int(result.rowcount or 0)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[DatabaseSessionProtocol]:
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()


@pytest.fixture
async def sqlite_db_service() -> AsyncIterator[SQLiteDatabaseService]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    service = SQLiteDatabaseService(session_factory)
    try:
        yield service
    finally:
        await engine.dispose()


def _sample_records() -> list[StockListRecord]:
    return [
        StockListRecord(symbol="AAA", name="Alpha", boards=("主板",)),
        StockListRecord(symbol="BBB", name="Beta", boards=("科创板",)),
        StockListRecord(symbol="CCC", name="Gamma", boards=("创业板", "A股")),
    ]


@pytest.mark.asyncio
async def test_persist_and_load_round_trip(sqlite_db_service: SQLiteDatabaseService):
    persistence = DataSourceRecordPersistence(sqlite_db_service)
    record_set = await persistence.persist_stock_list(
        _sample_records(),
        job_type="prefetch_stock_basics",
        data_source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.STOCK_LIST,
        expires_in=timedelta(minutes=10),
    )

    assert record_set.record_count == 3
    assert record_set.id is not None

    loaded = await persistence.load_latest_record_set(
        job_type="prefetch_stock_basics",
        data_source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.STOCK_LIST,
        max_age=timedelta(hours=1),
    )
    assert loaded is not None
    assert loaded.id == record_set.id
    assert len(loaded.records) == 3
    assert {entry["symbol"] for entry in loaded.records if "symbol" in entry} == {
        "AAA",
        "BBB",
        "CCC",
    }


@pytest.mark.asyncio
async def test_load_respects_expiration(sqlite_db_service: SQLiteDatabaseService):
    persistence = DataSourceRecordPersistence(sqlite_db_service)
    persisted = await persistence.persist_stock_list(
        _sample_records(),
        job_type="prefetch_stock_basics",
        data_source=DataSourceType.AMAZINGDATA,
        expires_in=timedelta(seconds=1),
    )
    assert persisted.id is not None

    # 将 expires_at/ completed_at 回退，模拟过期快照
    async with sqlite_db_service.transaction() as session:
        await session.execute(
            text(
                """
                UPDATE ingestion_jobs
                SET expires_at = :expired_at, completed_at = :completed_at
                WHERE id = :job_id
                """
            ),
            {
                "expired_at": datetime.now(timezone.utc) - timedelta(minutes=5),
                "completed_at": datetime.now(timezone.utc) - timedelta(minutes=5),
                "job_id": persisted.id,
            },
        )

    loaded = await persistence.load_latest_record_set(
        job_type="prefetch_stock_basics",
        data_source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.STOCK_LIST,
        max_age=timedelta(minutes=1),
    )
    assert loaded is None


@pytest.mark.asyncio
async def test_persist_reuses_existing_job(sqlite_db_service: SQLiteDatabaseService):
    persistence = DataSourceRecordPersistence(sqlite_db_service)
    job_id = await persistence.create_job(
        job_type="prefetch_stock_basics",
        data_source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.STOCK_LIST,
    )
    envelope = await persistence.persist_stock_list(
        _sample_records(),
        job_type="prefetch_stock_basics",
        data_source=DataSourceType.AMAZINGDATA,
        access_type=DataAccessType.STOCK_LIST,
        job_id=job_id,
    )
    assert envelope.id == job_id
    job_row = await persistence.fetch_job(job_id)
    assert job_row is not None
    assert job_row["status"] == "succeeded"
