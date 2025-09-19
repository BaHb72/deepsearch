"""
数据相关组件
包含数据库和缓存等数据存储组件
"""
import re
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from deepsearch.config import get_config
from deepsearch.core.async_component_v2 import AsyncComponent
from deepsearch.core.utils.exceptions import error_context, ComponentLifecycleError
from deepsearch.core.interfaces import ComponentType
from deepsearch.core.utils.timeout_config import get_timeout_manager, TimeoutCategory


class DatabaseComponent(AsyncComponent[Any]):
    """数据库组件 - 管理数据库连接和操作"""

    def __init__(self):
        super().__init__("database", ComponentType.EXTERNAL, "数据库")
        self._engine = None
        self._session_factory = None
        self._is_timescale_enabled = False
        self._timeout_manager = get_timeout_manager()

    @staticmethod
    def validate_table_name(table_name: str) -> bool:
        """
        验证表名是否安全，防止SQL注入

        Args:
            table_name: 要验证的表名

        Returns:
            bool: 表名是否有效
        """
        # 只允许字母、数字、下划线
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
        return bool(re.match(pattern, table_name))

    async def _do_initialize(self) -> Optional[Any]:
        """初始化数据库连接"""
        with error_context(self.name, "initialize"):
            config = get_config()
            db_config = config.database if config else None

            # 检查是否应该自动连接
            if not db_config.main.auto_connect:
                self._logger.info("数据库组件已初始化（未连接）- auto_connect=false")
                return None  # 返回None表示没有资源

            # 使用 connect_async 方法来建立连接
            try:
                await self.connect_async()
                self._logger.info("[OK] 数据库组件初始化成功")
                return self  # 返回self作为资源对象
            except Exception as e:
                # 自动连接失败时允许组件继续运行（可以稍后手动连接）
                self._logger.warning(f"数据库自动连接失败: {e}")
                return None  # 返回None表示连接失败

    async def _do_start(self) -> None:
        """启动数据库服务"""
        # 数据库通常不需要显式启动
        pass

    async def _do_stop(self) -> None:
        """停止数据库服务"""
        with error_context(self.name, "stop"):
            if self._engine:
                # 关闭数据库引擎
                self._logger.info("关闭数据库连接")
                await self._engine.dispose()

    def get_session(self):
        """获取数据库会话"""
        if not self._session_factory:
            raise ComponentLifecycleError(self.name, "get_session", "Database not initialized")
        return self._session_factory()

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """提供额外的状态信息"""
        return {
            "connected": self._engine is not None,
            "timescale_enabled": self._is_timescale_enabled
        }

    def _health_check(self) -> bool:
        """检查数据库健康状态"""
        if not self._engine:
            return False

        try:
            # 使用同步连接进行健康检查，避免协程警告
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
            return True
        except Exception:
            return False

    async def health_check_async(self) -> bool:
        """异步健康检查（带超时）"""
        if not self._engine:
            return False

        try:
            import asyncio
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.DB_HEALTH)

            async def _check():
                async with self._engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
                return True

            return await asyncio.wait_for(_check(), timeout=timeout)
        except Exception as e:
            self._logger.error(f"数据库健康检查失败: {e}")
            return False

    def is_connected(self) -> bool:
        """检查数据库是否已连接"""
        return self._engine is not None

    def _get_component_statistics(self) -> Dict[str, Any]:
        """获取数据库组件的统计信息"""
        return {
            "connected": self.is_connected(),
            "engine_type": type(self._engine).__name__ if self._engine else None,
            "timescale_enabled": self._is_timescale_enabled,
            "pool_status": self._get_pool_status() if self._engine else None
        }

    def _get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        if not self._engine:
            return {}

        pool = self._engine.pool
        return {
            "size": pool.size() if hasattr(pool, 'size') else 0,
            "checked_in": pool.checkedin() if hasattr(pool, 'checkedin') else 0,
            "checked_out": pool.checkedout() if hasattr(pool, 'checkedout') else 0,
            "overflow": pool.overflow() if hasattr(pool, 'overflow') else 0,
            "total": pool.total() if hasattr(pool, 'total') else 0
        }

    async def connect_async(self) -> None:
        """
        手动连接到数据库（带超时保护）

        用于在 auto_connect=false 或需要重新连接时手动建立连接
        """
        if self._engine is not None:
            # 已经连接
            self._logger.info("数据库已经连接")
            return

        # 获取配置
        config = get_config()
        db_config = config.database if config else None

        if not db_config or not db_config.main.enabled:
            raise RuntimeError("数据库功能未启用")

        # 获取数据库URL
        db_url = db_config.main.get_url()
        if not db_url:
            raise RuntimeError("数据库 URL 未配置")

        # 创建异步引擎
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

        # 获取连接超时配置
        connect_timeout = self._timeout_manager.get_timeout(TimeoutCategory.DB_CONNECT)

        self._engine = create_async_engine(
            db_url,
            echo=(config.app.env == "dev"),
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={
                "server_settings": {
                    "application_name": "deepsearch",
                    "jit": "off"  # 关闭JIT以提高稳定性
                },
                "timeout": connect_timeout,
                "command_timeout": connect_timeout
            }
        )

        # 创建会话工厂
        self._session_factory = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # 测试连接（带超时）
        try:
            import asyncio

            async def _test_connection():
                async with self._engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
                    self._logger.info("数据库连接成功")

            await asyncio.wait_for(_test_connection(), timeout=connect_timeout)
        except asyncio.TimeoutError:
            # 连接超时，清理资源
            if self._engine:
                await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            raise RuntimeError(f"数据库连接超时 ({connect_timeout}秒)")
        except Exception as e:
            # 连接失败，清理资源
            if self._engine:
                await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            raise RuntimeError(f"数据库连接失败: {e}")

        # 不需要设置_instance，基类会管理资源

    async def disconnect_async(self) -> None:
        """
        断开数据库连接
        """
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._logger.info("数据库连接已断开")

    def get_status_info(self) -> Dict[str, Any]:
        """获取详细状态信息"""
        info = super().get_status_info()

        # 添加数据库连接信息
        if self._engine:
            info['connection_status'] = 'connected'
            config = get_config()
            if config and config.database:
                info['connection_info'] = {
                    'type': config.database.main.type,
                    'host': config.database.main.host,
                    'port': config.database.main.port,
                    'database': config.database.main.database,
                }
        else:
            info['connection_status'] = 'disconnected'

        return info


