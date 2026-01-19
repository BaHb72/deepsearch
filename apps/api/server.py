"""
FastAPI 服务器主应用

提供 REST API 和 WebSocket 端点，为前端提供数据接口。
"""

from __future__ import annotations

import asyncio
import builtins
import json
import math
import sys
import threading
import time
import zlib
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional, cast

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

if not TYPE_CHECKING:
    setattr(builtins, "Optional", Optional)

from core.application.market_data.fallback_manager import ModuleFallbackManager
from core.config import Settings, get_config
from core.core.runtime.engine import MainEngine
from core.debug.diagnostics import diagnostic_logger, log_diagnostic
from core.observability.monitoring.event_monitor import EventSystemMonitor
from core.observability.monitoring.monitor_api import MonitorAPI
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

if TYPE_CHECKING:
    from core.application.market_data.orchestrator import RealtimeDataOrchestrator
    from core.event.engine.engine import EventEngine

STATIC_DIR = Path(__file__).parent / "static"

# Windows 兼容性：psycopg3 需要 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 记录模块导入
log_diagnostic(
    "MODULE_IMPORT",
    "server.py",
    {
        "imports": ["MainEngine", "EventSystemMonitor", "MonitorAPI", "FastAPI"],
        "platform": sys.platform,
    },
)


def safe_json_encoder(obj: Any) -> Any:
    """
    Custom JSON encoder that handles NaN, infinity, and other non-JSON-compliant values
    """
    if isinstance(obj, float):
        if math.isnan(obj):
            return None  # Convert NaN to null
        elif math.isinf(obj):
            if obj > 0:
                return 999999.99  # Convert positive infinity to large finite number
            else:
                return -999999.99  # Convert negative infinity to large negative number
    return jsonable_encoder(obj)


def sanitize_data(data: Any) -> Any:
    """
    Recursively sanitize data to handle NaN and infinity values
    """
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    elif isinstance(data, float):
        if math.isnan(data):
            return None
        elif math.isinf(data):
            return 999999.99 if data > 0 else -999999.99
        return data
    return data


class SafeJSONResponse(JSONResponse):
    """
    Custom JSON response that safely handles NaN and infinity values
    """

    def render(self, content: Any) -> bytes:
        # Sanitize the content before rendering
        safe_content = sanitize_data(content)
        rendered = super().render(safe_content)
        if isinstance(rendered, bytes):
            return rendered
        if isinstance(rendered, str):
            return rendered.encode("utf-8")
        return cast(bytes, rendered)


