#!/usr/bin/env python
"""
后端调试脚本
用于启动后端并输出详细的调试信息
"""

import asyncio
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from loguru import logger

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# 配置详细日志
logger.remove()  # 移除默认处理器
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level="DEBUG",
)


def debug_system_status_endpoint():
    """
    为 /system/status 端点添加调试信息
    """
    from deepsearch.webui.api.endpoints.system import system

    original_get_status = system.get_system_status

    async def debug_get_system_status():
        """带调试信息的系统状态端点"""
        request_time = datetime.now()
        logger.debug(f"[DEBUG] /system/status 被调用 - {request_time}")

        # 检查 app_state
        try:
            from deepsearch.webui.server import app_state

            logger.debug(f"[DEBUG] app_state = {app_state}")
            logger.debug(f"[DEBUG] app_state.engine = {getattr(app_state, 'engine', 'NO_ATTR')}")

            if hasattr(app_state, "engine"):
                engine = app_state.engine
                logger.debug(f"[DEBUG] engine is None = {engine is None}")
                if engine:
                    logger.debug(f"[DEBUG] engine type = {type(engine).__name__}")
                    logger.debug(
                        f"[DEBUG] engine.is_running() = {engine.is_running() if hasattr(engine, 'is_running') else 'NO_METHOD'}"
                    )
        except Exception as e:
            logger.error(f"[DEBUG] 检查 app_state 失败: {e}")

        # 调用原始函数
        try:
            result = await original_get_status()
            logger.debug(f"[DEBUG] /system/status 返回成功: {result}")
            return result
        except Exception as e:
            logger.error(f"[DEBUG] /system/status 执行失败: {e}")
            raise
        finally:
            response_time = (datetime.now() - request_time).total_seconds() * 1000
            logger.info(f"[DEBUG] /system/status 响应时间: {response_time:.2f}ms")

    # 替换原函数
    system.get_system_status = debug_get_system_status
    logger.info("[DEBUG] 已为 /system/status 端点添加调试信息")


def track_requests():
    """
    跟踪所有 API 请求
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request

    class RequestTrackingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            start_time = time.time()

            # 记录请求
            logger.info(f"[REQUEST] {request.method} {request.url.path}")

            # 处理请求
            response = await call_next(request)

            # 记录响应
            duration = (time.time() - start_time) * 1000
            logger.info(
                f"[RESPONSE] {request.method} {request.url.path} - {response.status_code} ({duration:.2f}ms)"
            )

            return response

    return RequestTrackingMiddleware


async def run_debug_server():
    """
    启动调试模式的后端服务
    """
    logger.info("=" * 60)
    logger.info("启动后端调试模式")
    logger.info("=" * 60)

    # 设置环境变量
    os.environ["LOG__LEVEL"] = "DEBUG"
    os.environ["WEBUI__BACKEND_PORT"] = "8000"

    # 导入并配置服务器
    from deepsearch.webui.server import create_app

    logger.info("[1] 创建 FastAPI 应用...")
    app = create_app()

    # 添加调试中间件
    logger.info("[2] 添加调试中间件...")
    app.add_middleware(track_requests())

    # 添加端点调试
    logger.info("[3] 添加端点调试...")
    debug_system_status_endpoint()

    # 启动服务器
    logger.info("[4] 启动 Uvicorn 服务器...")
    import uvicorn

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="debug",
        access_log=True,
        reload=False,  # 调试时不自动重载
    )

    server = uvicorn.Server(config)

    logger.info("=" * 60)
    logger.info("后端服务已启动在 http://localhost:8000")
    logger.info("API 文档: http://localhost:8000/docs")
    logger.info("=" * 60)

    await server.serve()


def main():
    """
    主函数
    """
    try:
        # 运行调试服务器
        asyncio.run(run_debug_server())
    except KeyboardInterrupt:
        logger.info("\n收到中断信号，正在关闭...")
    except Exception as e:
        logger.error(f"启动失败: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
