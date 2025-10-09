"""
优化的数据库连接池

提供高性能的数据库连接池管理，包括：
- 连接池预热
- 连接健康检查
- 批量查询支持
- 性能监控
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TypedDict, cast

import asyncpg
from asyncpg.pool import Pool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from deepsearch.infrastructure.persistence.types import DatabaseSessionManager, DatabaseSessionProtocol, RowDict, SQLParams
from deepsearch.observability import get_logger

logger = get_logger(__name__)


class PoolStatisticsPayload(TypedDict):
    """�Ż����ӳ�ͳ������"""

    total_connections: int
    active_connections: int
    idle_connections: int
    waiting_queries: int
    total_queries: int
    failed_queries: int
    avg_query_time: float
    max_query_time: float
    error_rate: float
    uptime_seconds: float
    last_error: Optional[str]
    last_error_time: Optional[str]


class AsyncpgPoolStatus(TypedDict, total=False):
    """asyncpg ���ӳ�״̬���"""

    status: str
    min_size: int
    max_size: int
    current_size: int
    free_connections: int
    used_connections: int
    waiting_queries: int


class OptimizedPoolStatisticsPayload(PoolStatisticsPayload):
    """�Ż��� asyncpg ���ӳ�ͳ����Ϣ��"""

    pool_status: AsyncpgPoolStatus


class SqlAlchemyPoolStatus(TypedDict, total=False):
    """SQLAlchemy ���ӳ�״̬���"""

    status: str
    size: int
    checked_in: int
    checked_out: int
    overflow: int
    total: int


class SqlAlchemyPoolStatisticsPayload(PoolStatisticsPayload):
    """SQLAlchemy ���ӳ�ͳ����Ϣ��"""

    pool_status: SqlAlchemyPoolStatus


@dataclass
class PoolConfig:
    """连接池配置"""

    dsn: str
    min_size: int = 10
    max_size: int = 50
    max_queries: int = 1000
    max_inactive_lifetime: int = 300
    command_timeout: int = 60
    statement_cache_size: int = 100
    max_cached_lifetime: int = 3600
    enable_jit: bool = False
    work_mem: str = "256MB"
    effective_cache_size: str = "4GB"


@dataclass
class PoolStatistics:
    """连接池统计信息"""

    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    waiting_queries: int = 0
    total_queries: int = 0
    failed_queries: int = 0
    avg_query_time: float = 0.0
    max_query_time: float = 0.0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> PoolStatisticsPayload:
        """ת��Ϊ�ֵ�"""
        return {
            "total_connections": self.total_connections,
            "active_connections": self.active_connections,
            "idle_connections": self.idle_connections,
            "waiting_queries": self.waiting_queries,
            "total_queries": self.total_queries,
            "failed_queries": self.failed_queries,
            "avg_query_time": round(self.avg_query_time, 3),
            "max_query_time": round(self.max_query_time, 3),
            "error_rate": round(self.failed_queries / max(self.total_queries, 1) * 100, 2),
            "uptime_seconds": (datetime.now() - self.created_at).total_seconds(),
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
        }


class OptimizedDatabasePool:
    """优化的数据库连接池"""

    def __init__(self, config: PoolConfig):
        self.config = config
        self.pool: Optional[Pool] = None
        self.statistics = PoolStatistics()
        self._lock = asyncio.Lock()
        self._prepared_statements: dict[str, str] = {}
        self._query_times: list[float] = []
        self._max_query_history = 1000

    @staticmethod
    def _coerce_to_int(value: object) -> int | None:
        """尝试将查询结果转换为整数"""
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return None
        return None

    async def initialize(self):
        """初始化连接池"""
        async with self._lock:
            if self.pool:
                logger.warning("连接池已经初始化")
                return

            try:
                logger.info(
                    f"初始化数据库连接池: min={self.config.min_size}, max={self.config.max_size}"
                )

                self.pool = await asyncpg.create_pool(
                    self.config.dsn,
                    min_size=self.config.min_size,
                    max_size=self.config.max_size,
                    max_queries=self.config.max_queries,
                    max_inactive_connection_lifetime=self.config.max_inactive_lifetime,
                    command_timeout=self.config.command_timeout,
                    init=self._init_connection,
                )

                # 预热连接池
                await self._warmup_pool()

                logger.info("数据库连接池初始化完成")

            except Exception as e:
                logger.error(f"初始化连接池失败: {e}")
                self.statistics.last_error = str(e)
                self.statistics.last_error_time = datetime.now()
                raise

    async def _init_connection(self, conn):
        """初始化连接配置"""
        try:
            # 设置连接级别的优化
            if not self.config.enable_jit:
                await conn.execute("SET jit = 'off'")

            await conn.execute(f"SET work_mem = '{self.config.work_mem}'")
            await conn.execute(f"SET effective_cache_size = '{self.config.effective_cache_size}'")

            # 设置应用名称
            await conn.execute("SET application_name = 'deepsearch'")

            # 准备常用语句
            await self._prepare_common_statements(conn)

            logger.debug("连接初始化完成")

        except Exception as e:
            logger.error(f"初始化连接失败: {e}")
            raise

    async def _prepare_common_statements(self, conn):
        """准备常用的预编译语句"""
        statements = {
            "get_stock_info": """
                PREPARE get_stock_info (text) AS
                SELECT * FROM stock_info WHERE symbol = $1
            """,
            "get_kline_data": """
                PREPARE get_kline_data (text, timestamp, timestamp) AS
                SELECT * FROM kline_data
                WHERE symbol = $1 AND timestamp BETWEEN $2 AND $3
                ORDER BY timestamp
            """,
            "get_latest_price": """
                PREPARE get_latest_price (text) AS
                SELECT symbol, price, volume, timestamp
                FROM stock_realtime
                WHERE symbol = $1
                ORDER BY timestamp DESC
                LIMIT 1
            """,
            "batch_insert_kline": """
                PREPARE batch_insert_kline AS
                INSERT INTO kline_data (symbol, open, high, low, close, volume, timestamp)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (symbol, timestamp) DO UPDATE
                SET open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    volume = EXCLUDED.volume
            """,
        }

        for name, sql in statements.items():
            try:
                await conn.execute(sql)
                self._prepared_statements[name] = sql
                logger.debug(f"准备语句 {name} 成功")
            except Exception as e:
                logger.warning(f"准备语句 {name} 失败: {e}")

    async def _warmup_pool(self):
        """预热连接池"""
        logger.info("开始预热连接池...")

        # 创建最小数量的连接
        tasks = []
        for _ in range(self.config.min_size):
            tasks.append(self._test_connection())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = sum(1 for r in results if r is True)
        logger.info(f"连接池预热完成: {success_count}/{self.config.min_size} 连接成功")

    async def _test_connection(self) -> bool:
        """测试单个连接"""
        try:
            async with self.acquire() as conn:
                result_obj = await conn.fetchval("SELECT 1")
                parsed = self._coerce_to_int(result_obj)
                return parsed == 1
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return False

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        """获取连接"""
        if not self.pool:
            raise RuntimeError("连接池未初始化")

        start_time = time.perf_counter()
        conn: asyncpg.Connection | None = None

        try:
            # 更新等待统计
            self.statistics.waiting_queries += 1

            # 获取连接
            conn = await self.pool.acquire()

            # 更新统计
            self.statistics.waiting_queries -= 1
            self.statistics.active_connections += 1

            yield conn

        except Exception as e:
            self.statistics.failed_queries += 1
            self.statistics.last_error = str(e)
            self.statistics.last_error_time = datetime.now()
            logger.error(f"数据库操作失败: {e}")
            raise

        finally:
            # 记录查询时间
            query_time = time.perf_counter() - start_time
            self._record_query_time(query_time)

            # 释放连接
            if conn:
                await self.pool.release(conn)
                self.statistics.active_connections -= 1

            # 更新统计
            self.statistics.total_queries += 1

    def _record_query_time(self, query_time: float):
        """记录查询时间"""
        self._query_times.append(query_time)

        # 限制历史记录大小
        if len(self._query_times) > self._max_query_history:
            self._query_times = self._query_times[-self._max_query_history :]

        # 更新统计
        if self._query_times:
            self.statistics.avg_query_time = sum(self._query_times) / len(self._query_times)
            self.statistics.max_query_time = max(self._query_times)

    async def execute(self, query: str, *args, timeout: Optional[float] = None) -> str:
        """执行查询"""
        timeout = timeout or self.config.command_timeout

        async with self.acquire() as conn:
            return await asyncio.wait_for(conn.execute(query, *args), timeout=timeout)

    async def fetch(self, query: str, *args, timeout: Optional[float] = None) -> list[asyncpg.Record]:
        """获取查询结果"""
        timeout = timeout or self.config.command_timeout

        async with self.acquire() as conn:
            return await asyncio.wait_for(conn.fetch(query, *args), timeout=timeout)

    async def fetchval(self, query: str, *args, timeout: Optional[float] = None) -> object:
        """获取单个值"""
        timeout = timeout or self.config.command_timeout

        async with self.acquire() as conn:
            result = await asyncio.wait_for(conn.fetchval(query, *args), timeout=timeout)
            return cast(object, result)

    async def fetchrow(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> Optional[asyncpg.Record]:
        """获取单行"""
        timeout = timeout or self.config.command_timeout

        async with self.acquire() as conn:
            return await asyncio.wait_for(conn.fetchrow(query, *args), timeout=timeout)

    async def execute_batch(self, queries: Sequence[tuple[object, ...]]) -> list[list[asyncpg.Record] | None]:
        """批量执行查询"""
        results: list[list[asyncpg.Record] | None] = []

        async with self.acquire() as conn:
            async with conn.transaction():
                for query_data in queries:
                    if len(query_data) == 1:
                        query = str(query_data[0])
                        params: tuple[object, ...] = tuple()
                    else:
                        query = str(query_data[0])
                        params = tuple(query_data[1:])

                    try:
                        result = await conn.fetch(query, *params)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"������ѯʧ��: {query[:100]}... - {e}")
                        results.append(None)
                        # ���ж����񣬼���ִ��

        return results

    async def execute_many(self, query: str, args_list: Sequence[tuple[object, ...]]) -> None:
        """执行多个相同的查询（不同参数）"""
        async with self.acquire() as conn:
            await conn.executemany(query, args_list)

    async def copy_records_to_table(
        self,
        table_name: str,
        *,
        records: Sequence[tuple[object, ...]],
        columns: Sequence[str],
        schema_name: Optional[str] = None,
    ) -> int:
        """批量复制记录到表（高性能）"""
        if schema_name:
            table_ref = f"{schema_name}.{table_name}"
        else:
            table_ref = table_name

        async with self.acquire() as conn:
            result = await conn.copy_records_to_table(table_ref, records=records, columns=columns)
            return int(result)

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            result_obj = await self.fetchval("SELECT 1", timeout=5.0)
            parsed = self._coerce_to_int(result_obj)
            return parsed == 1
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False

    def get_pool_status(self) -> AsyncpgPoolStatus:
        """��ȡ���ӳ�״̬"""
        if not self.pool:
            return {"status": "未初始化"}

        return {
            "min_size": self.pool._minsize,
            "max_size": self.pool._maxsize,
            "current_size": self.pool._size,
            "free_connections": self.pool._freesize,
            "used_connections": self.pool._size - self.pool._freesize,
            "waiting_queries": (
                len(self.pool._queue._waiters) if hasattr(self.pool._queue, "_waiters") else 0
            ),
        }

    def get_statistics(self) -> OptimizedPoolStatisticsPayload:
        """��ȡͳ����Ϣ"""
        stats_dict = self.statistics.to_dict()
        snapshot = cast(
            OptimizedPoolStatisticsPayload,
            {**stats_dict, "pool_status": self.get_pool_status()},
        )
        return snapshot

    async def close(self):
        """关闭连接池"""
        if self.pool:
            logger.info("关闭数据库连接池...")
            await self.pool.close()
            self.pool = None
            logger.info("数据库连接池已关闭")


class SQLAlchemyOptimizedPool:
    """基于SQLAlchemy的优化连接池"""

    def __init__(self, database_url: str, **kwargs):
        self.database_url = database_url
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None
        pool_size = int(kwargs.get("pool_size", 20))
        max_overflow = int(kwargs.get("max_overflow", 10))
        pool_pre_ping = bool(kwargs.get("pool_pre_ping", True))
        pool_recycle = int(kwargs.get("pool_recycle", 3600))
        echo = bool(kwargs.get("echo", False))
        echo_pool = bool(kwargs.get("echo_pool", False))
        pool_timeout = int(kwargs.get("pool_timeout", 30))
        connect_args_raw = kwargs.get("connect_args", {})
        connect_args = dict(connect_args_raw) if isinstance(connect_args_raw, Mapping) else {}

        self.config: dict[str, object] = {
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_pre_ping": pool_pre_ping,
            "pool_recycle": pool_recycle,
            "echo": echo,
            "echo_pool": echo_pool,
            "pool_timeout": pool_timeout,
            "connect_args": connect_args,
        }
        self.statistics = PoolStatistics()

    @staticmethod
    def _normalize_params(params: SQLParams | None) -> SQLParams:
        """统一 SQL 参数结构。"""
        return {} if params is None else params

    @staticmethod
    def _row_to_dict(row: Mapping[str, object]) -> RowDict:
        """将查询结果转换为普通字典。"""
        normalized: RowDict = {key: row[key] for key in row}
        return normalized

    def _ensure_engine(self) -> AsyncEngine:
        """确保引擎已初始化。"""
        if self.engine is None:
            raise RuntimeError("SQLAlchemy 引擎未初始化")
        return self.engine

    async def initialize(self):
        """初始化SQLAlchemy引擎"""
        if self.engine:
            logger.warning("SQLAlchemy引擎已经初始化")
            return

        # 确保URL使用异步驱动
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://")

        # 创建异步引擎
        self.engine = create_async_engine(
            self.database_url,
            pool_size=self.config["pool_size"],
            max_overflow=self.config["max_overflow"],
            pool_pre_ping=self.config["pool_pre_ping"],
            pool_recycle=self.config["pool_recycle"],
            echo=self.config["echo"],
            echo_pool=self.config["echo_pool"],
            connect_args=self.config["connect_args"],
        )

        # 创建会话工厂
        engine = self._ensure_engine()
        self.session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        # 测试连接
        await self._test_connection()

        logger.info("SQLAlchemy引擎初始化完成")

    async def _test_connection(self):
        """测试数据库连接"""
        engine = self._ensure_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("数据库连接测试成功")

    @asynccontextmanager
    async def _session_scope(self) -> AsyncIterator[DatabaseSessionProtocol]:
        """Yield a typed SQLAlchemy session bound to the optimized pool."""
        if not self.session_factory:
            raise RuntimeError('Session factory is not initialized')

        session_factory = self.session_factory
        async with session_factory() as session:
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
        """Return the reusable session scope managed by this pool."""
        return self._session_scope()

    def transaction(self) -> DatabaseSessionManager:
        """Compatibility alias exposing the session scope helper."""
        return self._session_scope()

    async def execute(self, sql: str, params: SQLParams | None = None) -> int:
        """执行SQL语句"""
        engine = self._ensure_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text(sql), self._normalize_params(params))
            rowcount = result.rowcount
            return int(rowcount or 0)

    async def fetch_all(self, sql: str, params: SQLParams | None = None) -> list[RowDict]:
        """获取所有结果"""
        engine = self._ensure_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text(sql), self._normalize_params(params))
            return [self._row_to_dict(row) for row in result.mappings().all()]

    async def fetch_one(self, sql: str, params: SQLParams | None = None) -> Optional[RowDict]:
        """获取单条结果"""
        engine = self._ensure_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text(sql), self._normalize_params(params))
            mapping = result.mappings().first()
            if mapping is None:
                return None
            return self._row_to_dict(mapping)

    def get_statistics(self) -> SqlAlchemyPoolStatisticsPayload:
        """��ȡͳ����Ϣ"""
        stats_dict = self.statistics.to_dict()
        snapshot = cast(
            SqlAlchemyPoolStatisticsPayload,
            {**stats_dict, "pool_status": self.get_pool_status()},
        )
        return snapshot

    async def close(self):
        """关闭引擎"""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            logger.info("SQLAlchemy引擎已关闭")

    def get_pool_status(self) -> SqlAlchemyPoolStatus:
        """��ȡ���ӳ�״̬"""
        if not self.engine:
            return {"status": "未初始化"}

        engine = self._ensure_engine()
        pool = engine.pool
        return {
            "size": pool.size() if hasattr(pool, "size") else 0,
            "checked_in": pool.checkedin() if hasattr(pool, "checkedin") else 0,
            "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else 0,
            "overflow": pool.overflow() if hasattr(pool, "overflow") else 0,
            "total": pool.total() if hasattr(pool, "total") else 0,
        }