class CacheComponent(AsyncComponent[Any]):
    """缓存组件 - 管理Redis缓存"""

    def __init__(self):
        super().__init__("cache", ComponentType.INFRASTRUCTURE, "缓存")
        self._redis_config = None
        self._redis_client = None
        self._redis_pool = None
        self._connected = False
        self._connection_error = None
        self._timeout_manager = get_timeout_manager()

    async def _do_initialize(self) -> Optional[Any]:
        """初始化缓存连接"""
        with error_context(self.name, "initialize"):
            # 检查缓存配置
            config = get_config()
            cache_config = config.database.cache if config and config.database else None

            # 检查是否启用
            if not cache_config.enabled:
                self._logger.info("Redis 缓存功能已禁用")
                return None  # 返回None表示没有资源

            # 获取Redis配置
            redis_config = cache_config.model_dump()
            self._redis_config = {
                'host': redis_config.get('host', 'localhost'),
                'port': redis_config.get('port', 6379),
                'db': redis_config.get('db', 0),
                'password': redis_config.get('password'),
            }

            # 尝试建立连接（可选，失败不影响系统）
            try:
                await self._connect_to_redis()
            except Exception as e:
                self._logger.warning(f"Redis connection failed (will run without cache): {e}")
                self._connected = False
                self._connection_error = str(e)

            # 返回self作为资源对象
            self._logger.info("缓存组件初始化完成")
            return self

    async def _connect_to_redis(self) -> None:
        """建立Redis连接（带超时保护）"""
        try:
            import redis.asyncio as aioredis
            import asyncio

            # 获取连接超时配置
            connect_timeout = self._timeout_manager.get_timeout(TimeoutCategory.CACHE_GET)

            # 创建连接池
            pool = aioredis.ConnectionPool(
                host=self._redis_config['host'],
                port=self._redis_config['port'],
                db=self._redis_config['db'],
                password=self._redis_config.get('password'),
                decode_responses=True,
                max_connections=self._redis_config.get('pool_size', 10),
                socket_keepalive=self._redis_config.get('socket_keepalive', True),
                socket_keepalive_options={
                    1: 1,  # TCP_KEEPIDLE
                    2: 1,  # TCP_KEEPINTVL
                    3: 3,  # TCP_KEEPCNT
                },
                socket_connect_timeout=connect_timeout,
                socket_timeout=connect_timeout,
                retry_on_timeout=self._redis_config.get('retry_on_timeout', True),
                health_check_interval=self._redis_config.get('health_check_interval', 30)
            )

            self._redis_client = aioredis.Redis(connection_pool=pool)

            # 测试连接（带超时）
            async def _test_connection():
                await self._redis_client.ping()

            await asyncio.wait_for(_test_connection(), timeout=connect_timeout)

            self._connected = True
            self._connection_error = None
            self._logger.info(f"成功连接到 Redis {self._redis_config['host']}:{self._redis_config['port']}")

        except asyncio.TimeoutError:
            self._connected = False
            self._connection_error = f"连接超时 ({connect_timeout}秒)"
            self._logger.error(f"Redis 连接超时")
            raise
        except Exception as e:
            self._connected = False
            self._connection_error = str(e)
            self._logger.error(f"Redis 连接失败: {e}")
            raise

    async def _do_start(self) -> None:
        """启动缓存服务"""
        # 如果连接已断开，尝试重新连接
        if not self._connected and self._redis_config:
            try:
                await self._connect_to_redis()
            except Exception as e:
                self._logger.error(f"启动时重新连接 Redis 失败: {e}")

    async def _do_stop(self) -> None:
        """停止缓存服务"""
        if self._redis_client:
            try:
                if hasattr(self._redis_client, 'close'):
                    await self._redis_client.close()
                    if hasattr(self._redis_client, 'wait_closed'):
                        await self._redis_client.wait_closed()
                    else:
                        await self._redis_client.aclose()
                elif hasattr(self._redis_client, 'aclose'):
                    await self._redis_client.aclose()
            except Exception as e:
                self._logger.error(f"关闭 Redis 连接时出错: {e}")
            finally:
                self._redis_client = None
                self._redis_pool = None
                self._connected = False

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """提供额外的状态信息"""
        config_info = self._redis_config.copy() if self._redis_config else {}
        # 隐藏密码
        if 'password' in config_info:
            config_info['password'] = '***' if config_info['password'] else None

        return {
            "enabled": get_config().database.cache.enabled if get_config() and hasattr(get_config().database, 'cache') else False,
            "connected": self._connected,
            "config": config_info,
            "error": self._connection_error,
            "has_client": self._redis_client is not None
        }

    def _health_check(self) -> bool:
        """检查缓存健康状态"""
        # 如果禁用了缓存，认为是健康的
        config = get_config()
        if config and hasattr(config.database, 'cache') and not config.database.cache.enabled:
            return True

        # 检查是否已连接
        return self._connected and self._redis_client is not None

    async def health_check_async(self) -> bool:
        """异步健康检查（带超时）"""
        if not self._connected or not self._redis_client:
            return False

        try:
            import asyncio
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.CACHE_GET)

            async def _ping():
                await self._redis_client.ping()
                return True

            return await asyncio.wait_for(_ping(), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.error(f"Redis 健康检查超时")
            self._connected = False
            self._connection_error = "健康检查超时"
            return False
        except Exception as e:
            self._logger.error(f"Redis 健康检查失败: {e}")
            self._connected = False
            self._connection_error = str(e)
            return False

    async def get_pool_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        if not self._redis_client or not hasattr(self._redis_client, 'connection_pool'):
            return {}

        pool = self._redis_client.connection_pool
        return {
            "max_connections": pool.max_connections,
            "created_connections": len(pool._created_connections) if hasattr(pool, '_created_connections') else 0,
            "available_connections": len(pool._available_connections) if hasattr(pool, '_available_connections') else 0,
            "in_use_connections": len(pool._in_use_connections) if hasattr(pool, '_in_use_connections') else 0,
        }

    async def get_status(self) -> Dict[str, Any]:
        """获取缓存组件状态信息"""
        status = {
            "connected": self._connected,
            "error": self._connection_error,
            "config": {
                "host": self._redis_config.get('host') if self._redis_config else None,
                "port": self._redis_config.get('port') if self._redis_config else None,
                "db": self._redis_config.get('db') if self._redis_config else None,
                "pool_size": self._redis_config.get('pool_size', 10) if self._redis_config else None
            }
        }

        if self._connected:
            # 获取连接池统计
            status["pool_stats"] = await self.get_pool_stats()

            # 获取 Redis 服务器信息（带超时）
            try:
                import asyncio
                timeout = self._timeout_manager.get_timeout(TimeoutCategory.CACHE_GET)

                async def _get_info():
                    return await self._redis_client.info()

                info = await asyncio.wait_for(_get_info(), timeout=timeout)
                status["server_info"] = {
                    "version": info.get("redis_version"),
                    "uptime_seconds": info.get("uptime_in_seconds"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory_human": info.get("used_memory_human"),
                    "used_memory_peak_human": info.get("used_memory_peak_human"),
                }
            except asyncio.TimeoutError:
                self._logger.error(f"获取 Redis 信息超时")
            except Exception as e:
                self._logger.error(f"获取 Redis 信息失败: {e}")

        return status

    # Redis 操作接口（带超时）
    async def get(self, key: str) -> Optional[str]:
        """获取缓存值（带超时）"""
        if not self._connected or not self._redis_client:
            return None

        try:
            import asyncio
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.CACHE_GET)

            async def _get():
                return await self._redis_client.get(key)

            return await asyncio.wait_for(_get(), timeout=timeout)
        except Exception as e:
            self._logger.error(f"Redis GET 操作失败: {e}")
            return None

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """设置缓存值（带超时）"""
        if not self._connected or not self._redis_client:
            return False

        try:
            import asyncio
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.CACHE_SET)

            async def _set():
                return await self._redis_client.set(key, value, ex=ttl)

            return await asyncio.wait_for(_set(), timeout=timeout)
        except Exception as e:
            error_msg = str(e)
            if "Connection refused" in error_msg or "Connection closed" in error_msg:
                self._logger.warning(f"Redis connection failed (SET operation): {error_msg}. Cache disabled for this operation.")
            else:
                self._logger.error(f"Redis SET operation failed: {error_msg}")
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存值（带超时）"""
        if not self._connected or not self._redis_client:
            return False

        try:
            import asyncio
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.CACHE_DELETE)

            async def _delete():
                return await self._redis_client.delete(key) > 0

            return await asyncio.wait_for(_delete(), timeout=timeout)
        except Exception as e:
            self._logger.error(f"Redis DELETE 操作失败: {e}")
            return False