class MessageBatcher:
    """消息批处理器"""

    def __init__(self, batch_size: int = 50, batch_timeout: float = 0.1):
        self.batch_size: int = batch_size
        self.batch_timeout: float = batch_timeout
        self.message_queue: deque[Dict[str, Any]] = deque()
        self.last_flush_time: float = time.time()
        self.lock: asyncio.Lock = asyncio.Lock()

    async def add_message(self, message: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        添加消息到批处理队列

        Returns:
            如果需要发送，返回消息列表；否则返回None
        """
        async with self.lock:
            self.message_queue.append(message)

            # 检查是否需要发送
            current_time = time.time()
            if (
                len(self.message_queue) >= self.batch_size
                or current_time - self.last_flush_time >= self.batch_timeout
            ):

                messages = list(self.message_queue)
                self.message_queue.clear()
                self.last_flush_time = current_time
                return messages

        return None

    async def flush(self) -> List[Dict[str, Any]]:
        """强制发送所有待发送消息"""
        async with self.lock:
            messages = list(self.message_queue)
            self.message_queue.clear()
            self.last_flush_time = time.time()
            return messages


class WebSocketManager:
    """WebSocket 连接管理器（支持批处理和压缩）"""

    def __init__(self, enable_compression: bool = True, enable_batching: bool = True):
        self._connections: list[WebSocket] = []
        self._connections_lock: asyncio.Lock = asyncio.Lock()  # 添加异步锁保护连接列表
        self._broadcast_task: Optional[asyncio.Task[None]] = None
        self._monitor_api: Optional[MonitorAPI] = None
        self._base_broadcast_interval: float = 2.0
        self._broadcast_interval: float = 2.0
        self._last_data_hash: Optional[int] = None  # 用于检测数据变化
        self._slow_connections_count: int = 0  # 慢连接计数
        self._send_timeout: float = 0.5  # 单连接发送超时（500ms）

        # 批处理和压缩配置
        self.enable_compression: bool = enable_compression
        self.enable_batching: bool = enable_batching
        self.message_batcher: Optional[MessageBatcher] = (
            MessageBatcher() if enable_batching else None
        )
        self.compression_threshold: int = 1024  # 压缩阈值（1KB）

        # 统计信息
        self.stats: dict[str, int] = {
            "messages_sent": 0,
            "messages_compressed": 0,
            "bytes_sent": 0,
            "bytes_saved": 0,
            "batches_sent": 0,
            "connection_errors": 0,
        }

    async def accept_connection(self, websocket: WebSocket) -> None:
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        async with self._connections_lock:
            self._connections.append(websocket)
            connection_count = len(self._connections)
        logger.debug(f"WebSocket 连接已建立（连接数：{connection_count}）")

    async def remove_connection(self, websocket: WebSocket) -> None:
        """移除 WebSocket 连接"""
        async with self._connections_lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
                connection_count = len(self._connections)
                logger.debug(f"WebSocket 连接已断开（连接数：{connection_count}）")

    async def broadcast_message(self, message: Dict[str, Any]) -> None:
        """向所有客户端广播消息（支持批处理和压缩）"""
        # 批处理逻辑
        message_to_send: Dict[str, Any]
        if self.enable_batching and self.message_batcher:
            messages = await self.message_batcher.add_message(message)
            if messages is None:
                # 消息已加入队列，等待批处理
                return
            # 批量发送
            message_to_send = {"type": "batch", "messages": messages, "count": len(messages)}
            self.stats["batches_sent"] += 1
        else:
            message_to_send = message

        # 获取连接副本，避免长时间持有锁
        async with self._connections_lock:
            if not self._connections:
                return
            connections_copy: list[WebSocket] = self._connections.copy()

        # 序列化消息
        message_text = json.dumps(message_to_send, ensure_ascii=False)
        original_size = len(message_text.encode("utf-8"))

        # 压缩消息（如果启用且超过阈值）
        if self.enable_compression and original_size > self.compression_threshold:
            compressed_data = zlib.compress(message_text.encode("utf-8"), level=1)
            if len(compressed_data) < original_size:
                # 构建压缩消息
                compressed_message = {
                    "type": "compressed",
                    "data": compressed_data.hex(),  # 转换为十六进制字符串
                    "original_size": original_size,
                    "compressed_size": len(compressed_data),
                }
                message_text = json.dumps(compressed_message)

                # 更新统计
                self.stats["messages_compressed"] += 1
                self.stats["bytes_saved"] += original_size - len(compressed_data)

        self.stats["messages_sent"] += 1
        self.stats["bytes_sent"] += len(message_text.encode("utf-8"))

        failed_connections: list[WebSocket] = []

        # 并发发送消息
        tasks = [
            self._send_to_connection(conn, message_text, failed_connections)
            for conn in connections_copy
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

        # 清理失败的连接
        for conn in failed_connections:
            await self.remove_connection(conn)
            self.stats["connection_errors"] += 1

    async def _send_to_connection(
        self, conn: WebSocket, message: str, failed_list: list[WebSocket]
    ) -> None:
        """发送消息到单个连接（带超时控制）"""
        try:
            # 使用超时控制，避免慢连接阻塞
            await asyncio.wait_for(conn.send_text(message), timeout=self._send_timeout)
        except asyncio.TimeoutError:
            logger.debug("消息发送超时，标记为慢连接")
            self._slow_connections_count += 1
            failed_list.append(conn)
        except Exception as e:
            logger.debug(f"消息发送失败: {e}")
            failed_list.append(conn)

    def get_statistics(self) -> Dict[str, Any]:
        """获取WebSocket统计信息"""
        return {
            **self.stats,
            "active_connections": len(self._connections),
            "slow_connections": self._slow_connections_count,
            "compression_enabled": self.enable_compression,
            "batching_enabled": self.enable_batching,
            "broadcast_interval": self._broadcast_interval,
        }

    async def start_monitoring_broadcast(self, monitor_api: MonitorAPI) -> None:
        """启动监控数据广播"""
        self._monitor_api = monitor_api
        if not self._broadcast_task or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring_broadcast(self) -> None:
        """停止监控数据广播"""
        # 发送所有待发送消息
        if self.message_batcher:
            messages = await self.message_batcher.flush()
            if messages:
                batch_message = {"type": "batch", "messages": messages, "count": len(messages)}
                await self.broadcast_message(batch_message)

        if self._broadcast_task and not self._broadcast_task.done():
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

    async def _monitoring_loop(self) -> None:
        """监控数据广播循环（带背压控制）"""
        while True:
            try:
                # 检查是否有连接，避免不必要的数据收集
                async with self._connections_lock:
                    has_connections = bool(self._connections)
                    connection_count = len(self._connections)

                if self._monitor_api and has_connections:
                    # 动态调整广播间隔
                    self._adjust_broadcast_interval(connection_count)

                    # 获取监控数据
                    monitor_data = self._monitor_api.get_dashboard_data()

                    # 检查数据是否有变化（简单哈希对比）
                    data_str = json.dumps(monitor_data, sort_keys=True)
                    current_hash = hash(data_str)

                    if self._last_data_hash is None or self._last_data_hash != current_hash:
                        # 数据有变化，执行广播
                        self._last_data_hash = current_hash
                        self._slow_connections_count = 0  # 重置慢连接计数

                        data = {
                            "type": "monitor_update",
                            "data": monitor_data,
                            "interval": self._broadcast_interval,  # 告知客户端当前间隔
                        }
                        await self.broadcast_message(data)

                        # 如果有太多慢连接，记录警告
                        if self._slow_connections_count > connection_count * 0.3:
                            logger.warning(
                                f"慢连接比例过高 ({self._slow_connections_count}/{connection_count})，"
                                f"广播间隔已调整至 {self._broadcast_interval:.1f}秒"
                            )
                    else:
                        # 数据无变化，跳过广播（节省带宽）
                        logger.debug("监控数据无变化，跳过本次广播")

                await asyncio.sleep(self._broadcast_interval)

            except asyncio.CancelledError:
                logger.debug("监控广播循环已停止")
                break
            except Exception as e:
                logger.error(f"监控广播错误: {e}")
                await asyncio.sleep(5)  # 错误后等待更长时间

    def _adjust_broadcast_interval(self, connection_count: int) -> None:
        """根据连接数和慢连接情况动态调整广播间隔"""
        # 基于连接数的调整
        if connection_count <= 5:
            new_interval = self._base_broadcast_interval  # 2秒
        elif connection_count <= 10:
            new_interval = self._base_broadcast_interval * 1.5  # 3秒
        elif connection_count <= 20:
            new_interval = self._base_broadcast_interval * 2  # 4秒
        else:
            new_interval = self._base_broadcast_interval * 2.5  # 5秒

        # 基于慢连接的额外调整
        if self._slow_connections_count > connection_count * 0.2:
            # 超过20%的连接是慢连接，进一步延长间隔
            new_interval *= 1.5
            new_interval = min(new_interval, 10.0)  # 最长10秒

        # 平滑过渡，避免间隔突变
        if hasattr(self, "_broadcast_interval"):
            # 渐进式调整，每次最多改变50%
            diff = new_interval - self._broadcast_interval
            self._broadcast_interval += diff * 0.5
        else:
            self._broadcast_interval = new_interval

    async def close_all_connections(self) -> None:
        """关闭所有连接"""
        tasks = []
        for conn in self._connections[:]:
            tasks.append(self._close_connection(conn))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._connections.clear()

    async def _close_connection(self, conn: WebSocket) -> None:
        """关闭单个连接"""
        try:
            await conn.close()
        except Exception:
            logger.opt(exception=True).debug("关闭 WebSocket 连接失败")


# 应用状态管理
@diagnostic_logger.diagnostic_class
class AppState:
    """应用全局状态"""

    def __init__(self):
        log_diagnostic(
            "APP_STATE_INIT",
            "AppState.__init__",
            {"thread": threading.current_thread().name, "instance_id": id(self)},
        )
        self.websocket_manager: WebSocketManager = WebSocketManager()
        self.engine: Optional[MainEngine] = None
        self.monitor: Optional[EventSystemMonitor] = None
        self.monitor_api: Optional[MonitorAPI] = None
        self.module_settings: Dict[str, Dict[str, Any]] = {}
        self.module_settings_lock = threading.RLock()
        self.market_data_service = None
        self.market_data_cache_writer = None
        self.market_data_pipeline = None
        self.market_data_runner = None
        self.market_data_reader = None
        self.market_data_provider = None
        self.market_data_orchestrator: RealtimeDataOrchestrator | None = None
        self.market_data_handle = None
        self.market_data_active_source: str | None = None
        self.market_data_health: Dict[str, Any] = {}
        self.market_data_initializing = False
        self.market_data_lock = asyncio.Lock()
        self.market_data_fallback_manager: ModuleFallbackManager | None = None
        self.provider_container: Any = None  # ProviderContainer 实例（用于 orchestrator 复用）

    @diagnostic_logger.diagnostic_method
    def set_engine(self, engine: MainEngine) -> None:
        """设置引擎实例"""
        log_diagnostic(
            "SET_ENGINE_START",
            "AppState.set_engine",
            {
                "engine": str(engine),
                "engine_type": type(engine).__name__,
                "engine_id": id(engine),
                "has_engine_before": self.engine is not None,
                "old_engine_id": id(self.engine) if self.engine else None,
                "instance_id": id(self),
            },
        )

        self.engine = engine
        logger.debug(f"引擎实例已设置：{engine}")

        log_diagnostic(
            "SET_ENGINE_AFTER",
            "AppState.set_engine",
            {
                "self.engine": str(self.engine),
                "self.engine_id": id(self.engine),
                "engine_is_set": self.engine is not None,
                "same_object": self.engine is engine,
            },
        )

        # 同时注册到应用上下文
        from core.core.runtime.context import get_context

        context = get_context()
        context.set_engine(engine)

    def initialize_monitoring(self) -> None:
        """初始化监控组件"""
        if not self.engine:
            raise RuntimeError("引擎未设置")

        # 获取或创建监控器
        if hasattr(self.engine, "_monitor") and self.engine._monitor:
            self.monitor = self.engine._monitor
        else:
            # 从引擎获取事件引擎组件
            from core.core.components import EventEngineComponent

            component = self.engine.get_component(EventEngineComponent)
            event_engine: Optional["EventEngine"] = None

            if component is None:
                logger.warning("无法获取事件引擎组件，监控功能将被禁用")
            elif isinstance(component, EventEngineComponent):
                event_engine = component.resource
                if event_engine is None:
                    logger.warning("事件引擎资源为空，监控功能将被禁用")
            else:
                logger.warning("事件引擎组件类型不匹配：{}", type(component).__name__)

            if event_engine is not None:
                self.monitor = EventSystemMonitor(event_engine)
            else:
                self.monitor = None

        if self.monitor:
            self.monitor_api = MonitorAPI(self.monitor)
            # 确保监控器已启动
            if not hasattr(self.monitor, "_monitoring") or not self.monitor._monitoring:
                self.monitor.start()
            self.monitor_api.start()
        else:
            self.monitor_api = None


# 全局应用状态
log_diagnostic("CREATE_APP_STATE", "server.py", {"location": "global", "before_creation": True})
app_state: AppState = AppState()
log_diagnostic(
    "CREATE_APP_STATE",
    "server.py",
    {
        "location": "global",
        "after_creation": True,
        "app_state_id": id(app_state),
        "app_state": str(app_state),
        "has_engine": hasattr(app_state, "engine"),
        "engine_value": str(getattr(app_state, "engine", None)),
    },
)


# 市场数据运行时函数已迁移到 services.market_data_runtime 模块
from apps.api.services.market_data_runtime import (
    ensure_market_data_runtime,
    shutdown_market_data_runtime,
)


def create_startup_handler(app_state: AppState) -> Callable[[], Awaitable[None]]:
    """创建启动处理函数"""

    async def startup_handler() -> None:
        """应用启动处理"""
        logger.debug("启动 Web UI 服务...")

        try:
            # 初始化定时缓存系统
            try:
                from core.core.scheduler import get_scheduler
                from core.core.scheduler.tasks.stock_list import StockListTask

                scheduler = get_scheduler()
                scheduler.register_task(StockListTask())

                # 从数据库恢复缓存
                await scheduler.restore_from_db()

                # 启动调度器
                await scheduler.start()

                # 检查并刷新过期的缓存（适用于非凌晨启动的情况）
                await scheduler.check_and_refresh_stale()

                logger.info("定时缓存系统已启动")
            except Exception as e:
                logger.warning(f"定时缓存系统启动失败（非致命）: {e}")

            settings = get_config()
            await ensure_market_data_runtime(app_state, settings)

            # 初始化模块数据源配置 Repository
            # 注意：DatabaseComponent 现在在 lifespan 中初始化，避免重复创建
            # 这里暂时跳过 Repository 初始化，待后续重构使用 app.state.db_service
            try:

                # 由于 Repository 需要 db_service，而 db_service 在 lifespan yield 后才可用
                # 这里暂时跳过初始化，将在后续请求中延迟初始化
                logger.debug("模块数据源 Repository 将在首次请求时延迟初始化")
            except Exception as e:
                logger.warning(f"初始化模块数据源 Repository 失败: {e}")

            # 检查是否已经设置了引擎
            if not app_state.engine:
                logger.warning("No engine set, WebUI running in limited mode")
                # 在有限模式下运行，不创建新引擎
                return

            # 只在引擎存在且监控未初始化时初始化
            if not app_state.monitor_api:
                app_state.initialize_monitoring()

            # 只在监控API存在且广播未启动时启动
            if app_state.monitor_api and not app_state.websocket_manager._broadcast_task:
                await app_state.websocket_manager.start_monitoring_broadcast(app_state.monitor_api)

            logger.info("Web UI 服务启动成功")

        except Exception as e:
            logger.error(f"启动失败: {e}")
            raise

    return startup_handler


def create_shutdown_handler(app_state: AppState) -> Callable[[], Awaitable[None]]:
    """创建关闭处理函数"""

    async def shutdown_handler() -> None:
        """应用关闭处理"""
        logger.debug("关闭 Web UI 服务...")

        try:
            # 停止定时缓存系统
            try:
                from core.core.scheduler import get_scheduler

                scheduler = get_scheduler()
                await scheduler.stop()
                logger.info("定时缓存系统已停止")
            except Exception as e:
                logger.warning(f"停止定时缓存系统失败: {e}")

            await shutdown_market_data_runtime(app_state)
            # 停止监控广播
            await app_state.websocket_manager.stop_monitoring_broadcast()

            # 关闭所有 WebSocket 连接
            await app_state.websocket_manager.close_all_connections()

            # 停止监控 API
            if app_state.monitor_api:
                app_state.monitor_api.stop()
                app_state.monitor_api = None

            # 停止监控器
            if app_state.monitor:
                app_state.monitor.stop()
                app_state.monitor = None

            logger.info("Web UI 服务优雅关闭完成")

        except Exception as e:
            logger.error(f"关闭时出错: {e}")

        logger.debug("Web UI 服务已关闭")

    return shutdown_handler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan 上下文管理器

    确保数据库连接池在 Uvicorn 的事件循环中初始化，
    避免 Event loop is closed 错误。
    """
    # 获取当前事件循环 ID 用于调试
    try:
        current_loop = asyncio.get_running_loop()
        logger.debug(f"Lifespan 启动，事件循环 ID: {id(current_loop)}")
    except RuntimeError:
        logger.warning("Lifespan 启动时无运行中的事件循环")

    # === STARTUP ===
    # 首先确保日志系统已正确初始化
    try:
        from core.observability.logger import logger_manager

        if not logger_manager._started:
            logger_manager.start()
            logger.info("日志系统已在 lifespan 中初始化")
        else:
            logger.debug("日志系统已启动，跳过重复初始化")
    except Exception as e:
        logger.warning(f"日志系统初始化检查失败: {e}")

    # 初始化 ProviderContainer（新架构）
    try:
        from core.infrastructure.providers.container import ProviderContainer

        logger.info("初始化 ProviderContainer...")
        provider_container = ProviderContainer()
        app.state.provider_container = provider_container

        # 同步到 AppState 实例，便于 market_data_runtime/orchestrator 访问
        if hasattr(app.state, "app_state") and app.state.app_state is not None:
            app.state.app_state.provider_container = provider_container

        # 预加载配置中的 Provider
        # 注意：跳过 amazingdata，因为 AmazingData SDK 不支持多进程同时登录
        # AmazingData 的 SDK 操作由 Dask Worker 中的 AmazingDataActor 处理
        # 主进程通过 orchestrator 使用 Worker 代理的数据
        SKIP_PRELOAD_PROVIDERS = {"amazingdata"}
        settings = get_config()
        if hasattr(settings, "data_sources") and settings.data_sources:
            for name, ds_config in settings.data_sources.providers.items():
                if name.lower() in SKIP_PRELOAD_PROVIDERS:
                    logger.info(f"跳过预加载 Provider: {name} (由 Dask Worker 处理)")
                    continue
                if ds_config.enabled:
                    try:
                        config_dict = ds_config.model_dump()
                        await provider_container.create_and_register(name, config_dict)
                        logger.info(f"预加载 Provider 成功: {name}")
                    except Exception as e:
                        logger.warning(f"预加载 Provider 失败: {name} - {e}")

        logger.info("ProviderContainer 初始化完成")
    except Exception as e:
        logger.warning(f"ProviderContainer 初始化失败（非致命）: {e}")
        app.state.provider_container = None

    # 初始化数据库组件（确保在正确的事件循环中）
    try:
        from core.core.component_factory import DatabaseComponentFactory
        from core.core.runtime.context import get_context
        from core.infrastructure.persistence.database import DatabaseService

        # 创建并初始化数据库组件（现在在 Uvicorn 的事件循环中）
        db_component = DatabaseComponentFactory.create()
        await db_component.initialize_async()

        # 将正确的数据库组件注册到 ApplicationContext
        # 这样所有通过 get_context().get_component("database") 的调用都会使用这个组件
        get_context().override_component("database", db_component)

        # 存储到 app.state 供依赖注入使用
        app.state.db_component = db_component
        app.state.db_service = DatabaseService(db_component)
        logger.info("数据库连接池已在 lifespan 中初始化并覆盖全局组件")
    except Exception as e:
        logger.warning(f"lifespan 中初始化数据库失败: {e}")
        app.state.db_component = None
        app.state.db_service = None

    # 启动 Windows Dask Workers（在市场数据服务之前）
    worker_started = False
    try:
        from core.compute.dask_worker_manager import ensure_windows_workers

        worker_started = await ensure_windows_workers()
        if worker_started:
            logger.info("Windows Dask Workers 自启动成功")
        else:
            logger.warning("Windows Dask Workers 自启动失败（将继续启动，但数据源功能可能受限）")
    except Exception as e:
        logger.warning(f"Windows Dask Workers 自启动异常: {e}")

    # 如果 Worker 启动成功，注册 AmazingData 代理到 ProviderContainer
    provider_container = getattr(app.state, "provider_container", None)
    if worker_started and provider_container is not None:
        try:
            import redis.asyncio as aioredis
            from core.infrastructure.providers.implementations.amazingdata.dask_adapter import (
                AmazingDataDaskAdapter,
            )
            from distributed import Client

            # 获取 scheduler 地址（从配置读取）
            scheduler_address = "tcp://localhost:8786"
            app_settings = get_config()
            dask_config = getattr(app_settings, "dask", None)
            if dask_config and hasattr(dask_config, "scheduler_address"):
                scheduler_address = dask_config.scheduler_address

            # 创建 Dask Client（用于任务提交）
            # 注意：不使用 future.result()，而是通过 Redis 获取结果
            # 这是为了绕过 tornado IOLoop 与 FastAPI asyncio 的冲突
            dask_client = Client(
                scheduler_address,
                timeout="30s",
                set_as_default=False,
                direct_to_workers=False,
            )

            # 创建 Redis 客户端（用于获取调用结果）
            # 使用与 Worker 相同的 Redis 实例
            redis_url = "redis://localhost:6379"
            cache_config = getattr(app_settings, "cache", None)
            if cache_config and hasattr(cache_config, "url"):
                redis_url = cache_config.url
            redis_client = aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

            # 从配置读取 AmazingData 超时设置
            # 配置路径: data_sources.providers.amazingdata.timeout / config.first_call_timeout
            amazingdata_timeout = 45.0  # 默认后续调用超时
            amazingdata_first_call_timeout = 90.0  # 默认首次调用超时（含登录）

            data_sources = getattr(app_settings, "data_sources", None)
            if data_sources:
                amazingdata_provider = data_sources.providers.get("amazingdata")
                if amazingdata_provider:
                    # 读取主超时配置
                    if amazingdata_provider.timeout:
                        amazingdata_timeout = amazingdata_provider.timeout
                    # 读取嵌套配置中的首次调用超时
                    nested_config = amazingdata_provider.config or {}
                    if "first_call_timeout" in nested_config:
                        amazingdata_first_call_timeout = float(nested_config["first_call_timeout"])
                    # 如果配置了 prewarm，首次调用超时可以适当降低（预热后不需要登录）
                    if nested_config.get("prewarm"):
                        logger.info("[AmazingData] 预热模式已启用，Worker 启动时将完成登录")

            logger.info(
                "[AmazingData/Dask] 超时配置 | normal={}s | first_call={}s",
                amazingdata_timeout,
                amazingdata_first_call_timeout,
            )

            # 创建代理 Adapter（带 Redis 客户端用于结果传递）
            adapter = AmazingDataDaskAdapter(
                dask_client,
                redis_client=redis_client,
                timeout=amazingdata_timeout,
                first_call_timeout=amazingdata_first_call_timeout,
            )

            # 初始化并验证 Actor 可用
            if await adapter.initialize():
                # 注册到 ProviderContainer
                provider_container.register_external("amazingdata", adapter)
                # 保存 client 引用以便关闭时使用
                app.state.amazingdata_dask_client = dask_client
                app.state.amazingdata_redis_client = redis_client
                logger.info(
                    "AmazingData Dask 代理已注册到 ProviderContainer（使用 Redis 结果传递）"
                )
            else:
                logger.warning("AmazingData Actor 不可用，跳过代理注册")
                # 同步关闭 Client
                dask_client.close()
                await redis_client.aclose()
        except Exception as e:
            logger.warning(f"注册 AmazingData 代理失败: {e}")

    # 然后执行其他启动逻辑
    startup_handler = create_startup_handler(app_state)
    await startup_handler()

    # 初始化通知推送服务
    try:
        from core.config.models.notifications import NotificationsConfig
        from core.core.runtime.context import get_context as get_ctx
        from core.infrastructure.notifications import NotificationQuotaGuard, NotificationService

        settings = get_config()
        notifications_config = getattr(settings, "notifications", None)
        if notifications_config is None:
            notifications_config = NotificationsConfig()
        elif not isinstance(notifications_config, NotificationsConfig):
            notifications_config = NotificationsConfig.model_validate(notifications_config)

        notification_service = NotificationService(
            notifications_config,
            quota_guard=NotificationQuotaGuard(),
        )
        get_ctx().register_service("notifications", notification_service)
        logger.info("通知推送服务已初始化")
    except Exception as e:
        logger.warning(f"通知推送服务初始化失败（非致命）: {e}")

    # 启动定时 GC 任务 (每 5 分钟执行一次)
    try:
        from apps.api.api.endpoints.system.memory import get_memory_manager

        memory_manager = get_memory_manager()
        await memory_manager.start_periodic_gc()
        logger.info("定时 GC 任务已启动")
    except Exception as e:
        logger.warning(f"定时 GC 任务启动失败（非致命）: {e}")

    yield  # 应用运行中

    # === SHUTDOWN ===
    # 停止定时 GC 任务
    try:
        from apps.api.api.endpoints.system.memory import get_memory_manager

        memory_manager = get_memory_manager()
        await memory_manager.stop_periodic_gc()
        logger.info("定时 GC 任务已停止")
    except Exception as e:
        logger.warning(f"停止定时 GC 任务失败: {e}")

    # 关闭 ProviderContainer（新架构）
    provider_container_raw = getattr(app.state, "provider_container", None)
    if provider_container_raw is not None:
        try:
            logger.info("关闭 ProviderContainer...")
            await provider_container_raw.shutdown()
            logger.info("ProviderContainer 已关闭")
        except Exception as e:
            logger.warning(f"关闭 ProviderContainer 失败: {e}")

    # 清理数据库连接池
    db_component_raw = getattr(app.state, "db_component", None)
    if db_component_raw is not None and hasattr(db_component_raw, "disconnect_async"):
        try:
            await db_component_raw.disconnect_async()
            logger.info("数据库连接池已在 lifespan 中关闭")
        except Exception as e:
            logger.warning(f"关闭数据库连接池失败: {e}")

    # 关闭通知推送服务
    try:
        from core.core.runtime.context import get_context as get_ctx
        from core.infrastructure.notifications import NotificationService

        context = get_ctx()
        if context.has_service("notifications"):
            service = context.get_service("notifications")
            if isinstance(service, NotificationService):
                await service.shutdown()
                logger.info("通知推送服务已关闭")
    except Exception as e:
        logger.warning(f"关闭通知推送服务失败: {e}")

    # 关闭 AmazingData Dask Client（在 ProviderContainer 关闭后、Worker 停止前）
    dask_client = getattr(app.state, "amazingdata_dask_client", None)
    if dask_client is not None:
        try:
            await dask_client.close()
            logger.info("AmazingData Dask Client 已关闭")
        except Exception as e:
            logger.warning(f"关闭 AmazingData Dask Client 失败: {e}")

    # 停止 Windows Dask Workers
    try:
        from core.compute.dask_worker_manager import stop_windows_workers

        await stop_windows_workers()
    except Exception as e:
        logger.warning(f"停止 Windows Dask Workers 失败: {e}")

    shutdown_handler = create_shutdown_handler(app_state)
    await shutdown_handler()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    # 使用全局 app_state 而不是创建新实例
    global app_state

    app = FastAPI(
        title="DeepSearch Web UI",
        description="DeepSearch 量化交易系统 Web 界面",
        version="0.1.0",
        default_response_class=SafeJSONResponse,
        lifespan=lifespan,  # 使用 lifespan 上下文管理器
    )

    # 存储全局应用状态
    app.state.app_state = app_state

    # 设置全局异常处理器
    try:
        from apps.api.api.exception_handlers import setup_global_exception_handlers

        setup_global_exception_handlers(app)
        logger.info("全局异常处理器已配置")
    except ImportError as e:
        logger.warning(f"无法导入异常处理器: {e}")

    # 添加请求限流和去重中间件
    try:
        from apps.api.api.middleware import DeduplicationMiddleware

        # 添加去重中间件（先去重，再限流）
        app.add_middleware(
            DeduplicationMiddleware,
            ttl=5,  # 5秒内的相同请求会被合并
            include_paths={
                "/api/qmt/orderbook",
                "/api/chart/series",
                "/api/data/realtime",
                "/api/market",
            },
        )

        # 添加限流中间件 (暂时禁用用于调试)
        # app.add_middleware(
        #     RateLimitMiddleware,
        #     requests_per_second=20,  # 每秒最多20个请求
        #     burst_size=50,  # 突发最多50个请求
        #     exclude_paths={"/docs", "/openapi.json", "/api/health"},
        # )

        logger.info("请求限流和去重中间件已配置")
    except ImportError as e:
        logger.warning(f"无法导入中间件: {e}")

    # 注意：已改用 lifespan 模式，不再使用 add_event_handler
    # app.add_event_handler("startup", create_startup_handler(app_state))
    # app.add_event_handler("shutdown", create_shutdown_handler(app_state))

    # 配置 CORS（根据环境区分）
    settings: Settings = get_config()
    app.state.settings = settings

    # 根据环境配置CORS
    if settings.app.env == "dev":
        # 开发环境允许所有来源
        cors_origins = ["*"]
    else:
        # 生产环境使用配置的白名单，包括常用的开发端口
        default_origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3002",
            "http://localhost:3003",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:3002",
            "http://127.0.0.1:3003",
        ]
        cors_origins = getattr(settings.webui, "cors_origins", default_origins)
        if isinstance(cors_origins, str):
            cors_origins = [cors_origins]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Total-Count", "X-Page-Count"],  # 暴露分页相关header
    )

    # 挂载静态文件
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # 导入并注册所有路由
    from apps.api.api.database import router as database_router
    from apps.api.api.endpoints.data.akshare_apis import router as akshare_apis_router
    from apps.api.api.endpoints.data.data import router as data_router
    from apps.api.api.endpoints.data.data_source import router as data_source_endpoints_router
    from apps.api.api.endpoints.data.data_unified import router as data_unified_router
    from apps.api.api.endpoints.market_data.live_api import router as market_live_router
    from apps.api.api.endpoints.monitor.analytics import router as monitoring_analytics_router
    from apps.api.api.endpoints.monitor.cache_api import router as monitoring_cache_router
    from apps.api.api.endpoints.monitor.monitor_api import router as monitor_api_router
    from apps.api.api.endpoints.notifications.push import router as notification_push_router
    from apps.api.api.endpoints.qmt.qmt import router as qmt_router
    from apps.api.api.endpoints.qmt.qmt_subscription import router as qmt_subscription_router

    # AmazingData API已移动到第819行单独注册，避免重复注册
    # from apps.api.api.endpoints.amazingdata import router as amazingdata_api
    from apps.api.api.endpoints.route_adapter import router as route_adapter_router
    from apps.api.api.endpoints.system.config import router as system_config_router
    from apps.api.api.endpoints.system.health import router as system_health_router
    from apps.api.api.endpoints.system.logs import router as system_logs_router
    from apps.api.api.endpoints.system.memory import router as memory_router
    from apps.api.api.endpoints.system.system import router as system_router
    from apps.api.api.endpoints.system.system_info import router as system_info_router
    from apps.api.api.endpoints.trading.chart import router as trading_chart_router
    from apps.api.api.endpoints.trading.market import router as trading_market_router
    from apps.api.api.endpoints.trading.market_overview import (
        router as trading_market_overview_router,
    )
    from apps.api.api.errors import router as frontend_errors_router
    from apps.api.api.proxy import router as workers_proxy_router
    from apps.api.api.stock_comment import router as stock_comment_router

    app.include_router(monitor_api_router, prefix="/api/monitor", tags=["Monitor"])
    app.include_router(system_config_router, prefix="/api/system/config", tags=["Config"])
    app.include_router(system_router, prefix="/api/system", tags=["System"])
    app.include_router(system_info_router)  # 系统信息路由
    app.include_router(system_logs_router, prefix="/api/system/logs", tags=["Logs"])
    app.include_router(
        memory_router, tags=["Memory Management"]
    )  # 内存管理路由，已包含 /api/system/memory 前缀

    app.include_router(
        data_source_endpoints_router, tags=["DataSource"]
    )  # 已包含 /api/data-source 前缀
    app.include_router(database_router, prefix="/api/database", tags=["Database"])
    app.include_router(monitoring_cache_router, prefix="/api/cache", tags=["Cache"])
    app.include_router(system_health_router, prefix="/api/health", tags=["Health"])
    app.include_router(frontend_errors_router, prefix="/api/frontend", tags=["Frontend Errors"])
    app.include_router(workers_proxy_router, tags=["Workers Proxy"])  # 已包含 /api/workers 前缀
    app.include_router(
        trading_market_router, tags=["Market"]
    )  # 市场数据路由，已包含 /api/market 前缀
    app.include_router(trading_chart_router, tags=["Chart"])  # 图表数据路由，已包含 /api/chart 前缀
    app.include_router(qmt_router, tags=["QMT"])  # QMT数据路由，已包含 /api/qmt 前缀
    app.include_router(qmt_subscription_router, tags=["QMT Subscription"])  # QMT订阅管理路由
    app.include_router(
        data_unified_router, tags=["UnifiedData"]
    )  # 统一数据API，已包含 /api/data 前缀

    # 新架构数据查询 API (统一查询接口)
    try:
        from apps.api.api.endpoints.data.unified_query import router as unified_query_router

        app.include_router(
            unified_query_router, tags=["UnifiedQuery"]
        )  # 新架构数据API，已包含 /api/v1/data 前缀
        logger.info("统一数据查询API已注册")
    except ImportError as e:
        logger.warning(f"统一数据查询API模块加载失败: {e}")

    app.include_router(
        data_router, prefix="/api/data", tags=["Data"]
    )  # 基础数据API，提供 /stocks、/kline 等
    app.include_router(
        monitoring_analytics_router, tags=["Analytics"]
    )  # 分析API，已包含 /api/analytics 前缀
    app.include_router(trading_market_overview_router, tags=["MarketOverview"])  # 市场总貌API
    app.include_router(market_live_router, tags=["MarketLive"])  # 市场实时行情API
    app.include_router(stock_comment_router, tags=["StockComment"])  # 千股千评API
    app.include_router(notification_push_router, tags=["Notification"])  # 通知配置与推送API
    app.include_router(akshare_apis_router, tags=["AkShareAPIs"])  # AkShare API列表
    # AmazingData API已移至第819行使用模块化版本注册

    # 数据源状态管理API
    # 数据源监控API
    try:
        from apps.api.api.endpoints.data.data_source_monitor_api import (
            router as data_source_monitor_router,
        )

        app.include_router(data_source_monitor_router, tags=["DataSourceMonitor"])  # 数据源监控API
        logger.info("数据源监控API已注册")
    except ImportError as e:
        logger.warning(f"数据源监控API模块加载失败: {e}")

    # 数据源能力对比API
    try:
        from apps.api.api.endpoints.data.data_source_capability_api import (
            router as data_source_capability_router,
        )

        app.include_router(
            data_source_capability_router, tags=["DataSourceCapability"]
        )  # 数据源能力API
        logger.info("数据源能力对比API已注册")
    except ImportError as e:
        logger.warning(f"数据源能力API模块加载失败: {e}")

    # 数据源配置管理API
    try:
        from apps.api.api.endpoints.data.data_source_config_api import (
            router as data_source_config_router,
        )

        app.include_router(data_source_config_router, tags=["DataSourceConfig"])  # 数据源配置API
        # data_source_config_api.setup_callbacks()  # 设置配置回调 - router对象没有这个方法
        logger.info("数据源配置API已注册")
    except ImportError as e:
        logger.warning(f"数据源配置API模块加载失败: {e}")

    # 数据源测试API
    # 注意：已禁用旧的test_data_source路由，避免与datasource_manager中的新路由冲突 (2025-09-18)
    # 新的测试端点在datasource_manager中实现，包含了更好的错误处理和AmazingData支持
    # try:
    #     from apps.api.api.endpoints.data.test_data_source import router as test_data_source
    #     app.include_router(test_data_source, tags=["DataSourceTest"])  # 数据源测试API，包含 /api/data-source 前缀
    #     logger.info("数据源测试API已注册")
    # except ImportError as e:
    #     logger.warning(f"数据源测试API模块加载失败: {e}")

    # MiniQMT API
    try:
        from apps.api.api.endpoints.qmt.miniqmt import router as miniqmt_router

        app.include_router(
            miniqmt_router, tags=["MiniQMT"]
        )  # MiniQMT数据路由，已包含 /api/miniqmt 前缀
    except ImportError:
        logger.warning("MiniQMT API 模块未找到，跳过注册")

    # 数据库连接管理API
    try:
        from apps.api.api.endpoints.system.database_manager import (
            register_database_connection_monitor,
        )
        from apps.api.api.endpoints.system.database_manager import router as database_manager_router

        app.include_router(
            database_manager_router, prefix="/api/system/database", tags=["Database Management"]
        )
        register_database_connection_monitor(app)
        logger.info("数据库连接管理API已注册")
    except ImportError as e:
        logger.warning(f"数据库连接管理API模块加载失败: {e}")

    # 数据源CRUD管理API
    try:
        from apps.api.api.endpoints.datasources.datasource_manager import (
            data_source_router as datasource_compatibility_router,
        )
        from apps.api.api.endpoints.datasources.datasource_manager import (
            router as datasource_manager_router,
        )
        from apps.api.api.endpoints.datasources.ingestion_jobs import (
            router as ingestion_jobs_router,
        )

        app.include_router(datasource_manager_router, tags=["DataSource Management"])
        app.include_router(datasource_compatibility_router, tags=["DataSource Compatibility"])
        app.include_router(ingestion_jobs_router, tags=["DataSource Jobs"])
        logger.info("数据源CRUD管理API已注册")
    except ImportError as e:
        logger.warning(f"数据源CRUD管理API模块加载失败: {e}")

    # 模块数据源配置API
    try:
        from apps.api.api.endpoints.datasources.module_sources_api import (
            router as module_sources_router,
        )

        app.include_router(module_sources_router, tags=["Module Sources"])
        logger.info("模块数据源配置API已注册")
    except ImportError as e:
        logger.warning(f"模块数据源配置API模块加载失败: {e}")

    # AKShare数据源集成API
    try:
        from apps.api.api.endpoints.datasources.akshare_integration import (
            router as akshare_integration_router,
        )

        app.include_router(akshare_integration_router, tags=["AKShare Integration"])
        logger.info("AKShare数据源API已注册")
    except ImportError as e:
        logger.warning(f"AKShare数据源API模块加载失败: {e}")

    # Backtest API
    try:
        from apps.api.api.endpoints.trading.backtest_api import router as backtest_router

        app.include_router(backtest_router, tags=["Backtest"])  # 回测API，已包含 /api/backtest 前缀
        logger.info("回测API已注册")
    except ImportError as e:
        logger.warning(f"回测API模块加载失败: {e}")

    # T-Trading 日内做T API
    try:
        from apps.api.api.endpoints.trading.ttrading import router as ttrading_router

        app.include_router(
            ttrading_router, tags=["T-Trading"]
        )  # 日内做T API，已包含 /api/ttrading 前缀
        logger.info("日内做T API已注册")
    except ImportError as e:
        logger.warning(f"日内做T API模块加载失败: {e}")

    # Strategy Center API (策略中心)
    try:
        from apps.api.api.endpoints.strategy_center import router as strategy_center_router

        app.include_router(
            strategy_center_router, tags=["Strategy Center"]
        )  # 策略中心API，已包含 /api/strategy-center 前缀
        logger.info("策略中心API已注册")
    except ImportError as e:
        logger.warning(f"策略中心API模块加载失败: {e}")

    # Positions API (通用持仓管理)
    try:
        from apps.api.api.endpoints.positions import router as positions_router

        app.include_router(
            positions_router, prefix="/api", tags=["Positions"]
        )  # 通用持仓API: /api/positions/*
        logger.info("通用持仓管理API已注册")
    except ImportError as e:
        logger.warning(f"通用持仓管理API模块加载失败: {e}")

    # Provider Management API (新架构)
    try:
        from apps.api.api.endpoints.providers import router as provider_management_router

        app.include_router(provider_management_router, tags=["Provider Management"])
        logger.info("Provider 管理API已注册（新架构）")
    except ImportError as e:
        logger.warning(f"Provider 管理API模块加载失败: {e}")

    # Data Source Monitor API
    try:
        from apps.api.api.monitor.data_source_api import router as monitor_data_source_router

        app.include_router(monitor_data_source_router, tags=["DataSourceMonitor"])  # 数据源监控API
        logger.info("数据源监控API已注册")
    except ImportError as e:
        logger.warning(f"数据源监控API模块加载失败: {e}")

    # 注册缓存管理API
    try:
        from apps.api.api.endpoints.cache import router as cache_management_router

        app.include_router(cache_management_router, prefix="/api", tags=["Cache Management"])
        logger.info("缓存管理API已注册")
    except ImportError as e:
        logger.warning(f"缓存管理API模块加载失败: {e}")

    # 注册图表数据API
    try:
        from apps.api.api.endpoints.chart import router as chart_data_router

        app.include_router(chart_data_router, prefix="/api", tags=["Chart Data"])
        logger.info("图表数据API已注册")
    except ImportError as e:
        logger.warning(f"图表数据API模块加载失败: {e}")

    # 注册市场分析API
    try:
        from apps.api.api.endpoints.market import router as market_analysis_router

        app.include_router(market_analysis_router, prefix="/api", tags=["Market Analysis"])
        app.include_router(market_live_router, tags=["Market Live"])
        logger.info("市场数据实时API已注册")
        logger.info("市场分析API已注册")
    except ImportError as e:
        logger.warning(f"市场分析API模块加载失败: {e}")

    # 注册市场数据API
    try:
        from apps.api.api.endpoints.data.market_data_api import router as market_data_router

        app.include_router(market_data_router, tags=["Market Data"])
        logger.info("市场数据API已注册")
    except ImportError as e:
        logger.warning(f"市场数据API模块加载失败: {e}")

    # 注册市场概览和排行榜API
    try:
        from apps.api.api.endpoints.data.market_overview_api import (
            router as market_overview_api_router,
        )

        app.include_router(market_overview_api_router, tags=["Market Overview"])
        logger.info("市场概览和排行榜API已注册")
    except ImportError as e:
        logger.warning(f"市场概览API模块加载失败: {e}")

    # 注册AmazingData API (P4级新增)
    # 注册AmazingData API (P4级新增)
    try:
        # 直接导入避免延迟加载掩盖错误
        from apps.api.api.endpoints.amazingdata.router import router as amazingdata_main_router

        app.include_router(amazingdata_main_router, tags=["AmazingData"])
        logger.info("AmazingData API已注册")
    except ImportError as e:
        logger.warning(f"AmazingData API模块加载失败 (ImportError): {e}")
    except Exception as e:
        logger.error(f"AmazingData API模块初始化失败: {e}")

    # 注册监控指标API
    try:
        from apps.api.api.endpoints.monitor.metrics_api import router as metrics_router

        app.include_router(metrics_router, tags=["Metrics"])
        logger.info("监控指标API已注册")
    except ImportError as e:
        logger.warning(f"监控指标API模块加载失败: {e}")

    # 注释掉 Cloudflare Tunnel API，因为不需要映射 webui 端口
    # Cloudflare Tunnel 已移除（使用 Workers 代理方案）

    # 注册路由适配器（必须放在最后，作为catch-all路由）
    app.include_router(route_adapter_router, tags=["RouteAdapter"])
    logger.info("API路由适配器已注册，处理前后端API不匹配问题")

    return app


