"""
系统组件包装类

将现有的各个模块包装成标准化的组件，
便于组件管理器统一管理。
"""
import asyncio
from typing import Optional

from deepsearch.core.component_manager import Component, ComponentType, ComponentStatus
from deepsearch.event.engine import EventEngine
from deepsearch.gateway.gateway import Gateway
from deepsearch.messaging.bus import CompositeMessageBus
from deepsearch.monitoring import EventSystemMonitor


class EventEngineComponent(Component):
    """事件引擎组件"""

    def __init__(self, queue_size: int = 10000, max_workers: int = 32,
                 batch_size: int = 100):
        super().__init__("event_engine", ComponentType.INFRASTRUCTURE)
        self.queue_size = queue_size
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.engine: Optional[EventEngine] = None

    def initialize(self) -> None:
        """初始化事件引擎"""
        self._logger.debug("初始化事件引擎")
        self.engine = EventEngine(
            queue_size=self.queue_size,
            max_workers=self.max_workers,
            enable_batch_processing=True,
            batch_size=self.batch_size,
            batch_timeout=0.1
        )
        self._status = ComponentStatus.INITIALIZED
        self._logger.debug("事件引擎初始化完成")

    def start(self) -> None:
        """启动事件引擎"""
        if not self.engine:
            raise RuntimeError("Event engine not initialized")
        self.engine.start()
        self._status = ComponentStatus.RUNNING
        self._logger.debug("事件引擎已启动")

    def stop(self) -> None:
        """停止事件引擎"""
        if self.engine:
            self.engine.stop()
        self._status = ComponentStatus.STOPPED
        self._logger.debug("事件引擎已停止")

    def health_check(self) -> bool:
        """健康检查"""
        if not self.engine:
            return False
        return self.engine._running

    def get_instance(self) -> EventEngine:
        """获取事件引擎实例"""
        if not self.engine:
            raise RuntimeError("Event engine not initialized")
        return self.engine


class MessageBusComponent(Component):
    """消息总线组件"""

    def __init__(self):
        super().__init__("message_bus", ComponentType.INFRASTRUCTURE)
        self.bus: Optional[CompositeMessageBus] = None

    def initialize(self) -> None:
        """初始化消息总线"""
        self._logger.debug("初始化消息总线")

        # 从配置加载消息总线
        from deepsearch.config import get_config
        from deepsearch.messaging.factory import MessageBusFactory

        config = get_config()
        bus_config = config.message_bus

        # 创建消息总线实例
        buses = {}
        for bus_name, bus_cfg in bus_config.buses.items():
            if bus_cfg.enabled:
                try:
                    bus = MessageBusFactory.create(bus_cfg.type, bus_cfg.config)
                    buses[bus_name] = bus
                    self._logger.debug(f"创建消息总线: {bus_name} ({bus_cfg.type})")
                except Exception as e:
                    self._logger.warning(f"创建消息总线 {bus_name} 失败: {e}")

        # 创建复合消息总线
        self.bus = CompositeMessageBus(buses=buses, routes=bus_config.routes)
        self._status = ComponentStatus.INITIALIZED
        self._logger.debug("消息总线初始化完成")

    def start(self) -> None:
        """启动消息总线"""
        if not self.bus:
            raise RuntimeError("Message bus not initialized")
        self.bus.start()
        self._status = ComponentStatus.RUNNING
        self._logger.debug("消息总线已启动")

    def stop(self) -> None:
        """停止消息总线"""
        if self.bus:
            self.bus.stop()
        self._status = ComponentStatus.STOPPED
        self._logger.debug("消息总线已停止")

    def health_check(self) -> bool:
        """健康检查"""
        return self._status == ComponentStatus.RUNNING

    def get_instance(self) -> CompositeMessageBus:
        """获取消息总线实例"""
        if not self.bus:
            raise RuntimeError("Message bus not initialized")
        return self.bus


class MonitorComponent(Component):
    """监控组件"""

    def __init__(self, event_engine: EventEngine, message_bus: Optional[CompositeMessageBus] = None):
        super().__init__("monitor", ComponentType.INFRASTRUCTURE)
        self.event_engine = event_engine
        self.message_bus = message_bus
        self.monitor: Optional[EventSystemMonitor] = None

    def initialize(self) -> None:
        """初始化监控器"""
        self._logger.debug("初始化系统监控")
        self.monitor = EventSystemMonitor(self.event_engine, self.message_bus)
        self._status = ComponentStatus.INITIALIZED
        self._logger.debug("系统监控初始化完成")

    def start(self) -> None:
        """启动监控器"""
        if not self.monitor:
            raise RuntimeError("Monitor not initialized")
        self.monitor.start()
        self._status = ComponentStatus.RUNNING
        self._logger.debug("系统监控已启动")

    def stop(self) -> None:
        """停止监控器"""
        if self.monitor:
            self.monitor.stop()
        self._status = ComponentStatus.STOPPED
        self._logger.debug("系统监控已停止")

    def health_check(self) -> bool:
        """健康检查"""
        if not self.monitor:
            return False
        return hasattr(self.monitor, '_monitoring') and self.monitor._monitoring

    def get_instance(self) -> EventSystemMonitor:
        """获取监控器实例"""
        if not self.monitor:
            raise RuntimeError("Monitor not initialized")
        return self.monitor


