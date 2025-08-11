"""
统一的系统组件实现

使用新的异步组件基类，消除了重复的sync/async方法，
并实现了清晰的关注点分离。
"""
import re
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from deepsearch.config import settings
from deepsearch.event.engine import EventEngine
from deepsearch.gateway.gateway import Gateway
from deepsearch.messaging.bus import CompositeMessageBus, RouteConfig
from deepsearch.messaging.factory import MessageBusFactory
from deepsearch.monitoring import EventSystemMonitor
from .async_component import AsyncComponent, SimpleAsyncComponent
from .exceptions import error_context, ComponentLifecycleError
from .interfaces import ComponentType


class EventEngineComponent(SimpleAsyncComponent[EventEngine]):
    """事件引擎组件 - 处理系统内所有事件"""

    def __init__(self, queue_size: int = 10000, max_workers: int = 32,
                 batch_size: int = 100):
        super().__init__(
            name="event_engine",
            component_type=ComponentType.INFRASTRUCTURE,
            instance_factory=EventEngine,
            display_name="事件引擎",
            queue_size=queue_size,
            max_workers=max_workers,
            enable_batch_processing=True,
            batch_size=batch_size,
            batch_timeout=0.1
        )
        self.queue_size = queue_size
        self.max_workers = max_workers
        self.batch_size = batch_size

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """提供额外的状态信息"""
        return {
            "queue_size": self.queue_size,
            "max_workers": self.max_workers,
            "batch_size": self.batch_size,
            "statistics": self._get_component_statistics() if self._instance else {}
        }

    def _health_check(self) -> bool:
        """检查事件引擎健康状态"""
        return self._instance and self._instance._running

    def _get_component_statistics(self) -> Dict[str, Any]:
        """获取事件引擎的详细统计信息"""
        if not self._instance:
            return {}

        stats = {
            "queue_size": self._instance._queue.qsize() if hasattr(self._instance, '_queue') else 0,
            "active_threads": len(self._instance._executors) if hasattr(self._instance, '_executors') else 0,
        }

        # 获取事件引擎自身的统计信息
        if hasattr(self._instance, 'get_statistics'):
            engine_stats = self._instance.get_statistics()
            stats.update(engine_stats)

        # 获取处理器统计
        if hasattr(self._instance, 'get_handler_statistics'):
            handler_stats = self._instance.get_handler_statistics()
            if hasattr(handler_stats, 'get_statistics'):
                handler_data = handler_stats.get_statistics()
                stats["handlers"] = handler_data
                # 计算总处理事件数
                total_processed = sum(
                    metrics.get('total', 0)
                    for metrics in handler_data.get('events', {}).values()
                )
                stats["total_processed"] = total_processed

        return stats


class MessageBusComponent(AsyncComponent[CompositeMessageBus]):
    """消息总线组件 - 处理进程间通信"""

    def __init__(self):
        super().__init__("message_bus", ComponentType.INFRASTRUCTURE, "消息总线")

    async def _initialize(self) -> None:
        """初始化消息总线"""
        with error_context(self.name, "initialize"):
            # 从配置创建消息总线
            buses = {}
            routes = []

            # 检查是否有消息总线配置
            if hasattr(settings, 'message_bus'):
                msg_bus_config = settings.message_bus

                # 创建各个总线实例
                if hasattr(msg_bus_config, 'buses'):
                    for bus_name, bus_cfg in msg_bus_config.buses.items():
                        if bus_cfg.enabled:
                            # bus_cfg.type 可能是枚举，需要转换为字符串
                            bus_type = str(bus_cfg.type.value) if hasattr(bus_cfg.type, 'value') else str(bus_cfg.type)
                            bus_config = bus_cfg.config if bus_cfg.config else {}
                            try:
                                bus_instance = MessageBusFactory.create(bus_type, bus_config)
                                buses[bus_name] = bus_instance
                                self._logger.info(f"创建消息总线: {bus_name} (type={bus_type})")
                            except Exception as e:
                                self._logger.error(f"创建消息总线 {bus_name} 失败: {e}")

                # 创建路由配置
                if hasattr(msg_bus_config, 'routes'):
                    for route_cfg in msg_bus_config.routes:
                        # 将buses转换为字符串列表（如果是枚举的话）
                        bus_list = []
                        for bus in route_cfg.buses:
                            if hasattr(bus, 'value'):
                                bus_list.append(bus.value)
                            else:
                                bus_list.append(str(bus))

                        route = RouteConfig(
                            match=route_cfg.match,
                            buses=bus_list
                        )
                        routes.append(route)
                        self._logger.debug(f"添加路由规则: {route.match} -> {route.buses}")

            # 如果没有配置，使用默认的内存总线
            if not buses:
                self._logger.warning("未找到消息总线配置，使用默认内存总线")
                buses['inmem'] = MessageBusFactory.create('inmem', {})
                routes.append(RouteConfig(match='*', buses=['inmem']))

            # 创建CompositeMessageBus实例
            self._instance = CompositeMessageBus(buses=buses, routes=routes)
            self._logger.info(f"消息总线初始化完成: {len(buses)} 个总线, {len(routes)} 条路由")

    async def _start(self) -> None:
        """启动消息总线"""
        with error_context(self.name, "start"):
            if self._instance:
                self._instance.start()  # start 是同步方法

    async def _stop(self) -> None:
        """停止消息总线"""
        with error_context(self.name, "stop"):
            if self._instance:
                self._instance.stop()  # stop 是同步方法

    def _health_check(self) -> bool:
        """检查消息总线健康状态"""
        return self._instance and self._instance.is_running()

    def get_statistics(self) -> Dict[str, Any]:
        """获取消息总线统计信息"""
        if self._instance:
            return self._instance.get_statistics()
        return {}