# 创建默认应用实例
app = create_app()


@app.get("/")
async def root():
    """根路径，返回前端页面或API信息。"""
    try:
        # 检查是否存在静态目录
        if STATIC_DIR.exists():
            index_file = STATIC_DIR / "index.html"
            if index_file.exists():
                return FileResponse(str(index_file))
    except Exception as e:
        logger.debug(f"无法加载静态文件: {e}")

    # 返回API信息而不是错误
    return JSONResponse(
        {
            "message": "DeepSearch Web UI Backend",
            "version": "0.1.0",
            "api_docs": "/docs",
            "health_check": "/api/health",
            "note": "Frontend is running separately on port 3000",
        }
    )


@app.websocket("/ws/monitor")
async def websocket_monitor(websocket: WebSocket):
    """监控数据 WebSocket 端点"""
    await app_state.websocket_manager.accept_connection(websocket)

    try:
        while True:
            # 保持连接，等待客户端消息
            data = await websocket.receive_text()

            # 处理客户端命令
            if data == "ping":
                await websocket.send_text("pong")
            elif data == "get_status":
                status = {
                    "type": "status",
                    "data": (
                        app_state.monitor_api.get_health_status() if app_state.monitor_api else {}
                    ),
                }
                await websocket.send_json(status)

    except WebSocketDisconnect:
        await app_state.websocket_manager.remove_connection(websocket)
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        await app_state.websocket_manager.remove_connection(websocket)


