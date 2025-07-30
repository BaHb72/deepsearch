"""
FastAPI 服务器主应用

提供 REST API 和 WebSocket 端点，为前端提供数据接口。
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from deepsearch.core import MainEngine
from deepsearch.monitoring import EventSystemMonitor, MonitorAPI

# Windows 兼容性：psycopg3 需要 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class WebSocketManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._broadcast_task: Optional[asyncio.Task] = None
        self._monitor_api: Optional[MonitorAPI] = None
        self._broadcast_interval: float = 2.0

    async def accept_connection(self, websocket: WebSocket) -> None:
        """接受新的 WebSocket 连接"""
        await websocket.accept()
        self._connections.append(websocket)
        logger.debug(f"WebSocket 连接已建立（连接数：{len(self._connections)}）")

    def remove_connection(self, websocket: WebSocket) -> None:
        """移除 WebSocket 连接"""
        if websocket in self._connections:
            self._connections.remove(websocket)
            logger.debug(f"WebSocket 连接已断开（连接数：{len(self._connections)}）")

    async def broadcast_message(self, message: dict) -> None:
        """向所有客户端广播消息"""
        if not self._connections:
            return

        message_text = json.dumps(message, ensure_ascii=False)
        failed_connections = []

        # 并发发送消息
        tasks = []
        for conn in self._connections:
            tasks.append(self._send_to_connection(conn, message_text, failed_connections))

        await asyncio.gather(*tasks, return_exceptions=True)

        # 清理失败的连接
        for conn in failed_connections:
            self.remove_connection(conn)

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
                if self._monitor_api and self._connections:
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
class AppState:
    """应用全局状态"""

    def __init__(self):
        self.websocket_manager = WebSocketManager()
        self.engine: Optional[MainEngine] = None
        self.monitor: Optional[EventSystemMonitor] = None
        self.monitor_api: Optional[MonitorAPI] = None

    def set_engine(self, engine: MainEngine) -> None:
        """设置引擎实例"""
        self.engine = engine
        logger.debug(f"引擎实例已设置：{engine}")

    def initialize_monitoring(self) -> None:
        """初始化监控组件"""
        if not self.engine:
            raise RuntimeError("引擎未设置")

        # 获取或创建监控器
        if hasattr(self.engine, '_monitor') and self.engine._monitor:
            self.monitor = self.engine._monitor
        else:
            self.monitor = EventSystemMonitor(self.engine._event_engine)

        self.monitor_api = MonitorAPI(self.monitor)

        # 确保监控器已启动
        if not hasattr(self.monitor, '_monitoring') or not self.monitor._monitoring:
            self.monitor.start()
        self.monitor_api.start()


# 全局应用状态
app_state = AppState()


async def startup_handler():
    """应用启动处理"""
    logger.debug("启动 Web UI 服务...")

    try:
        # 如果没有外部引擎，创建新的（独立运行模式）
        if not app_state.engine:
            engine = MainEngine()
            engine.initialize()
            engine.start()
            app_state.set_engine(engine)

        # 初始化监控
        app_state.initialize_monitoring()

        # 启动 WebSocket 监控广播
        await app_state.websocket_manager.start_monitoring_broadcast(app_state.monitor_api)

        logger.info("Web UI 服务启动成功")

    except Exception as e:
        logger.error(f"启动失败: {e}")
        raise


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


# 创建 FastAPI 应用
app = FastAPI(
    title="DeepSearch Web UI",
    description="DeepSearch 量化交易系统 Web 界面",
    version="0.1.0",
    on_startup=[startup_handler],
    on_shutdown=[shutdown_handler]
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件目录
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# 延迟导入 API 路由，避免循环导入
def setup_routes():
    from .api import monitor as monitor_routes
    from .api import config as config_routes
    from .api import system as system_routes
    from .api import logs as logs_routes
    from .api import data as data_routes
    from .api import database as database_routes

    app.include_router(monitor_routes.router, prefix="/api/monitor", tags=["监控"])
    app.include_router(config_routes.router, prefix="/api/config", tags=["配置"])
    app.include_router(system_routes.router, prefix="/api/system", tags=["系统"])
    app.include_router(logs_routes.router, prefix="/api/logs", tags=["日志"])
    app.include_router(data_routes.router, prefix="/api/data", tags=["数据管理"])
    app.include_router(database_routes.router, prefix="/api/database", tags=["数据库管理"])

    # 导入并注册缓存路由
    from .api import cache as cache_routes
    app.include_router(cache_routes.router, prefix="/api/cache", tags=["缓存管理"])

    # 导入并注册前端错误日志路由
    from .api import frontend_errors as frontend_errors_routes
    app.include_router(frontend_errors_routes.router, prefix="/api/frontend", tags=["前端错误"])


# 设置路由
setup_routes()


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
        app_state.websocket_manager.remove_connection(websocket)
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        app_state.websocket_manager.remove_connection(websocket)


@app.get("/health")
async def health_check():
    """健康检查端点"""
    if app_state.monitor_api:
        health_status = app_state.monitor_api.get_health_status()
        return {
            "status": "healthy" if health_status.get("status") == "healthy" else "unhealthy",
            "details": health_status
        }
    return {"status": "starting", "details": {}}


@app.get("/api/health")
async def api_health_check():
    """API健康检查端点"""
    return await health_check()


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
