"""
连接池管理器

提供高性能的连接池实现，用于管理数据源连接
"""

from __future__ import annotations

import asyncio
import inspect
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable, Generic, Optional, TypedDict, TypeVar, cast

from loguru import logger

T = TypeVar("T")
TConn = TypeVar("TConn")


class ConnectionStats(TypedDict):
    connections_created: int
    connections_closed: int
    connections_reused: int
    acquire_count: int
    acquire_timeout_count: int
    validation_failures: int


class PoolRuntimeStats(TypedDict):
    connections_created: int
    connections_closed: int
    connections_reused: int
    acquire_count: int
    acquire_timeout_count: int
    validation_failures: int
    current_size: int
    available: int
    in_use: int
    min_size: int
    max_size: int


async def _await_maybe(value: Awaitable[T] | T) -> T:
    """Await the value if needed."""
    if inspect.isawaitable(value):
        return cast(T, await cast(Awaitable[T], value))
    return cast(T, value)


@dataclass
class PoolConfig:
    """连接池配置"""

    min_size: int = 2
    max_size: int = 10
    idle_timeout: int = 300  # 空闲连接超时（秒）
    validation_interval: int = 60  # 连接验证间隔（秒）
    acquire_timeout: float = 5.0  # 获取连接超时（秒）


class Connection(Generic[TConn]):
    """连接包装器"""

    def __init__(self, conn: TConn, pool: "ConnectionPool[TConn]"):
        self.conn: TConn = conn
        self.pool = pool
        self.created_at = time.time()
        self.last_used = time.time()
        self.in_use = False
        self.closed = False

    def is_expired(self) -> bool:
        """检查连接是否过期"""
        if self.closed:
            return True
        idle_time = time.time() - self.last_used
        return idle_time > self.pool.config.idle_timeout

    async def validate(self) -> bool:
        """验证连接是否有效"""
        if self.closed:
            return False

        validator = self.pool.validator
        if validator is not None:
            try:
                return await _await_maybe(validator(self.conn))
            except Exception as e:
                logger.warning(f"连接验证失败: {e}")
                return False
        return True

    def mark_used(self) -> None:
        """标记连接已使用"""
        self.last_used = time.time()
        self.in_use = True

    def release(self) -> None:
        """释放连接回池"""
        self.in_use = False
        self.last_used = time.time()

    async def close(self) -> None:
        """关闭连接"""
        if not self.closed:
            self.closed = True
            closer = self.pool.closer
            if closer:
                try:
                    await _await_maybe(closer(self.conn))
                except Exception as e:
                    logger.error(f"关闭连接失败: {e}")


