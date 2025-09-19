"""
FastAPI 服务器主应用

提供 REST API 和 WebSocket 端点，为前端提供数据接口。
"""
from __future__ import annotations

import asyncio
import json
import math
import sys
import threading
import zlib
import time
from collections import deque
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from deepsearch.core import MainEngine
from deepsearch.debug.diagnostics import diagnostic_logger, log_diagnostic
from deepsearch.observability.monitoring.event_monitor import EventSystemMonitor
from deepsearch.observability.monitoring.monitor_api import MonitorAPI

# Windows 兼容性：psycopg3 需要 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 记录模块导入
log_diagnostic("MODULE_IMPORT", "server.py", {
    "imports": ["MainEngine", "EventSystemMonitor", "MonitorAPI", "FastAPI"],
    "platform": sys.platform
})


def safe_json_encoder(obj):
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


def sanitize_data(data):
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
    def render(self, content) -> bytes:
        # Sanitize the content before rendering
        safe_content = sanitize_data(content)
        return super().render(safe_content)


class MessageBatcher:
    """消息批处理器"""
    
    def __init__(self, batch_size: int = 50, batch_timeout: float = 0.1):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.message_queue = deque()
        self.last_flush_time = time.time()
        self.lock = asyncio.Lock()
    
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
            if (len(self.message_queue) >= self.batch_size or 
                current_time - self.last_flush_time >= self.batch_timeout):
                
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
        self._connections_lock = asyncio.Lock()  # 添加异步锁保护连接列表
        self._broadcast_task: Optional[asyncio.Task] = None
        self._monitor_api: Optional[MonitorAPI] = None
        self._base_broadcast_interval: float = 2.0
        self._broadcast_interval: float = 2.0
        self._last_data_hash: Optional[int] = None  # 用于检测数据变化
        self._slow_connections_count: int = 0  # 慢连接计数
        self._send_timeout: float = 0.5  # 单连接发送超时（500ms）
        
        # 批处理和压缩配置
        self.enable_compression = enable_compression
        self.enable_batching = enable_batching
        self.message_batcher = MessageBatcher() if enable_batching else None
        self.compression_threshold = 1024  # 压缩阈值（1KB）
        
        # 统计信息
        self.stats = {
            'messages_sent': 0,
            'messages_compressed': 0,
            'bytes_sent': 0,
            'bytes_saved': 0,
            'batches_sent': 0,
            'connection_errors': 0
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

    async def broadcast_message(self, message: dict) -> None:
        """向所有客户端广播消息（支持批处理和压缩）"""
        # 批处理逻辑
        if self.enable_batching and self.message_batcher:
            messages = await self.message_batcher.add_message(message)
            if messages is None:
                # 消息已加入队列，等待批处理
                return
            # 批量发送
            message_to_send = {
                'type': 'batch',
                'messages': messages,
                'count': len(messages)
            }
            self.stats['batches_sent'] += 1
        else:
            message_to_send = message
        
        # 获取连接副本，避免长时间持有锁
        async with self._connections_lock:
            if not self._connections:
                return
            connections_copy = self._connections.copy()
        
        # 序列化消息
        message_text = json.dumps(message_to_send, ensure_ascii=False)
        original_size = len(message_text.encode('utf-8'))
        
        # 压缩消息（如果启用且超过阈值）
        is_compressed = False
        if self.enable_compression and original_size > self.compression_threshold:
            compressed_data = zlib.compress(message_text.encode('utf-8'), level=1)
            if len(compressed_data) < original_size:
                # 构建压缩消息
                compressed_message = {
                    'type': 'compressed',
                    'data': compressed_data.hex(),  # 转换为十六进制字符串
                    'original_size': original_size,
                    'compressed_size': len(compressed_data)
                }
                message_text = json.dumps(compressed_message)
                is_compressed = True
                
                # 更新统计
                self.stats['messages_compressed'] += 1
                self.stats['bytes_saved'] += original_size - len(compressed_data)
        
        self.stats['messages_sent'] += 1
        self.stats['bytes_sent'] += len(message_text.encode('utf-8'))
        
        failed_connections = []

        # 并发发送消息
        tasks = []
        for conn in connections_copy:
            tasks.append(self._send_to_connection(conn, message_text, failed_connections))

        await asyncio.gather(*tasks, return_exceptions=True)

        # 清理失败的连接
        for conn in failed_connections:
            await self.remove_connection(conn)
            self.stats['connection_errors'] += 1

    async def _send_to_connection(self, conn: WebSocket, message: str, failed_list: list) -> None:
        """发送消息到单个连接（带超时控制）"""
        try:
            # 使用超时控制，避免慢连接阻塞
            await asyncio.wait_for(
                conn.send_text(message),
                timeout=self._send_timeout
            )
        except asyncio.TimeoutError:
            logger.debug(f"消息发送超时，标记为慢连接")
            self._slow_connections_count += 1
            failed_list.append(conn)
        except Exception as e:
            logger.debug(f"消息发送失败: {e}")
            failed_list.append(conn)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取WebSocket统计信息"""
        return {
            **self.stats,
            'active_connections': len(self._connections),
            'slow_connections': self._slow_connections_count,
            'compression_enabled': self.enable_compression,
            'batching_enabled': self.enable_batching,
            'broadcast_interval': self._broadcast_interval
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
                batch_message = {
                    'type': 'batch',
                    'messages': messages,
                    'count': len(messages)
                }
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
                            "interval": self._broadcast_interval  # 告知客户端当前间隔
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
        if hasattr(self, '_broadcast_interval'):
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
            pass


# 应用状态管理
@diagnostic_logger.diagnostic_class
class AppState:
    """应用全局状态"""

    def __init__(self):
        log_diagnostic("APP_STATE_INIT", "AppState.__init__", {
            "thread": threading.current_thread().name,
            "instance_id": id(self)
        })
        self.websocket_manager = WebSocketManager()
        self.engine: Optional[MainEngine] = None
        self.monitor: Optional[EventSystemMonitor] = None
        self.monitor_api: Optional[MonitorAPI] = None

    @diagnostic_logger.diagnostic_method
    def set_engine(self, engine: MainEngine) -> None:
        """设置引擎实例"""
        log_diagnostic("SET_ENGINE_START", "AppState.set_engine", {
            "engine": str(engine),
            "engine_type": type(engine).__name__,
            "engine_id": id(engine),
            "has_engine_before": self.engine is not None,
            "old_engine_id": id(self.engine) if self.engine else None,
            "instance_id": id(self)
        })
        
        self.engine = engine
        logger.debug(f"引擎实例已设置：{engine}")

        log_diagnostic("SET_ENGINE_AFTER", "AppState.set_engine", {
            "self.engine": str(self.engine),
            "self.engine_id": id(self.engine),
            "engine_is_set": self.engine is not None,
            "same_object": self.engine is engine
        })

        # 同时注册到应用上下文
        from deepsearch.core.runtime.context import get_context
        context = get_context()
        context.set_engine(engine)

    def initialize_monitoring(self) -> None:
        """初始化监控组件"""
        if not self.engine:
            raise RuntimeError("引擎未设置")

        # 获取或创建监控器
        if hasattr(self.engine, '_monitor') and self.engine._monitor:
            self.monitor = self.engine._monitor
        else:
            # 从引擎获取事件引擎组件
            from deepsearch.core.components import EventEngineComponent
            event_engine_component = self.engine.get_component(EventEngineComponent)
            if event_engine_component:
                event_engine = event_engine_component.get_instance()
                self.monitor = EventSystemMonitor(event_engine)
            else:
                logger.warning("无法获取事件引擎组件，监控功能将不可用")
                self.monitor = None

        if self.monitor:
            self.monitor_api = MonitorAPI(self.monitor)
            # 确保监控器已启动
            if not hasattr(self.monitor, '_monitoring') or not self.monitor._monitoring:
                self.monitor.start()
            self.monitor_api.start()
        else:
            self.monitor_api = None


# 全局应用状态
log_diagnostic("CREATE_APP_STATE", "server.py", {
    "location": "global",
    "before_creation": True
})
app_state = AppState()
log_diagnostic("CREATE_APP_STATE", "server.py", {
    "location": "global",
    "after_creation": True,
    "app_state_id": id(app_state),
    "app_state": str(app_state),
    "has_engine": hasattr(app_state, 'engine'),
    "engine_value": str(getattr(app_state, 'engine', None))
})


def create_startup_handler(app_state: AppState):
    """创建启动处理函数"""

    async def startup_handler():
        """应用启动处理"""
        logger.debug("启动 Web UI 服务...")

        try:
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


def create_shutdown_handler(app_state: AppState):
    """创建关闭处理函数"""

    async def shutdown_handler():
        """应用关闭处理"""
        logger.debug("关闭 Web UI 服务...")

        try:
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


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例"""
    # 使用全局 app_state 而不是创建新实例
    global app_state

    app = FastAPI(
        title="DeepSearch Web UI",
        description="DeepSearch 量化交易系统 Web 界面",
        version="0.1.0",
        default_response_class=SafeJSONResponse
    )

    # 存储全局应用状态
    app.state.app_state = app_state

    # 设置全局异常处理器
    try:
        from deepsearch.webui.api.exception_handlers import setup_global_exception_handlers
        setup_global_exception_handlers(app)
        logger.info("全局异常处理器已配置")
    except ImportError as e:
        logger.warning(f"无法导入异常处理器: {e}")
    
    # 添加请求限流和去重中间件
    try:
        from deepsearch.webui.api.middleware import RateLimitMiddleware, DeduplicationMiddleware
        
        # 添加去重中间件（先去重，再限流）
        app.add_middleware(
            DeduplicationMiddleware,
            ttl=5,  # 5秒内的相同请求会被合并
            include_paths={
                "/api/qmt/orderbook",
                "/api/chart/series",
                "/api/data/realtime",
                "/api/market"
            }
        )
        
        # 添加限流中间件
        app.add_middleware(
            RateLimitMiddleware,
            requests_per_second=20,  # 每秒最多20个请求
            burst_size=50,  # 突发最多50个请求
            exclude_paths={"/docs", "/openapi.json", "/api/health"}
        )
        
        logger.info("请求限流和去重中间件已配置")
    except ImportError as e:
        logger.warning(f"无法导入中间件: {e}")

    # 设置启动和关闭处理
    app.add_event_handler("startup", create_startup_handler(app_state))
    app.add_event_handler("shutdown", create_shutdown_handler(app_state))

    # 配置 CORS（根据环境区分）
    from deepsearch.config import get_config
    config = get_config()

    # 根据环境配置CORS
    if config.app.env == "dev":
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
            "http://127.0.0.1:3003"
        ]
        cors_origins = getattr(config.webui, "cors_origins", default_origins)
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
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # 导入并注册所有路由
    from deepsearch.webui.api.database import router as database
    from deepsearch.webui.api.endpoints.monitoring.cache_api import router as cache_api
    from deepsearch.webui.api.endpoints.system.system import router as system
    from deepsearch.webui.api.endpoints.system.health import router as health
    from deepsearch.webui.api.errors import router as errors
    from deepsearch.webui.api.endpoints.monitor.monitor_api import router as monitor_api
    from deepsearch.webui.api.endpoints.system.config import router as config
    from deepsearch.webui.api.endpoints.system.logs import router as logs
    from deepsearch.webui.api.endpoints.data.data import router as data
    from deepsearch.webui.api.endpoints.data.data_source import router as data_source
    from deepsearch.webui.api.proxy import router as proxy
    from deepsearch.webui.api.endpoints.system.system_info import router as system_info
    from deepsearch.webui.api.endpoints.trading.market import router as market
    from deepsearch.webui.api.endpoints.trading.chart import router as chart
    from deepsearch.webui.api.endpoints.qmt.qmt import router as qmt
    from deepsearch.webui.api.endpoints.data.data_unified import router as data_unified
    from deepsearch.webui.api.endpoints.monitoring.analytics import router as analytics
    from deepsearch.webui.api.endpoints.qmt.qmt_subscription import router as qmt_subscription
    from deepsearch.webui.api.endpoints.trading.market_overview import router as market_overview
    from deepsearch.webui.api.stock_comment import router as stock_comment
    from deepsearch.webui.api.endpoints.data.akshare_apis import router as akshare_apis
    from deepsearch.webui.api.endpoints.amazingdata import router as amazingdata_api
    from deepsearch.webui.api.endpoints.route_adapter import router as route_adapter

    app.include_router(monitor_api, prefix="/api/monitor", tags=["Monitor"])
    app.include_router(config, prefix="/api/system/config", tags=["Config"])
    app.include_router(system, prefix="/api/system", tags=["System"])
    app.include_router(system_info)  # 系统信息路由
    app.include_router(logs, prefix="/api/system/logs", tags=["Logs"])
    app.include_router(data, prefix="/api/data", tags=["Data"])
    app.include_router(data_source, tags=["DataSource"])  # 已包含 /api/data-source 前缀
    app.include_router(database, prefix="/api/database", tags=["Database"])
    app.include_router(cache_api, prefix="/api/cache", tags=["Cache"])
    app.include_router(health, prefix="/api/health", tags=["Health"])
    app.include_router(errors, prefix="/api/frontend", tags=["Frontend Errors"])
    app.include_router(proxy, tags=["Workers Proxy"])  # 已包含 /api/workers 前缀
    app.include_router(market, tags=["Market"])  # 市场数据路由，已包含 /api/market 前缀
    app.include_router(chart, tags=["Chart"])  # 图表数据路由，已包含 /api/chart 前缀
    app.include_router(qmt, tags=["QMT"])  # QMT数据路由，已包含 /api/qmt 前缀
    app.include_router(qmt_subscription, tags=["QMT Subscription"])  # QMT订阅管理路由
    app.include_router(data_unified, tags=["UnifiedData"])  # 统一数据API，已包含 /api/data 前缀
    app.include_router(analytics, tags=["Analytics"])  # 分析API，已包含 /api/analytics 前缀
    app.include_router(market_overview, tags=["MarketOverview"])  # 市场总貌API
    app.include_router(stock_comment, tags=["StockComment"])  # 千股千评API
    app.include_router(akshare_apis, tags=["AkShareAPIs"])  # AkShare API列表
    app.include_router(amazingdata_api, tags=["AmazingData"])  # AmazingData全部35个API接口

    # 数据源状态管理API
    try:
        from deepsearch.webui.api.endpoints.data.data_source_status import router as data_source_status
        app.include_router(data_source_status, tags=["DataSource"])  # 数据源管理API
        logger.info("数据源状态API已注册")
    except ImportError as e:
        logger.warning(f"数据源状态API模块加载失败: {e}")
    
    # 数据源监控API
    try:
        from deepsearch.webui.api.endpoints.data.data_source_monitor_api import router as data_source_monitor_api
        app.include_router(data_source_monitor_api, tags=["DataSourceMonitor"])  # 数据源监控API
        logger.info("数据源监控API已注册")
    except ImportError as e:
        logger.warning(f"数据源监控API模块加载失败: {e}")
    
    # 数据源能力对比API
    try:
        from deepsearch.webui.api.endpoints.data.data_source_capability_api import router as data_source_capability_api
        app.include_router(data_source_capability_api, tags=["DataSourceCapability"])  # 数据源能力API
        logger.info("数据源能力对比API已注册")
    except ImportError as e:
        logger.warning(f"数据源能力API模块加载失败: {e}")
    
    # 数据源配置管理API
    try:
        from deepsearch.webui.api.endpoints.data.data_source_config_api import router as data_source_config_api
        app.include_router(data_source_config_api, tags=["DataSourceConfig"])  # 数据源配置API
        # data_source_config_api.setup_callbacks()  # 设置配置回调 - router对象没有这个方法
        logger.info("数据源配置API已注册")
    except ImportError as e:
        logger.warning(f"数据源配置API模块加载失败: {e}")

    # 数据源测试API
    # 注意：已禁用旧的test_data_source路由，避免与datasource_manager中的新路由冲突 (2025-09-18)
    # 新的测试端点在datasource_manager中实现，包含了更好的错误处理和AmazingData支持
    # try:
    #     from deepsearch.webui.api.endpoints.data.test_data_source import router as test_data_source
    #     app.include_router(test_data_source, tags=["DataSourceTest"])  # 数据源测试API，包含 /api/data-source 前缀
    #     logger.info("数据源测试API已注册")
    # except ImportError as e:
    #     logger.warning(f"数据源测试API模块加载失败: {e}")

    # MiniQMT API
    try:
        from deepsearch.webui.api.endpoints.qmt.miniqmt import router as miniqmt
        app.include_router(miniqmt, tags=["MiniQMT"])  # MiniQMT数据路由，已包含 /api/miniqmt 前缀
    except ImportError:
        logger.warning("MiniQMT API 模块未找到，跳过注册")

    # 数据库连接管理API
    try:
        from deepsearch.webui.api.endpoints.system.database_manager import router as database_manager
        app.include_router(database_manager, prefix="/api/system/database", tags=["Database Management"])
        logger.info("数据库连接管理API已注册")
    except ImportError as e:
        logger.warning(f"数据库连接管理API模块加载失败: {e}")
    
    # 数据源CRUD管理API
    try:
        from deepsearch.webui.api.endpoints.datasources.datasource_manager import (
            router as datasource_manager,
            data_source_router
        )
        app.include_router(datasource_manager, tags=["DataSource Management"])
        app.include_router(data_source_router, tags=["DataSource Compatibility"])
        logger.info("数据源CRUD管理API已注册")
    except ImportError as e:
        logger.warning(f"数据源CRUD管理API模块加载失败: {e}")
    
    # AKShare数据源集成API
    try:
        from deepsearch.webui.api.endpoints.datasources.akshare_integration import router as akshare_api
        app.include_router(akshare_api, tags=["AKShare Integration"])
        logger.info("AKShare数据源API已注册")
    except ImportError as e:
        logger.warning(f"AKShare数据源API模块加载失败: {e}")
    
    # Backtest API
    try:
        from deepsearch.webui.api.endpoints.trading.backtest_api import router as backtest_api
        app.include_router(backtest_api, tags=["Backtest"])  # 回测API，已包含 /api/backtest 前缀
        logger.info("回测API已注册")
    except ImportError as e:
        logger.warning(f"回测API模块加载失败: {e}")
    
    # Data Source Monitor API
    try:
        from deepsearch.webui.api.monitor.data_source_api import router as data_source_api
        app.include_router(data_source_api, tags=["DataSourceMonitor"])  # 数据源监控API
        logger.info("数据源监控API已注册")
    except ImportError as e:
        logger.warning(f"数据源监控API模块加载失败: {e}")

    # Data Source Management API (新增)
    try:
        from deepsearch.webui.api.endpoints.datasources.datasource_management_api import router as datasource_management_api
        app.include_router(datasource_management_api, tags=["DataSource Management V2"])
        logger.info("数据源管理API V2已注册")
    except ImportError as e:
        logger.warning(f"数据源管理API V2模块加载失败: {e}")

    # 注册缓存管理API (P2级新增真实实现)
    try:
        from deepsearch.webui.api.endpoints.cache import router as cache_api
        app.include_router(cache_api, prefix="/api", tags=["Cache Management"])
        logger.info("缓存管理API已注册（真实实现）")
    except ImportError as e:
        logger.warning(f"缓存管理API模块加载失败: {e}")

    # 注册图表数据API (P2级新增真实实现)
    try:
        from deepsearch.webui.api.endpoints.chart import router as chart_api_v2
        app.include_router(chart_api_v2, prefix="/api", tags=["Chart Data V2"])
        logger.info("图表数据API V2已注册（真实实现）")
    except ImportError as e:
        logger.warning(f"图表数据API V2模块加载失败: {e}")

    # 注册市场分析API (P2级新增真实实现)
    try:
        from deepsearch.webui.api.endpoints.market import router as market_api_v2
        app.include_router(market_api_v2, prefix="/api", tags=["Market Analysis V2"])
        logger.info("市场分析API V2已注册（真实实现）")
    except ImportError as e:
        logger.warning(f"市场分析API V2模块加载失败: {e}")

    # 注册市场数据API
    try:
        from deepsearch.webui.api.endpoints.data.market_data_api import router as market_data_api
        app.include_router(market_data_api, tags=["Market Data"])
        logger.info("市场数据API已注册")
    except ImportError as e:
        logger.warning(f"市场数据API模块加载失败: {e}")

    # 注册市场概览和排行榜API
    try:
        from deepsearch.webui.api.endpoints.data.market_overview_api import router as market_overview_api
        app.include_router(market_overview_api, tags=["Market Overview"])
        logger.info("市场概览和排行榜API已注册")
    except ImportError as e:
        logger.warning(f"市场概览API模块加载失败: {e}")

    # 注册AmazingData API (P4级新增)
    try:
        from deepsearch.webui.api.endpoints.amazingdata import main_router as amazingdata_router
        app.include_router(amazingdata_router, tags=["AmazingData"])
        logger.info("AmazingData API已注册（37个接口）")
    except ImportError as e:
        logger.warning(f"AmazingData API模块加载失败: {e}")

    # 注册监控指标API
    try:
        from deepsearch.webui.api.endpoints.monitoring.metrics_api import router as metrics_api
        app.include_router(metrics_api, tags=["Metrics"])
        logger.info("监控指标API已注册")
    except ImportError as e:
        logger.warning(f"监控指标API模块加载失败: {e}")

    # 注释掉 Cloudflare Tunnel API，因为不需要映射 webui 端口
    # Cloudflare Tunnel 已移除（使用 Workers 代理方案）

    # 注册路由适配器（必须放在最后，作为catch-all路由）
    app.include_router(route_adapter, tags=["RouteAdapter"])
    logger.info("API路由适配器已注册，处理前后端API不匹配问题")

    return app


