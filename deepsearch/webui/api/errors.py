"""
前端错误日志 API
收集和管理前端错误信息
"""
from __future__ import annotations


import asyncio
import json
from collections import deque
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger

router = APIRouter()

# 错误缓存（最多保存100条）
error_buffer: deque[Dict[str, Any]] = deque(maxlen=100)
# SSE 客户端列表
sse_clients: list[asyncio.Queue[Dict[str, Any]]] = []


@router.post("/errors")
async def log_frontend_error(error: Dict[str, Any]) -> Dict[str, Any]:
    """
    接收前端错误日志

    Args:
        error: 错误信息

    Returns:
        确认信息
    """
    try:
        # 添加服务器端时间戳
        error["server_timestamp"] = datetime.now().isoformat()

        # 添加到缓冲区
        error_buffer.appendleft(error)

        # 记录到日志
        level = error.get("level", "error")
        error_type = error.get("type", "unknown")
        message = error.get("message", "No message")

        # 特殊处理 Redis 相关错误
        if error.get("category") == "redis":
            full_error = error.get("fullError", message)
            logger.warning(f"前端检测到 Redis 错误: {full_error}")
            logger.debug(f"完整错误信息: {json.dumps(error, ensure_ascii=False)}")
        else:
            log_message = f"[前端{error_type}] {message}"

            if level == "warning":
                logger.warning(log_message)
            else:
                logger.error(log_message)

            # 如果有堆栈信息，也记录下来
            if error.get("stack"):
                logger.debug(f"错误堆栈: {error['stack']}")

        # 通知所有 SSE 客户端
        await notify_sse_clients(error)

        return {"status": "success", "message": "错误已记录", "error_id": error.get("id")}

    except Exception as e:
        logger.error(f"记录前端错误失败: {e}")
        raise HTTPException(status_code=500, detail="记录错误失败")


@router.get("/errors")
async def get_frontend_errors(limit: int = 50, error_type: Optional[str] = None) -> Dict[str, Any]:
    """
    获取前端错误列表

    Args:
        limit: 返回的错误数量
        error_type: 过滤的错误类型

    Returns:
        错误列表
    """
    errors = list(error_buffer)

    # 过滤错误类型
    if error_type:
        errors = [e for e in errors if e.get("type") == error_type]

    # 限制返回数量
    errors = errors[:limit]

    return {
        "status": "success",
        "errors": errors,
        "total": len(error_buffer),
        "filtered": len(errors),
    }


@router.delete("/errors")
async def clear_frontend_errors() -> Dict[str, Any]:
    """
    清空前端错误日志

    Returns:
        清空结果
    """
    error_buffer.clear()
    return {"status": "success", "message": "错误日志已清空"}


@router.get("/errors/stream")
async def error_event_stream(request: Request):
    """
    SSE 错误事件流
    实时推送错误信息
    """

    async def event_generator():
        # 创建一个队列来接收错误
        client_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
        sse_clients.append(client_queue)

        try:
            # 发送初始连接消息
            yield f"data: {json.dumps({'type': 'connected', 'timestamp': datetime.now().isoformat()})}\n\n"

            while True:
                # 检查客户端是否断开
                if await request.is_disconnected():
                    break

                try:
                    # 等待新的错误（超时1秒）
                    error = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(error)}\n\n"
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield ": heartbeat\n\n"

        finally:
            # 清理客户端
            sse_clients.remove(client_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def notify_sse_clients(error: Dict[str, Any]):
    """通知所有 SSE 客户端"""
    for client_queue in sse_clients:
        try:
            await client_queue.put(error)
        except Exception as e:
            logger.debug(f"通知 SSE 客户端失败: {e}")


@router.get("/errors/stats")
async def get_error_stats() -> Dict[str, Any]:
    """
    获取错误统计信息

    Returns:
        统计信息
    """
    errors = list(error_buffer)

    # 按类型统计
    type_stats: dict[str, int] = {}
    for error in errors:
        error_type = error.get("type", "unknown")
        type_stats[error_type] = type_stats.get(error_type, 0) + 1

    # 按级别统计
    level_stats: dict[str, int] = {}
    for error in errors:
        level = error.get("level", "error")
        level_stats[level] = level_stats.get(level, 0) + 1

    # 最近一小时的错误数
    recent_errors = 0
    one_hour_ago = datetime.now().timestamp() - 3600
    for error in errors:
        try:
            error_time = datetime.fromisoformat(error.get("timestamp", "")).timestamp()
            if error_time > one_hour_ago:
                recent_errors += 1
        except Exception as e:
            # Skip invalid timestamp entries
            logger.debug(f"Invalid timestamp in error entry: {e}")
            pass

    return {
        "status": "success",
        "stats": {
            "total": len(errors),
            "by_type": type_stats,
            "by_level": level_stats,
            "recent_hour": recent_errors,
            "sse_clients": len(sse_clients),
        },
    }