class GatewayComponent(Component):
    """网关组件"""

    def __init__(self, event_engine: EventEngine):
        super().__init__("gateway", ComponentType.BUSINESS)
        self.event_engine = event_engine
        self.gateway: Optional[Gateway] = None

    def initialize(self) -> None:
        """初始化网关"""
        self._logger.debug("初始化网关")
        self.gateway = Gateway(self.event_engine)
        self._status = ComponentStatus.INITIALIZED
        self._logger.debug("网关初始化完成")

    def start(self) -> None:
        """启动网关"""
        if not self.gateway:
            raise RuntimeError("Gateway not initialized")

        # 如果网关已经被关闭，需要重新创建实例
        if hasattr(self.gateway, '_shutdown') and self.gateway._shutdown:
            self._logger.debug("网关需要重新创建")
            self.gateway = Gateway(self.event_engine)
        
        self.gateway.start()
        self._status = ComponentStatus.RUNNING
        self._logger.debug("网关已启动")

    def stop(self) -> None:
        """停止网关"""
        if self.gateway:
            self.gateway.stop()
        self._status = ComponentStatus.STOPPED
        self._logger.debug("网关已停止")

    def health_check(self) -> bool:
        """健康检查"""
        if not self.gateway:
            return False
        # 检查网关状态和连接状态
        return (hasattr(self.gateway, '_connected') and self.gateway._connected and
                not getattr(self.gateway, '_shutdown', False))

    def get_instance(self) -> Gateway:
        """获取网关实例"""
        if not self.gateway:
            raise RuntimeError("Gateway not initialized")
        return self.gateway


