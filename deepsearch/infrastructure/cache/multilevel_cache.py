"""多级缓存系统实现，涵盖 Redis 与数据库的协同缓存策略。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import pickle
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncContextManager, Callable, Dict, Optional, Tuple, TYPE_CHECKING, cast

import redis.asyncio as aioredis
from cachetools import TTLCache  # type: ignore[import-untyped]
from sqlalchemy import Column, DateTime, Integer, LargeBinary, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from deepsearch.observability import get_logger

if TYPE_CHECKING:
    # 仅用于类型检查，避免运行时强依赖
    from redis.asyncio import Redis as AsyncRedis
else:  # pragma: no cover - 运行时代码路径
    AsyncRedis = aioredis.Redis


class Base(DeclarativeBase):
    """声明式基类，便于 mypy 正确识别 ORM 模型类型。"""

    pass


SessionFactory = Callable[[], AsyncContextManager[AsyncSession]]
"""统一的异步会话工厂类型，便于与 SQLAlchemy 保持一致。"""


class CacheLevel(Enum):
    """缓存级别"""

    L1_MEMORY = "L1_MEMORY"
    L2_REDIS = "L2_REDIS"
    L3_DATABASE = "L3_DATABASE"
    MISS = "MISS"


@dataclass
class CacheStatistics:
    """缓存统计信息"""

    l1_hits: int = 0
    l1_misses: int = 0
    l2_hits: int = 0
    l2_misses: int = 0
    l3_hits: int = 0
    l3_misses: int = 0
    total_gets: int = 0
    total_sets: int = 0
    total_deletes: int = 0
    avg_get_time_ms: float = 0.0
    avg_set_time_ms: float = 0.0
    last_cleanup: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def hit_rate(self) -> float:
        """计算总体命中率"""
        total_hits = self.l1_hits + self.l2_hits + self.l3_hits
        if self.total_gets == 0:
            return 0.0
        return total_hits / self.total_gets

    @property
    def l1_hit_rate(self) -> float:
        """L1 命中率"""
        if self.total_gets == 0:
            return 0.0
        return self.l1_hits / self.total_gets

    @property
    def l2_hit_rate(self) -> float:
        """L2 命中率"""
        l2_attempts = self.l2_hits + self.l2_misses
        if l2_attempts == 0:
            return 0.0
        return self.l2_hits / l2_attempts

    @property
    def l3_hit_rate(self) -> float:
        """L3 命中率"""
        l3_attempts = self.l3_hits + self.l3_misses
        if l3_attempts == 0:
            return 0.0
        return self.l3_hits / l3_attempts


class CacheEntry(Base):
    """数据库缓存表模型"""

    __tablename__ = "cache_entries"

    key = Column(String(255), primary_key=True)
    value = Column(LargeBinary)
    created_at = Column(DateTime, default=datetime.now)
    expires_at = Column(DateTime)
    access_count = Column(Integer, default=0)
    last_accessed = Column(DateTime, default=datetime.now)

    def __init__(self, **kwargs: Any) -> None:  # pragma: no cover - ORM 初始化辅助
        """
        SQLAlchemy 默认会在 Declarative 模型上注入 `__init__`，但 mypy 无法感知。
        显式声明后既不影响运行时行为，也能让类型检查器理解关键字参数。
        """
        super().__init__(**kwargs)


@dataclass
class CacheConfig:
    """缓存配置"""

    # L1 配置
    l1_enabled: bool = True
    l1_max_size: int = 10000
    l1_ttl_seconds: int = 60  # 1分钟

    # L2 配置
    l2_enabled: bool = True
    l2_host: str = "localhost"
    l2_port: int = 6379
    l2_db: int = 0
    l2_password: Optional[str] = None
    l2_ttl_seconds: int = 3600  # 1小时
    l2_max_connections: int = 50

    # L3 配置
    l3_enabled: bool = True
    l3_ttl_seconds: int = 86400  # 24小时
    l3_cleanup_interval: int = 3600  # 清理间隔

    # 通用配置
    enable_statistics: bool = True
    enable_compression: bool = False
    compression_threshold: int = 1024  # 压缩阈值（字节）


class MultiLevelCache:
    """
    多级缓存系统

    特性：
    1. L1: 进程内存缓存（热数据）
    2. L2: Redis 缓存（温数据）
    3. L3: 数据库缓存（冷数据）
    4. 自动数据提升
    5. 统计和监控
    """

    def __init__(
        self, config: CacheConfig, db_session_factory: Optional[SessionFactory] = None
    ) -> None:
        """
        初始化多级缓存

        Args:
            config: 缓存配置
            db_session_factory: 数据库会话工厂（用于L3）
        """
        self.config = config
        self.db_session_factory = db_session_factory
        self._logger = get_logger("deepsearch.cache.multilevel")

        # L1: 内存缓存
        if config.l1_enabled:
            self.l1_cache = TTLCache(maxsize=config.l1_max_size, ttl=config.l1_ttl_seconds)
        else:
            self.l1_cache = None

        # L2: Redis 缓存
        self.l2_cache: Optional[AsyncRedis] = None

        # 统计信息
        self.statistics = CacheStatistics() if config.enable_statistics else None

        # 清理任务
        self._cleanup_task: Optional[asyncio.Task[None]] = None

    async def initialize(self) -> None:
        """初始化缓存系统"""
        # 初始化 L2 Redis
        if self.config.l2_enabled:
            try:
                self.l2_cache = aioredis.from_url(
                    f"redis://{self.config.l2_host}:{self.config.l2_port}/{self.config.l2_db}",
                    password=self.config.l2_password,
                    encoding="utf-8",
                    decode_responses=False,
                    max_connections=self.config.l2_max_connections,
                )
                # 测试连接
                await self.l2_cache.ping()
                self._logger.info("L2 Redis 缓存已连接")
            except Exception as e:
                self._logger.warning(f"L2 Redis 连接失败: {e}")
                self.l2_cache = None

        # 启动清理任务
        if self.config.l3_enabled and self.db_session_factory:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        self._logger.info("多级缓存系统初始化完成")

    def _generate_key(self, namespace: str, key: Any) -> str:
        """
        生成缓存键

        Args:
            namespace: 命名空间
            key: 原始键

        Returns:
            哈希后的缓存键
        """
        if isinstance(key, (dict, list)):
            key_str = json.dumps(key, sort_keys=True)
        else:
            key_str = str(key)

        hash_key = hashlib.md5(f"{namespace}:{key_str}".encode()).hexdigest()
        return f"{namespace}:{hash_key}"

    async def get(
        self, namespace: str, key: Any, fetcher: Optional[Callable] = None
    ) -> Tuple[Optional[Any], CacheLevel]:
        """
        获取缓存数据

        Args:
            namespace: 命名空间
            key: 缓存键
            fetcher: 数据获取函数（缓存未命中时调用）

        Returns:
            (数据, 缓存级别) 元组
        """
        cache_key = self._generate_key(namespace, key)
        start_time = time.time()

        if self.statistics:
            self.statistics.total_gets += 1

        # L1 查询
        if self.l1_cache is not None:
            try:
                value = self.l1_cache.get(cache_key)
                if value is not None:
                    if self.statistics:
                        self.statistics.l1_hits += 1
                    self._update_get_time(start_time)
                    return value, CacheLevel.L1_MEMORY
            except Exception as e:
                self._logger.debug(f"L1 查询失败: {e}")

            if self.statistics:
                self.statistics.l1_misses += 1

        # L2 查询
        if self.l2_cache is not None:
            try:
                value_bytes = await self.l2_cache.get(cache_key)
                if value_bytes:
                    value = pickle.loads(value_bytes)
                    if self.statistics:
                        self.statistics.l2_hits += 1

                    # 提升到 L1
                    if self.l1_cache is not None:
                        self.l1_cache[cache_key] = value

                    self._update_get_time(start_time)
                    return value, CacheLevel.L2_REDIS
            except Exception as e:
                self._logger.debug(f"L2 查询失败: {e}")

            if self.statistics:
                self.statistics.l2_misses += 1

        # L3 查询
        if self.config.l3_enabled and self.db_session_factory:
            try:
                value = await self._get_from_l3(cache_key)
                if value is not None:
                    if self.statistics:
                        self.statistics.l3_hits += 1

                    # 提升到 L2 和 L1
                    await self._promote_to_l2(cache_key, value)
                    if self.l1_cache is not None:
                        self.l1_cache[cache_key] = value

                    self._update_get_time(start_time)
                    return value, CacheLevel.L3_DATABASE
            except Exception as e:
                self._logger.debug(f"L3 查询失败: {e}")

            if self.statistics:
                self.statistics.l3_misses += 1

        # 缓存未命中，调用 fetcher
        if fetcher:
            try:
                value = await fetcher() if asyncio.iscoroutinefunction(fetcher) else fetcher()
                await self.set(namespace, key, value)
                self._update_get_time(start_time)
                return value, CacheLevel.MISS
            except Exception as e:
                self._logger.error(f"Fetcher 执行失败: {e}")

        self._update_get_time(start_time)
        return None, CacheLevel.MISS

    async def set(self, namespace: str, key: Any, value: Any, ttl: Optional[int] = None) -> None:
        """
        设置缓存数据

        Args:
            namespace: 命名空间
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒）
        """
        cache_key = self._generate_key(namespace, key)
        start_time = time.time()

        if self.statistics:
            self.statistics.total_sets += 1

        # 写入 L1
        if self.l1_cache is not None:
            try:
                self.l1_cache[cache_key] = value
            except Exception as e:
                self._logger.debug(f"L1 写入失败: {e}")

        # 写入 L2
        if self.l2_cache is not None:
            try:
                serialized = pickle.dumps(value)
                await self.l2_cache.setex(cache_key, ttl or self.config.l2_ttl_seconds, serialized)
            except Exception as e:
                self._logger.debug(f"L2 写入失败: {e}")

        # 异步写入 L3
        if self.config.l3_enabled and self.db_session_factory:
            asyncio.create_task(
                self._set_to_l3(cache_key, value, ttl or self.config.l3_ttl_seconds)
            )

        self._update_set_time(start_time)

    async def delete(self, namespace: str, key: Any) -> bool:
        """
        删除缓存数据

        Args:
            namespace: 命名空间
            key: 缓存键

        Returns:
            是否删除成功
        """
        cache_key = self._generate_key(namespace, key)

        if self.statistics:
            self.statistics.total_deletes += 1

        success = False

        # 从 L1 删除
        if self.l1_cache is not None:
            try:
                del self.l1_cache[cache_key]
                success = True
            except KeyError:
                pass

        # 从 L2 删除
        if self.l2_cache is not None:
            try:
                result = await self.l2_cache.delete(cache_key)
                if result > 0:
                    success = True
            except Exception as e:
                self._logger.debug(f"L2 删除失败: {e}")

        # 从 L3 删除
        if self.config.l3_enabled and self.db_session_factory:
            try:
                await self._delete_from_l3(cache_key)
                success = True
            except Exception as e:
                self._logger.debug(f"L3 删除失败: {e}")

        return success

    async def invalidate(self, namespace: str) -> int:
        """
        失效整个命名空间

        Args:
            namespace: 命名空间

        Returns:
            删除的键数量
        """
        pattern = f"{namespace}:*"
        count = 0

        # 清理 L1
        if self.l1_cache is not None:
            keys_to_remove = [k for k in self.l1_cache if k.startswith(namespace)]
            for k in keys_to_remove:
                del self.l1_cache[k]
                count += 1

        # 清理 L2
        if self.l2_cache is not None:
            try:
                cursor = 0
                while True:
                    cursor, raw_keys = await self.l2_cache.scan(
                        cursor, match=pattern, count=100
                    )
                    keys = cast(Tuple[str | bytes, ...], tuple(raw_keys))
                    if keys:
                        await self.l2_cache.delete(*keys)
                        count += len(keys)
                    if cursor == 0:
                        break
            except Exception as e:
                self._logger.error(f"L2 失效失败: {e}")

        # 清理 L3
        if self.config.l3_enabled and self.db_session_factory:
            try:
                count += await self._invalidate_l3(pattern)
            except Exception as e:
                self._logger.error(f"L3 失效失败: {e}")

        return count

    async def _get_from_l3(self, key: str) -> Optional[Any]:
        """从 L3 数据库获取数据"""
        if not self.db_session_factory:
            return None

        async with self.db_session_factory() as session:
            stmt = select(CacheEntry).where(
                CacheEntry.key == key, CacheEntry.expires_at > datetime.now()
            )
            result = await session.execute(stmt)
            entry = result.scalar_one_or_none()

            if entry:
                # 更新访问信息
                entry.access_count += 1
                entry.last_accessed = datetime.now()
                await session.commit()

                return pickle.loads(entry.value)

        return None

    async def _set_to_l3(self, key: str, value: Any, ttl: int) -> None:
        """写入 L3 数据库"""
        if not self.db_session_factory:
            return

        async with self.db_session_factory() as session:
            expires_at = datetime.now() + timedelta(seconds=ttl)
            serialized = pickle.dumps(value)

            # 查找现有记录
            stmt = select(CacheEntry).where(CacheEntry.key == key)
            result = await session.execute(stmt)
            entry = result.scalar_one_or_none()

            if entry:
                # 更新现有记录
                entry.value = serialized
                entry.expires_at = expires_at
                entry.last_accessed = datetime.now()
            else:
                # 创建新记录
                entry = CacheEntry(key=key, value=serialized, expires_at=expires_at)
                cast(AsyncSession, session).add(entry)

            await session.commit()

    async def _delete_from_l3(self, key: str) -> None:
        """从 L3 数据库删除"""
        if not self.db_session_factory:
            return

        async with self.db_session_factory() as session:
            stmt = select(CacheEntry).where(CacheEntry.key == key)
            result = await session.execute(stmt)
            entry = result.scalar_one_or_none()

            if entry:
                await cast(AsyncSession, session).delete(entry)
                await session.commit()

    async def _invalidate_l3(self, pattern: str) -> int:
        """失效 L3 中的键"""
        if not self.db_session_factory:
            return 0

        async with self.db_session_factory() as session:
            # 使用 LIKE 查询
            like_pattern = pattern.replace("*", "%")
            stmt = select(CacheEntry).where(CacheEntry.key.like(like_pattern))
            result = await session.execute(stmt)
            entries = result.scalars().all()

            count = len(entries)
            for entry in entries:
                await cast(AsyncSession, session).delete(entry)

            await session.commit()
            return count

    async def _promote_to_l2(self, key: str, value: Any) -> None:
        """将数据提升到 L2"""
        if self.l2_cache is not None:
            try:
                serialized = pickle.dumps(value)
                await self.l2_cache.setex(key, self.config.l2_ttl_seconds, serialized)
            except Exception as e:
                self._logger.debug(f"提升到 L2 失败: {e}")

    async def _cleanup_loop(self) -> None:
        """清理过期缓存的循环任务"""
        while True:
            try:
                await asyncio.sleep(self.config.l3_cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"清理任务失败: {e}")

    async def _cleanup_expired(self) -> None:
        """清理过期的 L3 缓存"""
        if not self.db_session_factory:
            return

        async with self.db_session_factory() as session:
            # 删除过期记录
            stmt = select(CacheEntry).where(CacheEntry.expires_at < datetime.now())
            result = await session.execute(stmt)
            expired_entries = result.scalars().all()

            for entry in expired_entries:
                await session.delete(entry)

            await session.commit()

            if self.statistics:
                self.statistics.last_cleanup = datetime.now()

            self._logger.info(f"清理了 {len(expired_entries)} 个过期缓存项")

    def _update_get_time(self, start_time: float) -> None:
        """更新获取时间统计"""
        if not self.statistics:
            return

        elapsed_ms = (time.time() - start_time) * 1000
        if self.statistics.avg_get_time_ms == 0:
            self.statistics.avg_get_time_ms = elapsed_ms
        else:
            # 使用移动平均
            alpha = 0.1
            self.statistics.avg_get_time_ms = (
                alpha * elapsed_ms + (1 - alpha) * self.statistics.avg_get_time_ms
            )

    def _update_set_time(self, start_time: float) -> None:
        """更新设置时间统计"""
        if not self.statistics:
            return

        elapsed_ms = (time.time() - start_time) * 1000
        if self.statistics.avg_set_time_ms == 0:
            self.statistics.avg_set_time_ms = elapsed_ms
        else:
            # 使用移动平均
            alpha = 0.1
            self.statistics.avg_set_time_ms = (
                alpha * elapsed_ms + (1 - alpha) * self.statistics.avg_set_time_ms
            )

    def get_statistics(self) -> Optional[Dict[str, Any]]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        if not self.statistics:
            return None

        return {
            "hit_rate": f"{self.statistics.hit_rate:.2%}",
            "l1_hit_rate": f"{self.statistics.l1_hit_rate:.2%}",
            "l2_hit_rate": f"{self.statistics.l2_hit_rate:.2%}",
            "l3_hit_rate": f"{self.statistics.l3_hit_rate:.2%}",
            "total_gets": self.statistics.total_gets,
            "total_sets": self.statistics.total_sets,
            "total_deletes": self.statistics.total_deletes,
            "l1_hits": self.statistics.l1_hits,
            "l2_hits": self.statistics.l2_hits,
            "l3_hits": self.statistics.l3_hits,
            "avg_get_time_ms": round(self.statistics.avg_get_time_ms, 2),
            "avg_set_time_ms": round(self.statistics.avg_set_time_ms, 2),
            "uptime_seconds": (datetime.now() - self.statistics.created_at).total_seconds(),
            "last_cleanup": (
                self.statistics.last_cleanup.isoformat() if self.statistics.last_cleanup else None
            ),
        }

    async def close(self) -> None:
        """关闭缓存系统"""
        # 取消清理任务
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # 关闭 Redis 连接
        if self.l2_cache:
            close_coro = getattr(self.l2_cache, "aclose", None)
            if callable(close_coro):
                await close_coro()
            else:
                close_sync = getattr(self.l2_cache, "close", None)
                if callable(close_sync):
                    close_sync()

        self._logger.info("多级缓存系统已关闭")
