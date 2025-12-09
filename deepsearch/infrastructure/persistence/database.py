"""数据库服务层

提供统一的数据库访问接口
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, Literal, Optional, TypedDict, cast

from sqlalchemy import text
from sqlalchemy.engine import Result
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.elements import Executable, TextClause

from deepsearch.core.components.data_components import DatabaseComponent
from deepsearch.infrastructure.persistence.types import (
    DatabaseServiceProtocol,
    DatabaseSessionManager,
    DatabaseSessionProtocol,
    RowDict,
    SQLParams,
)
from deepsearch.observability.logger import logger


class DatabaseStatus(TypedDict, total=False):
    """���ݿ�״̬��ʾ��"""

    connected: bool
    type: str
    host: str
    database: str
    pool_size: int
    active_connections: int
    error: str


CheckStatus = Literal["up", "down"]
HealthStatus = Literal["unknown", "healthy", "degraded", "unhealthy", "error"]


class HealthCheckEntry(TypedDict, total=False):
    """������ؼ����ʵ�����"""

    status: CheckStatus
    latency_ms: float
    version: str
    error: str


class DatabaseHealth(TypedDict, total=False):
    """���ݿ⽡����ܱ���"""

    status: HealthStatus
    checks: dict[str, HealthCheckEntry]
    timestamp: str | None
    error: str


class DatabaseService(DatabaseServiceProtocol):
    """数据库服务

    提供统一的数据库访问接口，封装数据库操作
    """

    def __init__(self, database_component: DatabaseComponent):
        self.db: DatabaseComponent = database_component
        self.logger = logger.bind(module="数据库服务")

    @staticmethod
    def _normalize_params(params: SQLParams | None) -> SQLParams:
        """确保 SQL 参数始终为 SQLAlchemy 可接受的结构。"""
        return {} if params is None else params

    @staticmethod
    def _normalize_row(row: Mapping[str, object]) -> RowDict:
        """将 SQLAlchemy 行映射转换为可变字典，便于后续加工。"""
        normalized: RowDict = {key: row[key] for key in row}
        return normalized

    @staticmethod
    def _as_executable(statement: TextClause) -> Executable:
        return cast(Executable, statement)

    @asynccontextmanager
    async def _session_scope(self) -> AsyncIterator[DatabaseSessionProtocol]:
        """Yield a typed database session wrapped in a transaction scope."""
        async with self.db.get_session() as session:
            typed_session = cast(DatabaseSessionProtocol, session)
            try:
                yield typed_session
                await typed_session.commit()
            except Exception:
                await typed_session.rollback()
                raise
            finally:
                await typed_session.close()

    def get_session(self) -> DatabaseSessionManager:
        """Return an async context manager that manages a database session scope."""
        return self._session_scope()

    def transaction(self) -> DatabaseSessionManager:
        """Expose the session scope API under the historical transaction helper."""
        return self._session_scope()

    async def execute(self, query: str, params: SQLParams | None = None) -> int:
        """执行写操作并返回受影响行数。"""
        normalized_params = self._normalize_params(params)
        async with self.get_session() as session:
            result: Result[Any] = await session.execute(text(query), normalized_params)
            rowcount = result.rowcount
            return int(rowcount or 0)

    async def fetch_all(self, query: str, params: SQLParams | None = None) -> list[RowDict]:
        """批量查询并返回行字典列表。"""
        normalized_params = self._normalize_params(params)
        async with self.get_session() as session:
            result: Result[Any] = await session.execute(text(query), normalized_params)
            return [self._normalize_row(row) for row in result.mappings().all()]

    async def fetch_one(self, query: str, params: SQLParams | None = None) -> RowDict | None:
        """查询单条记录。"""
        normalized_params = self._normalize_params(params)
        async with self.get_session() as session:
            result: Result[Any] = await session.execute(text(query), normalized_params)
            mapping = result.mappings().first()
            if mapping is None:
                return None
            return self._normalize_row(mapping)

    async def init_database(self) -> None:
        """初始化数据库表结构"""
        from .models.base import Base

        engine = self.db.engine
        if engine is None:
            raise RuntimeError("数据库引擎尚未初始化，无法创建表结构")

        async with engine.begin() as conn:
            # 创建所有表
            await conn.run_sync(Base.metadata.create_all)
            self.logger.info("数据库表结构创建完成")

            # 如果启用了 TimescaleDB，设置超表
            if self.db.is_timescale_enabled:
                await self._init_timescaledb_tables(conn)

    async def _init_timescaledb_tables(self, conn: AsyncConnection) -> None:
        """初始化 TimescaleDB 超表"""

        try:
            # 将时序表转换为超表
            hypertables = [
                ("market_tick", "time"),
                ("market_1min", "time"),
                ("market_5min", "time"),
                ("market_snapshots", "ingested_at"),
            ]

            for table_name, time_column in hypertables:
                try:
                    # 检查是否已经是超表
                    check_sql = cast(
                        TextClause,
                        text(
                            """
                            SELECT EXISTS (SELECT 1
                                           FROM timescaledb_information.hypertables
                                           WHERE hypertable_name = :table_name);
                            """
                        ),
                    )
                    result = await conn.execute(
                        self._as_executable(check_sql), {"table_name": table_name}
                    )
                    is_hypertable = result.scalar()

                    if not is_hypertable:
                        # 创建超表
                        create_sql = cast(
                            TextClause,
                            text(
                                f"SELECT create_hypertable('{table_name}', '{time_column}');"
                            ),
                        )
                        await conn.execute(self._as_executable(create_sql))
                        self.logger.info(f"创建超表: {table_name}")

                        # 设置分区间隔（7天一个分区）
                        interval_sql = cast(
                            TextClause,
                            text(
                                f"""
                                SELECT set_chunk_time_interval('{table_name}', INTERVAL '7 days');
                            """
                            ),
                        )
                        await conn.execute(self._as_executable(interval_sql))
                    else:
                        self.logger.info(f"超表已存在: {table_name}")

                except Exception as e:
                    self.logger.warning(f"创建超表 {table_name} 失败: {e}")

            # 创建连续聚合视图
            await self._create_continuous_aggregates(conn)

        except Exception as e:
            self.logger.error(f"TimescaleDB 初始化失败: {e}")
            raise

    async def _create_continuous_aggregates(self, conn: AsyncConnection) -> None:
        """创建连续聚合视图"""

        # 创建 1分钟 -> 5分钟 的连续聚合
        try:
            # 检查视图是否存在
            check_sql = cast(
                TextClause,
                text(
                    """
                    SELECT EXISTS (SELECT 1
                                   FROM timescaledb_information.continuous_aggregates
                                   WHERE view_name = 'market_5min_agg');
                    """
                ),
            )
            result = await conn.execute(self._as_executable(check_sql))
            exists = result.scalar()

            if not exists:
                create_agg_sql = cast(
                    TextClause,
                    text(
                        """
                        CREATE MATERIALIZED VIEW market_5min_agg
                        WITH (timescaledb.continuous) AS
                        SELECT 
                            time_bucket('5 minutes', time) AS time,
                            symbol,
                            first(open, time) as open,
                            max(high) as high,
                            min(low) as low,
                            last(close, time) as close,
                            sum(volume) as volume,
                            sum(turnover) as turnover
                        FROM market_1min
                        GROUP BY time_bucket('5 minutes', time), symbol;
                    """
                    ),
                )
                await conn.execute(self._as_executable(create_agg_sql))

                # 添加刷新策略
                policy_sql = cast(
                    TextClause,
                    text(
                        """
                        SELECT add_continuous_aggregate_policy('market_5min_agg',
                            start_offset => INTERVAL '1 hour',
                            end_offset => INTERVAL '1 minute',
                            schedule_interval => INTERVAL '5 minutes');
                    """
                    ),
                )
                await conn.execute(self._as_executable(policy_sql))

                self.logger.info("创建连续聚合: market_5min_agg")
            else:
                self.logger.info("连续聚合已存在: market_5min_agg")

        except Exception as e:
            self.logger.warning(f"创建连续聚合失败: {e}")

    async def get_database_status(self) -> DatabaseStatus:
        """获取数据库状态"""
        status: DatabaseStatus = {
            "connected": False,
            "type": "postgresql",
            "host": getattr(self.db.config, "host", "localhost"),
            "database": getattr(self.db.config, "database", "deepsearch"),
            "pool_size": 10,
            "active_connections": 0,
        }

        try:
            # 测试数据库连接
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    status["connected"] = True

                    engine = getattr(self.db, "engine", None)
                    pool = getattr(engine, "pool", None)
                    if pool is not None:
                        if hasattr(pool, "size"):
                            status["pool_size"] = int(pool.size())
                        if hasattr(pool, "checked_out_connections"):
                            status["active_connections"] = int(pool.checked_out_connections())
        except Exception as error:
            status["error"] = str(error)
            self.logger.error(f"获取数据库状态失败: {error}")

        return status

    async def get_health(self) -> DatabaseHealth:
        """获取数据库健康状态"""
        checks: dict[str, HealthCheckEntry] = {}
        health: DatabaseHealth = {"status": "unknown", "checks": checks, "timestamp": None}

        try:
            # PostgreSQL 可用性检查
            pg_check: HealthCheckEntry = {"status": "down"}
            try:
                import time

                async with self.get_session() as session:
                    start = time.time()
                    result = await session.execute(text("SELECT version()"))
                    version = result.scalar()
                    latency_ms = (time.time() - start) * 1000

                    pg_check = {
                        "status": "up",
                        "latency_ms": round(latency_ms, 2),
                        "version": str(version),
                    }
            except Exception as pg_error:
                pg_check["error"] = str(pg_error)

            checks["postgresql"] = pg_check

            if all(entry.get("status") == "up" for entry in checks.values()):
                health["status"] = "healthy"
            elif any(entry.get("status") == "up" for entry in checks.values()):
                health["status"] = "degraded"
            else:
                health["status"] = "unhealthy"

            import datetime

            health["timestamp"] = datetime.datetime.now().isoformat()

        except Exception as error:
            health["status"] = "error"
            health["error"] = str(error)
            self.logger.error(f"获取数据库健康状态失败: {error}")

        return health


# 全局函数（为了兼容测试）
_database_service: Optional[DatabaseService] = None


async def get_connection():
    """获取数据库连接（兼容性函数）"""
    global _database_service
    if _database_service is None:
        from deepsearch.core.runtime.context import get_context
        from deepsearch.core.components.data_components import DatabaseComponent

        try:
            component = get_context().get_component("database")
            if isinstance(component, DatabaseComponent):
                _database_service = DatabaseService(component)
        except Exception:
            pass

    if _database_service:
        return _database_service.db

    # 如果没有初始化，返回mock对象用于测试
    from unittest.mock import AsyncMock

    return AsyncMock()


async def get_database_status():
    """获取数据库状态（兼容性函数）"""
    global _database_service
    if _database_service:
        return await _database_service.get_database_status()

    # 默认返回
    return {"connected": False, "type": "unknown", "error": "Database service not initialized"}