class DatabaseComponent(AsyncComponent[Any]):
    """数据库组件 - 管理数据库连接和操作"""

    def __init__(self):
        super().__init__("database", ComponentType.EXTERNAL, "数据库")
        self._engine = None
        self._session_factory = None
        self._is_timescale_enabled = False

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

    async def _initialize(self) -> None:
        """初始化数据库连接"""
        with error_context(self.name, "initialize"):
            db_config = settings.database

            # 检查是否应该自动连接
            if not db_config.main.auto_connect:
                self._logger.info("数据库组件已初始化（未连接）- auto_connect=false")
                return

            # 获取数据库URL
            db_url = db_config.main.get_url()
            if not db_url:
                raise RuntimeError("数据库 URL 未配置")

            # 创建异步引擎
            if db_url.startswith("postgresql://"):
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

            self._engine = create_async_engine(
                db_url,
                echo=(settings.app.env == "dev"),
                pool_size=20,
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
            )

            # 创建会话工厂
            self._session_factory = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            # 设置实例为self以满足基类要求
            self._instance = self

            self._logger.info("[OK] 数据库组件初始化成功")

    async def _start(self) -> None:
        """启动数据库服务"""
        # 数据库通常不需要显式启动
        pass

    async def _stop(self) -> None:
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
            from sqlalchemy import text
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                conn.commit()
            return True
        except Exception:
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