# 创建默认应用实例
app = create_app()




@app.get("/")
async def root():
    """根路径，返回前端页面或API信息。"""
    try:
        # 检查是否定义了static_dir
        if 'static_dir' in globals():
            index_file = static_dir / "index.html"
            if index_file.exists():
                return FileResponse(str(index_file))
    except Exception as e:
        logger.debug(f"无法加载静态文件: {e}")
    
    # 返回API信息而不是错误
    return JSONResponse({
        "message": "DeepSearch Web UI Backend",
        "version": "0.1.0",
        "api_docs": "/docs",
        "health_check": "/api/health",
        "note": "Frontend is running separately on port 3000"
    })


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
                    "data": app_state.monitor_api.get_health_status() if app_state.monitor_api else {}
                }
                await websocket.send_json(status)

    except WebSocketDisconnect:
        await app_state.websocket_manager.remove_connection(websocket)
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        await app_state.websocket_manager.remove_connection(websocket)


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """健康检查端点"""
    if app_state.monitor_api:
        health_status = app_state.monitor_api.get_health_status()
        return {
            "status": "healthy" if health_status.get("status") == "healthy" else "unhealthy",
            "details": health_status
        }
    return {"status": "starting", "details": {}}


@app.post("/api/frontend/errors")
async def report_frontend_error(error: dict):
    """前端错误报告端点"""
    # 只在开发环境记录详细错误
    if get_config().env == "dev":
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
    from deepsearch.config import get_config
    
    # 开发环境运行
    config = get_config()
    manager = get_server_manager()
    uvicorn.run(
        "deepsearch.webui.server:app",
        host=config.webui.backend_host,
        port=config.webui.backend_port,
        reload=config.webui.reload,
        log_level="info"
    )