class DatabaseComponent(Component):
    """数据库组件 - 管理 PostgreSQL + TimescaleDB 连接"""

    def __init__(self):
        super().__init__("database", ComponentType.INFRASTRUCTURE)

        # 数据库引擎
        self._engine: Optional['AsyncEngine'] = None
        self._session_factory: Optional['sessionmaker'] = None

        # 健康检查
        self._health_check_task: Optional['asyncio.Task'] = None
        self._last_health_check: Optional['datetime'] = None
        self._is_timescale_enabled = False

    async def initialize_async(self) -> None:
        """异步初始化数据库连接"""
        from datetime import datetime
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import text

        if self.status != ComponentStatus.UNINITIALIZED:
            raise RuntimeError(f"{self.name} has already been initialized")

        try:
            self._logger.info(f"正在初始化数据库组件...")

            # 获取数据库配置
            from deepsearch.config import settings
            db_config = settings.database.main
            db_url = db_config.get_url()

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

            # 测试连接
            await self._test_connection()

            # 检查并安装 TimescaleDB
            if db_config.type == "postgresql":
                await self._setup_timescaledb()

            self._status = ComponentStatus.INITIALIZED
            self._logger.info(f"✓ 数据库组件初始化成功")

        except Exception as e:
            self._status = ComponentStatus.ERROR
            self._logger.error(f"数据库组件初始化失败: {e}")
            raise RuntimeError(f"Failed to initialize database: {e}")

    def initialize(self) -> None:
        """同步初始化接口（为兼容组件管理器）"""
        import asyncio
        try:
            asyncio.run(self.initialize_async())
        except RuntimeError:
            # 如果已经在事件循环中，使用现有循环
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.initialize_async())

    async def _test_connection(self) -> None:
        """测试数据库连接"""
        from sqlalchemy import text

        async with self._engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            if not result:
                raise RuntimeError("数据库连接测试失败")

            # 获取数据库版本
            version_result = await conn.execute(text("SELECT version()"))
            version = version_result.scalar()
            self._logger.info(f"数据库版本: {version}")

    async def _setup_timescaledb(self) -> None:
        """安装和配置 TimescaleDB"""
        from sqlalchemy import text

        try:
            async with self._engine.begin() as conn:
                # 检查 TimescaleDB 是否已安装
                check_sql = """
                            SELECT EXISTS (SELECT 1
                                           FROM pg_extension
                                           WHERE extname = 'timescaledb'); \
                            """
                result = await conn.execute(text(check_sql))
                exists = result.scalar()

                if not exists:
                    self._logger.info("正在安装 TimescaleDB 扩展...")
                    try:
                        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
                        self._logger.info("✓ TimescaleDB 扩展安装成功")
                    except Exception as e:
                        self._logger.warning(f"TimescaleDB 安装失败: {e}")
                        self._logger.warning("将继续使用普通 PostgreSQL 功能")
                        return

                self._is_timescale_enabled = True

                # 获取 TimescaleDB 版本
                version_sql = "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"
                result = await conn.execute(text(version_sql))
                version = result.scalar()
                self._logger.info(f"✓ TimescaleDB 版本: {version}")

        except Exception as e:
            self._logger.warning(f"TimescaleDB 设置失败: {e}")
            self._is_timescale_enabled = False

    async def start_async(self) -> None:
        """异步启动数据库组件"""
        import asyncio

        if self.status != ComponentStatus.INITIALIZED:
            raise RuntimeError(f"{self.name} is not initialized")

        try:
            self._logger.info(f"正在启动数据库组件...")

            # 启动健康检查任务
            self._health_check_task = asyncio.create_task(self._health_check_loop())

            self._status = ComponentStatus.RUNNING
            self._logger.info(f"✓ 数据库组件启动成功")

        except Exception as e:
            self._status = ComponentStatus.ERROR
            self._logger.error(f"数据库组件启动失败: {e}")
            raise RuntimeError(f"Failed to start database: {e}")

    def start(self) -> None:
        """同步启动接口（为兼容组件管理器）"""
        import asyncio
        try:
            asyncio.run(self.start_async())
        except RuntimeError:
            # 如果已经在事件循环中，使用现有循环
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.start_async())

    async def stop_async(self) -> None:
        """异步停止数据库组件"""
        if self.status != ComponentStatus.RUNNING:
            return

        try:
            self._logger.info(f"正在停止数据库组件...")

            # 停止健康检查
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass

            # 关闭数据库连接
            if self._engine:
                # Properly dispose of the engine with timeout
                try:
                    await asyncio.wait_for(self._engine.dispose(), timeout=5.0)
                except asyncio.TimeoutError:
                    self._logger.warning("数据库连接关闭超时")
                except Exception as e:
                    self._logger.warning(f"关闭数据库连接时出现警告: {e}")

            self._status = ComponentStatus.STOPPED
            self._logger.info(f"✓ 数据库组件已停止")

        except Exception as e:
            self._logger.error(f"数据库组件停止失败: {e}")
            raise RuntimeError(f"Failed to stop database: {e}")

    def stop(self) -> None:
        """同步停止接口（为兼容组件管理器）"""
        import asyncio

        if self.status != ComponentStatus.RUNNING:
            return

        try:
            asyncio.run(self.stop_async())
        except RuntimeError:
            # 如果已经在事件循环中，使用现有循环
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.stop_async())

    async def _health_check_loop(self) -> None:
        """健康检查循环"""
        import asyncio

        while True:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次
                await self.health_check()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"健康检查失败: {e}")

    async def health_check(self) -> dict:
        """执行健康检查"""
        from datetime import datetime
        from sqlalchemy import text

        try:
            async with self._engine.begin() as conn:
                # 基本连接测试
                await conn.execute(text("SELECT 1"))

                # 获取连接池状态
                try:
                    pool = self._engine.pool
                    pool_status = {
                        "size": pool.size(),
                        "checked_in": pool.checked_in_connections,
                        "overflow": pool.overflow(),
                        "total": pool.size() + pool.overflow()
                    }
                except:
                    pool_status = {"status": "unavailable"}

                # 检查 TimescaleDB 状态
                timescale_status = {
                    "enabled": self._is_timescale_enabled,
                    "healthy": True
                }

                if self._is_timescale_enabled:
                    result = await conn.execute(text(
                        "SELECT COUNT(*) FROM timescaledb_information.hypertables"
                    ))
                    hypertable_count = result.scalar()
                    timescale_status["hypertable_count"] = hypertable_count

                self._last_health_check = datetime.now()

                return {
                    "status": "healthy",
                    "last_check": self._last_health_check.isoformat(),
                    "connection_pool": pool_status,
                    "timescaledb": timescale_status
                }

        except Exception as e:
            from datetime import datetime
            return {
                "status": "unhealthy",
                "error": str(e),
                "last_check": datetime.now().isoformat()
            }

    def get_status_info(self) -> dict:
        """获取组件状态信息"""
        info = {
            "name": self.name,
            "type": self.component_type.value,
            "status": self.status.value,
        }

        # 添加数据库特定信息
        if self._engine:
            try:
                pool = self._engine.pool
                info["connection_pool"] = {
                    "size": pool.size() if hasattr(pool, 'size') else 'N/A',
                    "overflow": pool.overflow() if hasattr(pool, 'overflow') else 'N/A'
                }
            except:
                info["connection_pool"] = {"status": "unavailable"}

        info["timescaledb_enabled"] = self._is_timescale_enabled
        info["last_health_check"] = (
            self._last_health_check.isoformat()
            if self._last_health_check else None
        )

        return info

    @property
    def engine(self):
        """获取数据库引擎"""
        if not self._engine:
            raise RuntimeError("数据库引擎未初始化")
        return self._engine

    @property
    def session_factory(self):
        """获取会话工厂"""
        if not self._session_factory:
            raise RuntimeError("会话工厂未初始化")
        return self._session_factory

    def get_session(self):
        """获取新的数据库会话"""
        return self.session_factory()

    @property
    def is_timescale_enabled(self) -> bool:
        """TimescaleDB 是否启用"""
        return self._is_timescale_enabled
