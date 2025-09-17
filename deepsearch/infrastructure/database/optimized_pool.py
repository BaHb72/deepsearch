"""
优化的数据库连接池实现

提供高性能的数据库连接池管理，包括连接预热、健康检查和监控
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import time

import asyncpg
from asyncpg.pool import Pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool


@dataclass
class PoolConfig:
    """连接池配置"""
    dsn: str  # 数据库连接字符串
    min_size: int = 50  # 最小连接数（从10提升到50）
    max_size: int = 100  # 最大连接数（从20提升到100）
    max_queries: int = 1000  # 每个连接的最大查询数
    max_inactive_connection_lifetime: float = 300  # 空闲连接最大生命周期（秒）
    command_timeout: float = 60  # 命令超时（秒）
    statement_cache_size: int = 100  # 语句缓存大小
    max_cached_statement_lifetime: int = 3600  # 缓存语句最大生命周期（秒）
    pool_recycle: int = 3600  # 连接回收时间（秒）
    echo_pool: bool = False  # 是否输出连接池日志
    pre_ping: bool = True  # 连接前ping检查


@dataclass
class PoolStatistics:
    """连接池统计信息"""
    created_at: datetime = field(default_factory=datetime.now)
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    waiting_requests: int = 0
    total_queries: int = 0
    failed_queries: int = 0
    avg_query_time: float = 0.0
    max_query_time: float = 0.0
    min_query_time: float = float('inf')
    connection_errors: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None


class OptimizedDatabasePool:
    """
    优化的数据库连接池

    主要优化：
    1. 连接数从10-20提升到50-100
    2. 添加连接预热机制
    3. 实现连接健康检查
    4. 添加性能监控
    5. 支持批量操作
    """

    def __init__(self, config: PoolConfig):
        """
        初始化连接池

        Args:
            config: 连接池配置
        """
        self.config = config
        self.pool: Optional[Pool] = None
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[sessionmaker] = None
        self.statistics = PoolStatistics()
        self._logger = logging.getLogger("deepsearch.database.pool")
        self._initialized = False
        self._warmup_complete = False

    async def initialize(self) -> None:
        """初始化连接池"""
        if self._initialized:
            return

        try:
            # 创建 asyncpg 连接池
            self.pool = await asyncpg.create_pool(
                self.config.dsn,
                min_size=self.config.min_size,
                max_size=self.config.max_size,
                max_queries=self.config.max_queries,
                max_inactive_connection_lifetime=self.config.max_inactive_connection_lifetime,
                command_timeout=self.config.command_timeout,
                init=self._init_connection
            )

            # 创建 SQLAlchemy 引擎
            self.engine = create_async_engine(
                self.config.dsn.replace('postgresql://', 'postgresql+asyncpg://'),
                pool_size=self.config.min_size,
                max_overflow=self.config.max_size - self.config.min_size,
                pool_recycle=self.config.pool_recycle,
                pool_pre_ping=self.config.pre_ping,
                echo_pool=self.config.echo_pool,
                poolclass=QueuePool
            )

            # 创建会话工厂
            self.session_factory = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            self._initialized = True
            self._logger.info(
                f"数据库连接池初始化成功 (最小: {self.config.min_size}, 最大: {self.config.max_size})"
            )

            # 执行连接预热
            await self.warmup()

        except Exception as e:
            self.statistics.connection_errors += 1
            self.statistics.last_error = str(e)
            self.statistics.last_error_time = datetime.now()
            self._logger.error(f"初始化连接池失败: {e}")
            raise

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """
        初始化单个连接

        Args:
            conn: asyncpg 连接
        """
        # 设置连接级别的优化参数
        await conn.execute("SET jit = 'off'")  # 对小查询关闭JIT
        await conn.execute("SET work_mem = '256MB'")  # 增加工作内存
        await conn.execute("SET effective_cache_size = '4GB'")  # 设置有效缓存大小
        await conn.execute("SET random_page_cost = 1.1")  # SSD优化

        # 准备常用语句
        await self._prepare_statements(conn)

    async def _prepare_statements(self, conn: asyncpg.Connection) -> None:
        """
        准备常用的SQL语句

        Args:
            conn: asyncpg 连接
        """
        # 准备常用查询语句
        statements = [
            ("get_stock_info", "SELECT * FROM stock_info WHERE symbol = $1"),
            ("get_kline_data", """
                SELECT * FROM kline_data
                WHERE symbol = $1 AND timestamp BETWEEN $2 AND $3
                ORDER BY timestamp
            """),
            ("get_latest_price", """
                SELECT price, volume, timestamp
                FROM market_data
                WHERE symbol = $1
                ORDER BY timestamp DESC
                LIMIT 1
            """),
        ]

        for name, sql in statements:
            try:
                await conn.execute(f"PREPARE {name} AS {sql}")
            except Exception as e:
                self._logger.debug(f"准备语句 {name} 失败: {e}")

    async def warmup(self) -> None:
        """
        预热连接池

        创建最小数量的连接并进行健康检查
        """
        if self._warmup_complete:
            return

        self._logger.info("开始预热连接池...")
        start_time = time.time()

        try:
            # 创建最小数量的连接
            tasks = []
            for _ in range(self.config.min_size):
                tasks.append(self._create_and_test_connection())

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 统计成功的连接
            success_count = sum(1 for r in results if r is True)
            self.statistics.total_connections = success_count

            elapsed = time.time() - start_time
            self._logger.info(
                f"连接池预热完成: {success_count}/{self.config.min_size} 个连接 "
                f"(耗时: {elapsed:.2f}秒)"
            )

            self._warmup_complete = True

        except Exception as e:
            self._logger.error(f"连接池预热失败: {e}")
            raise

    async def _create_and_test_connection(self) -> bool:
        """
        创建并测试单个连接

        Returns:
            连接是否成功
        """
        try:
            async with self.pool.acquire() as conn:
                # 执行简单查询测试连接
                await conn.fetchval("SELECT 1")
                return True
        except Exception as e:
            self._logger.debug(f"连接测试失败: {e}")
            return False

    @asynccontextmanager
    async def acquire(self):
        """
        获取数据库连接

        Yields:
            数据库连接
        """
        if not self._initialized:
            await self.initialize()

        start_time = time.time()
        try:
            async with self.pool.acquire() as conn:
                self.statistics.active_connections += 1
                yield conn
        finally:
            self.statistics.active_connections -= 1
            query_time = time.time() - start_time
            self._update_query_statistics(query_time)

    @asynccontextmanager
    async def get_session(self) -> AsyncSession:
        """
        获取 SQLAlchemy 会话

        Yields:
            数据库会话
        """
        if not self._initialized:
            await self.initialize()

        async with self.session_factory() as session:
            yield session

    async def execute(self, query: str, *args, timeout: Optional[float] = None) -> Any:
        """
        执行查询

        Args:
            query: SQL查询
            *args: 查询参数
            timeout: 超时时间

        Returns:
            查询结果
        """
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)

    async def execute_batch(self, queries: List[tuple]) -> List[Any]:
        """
        批量执行查询

        Args:
            queries: 查询列表，每个元素为 (query, *params)

        Returns:
            查询结果列表
        """
        results = []
        async with self.acquire() as conn:
            async with conn.transaction():
                for query_data in queries:
                    if isinstance(query_data, tuple):
                        query = query_data[0]
                        params = query_data[1:] if len(query_data) > 1 else []
                    else:
                        query = query_data
                        params = []

                    result = await conn.fetch(query, *params)
                    results.append(result)

        self.statistics.total_queries += len(queries)
        return results

    async def health_check(self) -> bool:
        """
        健康检查

        Returns:
            连接池是否健康
        """
        try:
            async with self.acquire() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            self._logger.error(f"健康检查失败: {e}")
            self.statistics.connection_errors += 1
            return False

    def _update_query_statistics(self, query_time: float) -> None:
        """
        更新查询统计信息

        Args:
            query_time: 查询时间（秒）
        """
        self.statistics.total_queries += 1

        # 更新平均查询时间
        if self.statistics.total_queries == 1:
            self.statistics.avg_query_time = query_time
        else:
            # 使用移动平均
            alpha = 0.1  # 平滑因子
            self.statistics.avg_query_time = (
                alpha * query_time +
                (1 - alpha) * self.statistics.avg_query_time
            )

        # 更新最大/最小查询时间
        self.statistics.max_query_time = max(
            self.statistics.max_query_time,
            query_time
        )
        self.statistics.min_query_time = min(
            self.statistics.min_query_time,
            query_time
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取连接池统计信息

        Returns:
            统计信息字典
        """
        pool_stats = {}
        if self.pool:
            pool_stats = {
                "size": self.pool.get_size(),
                "min_size": self.pool.get_min_size(),
                "max_size": self.pool.get_max_size(),
                "free_connections": self.pool.get_idle_size(),
            }

        return {
            "pool": pool_stats,
            "statistics": {
                "total_connections": self.statistics.total_connections,
                "active_connections": self.statistics.active_connections,
                "idle_connections": self.statistics.idle_connections,
                "total_queries": self.statistics.total_queries,
                "failed_queries": self.statistics.failed_queries,
                "avg_query_time_ms": self.statistics.avg_query_time * 1000,
                "max_query_time_ms": self.statistics.max_query_time * 1000,
                "min_query_time_ms": (
                    self.statistics.min_query_time * 1000
                    if self.statistics.min_query_time != float('inf')
                    else 0
                ),
                "connection_errors": self.statistics.connection_errors,
                "last_error": self.statistics.last_error,
                "uptime_seconds": (
                    datetime.now() - self.statistics.created_at
                ).total_seconds() if self._initialized else 0,
            }
        }

    async def close(self) -> None:
        """关闭连接池"""
        if self.pool:
            await self.pool.close()
            self._logger.info("数据库连接池已关闭")

        if self.engine:
            await self.engine.dispose()

        self._initialized = False
        self._warmup_complete = False

    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()