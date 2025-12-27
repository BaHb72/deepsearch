"""
数据相关组件
包含数据库和缓存等数据存储组件
"""

import asyncio
import copy
import importlib
import inspect
import ipaddress
import os
import platform
import re
from contextlib import suppress
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import redis.exceptions as redis_exceptions
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from deepsearch.config import get_config
from deepsearch.core.async_component import AsyncComponent
from deepsearch.core.interfaces import ComponentType
from deepsearch.core.utils.exceptions import ComponentLifecycleError, error_context
from deepsearch.core.utils.timeout_config import TimeoutCategory, get_timeout_manager
from deepsearch.infrastructure.persistence.runtime_state.database_status_store import (
    get_database_status_store,
)

if TYPE_CHECKING:
    from redis.exceptions import RedisError as RedisConnectionError
else:
    _connection_cls = getattr(redis_exceptions, "ConnectionError", None)
    if isinstance(_connection_cls, type) and issubclass(_connection_cls, BaseException):
        RedisConnectionError = _connection_cls  # type: ignore[assignment]
    else:
        RedisConnectionError = redis_exceptions.RedisError  # type: ignore[assignment]

LOCAL_HOST_CANDIDATES = {"localhost", "127.0.0.1", "::1"}


def _is_running_in_wsl() -> bool:
    if platform.system().lower() != "linux":
        return False

    release = platform.release().lower()
    if "microsoft" in release or "wsl" in release:
        return True

    if os.environ.get("WSL_INTEROP"):
        return True
    return False


def _resolve_windows_host_ip(logger: Any) -> Optional[str]:
    """解析 Windows 宿主机在 WSL 中的 IP 地址。"""
    resolv_path = "/etc/resolv.conf"
    try:
        with open(resolv_path, "r", encoding="utf-8", errors="ignore") as fp:
            for raw_line in fp:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if not line.startswith("nameserver"):
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                candidate = parts[1]
                try:
                    ip_obj = ipaddress.ip_address(candidate)
                except ValueError:
                    continue
                if ip_obj.version == 4:
                    return candidate
    except FileNotFoundError:
        logger.debug("未找到 %s，无法解析 Windows 宿主机 IP", resolv_path)
    except Exception as exc:  # pragma: no cover - 防御性日志
        logger.debug("解析 Windows 宿主机 IP 失败: %s", exc)
    return None


def _is_connection_related_error(error: Exception) -> bool:
    if isinstance(error, (RedisConnectionError, asyncio.TimeoutError, OSError)):
        return True

    cause = getattr(error, "__cause__", None)
    if isinstance(cause, (RedisConnectionError, OSError)):
        return True
    return False


def _should_try_windows_host(host: str) -> bool:
    host = (host or "").strip()
    return host in LOCAL_HOST_CANDIDATES