class CacheComponent(AsyncComponent[Any]):
    """缓存组件 - 管理Redis缓存"""

    def __init__(self):
        super().__init__("cache", ComponentType.INFRASTRUCTURE, "缓存")
        self._redis_config = None
        self._redis_client = None
        self._redis_pool = None
        self._connected = False
        self._connection_error = None

    async def _initialize(self) -> None:
        """初始化缓存连接"""
        with error_context(self.name, "initialize"):
            # 检查缓存配置
            cache_config = settings.database.cache

            # 检查是否启用
            if not cache_config.enabled:
                self._logger.info("Redis 缓存功能已禁用")
                self._instance = self
                return

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

            # 设置实例为self以满足基类要求
            self._instance = self
            self._logger.info("缓存组件初始化完成")

    async def _connect_to_redis(self) -> None:
        """建立Redis连接"""
        try:
            # 直接使用 redis-py 的异步支持，不再尝试导入旧的 aioredis
            import redis.asyncio as aioredis

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
                socket_connect_timeout=self._redis_config.get('socket_connect_timeout', 5),
                socket_timeout=self._redis_config.get('socket_timeout', 5),
                retry_on_timeout=self._redis_config.get('retry_on_timeout', True),
                health_check_interval=self._redis_config.get('health_check_interval', 30)
            )

            self._redis_client = aioredis.Redis(connection_pool=pool)

            # 测试连接
            await self._redis_client.ping()

            self._connected = True
            self._connection_error = None
            self._logger.info(f"成功连接到 Redis {self._redis_config['host']}:{self._redis_config['port']}")

        except Exception as e:
            self._connected = False
            self._connection_error = str(e)
            self._logger.error(f"Redis 连接失败: {e}")
            raise

    async def _start(self) -> None:
        """启动缓存服务"""
        # 如果连接已断开，尝试重新连接
        if not self._connected and self._redis_config:
            try:
                await self._connect_to_redis()
            except Exception as e:
                self._logger.error(f"启动时重新连接 Redis 失败: {e}")

    async def _stop(self) -> None:
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
            "enabled": settings.database.cache.enabled if hasattr(settings.database, 'cache') else False,
            "connected": self._connected,
            "config": config_info,
            "error": self._connection_error,
            "has_client": self._redis_client is not None
        }

    def _health_check(self) -> bool:
        """检查缓存健康状态"""
        # 如果禁用了缓存，认为是健康的
        if hasattr(settings.database, 'cache') and not settings.database.cache.enabled:
            return True

        # 检查是否已连接
        return self._connected and self._redis_client is not None

    async def health_check_async(self) -> bool:
        """异步健康检查"""
        if not self._connected or not self._redis_client:
            return False

        try:
            # 尝试ping Redis服务器
            await self._redis_client.ping()
            return True
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
            "created_connections": len(pool._created_connections),
            "available_connections": len(pool._available_connections),
            "in_use_connections": len(pool._in_use_connections),
        }

    async def get_status(self) -> Dict[str, Any]:
        """获取缓存组件状态信息"""
        status = {
            "connected": self._connected,
            "error": self._connection_error,
            "config": {
                "host": self._redis_config.get('host'),
                "port": self._redis_config.get('port'),
                "db": self._redis_config.get('db'),
                "pool_size": self._redis_config.get('pool_size', 10)
            }
        }

        if self._connected:
            # 获取连接池统计
            status["pool_stats"] = await self.get_pool_stats()

            # 获取 Redis 服务器信息
            try:
                info = await self._redis_client.info()
                status["server_info"] = {
                    "version": info.get("redis_version"),
                    "uptime_seconds": info.get("uptime_in_seconds"),
                    "connected_clients": info.get("connected_clients"),
                    "used_memory_human": info.get("used_memory_human"),
                    "used_memory_peak_human": info.get("used_memory_peak_human"),
                }
            except Exception as e:
                self._logger.error(f"获取 Redis 信息失败: {e}")

        return status

    # Redis 操作接口
    async def get(self, key: str) -> Optional[str]:
        """获取缓存值"""
        if not self._redis_client:
            return None
        try:
            return await self._redis_client.get(key)
        except Exception as e:
            self._logger.error(f"Redis GET 操作失败: {e}")
            return None

    async def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        """设置缓存值"""
        if not self._redis_client:
            return False
        try:
            if expire:
                await self._redis_client.setex(key, expire, value)
            else:
                await self._redis_client.set(key, value)
            return True
        except Exception as e:
            self._logger.error(f"Redis SET 操作失败: {e}")
            return False

    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        if not self._redis_client:
            return False
        try:
            await self._redis_client.delete(key)
            return True
        except Exception as e:
            self._logger.error(f"Redis DELETE 操作失败: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if not self._redis_client:
            return False
        try:
            return bool(await self._redis_client.exists(key))
        except Exception as e:
            self._logger.error(f"Redis EXISTS 操作失败: {e}")
            return False

    # 连接管理方法
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected

    async def connect_async(self) -> None:
        """异步连接到 Redis"""
        if self._connected:
            return
        await self._connect_to_redis()

    async def disconnect_async(self) -> None:
        """异步断开 Redis 连接"""
        await self._stop()

    def get_status_info(self) -> Dict[str, Any]:
        """获取详细状态信息"""
        info = super().get_status_info()

        # 添加连接状态信息
        if self._connected:
            info['connection_status'] = 'connected'
            info['connection_info'] = {
                'host': self._redis_config.get('host') if self._redis_config else None,
                'port': self._redis_config.get('port') if self._redis_config else None,
                'db': self._redis_config.get('db') if self._redis_config else None
            }
        else:
            info['connection_status'] = 'disconnected'
            if self._connection_error:
                info['disconnect_reason'] = self._connection_error

        return info

    def _get_component_statistics(self) -> Dict[str, Any]:
        """获取缓存组件的统计信息"""
        stats = {
            "connected": self._connected,
            "host": self._redis_config.get('host') if self._redis_config else None,
            "port": self._redis_config.get('port') if self._redis_config else None,
            "db": self._redis_config.get('db') if self._redis_config else None
        }

        # 如果连接了，获取更多信息
        if self._connected and self._redis_client:
            try:
                # 这些需要异步获取，所以在同步方法中只返回基本信息
                if hasattr(self._redis_client, 'connection_pool'):
                    pool = self._redis_client.connection_pool
                    stats["pool_info"] = {
                        "created_connections": getattr(pool, 'created_connections', 0),
                        "max_connections": getattr(pool, 'max_connections', 0)
                    }
            except Exception:
                pass

        return stats

    @property
    def redis_client(self):
        """获取 Redis 客户端实例"""
        return self._redis_client


class MonitorComponent(AsyncComponent[EventSystemMonitor]):
    """监控组件 - 系统监控和指标收集"""

    def __init__(self):
        super().__init__("monitor", ComponentType.SUPPORTING, "监控器")
        self._event_engine = None

    def set_event_engine(self, event_engine: EventEngine):
        """设置事件引擎（用于依赖注入）"""
        self._event_engine = event_engine

    async def _initialize(self) -> None:
        """初始化监控器"""
        with error_context(self.name, "initialize"):
            if not self._event_engine:
                raise ComponentLifecycleError(
                    self.name, "initialize",
                    "Event engine not provided"
                )

            self._instance = EventSystemMonitor(self._event_engine)

    async def _start(self) -> None:
        """启动监控器"""
        with error_context(self.name, "start"):
            if self._instance:
                self._instance.start()

    async def _stop(self) -> None:
        """停止监控器"""
        with error_context(self.name, "stop"):
            if self._instance:
                self._instance.stop()

    def _health_check(self) -> bool:
        """检查监控器健康状态"""
        return self._instance and self._instance.is_running()

    def get_statistics(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        if self._instance:
            return self._instance.get_metrics()
        return {}

    def _get_component_statistics(self) -> Dict[str, Any]:
        """获取监控器的统计信息"""
        if not self._instance:
            return {}

        # 获取监控器的核心指标
        summary = self._instance.get_summary() if hasattr(self._instance, 'get_summary') else {}

        return {
            "monitoring_active": hasattr(self._instance, '_running') and self._instance._running,
            "events_monitored": len(summary.get('events', {})),
            "health_status": summary.get('health', {}).get('status', 'unknown'),
            "total_events": sum(
                metrics.get('total', 0)
                for metrics in summary.get('events', {}).values()
            ) if 'events' in summary else 0
        }


class GatewayComponent(AsyncComponent[Gateway]):
    """网关组件 - 外部交易接口"""

    def __init__(self):
        super().__init__("gateway", ComponentType.BUSINESS, "交易网关")
        self._gateway_type = "simulation"  # 默认使用模拟网关
        self._config = None

    async def _initialize(self) -> None:
        """初始化网关"""
        with error_context(self.name, "initialize"):
            # 从配置获取网关配置
            # 检查是否有 gateway 配置
            if hasattr(settings, 'gateway'):
                self._config = getattr(settings.gateway, self._gateway_type, {})
            else:
                # 使用默认的模拟网关配置
                self._config = {'type': 'simulation'}

            # 创建网关实例 - Gateway 只需要 engine 参数
            # 这里暂时传入 None，实际应该注入 EventEngine
            self._instance = Gateway(None)

            # 如果网关有初始化方法，调用它
            if hasattr(self._instance, 'initialize'):
                await self._instance.initialize()

    async def _start(self) -> None:
        """启动网关"""
        with error_context(self.name, "start"):
            if self._instance and hasattr(self._instance, 'connect'):
                # Gateway 的 connect 是同步方法
                self._instance.connect()

    async def _stop(self) -> None:
        """停止网关"""
        with error_context(self.name, "stop"):
            if self._instance:
                if hasattr(self._instance, 'close'):
                    # Gateway 使用 close 方法
                    self._instance.close()
                elif hasattr(self._instance, 'disconnect'):
                    self._instance.disconnect()

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """提供额外的状态信息"""
        return {
            "gateway_type": self._gateway_type,
            "connected": self._instance and getattr(self._instance, 'is_connected', lambda: False)()
        }

    def _health_check(self) -> bool:
        """检查网关健康状态"""
        if not self._instance:
            return False

        # 检查连接状态
        if hasattr(self._instance, 'is_connected'):
            return self._instance.is_connected()

        return True


class WebUIComponent(AsyncComponent):
    """WebUI组件 - Web管理界面"""

    def __init__(self):
        super().__init__("webui", ComponentType.INTERFACE, "Web界面")
        self._server = None
        self._frontend_process = None
        self._backend_port = settings.webui.backend_port
        self._frontend_port = settings.webui.frontend_port

    async def _initialize(self) -> None:
        """初始化WebUI"""
        with error_context(self.name, "initialize"):
            # WebUI的初始化在启动时进行
            pass

    async def _start(self) -> None:
        """启动WebUI服务"""
        with error_context(self.name, "start"):
            # WebUI 服务器现在由 MainEngine 的异步任务管理
            # 这里只记录启动信息
            self._logger.info(f"WebUI组件已准备就绪，后端端口: {self._backend_port}")

    async def _stop(self) -> None:
        """停止WebUI服务"""
        with error_context(self.name, "stop"):
            # 停止服务器的逻辑
            self._logger.info("停止WebUI服务")

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """提供额外的状态信息"""
        return {
            "backend_port": self._backend_port,
            "frontend_port": self._frontend_port,
            "backend_url": f"http://localhost:{self._backend_port}",
            "frontend_url": f"http://localhost:{self._frontend_port}"
        }