class ConnectionPool(Generic[TConn]):
    """
    异步连接池

    特性：
    - 动态连接管理（最小/最大连接数）
    - 连接验证和自动重连
    - 空闲连接清理
    - 连接获取超时控制
    """

    def __init__(
        self,
        factory: Callable[[], Awaitable[TConn] | TConn],
        config: Optional[PoolConfig] = None,
        validator: Optional[Callable[[TConn], Awaitable[bool] | bool]] = None,
        closer: Optional[Callable[[TConn], Awaitable[None] | None]] = None,
    ) -> None:
        """
        初始化连接池

        Args:
            factory: 连接工厂函数
            config: 连接池配置
            validator: 连接验证函数
            closer: 连接关闭函数
        """
        self.factory: Callable[[], Awaitable[TConn] | TConn] = factory
        self.config = config or PoolConfig()
        self.validator: Optional[Callable[[TConn], Awaitable[bool] | bool]] = validator
        self.closer: Optional[Callable[[TConn], Awaitable[None] | None]] = closer

        self.pool: asyncio.Queue[Connection[TConn]] = asyncio.Queue(maxsize=self.config.max_size)
        self.semaphore = asyncio.Semaphore(self.config.max_size)
        self.connections: list[Connection[TConn]] = []
        self._created = 0
        self._closed = False
        self._lock = asyncio.Lock()

        # 统计信息
        self.stats: ConnectionStats = {
            "connections_created": 0,
            "connections_closed": 0,
            "connections_reused": 0,
            "acquire_count": 0,
            "acquire_timeout_count": 0,
            "validation_failures": 0,
        }

        # 启动后台任务
        self._maintenance_task: Optional[asyncio.Task[None]] = None

    async def initialize(self):
        """初始化连接池"""
        logger.info(f"初始化连接池 (min={self.config.min_size}, max={self.config.max_size})")

        # 创建最小数量的连接
        for _ in range(self.config.min_size):
            try:
                conn = await self._create_connection()
                await self.pool.put(conn)
            except Exception as e:
                logger.error(f"创建初始连接失败: {e}")

        # 启动维护任务
        if not self._maintenance_task:
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())

        logger.info(f"连接池初始化完成，当前连接数: {self._created}")

    async def _create_connection(self) -> Connection:
        """创建新连接"""
        try:
            raw_conn = await _await_maybe(self.factory())
            conn = Connection(raw_conn, self)

            async with self._lock:
                self.connections.append(conn)
                self._created += 1
                self.stats["connections_created"] += 1

            logger.debug(f"创建新连接，当前总数: {self._created}")
            return conn

        except Exception as e:
            logger.error(f"创建连接失败: {e}")
            raise

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[TConn]:
        """
        获取连接（上下文管理器）

        使用示例：
        ```python
        async with pool.acquire() as conn:
            # 使用连接
            result = await conn.query(...)
        ```
        """
        conn: Optional[Connection[TConn]] = None
        try:
            conn = await self.acquire_connection()
            yield conn.conn
        finally:
            if conn:
                self.release_connection(conn)

    async def acquire_connection(self) -> Connection[TConn]:
        """获取连接"""
        if self._closed:
            raise RuntimeError("连接池已关闭")

        self.stats["acquire_count"] += 1
        start_time = time.time()

        while time.time() - start_time < self.config.acquire_timeout:
            try:
                # 尝试从池中获取连接
                try:
                    conn = cast(Connection[TConn], self.pool.get_nowait())

                    # 验证连接
                    if await conn.validate():
                        conn.mark_used()
                        self.stats["connections_reused"] += 1
                        logger.debug(f"复用连接 (池中剩余: {self.pool.qsize()})")
                        return conn
                    else:
                        # 连接无效，关闭并创建新的
                        await self._remove_connection(conn)
                        self.stats["validation_failures"] += 1

                except asyncio.QueueEmpty:
                    pass

                # 检查是否可以创建新连接
                async with self._lock:
                    if self._created < self.config.max_size:
                        conn = await self._create_connection()
                        conn.mark_used()
                        return conn

                # 等待连接可用
                try:
                    conn = cast(
                        Connection[TConn], await asyncio.wait_for(self.pool.get(), timeout=0.1)
                    )
                    if await conn.validate():
                        conn.mark_used()
                        self.stats["connections_reused"] += 1
                        return conn
                    else:
                        await self._remove_connection(conn)

                except asyncio.TimeoutError:
                    continue

            except Exception as e:
                logger.error(f"获取连接异常: {e}")
                raise

        self.stats["acquire_timeout_count"] += 1
        raise asyncio.TimeoutError(f"获取连接超时 ({self.config.acquire_timeout}秒)")

    def release_connection(self, conn: Connection[TConn]) -> None:
        """释放连接回池"""
        if not conn or conn.closed:
            return

        conn.release()

        try:
            self.pool.put_nowait(conn)
            logger.debug(f"连接已释放 (池中连接: {self.pool.qsize()})")
        except asyncio.QueueFull:
            # 池已满，关闭连接
            asyncio.create_task(self._remove_connection(conn))

    async def _remove_connection(self, conn: Connection[TConn]) -> None:
        """移除连接"""
        try:
            await conn.close()

            async with self._lock:
                if conn in self.connections:
                    self.connections.remove(conn)
                self._created -= 1
                self.stats["connections_closed"] += 1

            logger.debug(f"连接已移除，当前总数: {self._created}")

        except Exception as e:
            logger.error(f"移除连接失败: {e}")

    async def _maintenance_loop(self) -> None:
        """维护循环 - 清理过期连接，保持最小连接数"""
        while not self._closed:
            try:
                # 使用可中断的短休眠，每秒检查一次关闭状态
                for _ in range(self.config.validation_interval):
                    if self._closed:
                        break
                    await asyncio.sleep(1)

                # 再次检查是否已关闭
                if self._closed:
                    break

                # 清理过期连接
                expired_conns = []
                async with self._lock:
                    for conn in self.connections:
                        if not conn.in_use and conn.is_expired():
                            expired_conns.append(conn)

                for conn in expired_conns:
                    await self._remove_connection(conn)
                    logger.debug("清理过期连接")

                # 保持最小连接数
                async with self._lock:
                    while self._created < self.config.min_size and not self._closed:
                        try:
                            conn = await self._create_connection()
                            await self.pool.put(conn)
                        except Exception as e:
                            logger.error(f"维护任务创建连接失败: {e}")
                            break

            except Exception as e:
                logger.error(f"连接池维护任务异常: {e}")

    async def close(self):
        """关闭连接池"""
        self._closed = True

        # 取消维护任务
        if self._maintenance_task:
            self._maintenance_task.cancel()
            try:
                # 使用更短的超时时间等待任务完成
                await asyncio.wait_for(self._maintenance_task, timeout=0.5)
            except asyncio.CancelledError, asyncio.TimeoutError:
                pass

        # 关闭所有连接
        async with self._lock:
            for conn in self.connections:
                try:
                    await conn.close()
                except Exception as e:
                    logger.error(f"关闭连接失败: {e}")

            self.connections.clear()
            self._created = 0

        logger.info("连接池已关闭")

    def get_stats(self) -> PoolRuntimeStats:
        """获取统计信息"""
        base_stats: ConnectionStats = {
            "connections_created": self.stats["connections_created"],
            "connections_closed": self.stats["connections_closed"],
            "connections_reused": self.stats["connections_reused"],
            "acquire_count": self.stats["acquire_count"],
            "acquire_timeout_count": self.stats["acquire_timeout_count"],
            "validation_failures": self.stats["validation_failures"],
        }
        runtime_stats: PoolRuntimeStats = {
            **base_stats,
            "current_size": self._created,
            "available": self.pool.qsize(),
            "in_use": self._created - self.pool.qsize(),
            "min_size": self.config.min_size,
            "max_size": self.config.max_size,
        }
        return runtime_stats
