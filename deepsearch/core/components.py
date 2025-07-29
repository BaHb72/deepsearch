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
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        import warnings

        # 忽略 asyncpg 的协程警告
        warnings.filterwarnings("ignore", message="coroutine.*was never awaited")

        if self.status != ComponentStatus.UNINITIALIZED:
            raise RuntimeError(f"{self.name} has already been initialized")

        try:
            self._logger.info(f"正在初始化数据库组件...")

            # 获取数据库配置
            from deepsearch.config import settings
            db_config = settings.database.main

            # 调试信息
            self._logger.debug(f"数据库配置: type={db_config.type}, host={db_config.host}, "
                               f"port={db_config.port}, database={db_config.database}, "
                               f"username={db_config.username}, has_password={bool(db_config.password)}, "
                               f"auto_connect={db_config.auto_connect}")

            # 检查是否应该自动连接
            if not db_config.auto_connect:
                self._logger.info("数据库组件已初始化（未连接）- auto_connect=false")
                self._status = ComponentStatus.INITIALIZED
                self._engine = None
                self._session_factory = None
                return

            # 检查密码是否为空或是占位符
            if db_config.type != "sqlite" and (not db_config.password or db_config.password == "***"):
                self._logger.warning("数据库密码为空或无效，跳过连接。请在配置页面设置数据库密码。")
                self._status = ComponentStatus.INITIALIZED
                self._engine = None
                self._session_factory = None
                return
            
            db_url = db_config.get_url()
            self._logger.debug(
                f"构建的数据库URL: {db_url.replace(db_config.password, '***') if db_config.password else db_url}")

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
            error_msg = self._get_friendly_error_message(e)
            self._logger.error(f"数据库组件初始化失败: {error_msg}")

            # 提供解决方案建议
            if "connection was closed" in str(e) or "ConnectionDoesNotExistError" in str(e):
                self._logger.info("解决方案：")
                self._logger.info("1. 检查 PostgreSQL 服务是否正在运行")
                self._logger.info("2. 确认数据库配置信息是否正确（主机、端口、用户名、密码）")
                self._logger.info("3. 使用命令测试连接: psql -h localhost -U bahb -d deepsearch")
            elif "password authentication failed" in str(e):
                self._logger.info("解决方案：请检查数据库密码是否正确")
            elif "database" in str(e) and "does not exist" in str(e):
                self._logger.info("解决方案：请先创建数据库 'deepsearch'")

            raise RuntimeError(f"Failed to initialize database: {error_msg}")

    def initialize(self) -> None:
        """同步初始化接口（为兼容组件管理器）"""
        import asyncio
        try:
            # 尝试获取当前运行的事件循环
            loop = asyncio.get_running_loop()
            # 如果在异步上下文中，创建任务
            task = loop.create_task(self.initialize_async())
            # 注意：这里不会等待任务完成，因为我们已经在事件循环中
        except RuntimeError:
            # 不在异步上下文中，创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.initialize_async())
            finally:
                # 清理事件循环
                loop.close()
                asyncio.set_event_loop(None)

    async def _test_connection(self) -> None:
        """测试数据库连接"""
        from sqlalchemy import text

        # 使用 connect() 而不是 begin() 来避免警告
        async with self._engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            if not result:
                raise RuntimeError("数据库连接测试失败")

            # 获取数据库版本
            version_result = await conn.execute(text("SELECT version()"))
            version = version_result.scalar()
            self._logger.info(f"数据库版本: {version}")

            # 显式提交以确保连接正确关闭
            await conn.commit()

    async def _setup_timescaledb(self) -> None:
        """检查 TimescaleDB 是否可用"""
        from sqlalchemy import text

        try:
            async with self._engine.connect() as conn:
                # 检查 TimescaleDB 是否已安装
                check_sql = """
                            SELECT EXISTS (SELECT 1
                                           FROM pg_extension
                                           WHERE extname = 'timescaledb');
                            """
                result = await conn.execute(text(check_sql))
                exists = result.scalar()

                if exists:
                    self._is_timescale_enabled = True
                    # 获取 TimescaleDB 版本
                    version_sql = "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"
                    result = await conn.execute(text(version_sql))
                    version = result.scalar()
                    self._logger.info(f"✓ TimescaleDB 已启用，版本: {version}")
                else:
                    self._is_timescale_enabled = False
                    self._logger.info("TimescaleDB 未安装，使用标准 PostgreSQL 功能")

                await conn.commit()

        except Exception as e:
            self._logger.debug(f"检查 TimescaleDB 时出错: {e}")
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
                    # 直接处置引擎，这会关闭所有连接
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
                except (AttributeError, Exception) as e:
                    pool_status = {"status": "unavailable", "error": str(e)}

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

        # 添加数据库连接状态
        info["connection_status"] = "connected" if self._engine else "disconnected"
        
        # 添加数据库特定信息
        if self._engine:
            try:
                pool = self._engine.pool
                info["connection_pool"] = {
                    "size": pool.size() if hasattr(pool, 'size') else 'N/A',
                    "overflow": pool.overflow() if hasattr(pool, 'overflow') else 'N/A'
                }
            except (AttributeError, Exception) as e:
                info["connection_pool"] = {"status": "unavailable", "error": str(e)}
        else:
            info["connection_pool"] = {"status": "not connected"}

        info["timescaledb_enabled"] = self._is_timescale_enabled
        info["last_health_check"] = (
            self._last_health_check.isoformat()
            if self._last_health_check else None
        )

        # 如果未连接，添加原因说明
        if not self._engine:
            from deepsearch.config import settings
            db_config = settings.database.main
            if not db_config.auto_connect:
                info["disconnect_reason"] = "自动连接已禁用"
            elif not db_config.password and db_config.type != "sqlite":
                info["disconnect_reason"] = "数据库密码未设置"

        return info

    @property
    def engine(self):
        """获取数据库引擎"""
        if not self._engine:
            raise RuntimeError("数据库未连接。请先在配置页面设置数据库连接信息。")
        return self._engine

    @property
    def session_factory(self):
        """获取会话工厂"""
        if not self._session_factory:
            raise RuntimeError("数据库未连接。请先在配置页面设置数据库连接信息。")
        return self._session_factory

    def get_session(self):
        """获取新的数据库会话"""
        if not self._session_factory:
            raise RuntimeError("数据库未连接。请先在配置页面设置数据库连接信息。")
        return self.session_factory()

    @property
    def is_timescale_enabled(self) -> bool:
        """TimescaleDB 是否启用"""
        return self._is_timescale_enabled

    def _get_friendly_error_message(self, error: Exception) -> str:
        """将技术错误转换为友好的错误信息"""
        error_str = str(error)

        if "connection was closed" in error_str or "ConnectionDoesNotExistError" in error_str:
            return "无法连接到数据库服务器"
        elif "password authentication failed" in error_str:
            return "数据库密码验证失败"
        elif "database" in error_str and "does not exist" in error_str:
            return "数据库不存在"
        elif "Connection refused" in error_str:
            return "数据库服务器拒绝连接（可能未启动）"
        elif "timeout" in error_str.lower():
            return "数据库连接超时"
        else:
            return error_str

    async def connect_async(self) -> None:
        """手动连接数据库"""
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker

        if self._engine is not None:
            self._logger.warning("数据库已经连接")
            return

        try:
            self._logger.info("正在手动连接数据库...")

            # 获取数据库配置
            from deepsearch.config import settings
            db_config = settings.database.main

            # 检查密码是否为空
            if not db_config.password and db_config.type != "sqlite":
                raise RuntimeError("数据库密码未设置")

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

            self._logger.info("✓ 数据库连接成功")

        except Exception as e:
            error_msg = self._get_friendly_error_message(e)
            self._logger.error(f"数据库连接失败: {error_msg}")
            # 清理资源
            if self._engine:
                await self._engine.dispose()
                self._engine = None
                self._session_factory = None
            raise RuntimeError(f"数据库连接失败: {error_msg}")

    def connect(self) -> None:
        """同步连接接口"""
        import asyncio
        try:
            asyncio.run(self.connect_async())
        except RuntimeError:
            # 如果已经在事件循环中，使用现有循环
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.connect_async())

    async def disconnect_async(self) -> None:
        """断开数据库连接"""
        if self._engine is None:
            self._logger.warning("数据库未连接")
            return

        try:
            self._logger.info("正在断开数据库连接...")
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._logger.info("✓ 数据库连接已断开")
        except Exception as e:
            self._logger.error(f"断开数据库连接失败: {e}")
            raise

    def disconnect(self) -> None:
        """同步断开连接接口"""
        import asyncio
        if self._engine is None:
            return

        try:
            asyncio.run(self.disconnect_async())
        except RuntimeError:
            # 如果已经在事件循环中，使用现有循环
            loop = asyncio.get_event_loop()
            loop.run_until_complete(self.disconnect_async())

    def is_connected(self) -> bool:
        """检查数据库是否已连接"""
        return self._engine is not None
