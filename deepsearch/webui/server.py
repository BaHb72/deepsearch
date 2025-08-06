"""
FastAPI 服务器主应用

提供 REST API 和 WebSocket 端点，为前端提供数据接口。
"""
from __future__ import annotations

import asyncio
import json
import sys
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from deepsearch.core import MainEngine
from deepsearch.diagnostics import diagnostic_logger, log_diagnostic
from deepsearch.monitoring import EventSystemMonitor, MonitorAPI

# Windows 兼容性：psycopg3 需要 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 记录模块导入
log_diagnostic("MODULE_IMPORT", "server.py", {
    "imports": ["MainEngine", "EventSystemMonitor", "MonitorAPI", "FastAPI"],
    "platform": sys.platform
})


class WebSocketManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._connections_lock = asyncio.Lock()  # 添加异步锁保护连接列表
        self._broadcast_task: Optional[asyncio.Task] = None
        self._monitor_api: Optional[MonitorAPI] = None
        self._broadcast_interval: float = 2.0

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
        """向所有客户端广播消息"""
        # 获取连接副本，避免长时间持有锁
        async with self._connections_lock:
            if not self._connections:
                return
            connections_copy = self._connections.copy()

        message_text = json.dumps(message, ensure_ascii=False)
        failed_connections = []

        # 并发发送消息
        tasks = []
        for conn in connections_copy:
            tasks.append(self._send_to_connection(conn, message_text, failed_connections))

        await asyncio.gather(*tasks, return_exceptions=True)

        # 清理失败的连接
        for conn in failed_connections:
            await self.remove_connection(conn)

    async def _send_to_connection(self, conn: WebSocket, message: str, failed_list: list) -> None:
        """发送消息到单个连接"""
        try:
            await conn.send_text(message)
        except Exception as e:
            logger.debug(f"消息发送失败: {e}")
            failed_list.append(conn)

    async def start_monitoring_broadcast(self, monitor_api: MonitorAPI) -> None:
        """启动监控数据广播"""
        self._monitor_api = monitor_api
        if not self._broadcast_task or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring_broadcast(self) -> None:
        """停止监控数据广播"""
        if self._broadcast_task and not self._broadcast_task.done():
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

    async def _monitoring_loop(self) -> None:
        """监控数据广播循环"""
        while True:
            try:
                # 检查是否有连接，避免不必要的数据收集
                async with self._connections_lock:
                    has_connections = bool(self._connections)

                if self._monitor_api and has_connections:
                    data = {
                        "type": "monitor_update",
                        "data": self._monitor_api.get_dashboard_data()
                    }
                    await self.broadcast_message(data)

                await asyncio.sleep(self._broadcast_interval)

            except asyncio.CancelledError:
                logger.debug("监控广播循环已停止")
                break
            except Exception as e:
                logger.error(f"监控广播错误: {e}")
                await asyncio.sleep(5)  # 错误后等待更长时间

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
        from deepsearch.core.context import get_context
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
            from deepsearch.core.unified_components import EventEngineComponent
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

            # 初始化监控
            app_state.initialize_monitoring()

            # 启动 WebSocket 监控广播
            if app_state.monitor_api:
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
        version="0.1.0"
    )

    # 存储全局应用状态
    app.state.app_state = app_state

    # 设置启动和关闭处理
    app.add_event_handler("startup", create_startup_handler(app_state))
    app.add_event_handler("shutdown", create_shutdown_handler(app_state))

    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应该限制具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 挂载静态文件
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # 导入并注册所有路由
    from deepsearch.webui.api import (
        database, cache, system, health, frontend_errors,
        monitor, config, logs, data
    )

    app.include_router(monitor.router, prefix="/api/monitor", tags=["Monitor"])
    app.include_router(config.router, prefix="/api/config", tags=["Config"])
    app.include_router(system.router, prefix="/api/system", tags=["System"])
    app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
    app.include_router(data.router, prefix="/api/data", tags=["Data"])
    app.include_router(database.router, prefix="/api/database", tags=["Database"])
    app.include_router(cache.router, prefix="/api/cache", tags=["Cache"])
    app.include_router(health.router, prefix="/api/health", tags=["Health"])
    app.include_router(frontend_errors.router, prefix="/api/frontend", tags=["Frontend Errors"])

    return app


# 创建默认应用实例
app = create_app()




@app.get("/")
async def root():
    """根路径，返回前端页面。"""
    index_file = static_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "DeepSearch Web UI", "version": "0.1.0"}


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