class DatabaseComponent(AsyncComponent[Any]):
    """数据库组件 - 管理数据库连接和操作"""

    def __init__(self):
        super().__init__("database", ComponentType.EXTERNAL, "数据库")
        self._engine: AsyncEngine | None = None
        self._session_factory: Callable[[], AsyncSession] | None = None
        self._is_timescale_enabled: bool = False
        self._timeout_manager = get_timeout_manager()
        self._active_db_host: Optional[str] = None

        self._instance = self

    @property
    def _instance(self):
        return self.resource or self

    @_instance.setter
    def _instance(self, value):
        if value is None:
            self._state_manager.state.clear_resource()
        else:
            self._state_manager.state.set_resource(value)

    @_instance.deleter
    def _instance(self):
        self._state_manager.state.clear_resource()

    async def _initialize(self) -> Optional[Any]:
        result = await self._do_initialize()
        if result is None:
            self._instance = self
            return None
        self._instance = result
        return result

    async def _stop(self) -> None:
        await self._do_stop()

    def _get_store_and_key(self):
        store = get_database_status_store()
        active_id = store.get_active_connection_id()
        key = str(active_id) if active_id is not None else "primary"
        return store, key

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
        pattern = r"^[a-zA-Z_][a-zA-Z0-9_]*$"
        return bool(re.match(pattern, table_name))

    async def _do_initialize(self) -> Optional[Any]:
        """初始化数据库连接"""
        with error_context(self.name, "initialize"):
            config = get_config()
            db_config = config.database if config else None

            # 检查是否应该自动连接
            if not db_config or not db_config.main.auto_connect:
                store, key = self._get_store_and_key()
                store.save_connectivity_status(key, {"state": "disconnected", "retrying": False})
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

    @property
    def engine(self) -> AsyncEngine | None:
        """Expose the underlying async engine for consumers requiring direct access."""
        return self._engine

    @property
    def is_timescale_enabled(self) -> bool:
        """Whether the component has enabled TimescaleDB features."""
        return self._is_timescale_enabled

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """提供额外的状态信息"""
        return {
            "connected": self._engine is not None,
            "timescale_enabled": self._is_timescale_enabled,
        }

    def _health_check(self) -> bool:
        """检查数据库可用状态"""
        if not self._engine:
            return False

        engine_to_use = self._engine
        sync_engine = getattr(self._engine, "sync_engine", None)

        async_module = None
        try:
            async_module = importlib.import_module("sqlalchemy.ext.asyncio")
        except Exception:  # pragma: no cover - SQLAlchemy 版本差异
            async_module = None

        async_engine_cls: type[Any] | None = None
        if async_module is not None:
            candidate = getattr(async_module, "AsyncEngine", None)
            if isinstance(candidate, type):
                async_engine_cls = candidate

        if async_engine_cls is not None and isinstance(self._engine, async_engine_cls):
            sync_engine = getattr(self._engine, "sync_engine", None)

        if sync_engine is not None:
            module_name = getattr(sync_engine.__class__, "__module__", "")
            if not module_name.startswith("unittest.mock"):
                engine_to_use = sync_engine

        connection = None
        try:
            connect_callable = getattr(engine_to_use, "connect", None)
            if not callable(connect_callable):
                self._logger.error("当前数据库引擎不支持同步健康检查接口")
                return False

            connection = connect_callable()
            try:
                connection.execute(text("SELECT 1"))
            except Exception:
                if hasattr(connection, "__enter__") and hasattr(connection, "__exit__"):
                    with connection as conn:
                        conn.execute(text("SELECT 1"))
                else:
                    raise
            close_method = getattr(connection, "close", None)
            if callable(close_method):
                close_method()
            return True
        except Exception as exc:
            self._logger.error(f"数据库健康检查失败: {exc}")
            return False
        finally:
            if connection is not None:
                dispose_method = getattr(connection, "dispose", None)
                if callable(dispose_method):
                    dispose_method()

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
            "pool_status": self._get_pool_status() if self._engine else None,
        }

    def _get_pool_status(self) -> Dict[str, Any]:
        """获取连接池状态"""
        if not self._engine:
            return {}

        pool = self._engine.pool
        return {
            "size": pool.size() if hasattr(pool, "size") else 0,
            "checked_in": pool.checkedin() if hasattr(pool, "checkedin") else 0,
            "checked_out": pool.checkedout() if hasattr(pool, "checkedout") else 0,
            "overflow": pool.overflow() if hasattr(pool, "overflow") else 0,
            "total": pool.total() if hasattr(pool, "total") else 0,
        }

    async def connect_async(self) -> None:
        """
        手动连接到数据库（带超时保护）

        用于在 auto_connect=false 或需要重新连接时手动建立连接
        """
        store, key = self._get_store_and_key()
        if self._engine is not None:
            store.save_connectivity_status(
                key,
                {
                    "state": "connected",
                    "last_success_at": datetime.now(timezone.utc),
                    "last_error": None,
                    "retrying": False,
                },
            )
            self._logger.info("数据库已经连接")
            return

        # 获取配置
        config = get_config()
        db_config = config.database if config else None

        if not db_config or not db_config.main.enabled:
            raise RuntimeError("数据库功能未启用")

        connect_timeout = self._timeout_manager.get_timeout(TimeoutCategory.DB_CONNECT)
        store.save_connectivity_status(key, {"state": "connecting", "retrying": False})

        main_config = db_config.main
        candidate_hosts = self._build_database_host_candidates(main_config.host)

        last_error: Optional[str] = None
        last_exception: Optional[Exception] = None

        for attempt, host in enumerate(candidate_hosts):
            if attempt > 0:
                self._logger.info("尝试使用备用数据库地址 %s:%s", host, main_config.port)

            try:
                await self._attempt_database_connection(
                    db_config=db_config,
                    main_config=main_config,
                    host=host,
                    connect_timeout=connect_timeout,
                )
                last_error = None
                last_exception = None
                break
            except asyncio.TimeoutError:
                last_error = f"数据库连接超时 ({connect_timeout}秒)"
                last_exception = None
                self._logger.warning(
                    "数据库连接 %s:%s 超时 (%s秒)",
                    host,
                    main_config.port,
                    connect_timeout,
                )
            except Exception as exc:
                last_exception = exc
                last_error = f"数据库连接失败: {exc}"
                self._logger.error("数据库连接 %s:%s 失败: %s", host, main_config.port, exc)

            if attempt + 1 < len(candidate_hosts):
                store.save_connectivity_status(
                    key,
                    {
                        "state": "connecting",
                        "last_error": last_error,
                        "retrying": True,
                    },
                )

        if self._engine is None or self._session_factory is None:
            store.save_connectivity_status(
                key,
                {
                    "state": "error",
                    "last_error": last_error or "数据库连接失败",
                    "retrying": False,
                },
            )
            if last_exception is not None:
                raise RuntimeError(last_error or "数据库连接失败") from last_exception
            raise RuntimeError(last_error or "数据库连接失败")

        store.save_connectivity_status(
            key,
            {
                "state": "connected",
                "last_success_at": datetime.now(timezone.utc),
                "last_error": None,
                "retrying": False,
            },
        )

        self._instance = self

        # 不需要设置_instance，基类会管理资源

    async def disconnect_async(self) -> None:
        """
        断开数据库连接
        """
        store, key = self._get_store_and_key()
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._active_db_host = None
            self._logger.info("数据库连接已断开")
            store.save_connectivity_status(
                key, {"state": "disconnected", "last_error": None, "retrying": False}
            )
        else:
            store.save_connectivity_status(key, {"state": "disconnected", "retrying": False})

    def _build_database_host_candidates(self, host: str) -> List[str]:
        candidates: List[str] = [host]
        if _is_running_in_wsl() and _should_try_windows_host(host):
            fallback_host = _resolve_windows_host_ip(self._logger)
            if fallback_host and fallback_host not in candidates:
                candidates.append(fallback_host)
        return candidates

    async def _attempt_database_connection(
        self,
        *,
        db_config: Any,
        main_config: Any,
        host: str,
        connect_timeout: float,
    ) -> None:
        temp_config = copy.deepcopy(main_config)
        temp_config.host = host

        db_url = temp_config.get_url()
        if not db_url:
            raise RuntimeError("数据库 URL 未配置")

        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

        engine = create_async_engine(
            db_url,
            echo=(db_config.main.echo if db_config else False),
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={
                "server_settings": {
                    "application_name": "deepsearch",
                    "jit": "off",
                },
                "timeout": connect_timeout,
                "command_timeout": connect_timeout,
            },
        )

        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def _test_connection() -> None:
            async with engine.begin() as conn:
                await conn.exec_driver_sql("SELECT 1")
            self._logger.info("数据库连接成功 (%s:%s)", host, main_config.port)

        test_task = asyncio.create_task(_test_connection())
        try:
            await asyncio.wait_for(test_task, timeout=connect_timeout)
        except asyncio.TimeoutError:
            test_task.cancel()
            with suppress(asyncio.CancelledError):
                await test_task
            await engine.dispose()
            raise
        except Exception:
            if not test_task.done():
                test_task.cancel()
                with suppress(asyncio.CancelledError):
                    await test_task
            await engine.dispose()
            raise

        # 关闭旧引擎（若存在）
        if self._engine:
            await self._engine.dispose()

        self._engine = engine
        self._session_factory = session_factory
        self._active_db_host = host

    def get_status_info(self) -> Dict[str, Any]:
        """获取详细状态信息"""
        info: Dict[str, Any] = super().get_status_info()

        # 添加数据库连接信息
        if self._engine:
            info["connection_status"] = "connected"
            config = get_config()
            if config and config.database:
                active_host = self._active_db_host or config.database.main.host
                info["connection_info"] = {
                    "type": config.database.main.type,
                    "host": active_host,
                    "port": config.database.main.port,
                    "database": config.database.main.database,
                }
        else:
            info["connection_status"] = "disconnected"

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

        self._instance = self

    @property
    def _instance(self):
        return self.resource or self

    @_instance.setter
    def _instance(self, value):
        if value is None:
            self._state_manager.state.clear_resource()
        else:
            self._state_manager.state.set_resource(value)

    @_instance.deleter
    def _instance(self):
        self._state_manager.state.clear_resource()

    async def _initialize(self) -> Optional[Any]:
        result = await self._do_initialize()
        if result is None:
            self._instance = self
            return None
        self._instance = result
        return result

    async def _stop(self) -> None:
        await self._do_stop()

    async def _do_initialize(self) -> Optional[Any]:
        """初始化缓存连接"""
        with error_context(self.name, "initialize"):
            # 检查缓存配置
            config = get_config()
            cache_config = config.database.cache if config and config.database else None

            # 检查是否启用
            if not cache_config or not cache_config.enabled:
                self._logger.info("Redis 缓存功能已禁用")
                return None  # 返回None表示没有资源

            # 获取Redis配置
            redis_config = cache_config.model_dump()
            self._redis_config = {
                "host": redis_config.get("host", "localhost"),
                "port": redis_config.get("port", 6379),
                "db": redis_config.get("db", 0),
                "username": redis_config.get("username"),
                "password": redis_config.get("password"),
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

            # 获取连接超时配置
            connect_timeout = self._timeout_manager.get_timeout(TimeoutCategory.CACHE_GET)

            # 创建连接池
            pool_kwargs: Dict[str, Any] = {
                "host": self._redis_config["host"],
                "port": self._redis_config["port"],
                "db": self._redis_config["db"],
                "username": self._redis_config.get("username"),
                "password": self._redis_config.get("password"),
                "decode_responses": True,
                "max_connections": self._redis_config.get("pool_size", 10),
                "socket_keepalive": self._redis_config.get("socket_keepalive", True),
                "socket_connect_timeout": connect_timeout,
                "socket_timeout": connect_timeout,
                "retry_on_timeout": self._redis_config.get("retry_on_timeout", True),
                "health_check_interval": self._redis_config.get("health_check_interval", 30),
            }

            keepalive_options = self._build_keepalive_options()
            if keepalive_options:
                pool_kwargs["socket_keepalive_options"] = keepalive_options

            current_kwargs = dict(pool_kwargs)
            attempted_keepalive_fix = False
            attempted_windows_host = False

            while True:
                try:
                    await self._initialize_redis_client(aioredis, current_kwargs, connect_timeout)
                    break
                except Exception as exc:
                    if not attempted_keepalive_fix and self._should_disable_keepalive(
                        exc, current_kwargs
                    ):
                        attempted_keepalive_fix = True
                        current_kwargs = dict(current_kwargs)
                        current_kwargs["socket_keepalive"] = False
                        current_kwargs.pop("socket_keepalive_options", None)
                        self._logger.warning(
                            "当前环境不支持配置的 TCP keepalive 选项，已禁用 keepalive 后重试 Redis 连接"
                        )
                        continue

                    if not attempted_windows_host:
                        fallback_kwargs = self._prepare_windows_host_retry(current_kwargs, exc)
                        if fallback_kwargs:
                            attempted_windows_host = True
                            current_kwargs = fallback_kwargs
                            host_for_log = fallback_kwargs.get("host")
                            if host_for_log:
                                self._logger.info(
                                    "检测到 WSL 环境，尝试使用宿主机 IP %s 连接 Redis", host_for_log
                                )
                            continue

                    raise

            self._connected = True
            self._connection_error = None
            self._redis_config["host"] = current_kwargs.get("host", self._redis_config["host"])
            self._logger.info(
                f"成功连接到 Redis {self._redis_config['host']}:{self._redis_config['port']}"
            )

        except asyncio.TimeoutError:
            self._connected = False
            self._connection_error = f"连接超时 ({connect_timeout}秒)"
            self._logger.error("Redis 连接超时")
            raise
        except Exception as e:
            self._connected = False
            self._connection_error = str(e)
            self._logger.error(f"Redis 连接失败: {e}")
            raise

    def _build_keepalive_options(self) -> Optional[Dict[int, int]]:
        """构建跨平台可用的 TCP keepalive 参数。"""
        if not self._redis_config:
            return None

        if not self._redis_config.get("socket_keepalive", True):
            return None

        try:
            import socket
        except Exception as exc:  # pragma: no cover - 防御性处理
            self._logger.debug("socket 模块不可用，跳过 keepalive 配置: %s", exc)
            return None

        option_map: Dict[int, int] = {}
        option_candidates = [
            ("TCP_KEEPIDLE", 1),
            ("TCP_KEEPALIVE", 1),  # macOS 使用 TCP_KEEPALIVE 常量
            ("TCP_KEEPINTVL", 1),
            ("TCP_KEEPCNT", 3),
        ]

        for name, value in option_candidates:
            option = getattr(socket, name, None)
            if option is None:
                continue
            try:
                option_map[int(option)] = value
            except (TypeError, ValueError):
                continue

        if not option_map:
            self._logger.debug("当前平台未提供可用的 TCP keepalive 常量，跳过 keepalive 配置")
            return None

        return option_map

    async def _initialize_redis_client(
        self,
        aioredis: Any,
        pool_kwargs: Dict[str, Any],
        connect_timeout: float,
    ) -> None:
        """根据给定参数建立 Redis 连接并执行连通性探测。"""
        import asyncio

        pool = aioredis.ConnectionPool(**pool_kwargs)
        client = aioredis.Redis(connection_pool=pool)

        async def _test_connection() -> None:
            await client.ping()

        test_task = asyncio.create_task(_test_connection())
        try:
            await asyncio.wait_for(test_task, timeout=connect_timeout)
        except asyncio.TimeoutError:
            test_task.cancel()
            with suppress(asyncio.CancelledError):
                await test_task
            await client.close()
            raise
        except RedisConnectionError:
            if not test_task.done():
                test_task.cancel()
                with suppress(asyncio.CancelledError):
                    await test_task
            await client.close()
            raise
        except Exception:
            if not test_task.done():
                test_task.cancel()
                with suppress(asyncio.CancelledError):
                    await test_task
            await client.close()
            raise

        self._redis_client = client

    def _should_disable_keepalive(self, error: Exception, pool_kwargs: Dict[str, Any]) -> bool:
        """判断异常是否由于 keepalive 参数导致，并决定是否尝试禁用 keepalive。"""
        if not pool_kwargs.get("socket_keepalive", True):
            return False

        message = str(error).lower()
        if "invalid argument" in message:
            return True

        errno_value = getattr(error, "errno", None)
        if errno_value == 22:
            return True

        if isinstance(error, RedisConnectionError):
            cause = getattr(error, "__cause__", None)
            if cause is not None and getattr(cause, "errno", None) == 22:
                return True

        return False

    def _prepare_windows_host_retry(
        self, pool_kwargs: Dict[str, Any], error: Exception
    ) -> Optional[Dict[str, Any]]:
        """在 WSL 环境下尝试使用宿主机 IP 重试连接。"""
        if not _is_running_in_wsl():
            return None

        host = str(pool_kwargs.get("host", "")).strip()
        if not _should_try_windows_host(host):
            return None

        if not _is_connection_related_error(error):
            return None

        windows_host_ip = _resolve_windows_host_ip(self._logger)
        if not windows_host_ip:
            return None

        new_kwargs = dict(pool_kwargs)
        new_kwargs["host"] = windows_host_ip
        # 禁用 keepalive options，避免上次失败的配置残留
        new_kwargs.pop("socket_keepalive_options", None)
        return new_kwargs

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
                close_method = getattr(self._redis_client, "close", None)
                if close_method:
                    close_result = close_method()
                    if inspect.isawaitable(close_result):
                        await close_result
                alternate_close = getattr(self._redis_client, "aclose", None)
                if alternate_close and alternate_close is not close_method:
                    alt_result = alternate_close()
                    if inspect.isawaitable(alt_result):
                        await alt_result
                wait_closed = getattr(self._redis_client, "wait_closed", None)
                if wait_closed:
                    wait_result = wait_closed()
                    if inspect.isawaitable(wait_result):
                        await wait_result
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
        if "password" in config_info:
            config_info["password"] = "***" if config_info["password"] else None

        return {
            "enabled": (
                get_config().database.cache.enabled
                if get_config() and hasattr(get_config().database, "cache")
                else False
            ),
            "connected": self._connected,
            "config": config_info,
            "error": self._connection_error,
            "has_client": self._redis_client is not None,
        }

    def _health_check(self) -> bool:
        """检查缓存健康状态"""
        # 如果禁用了缓存，认为是健康的
        config = get_config()
        if config and hasattr(config.database, "cache") and not config.database.cache.enabled:
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
            self._logger.error("Redis 健康检查超时")
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
        if not self._redis_client or not hasattr(self._redis_client, "connection_pool"):
            return {}

        pool = self._redis_client.connection_pool
        return {
            "max_connections": pool.max_connections,
            "created_connections": (
                len(pool._created_connections) if hasattr(pool, "_created_connections") else 0
            ),
            "available_connections": (
                len(pool._available_connections) if hasattr(pool, "_available_connections") else 0
            ),
            "in_use_connections": (
                len(pool._in_use_connections) if hasattr(pool, "_in_use_connections") else 0
            ),
        }

    async def get_status_details(self) -> Dict[str, Any]:
        """获取缓存组件状态信息"""
        status = {
            "connected": self._connected,
            "error": self._connection_error,
            "config": {
                "host": self._redis_config.get("host") if self._redis_config else None,
                "port": self._redis_config.get("port") if self._redis_config else None,
                "db": self._redis_config.get("db") if self._redis_config else None,
                "pool_size": (
                    self._redis_config.get("pool_size", 10) if self._redis_config else None
                ),
            },
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
                self._logger.error("获取 Redis 信息超时")
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
                self._logger.warning(
                    f"Redis connection failed (SET operation): {error_msg}. Cache disabled for this operation."
                )
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