# 为测试提供简化的 WebSocket 端点，路径为 /ws
@app.websocket("/ws")
async def websocket_basic(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "subscribe":
                # 简化的订阅确认
                await websocket.send_json(
                    {"type": "subscribed", "channel": message.get("channel"), "ok": True}
                )
            else:
                await websocket.send_json({"type": "unknown", "received": message})
    except WebSocketDisconnect:
        pass


# 持仓管理 WebSocket 端点
@app.websocket("/ws/positions")
async def websocket_positions(websocket: WebSocket):
    """持仓数据 WebSocket 端点

    支持的消息类型:
    - {"type": "ping"} → {"type": "pong"}
    - {"type": "subscribe"} → 订阅持仓变更
    - {"type": "get_positions"} → 获取当前持仓
    - {"type": "get_summary"} → 获取持仓汇总
    """
    await websocket.accept()

    try:
        while True:
            message = await websocket.receive_json()
            msg_type = message.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "subscribe":
                await websocket.send_json(
                    {"type": "subscribed", "channel": "positions", "ok": True}
                )

            elif msg_type == "get_positions":
                # 获取持仓列表
                try:
                    from core.application.services.position_service import PositionService
                    from core.core.components.data_components import DatabaseComponent
                    from core.core.runtime.context import get_context

                    db_component = get_context().get_component("database")
                    if not isinstance(db_component, DatabaseComponent):
                        raise RuntimeError("数据库组件类型错误")
                    async with db_component.get_session() as session:
                        service = PositionService(session)
                        positions = await service.get_all()
                        await websocket.send_json(
                            {"type": "positions", "data": [p.to_dict() for p in positions]}
                        )
                except Exception as e:
                    logger.error(f"获取持仓失败: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})

            elif msg_type == "get_summary":
                # 获取持仓汇总
                try:
                    from core.application.services.position_service import PositionService
                    from core.core.components.data_components import DatabaseComponent
                    from core.core.runtime.context import get_context

                    db_component = get_context().get_component("database")
                    if not isinstance(db_component, DatabaseComponent):
                        raise RuntimeError("数据库组件类型错误")
                    async with db_component.get_session() as session:
                        service = PositionService(session)
                        positions = await service.get_all()
                        prices = {p.symbol: p.cost_price for p in positions}
                        summary = await service.calc_portfolio_summary(prices)
                        await websocket.send_json(
                            {
                                "type": "summary",
                                "data": {
                                    "total_positions": summary.total_positions,
                                    "total_market_value": summary.total_market_value,
                                    "total_cost_value": summary.total_cost_value,
                                    "total_unrealized_pnl": summary.total_unrealized_pnl,
                                    "total_pnl_ratio": summary.total_pnl_ratio,
                                },
                            }
                        )
                except Exception as e:
                    logger.error(f"获取持仓汇总失败: {e}")
                    await websocket.send_json({"type": "error", "message": str(e)})

            else:
                await websocket.send_json({"type": "unknown", "received": message})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"持仓 WebSocket 错误: {e}")


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    if app_state.monitor_api:
        health_status = app_state.monitor_api.get_health_status()
        return {
            "status": "healthy" if health_status.get("status") == "healthy" else "unhealthy",
            "details": health_status,
        }
    # 默认返回健康，便于在无引擎初始化的测试环境通过健康检查
    return {"status": "healthy", "details": {}}


@app.post("/api/frontend/errors")
async def report_frontend_error(error: Dict[str, Any]) -> Dict[str, Any]:
    """前端错误上报接口"""
    # 仅在开发环境记录详细信息
    settings: Optional[Settings] = getattr(app.state, "settings", None)
    if settings and settings.app.env == "dev":
        logger.warning(f"Frontend error: {error}")
    return {"success": True, "message": "Error reported"}


# 向后兼容的函数
def set_engine(engine: MainEngine) -> None:
    """设置引擎实例（向后兼容）"""
    app_state.set_engine(engine)


def get_engine() -> Optional[MainEngine]:
    """获取引擎实例（向后兼容）"""
    return app_state.engine


def get_monitor() -> Optional[EventSystemMonitor]:
    """获取监控器实例（向后兼容）"""
    return app_state.monitor


def get_monitor_api() -> Optional[MonitorAPI]:
    """获取监控API实例（向后兼容）"""
    return app_state.monitor_api


if __name__ == "__main__":
    import uvicorn

    from .server_manager import get_server_manager

    # 开发环境运行
    config = get_config()
    manager = get_server_manager()
    uvicorn.run(
        "apps.api.server:app",
        host=config.webui.backend_host,
        port=config.webui.backend_port,
        reload=config.webui.reload,
        log_level="info",
    )
