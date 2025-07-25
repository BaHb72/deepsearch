"""
FastAPI 服务器主应用。

提供 REST API 和 WebSocket 端点，为前端提供数据接口。
"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from deepsearch.core import MainEngine
from deepsearch.monitoring import EventSystemMonitor, MonitorAPI


# WebSocket 连接管理器
class ConnectionManager:
    """WebSocket 连接管理器。"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._broadcast_task: Optional[asyncio.Task] = None
        self._monitor_api: Optional[MonitorAPI] = None

    async def connect(self, websocket: WebSocket):
        """接受新的 WebSocket 连接。"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket 客户端已连接，当前连接数：{len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """断开 WebSocket 连接。"""
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket 客户端已断开，当前连接数：{len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """向所有连接的客户端广播消息。"""
        if not self.active_connections:
            return

        message_str = json.dumps(message, ensure_ascii=False)
        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                logger.error(f"发送消息失败：{e}")
                disconnected.append(connection)

        # 清理断开的连接
        for conn in disconnected:
            if conn in self.active_connections:
                self.disconnect(conn)

    async def start_broadcasting(self, monitor_api: MonitorAPI):
        """开始定期广播监控数据。"""
        self._monitor_api = monitor_api
        if self._broadcast_task is None or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())

    async def stop_broadcasting(self):
        """停止广播。"""
        if self._broadcast_task and not self._broadcast_task.done():
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

    async def _broadcast_loop(self):
        """定期广播监控数据。"""
        while True:
            try:
                if self._monitor_api and self.active_connections:
                    # 获取最新的监控数据
                    data = {
                        "type": "monitor_update",
                        "data": self._monitor_api.get_dashboard_data()
                    }
                    await self.broadcast(data)

                await asyncio.sleep(2)  # 每2秒更新一次

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"广播循环错误：{e}")
                await asyncio.sleep(5)


# 全局对象
manager = ConnectionManager()
engine: Optional[MainEngine] = None
monitor: Optional[EventSystemMonitor] = None
monitor_api: Optional[MonitorAPI] = None


# 设置外部传入的引擎实例
def set_engine(external_engine: MainEngine):
    """设置外部传入的MainEngine实例"""
    global engine
    engine = external_engine
    logger.info(f"Engine已设置: {engine}")


# 获取全局对象的函数
def get_engine():
    """获取引擎实例"""
    if engine is None:
        logger.warning("Engine未设置，返回None")
    return engine


def get_monitor():
    """获取监控器实例"""
    return monitor


def get_monitor_api():
    """获取监控API实例"""
    return monitor_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    global engine, monitor, monitor_api

    # 启动时
    logger.info("正在启动 DeepSearch Web UI...")

    # 初始化监控 - 使用外部传入的引擎或创建新的
    try:
        if engine is None:
            # 如果没有外部引擎，创建一个新的（独立运行模式）
            engine = MainEngine()
            engine.initialize()
            engine.start()

        # 从引擎获取监控器
        if hasattr(engine, '_monitor') and engine._monitor:
            monitor = engine._monitor
        else:
            monitor = EventSystemMonitor(engine._event_engine)

        monitor_api = MonitorAPI(monitor)

        # 确保监控器已启动
        if not hasattr(monitor, '_monitoring') or not monitor._monitoring:
            monitor.start()
        monitor_api.start()

        # 启动 WebSocket 广播
        await manager.start_broadcasting(monitor_api)

        logger.info("DeepSearch Web UI 启动成功")

    except Exception as e:
        logger.error(f"启动失败：{e}")
        raise

    yield

    # 关闭时
    logger.info("正在关闭 DeepSearch Web UI...")

    # 停止广播
    await manager.stop_broadcasting()

    # 停止监控API（但不停止监控器本身，因为它可能被主系统使用）
    if monitor_api:
        monitor_api.stop()

    logger.info("DeepSearch Web UI 已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="DeepSearch Web UI",
    description="DeepSearch 量化交易系统 Web 界面",
    version="0.1.0",
    lifespan=lifespan
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

    app.include_router(monitor_routes.router, prefix="/api/monitor", tags=["监控"])
    app.include_router(config_routes.router, prefix="/api/config", tags=["配置"])
    app.include_router(system_routes.router, prefix="/api/system", tags=["系统"])


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
    """监控数据 WebSocket 端点。"""
    await manager.connect(websocket)
    try:
        while True:
            # 保持连接，等待客户端消息
            data = await websocket.receive_text()
            # 可以处理客户端命令
            if data == "ping":
                await websocket.send_text("pong")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket 错误：{e}")
        manager.disconnect(websocket)


@app.get("/health")
async def health_check():
    """健康检查端点。"""
    if monitor_api:
        health_status = monitor_api.get_health_status()
        return {
            "status": "healthy" if health_status.get("status") == "healthy" else "unhealthy",
            "details": health_status
        }
    return {"status": "starting", "details": {}}


if __name__ == "__main__":
    import uvicorn

    # 开发环境运行
    uvicorn.run(
        "deepsearch.webui.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
