"""
优化的数据库连接池

提供高性能的数据库连接池管理，包括：
- 连接池预热
- 连接健康检查
- 批量查询支持
- 性能监控
"""
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, AsyncGenerator
import asyncio
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import asyncpg
from asyncpg.pool import Pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

logger = logging.getLogger(__name__)


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

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
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
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None
        }


class OptimizedDatabasePool:
    """优化的数据库连接池"""

    def __init__(self, config: PoolConfig):
        self.config = config
        self.pool: Optional[Pool] = None
        self.statistics = PoolStatistics()
        self._lock = asyncio.Lock()
        self._prepared_statements: Dict[str, str] = {}
        self._query_times: List[float] = []
        self._max_query_history = 1000

    async def initialize(self):
        """初始化连接池"""
        async with self._lock:
            if self.pool:
                logger.warning("连接池已经初始化")
                return

            try:
                logger.info(f"初始化数据库连接池: min={self.config.min_size}, max={self.config.max_size}")

                self.pool = await asyncpg.create_pool(
                    self.config.dsn,
                    min_size=self.config.min_size,
                    max_size=self.config.max_size,
                    max_queries=self.config.max_queries,
                    max_inactive_connection_lifetime=self.config.max_inactive_lifetime,
                    command_timeout=self.config.command_timeout,
                    init=self._init_connection
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
            """
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
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return False

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator:
        """获取连接"""
        if not self.pool:
            raise RuntimeError("连接池未初始化")

        start_time = time.perf_counter()
        conn = None

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
            self._query_times = self._query_times[-self._max_query_history:]

        # 更新统计
        if self._query_times:
            self.statistics.avg_query_time = sum(self._query_times) / len(self._query_times)
            self.statistics.max_query_time = max(self._query_times)

    async def execute(self, query: str, *args, timeout: Optional[float] = None) -> str:
        """执行查询"""
        timeout = timeout or self.config.command_timeout

        async with self.acquire() as conn:
            return await asyncio.wait_for(
                conn.execute(query, *args),
                timeout=timeout
            )

    async def fetch(self, query: str, *args, timeout: Optional[float] = None) -> List:
        """获取查询结果"""
        timeout = timeout or self.config.command_timeout

        async with self.acquire() as conn:
            return await asyncio.wait_for(
                conn.fetch(query, *args),
                timeout=timeout
            )

    async def fetchval(self, query: str, *args, timeout: Optional[float] = None) -> Any:
        """获取单个值"""
        timeout = timeout or self.config.command_timeout

        async with self.acquire() as conn:
            return await asyncio.wait_for(
                conn.fetchval(query, *args),
                timeout=timeout
            )

    async def fetchrow(self, query: str, *args, timeout: Optional[float] = None) -> Optional[asyncpg.Record]:
        """获取单行"""
        timeout = timeout or self.config.command_timeout

        async with self.acquire() as conn:
            return await asyncio.wait_for(
                conn.fetchrow(query, *args),
                timeout=timeout
            )

    async def execute_batch(self, queries: List[tuple]) -> List[Any]:
        """批量执行查询"""
        results = []

        async with self.acquire() as conn:
            async with conn.transaction():
                for query_data in queries:
                    if len(query_data) == 1:
                        query = query_data[0]
                        params = []
                    else:
                        query = query_data[0]
                        params = query_data[1:]

                    try:
                        result = await conn.fetch(query, *params)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"批量查询失败: {query[:100]}... - {e}")
                        results.append(None)
                        # 不中断事务，继续执行

        return results

    async def execute_many(self, query: str, args_list: List[tuple]) -> None:
        """执行多个相同的查询（不同参数）"""
        async with self.acquire() as conn:
            await conn.executemany(query, args_list)

    async def copy_records_to_table(
        self,
        table_name: str,
        *,
        records: List[tuple],
        columns: List[str],
        schema_name: Optional[str] = None
    ) -> int:
        """批量复制记录到表（高性能）"""
        if schema_name:
            table_ref = f"{schema_name}.{table_name}"
        else:
            table_ref = table_name

        async with self.acquire() as conn:
            result = await conn.copy_records_to_table(
                table_ref,
                records=records,
                columns=columns
            )
            return result

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            result = await self.fetchval("SELECT 1", timeout=5.0)
            return result == 1
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False

    def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        if not self.pool:
            return {"status": "未初始化"}

        return {
            "min_size": self.pool._minsize,
            "max_size": self.pool._maxsize,
            "current_size": self.pool._size,
            "free_connections": self.pool._freesize,
            "used_connections": self.pool._size - self.pool._freesize,
            "waiting_queries": len(self.pool._queue._waiters) if hasattr(self.pool._queue, '_waiters') else 0,
        }

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self.statistics.to_dict()
        stats["pool_status"] = self.get_pool_status()
        return stats

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
        self.session_factory: Optional[sessionmaker] = None
        self.config = {
            "pool_size": kwargs.get("pool_size", 20),
            "max_overflow": kwargs.get("max_overflow", 10),
            "pool_pre_ping": kwargs.get("pool_pre_ping", True),
            "pool_recycle": kwargs.get("pool_recycle", 3600),
            "echo": kwargs.get("echo", False),
            "echo_pool": kwargs.get("echo_pool", False),
            "pool_timeout": kwargs.get("pool_timeout", 30),
            "connect_args": kwargs.get("connect_args", {})
        }
        self.statistics = PoolStatistics()

    async def initialize(self):
        """初始化SQLAlchemy引擎"""
        if self.engine:
            logger.warning("SQLAlchemy引擎已经初始化")
            return

        # 确保URL使用异步驱动
        if self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace(
                "postgresql://", "postgresql+asyncpg://"
            )

        # 创建异步引擎
        self.engine = create_async_engine(
            self.database_url,
            pool_size=self.config["pool_size"],
            max_overflow=self.config["max_overflow"],
            pool_pre_ping=self.config["pool_pre_ping"],
            pool_recycle=self.config["pool_recycle"],
            echo=self.config["echo"],
            echo_pool=self.config["echo_pool"],
            connect_args=self.config["connect_args"]
        )

        # 创建会话工厂
        self.session_factory = sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # 测试连接
        await self._test_connection()

        logger.info("SQLAlchemy引擎初始化完成")

    async def _test_connection(self):
        """测试数据库连接"""
        async with self.engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            logger.info("数据库连接测试成功")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """获取数据库会话"""
        if not self.session_factory:
            raise RuntimeError("会话工厂未初始化")

        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def execute(self, sql: str, params: Optional[Dict] = None) -> Any:
        """执行SQL语句"""
        async with self.engine.begin() as conn:
            result = await conn.execute(text(sql), params or {})
            return result

    async def fetch_all(self, sql: str, params: Optional[Dict] = None) -> List:
        """获取所有结果"""
        async with self.engine.begin() as conn:
            result = await conn.execute(text(sql), params or {})
            return result.fetchall()

    async def fetch_one(self, sql: str, params: Optional[Dict] = None) -> Optional[Any]:
        """获取单条结果"""
        async with self.engine.begin() as conn:
            result = await conn.execute(text(sql), params or {})
            return result.fetchone()

    async def close(self):
        """关闭引擎"""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            logger.info("SQLAlchemy引擎已关闭")

    def get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        if not self.engine:
            return {"status": "未初始化"}

        pool = self.engine.pool
        return {
            "size": pool.size() if hasattr(pool, 'size') else 0,
            "checked_in": pool.checkedin() if hasattr(pool, 'checkedin') else 0,
            "checked_out": pool.checkedout() if hasattr(pool, 'checkedout') else 0,
            "overflow": pool.overflow() if hasattr(pool, 'overflow') else 0,
            "total": pool.total() if hasattr(pool, 'total') else 0
        }