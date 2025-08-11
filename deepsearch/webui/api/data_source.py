"""
数据源管理 API
提供数据源监控、测试和管理功能
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel

from deepsearch.data_providers.akshare_proxy_provider import AkShareProxyProvider

router = APIRouter(prefix="/api/data-source", tags=["数据源"])

# 全局数据提供者实例
data_provider = None


def get_data_provider() -> AkShareProxyProvider:
    """获取数据提供者实例"""
    global data_provider
    if data_provider is None:
        data_provider = AkShareProxyProvider()
    return data_provider


class WorkerTestRequest(BaseModel):
    """Worker 测试请求"""
    url: str


class DataRequest(BaseModel):
    """数据请求"""
    symbols: List[str]
    data_type: str = "realtime"  # realtime, history
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    period: Optional[str] = "daily"


@router.get("/workers")
async def get_worker_status():
    """获取所有 Worker 节点状态"""
    provider = get_data_provider()

    workers = []
    for url in provider.worker_urls:
        stats = provider.worker_stats.get(url, {})
        health = provider.worker_health.get(url, False)

        success_rate = 0
        if stats.get("total_requests", 0) > 0:
            success_rate = stats["success_count"] / stats["total_requests"]

        workers.append({
            "url": url,
            "region": url.split(".")[0].split("-")[-1] if "-" in url else "unknown",
            "healthy": health,
            "latency": round(stats.get("avg_latency", 0), 2),
            "success_rate": round(success_rate, 3),
            "total_requests": stats.get("total_requests", 0),
            "last_check": stats.get("last_check").isoformat() if stats.get("last_check") else None
        })

    return workers


@router.get("/stats")
async def get_statistics():
    """获取数据源统计信息"""
    provider = get_data_provider()
    stats = provider.get_statistics()

    # 计算额外的统计信息
    total_requests = stats.get("total_requests", 0)
    success_rate = stats.get("success_rate", 0) * 100

    # 计算平均延迟
    total_latency = 0
    latency_count = 0
    for worker_stat in stats.get("worker_stats", {}).values():
        if worker_stat["total_requests"] > 0:
            total_latency += worker_stat["avg_latency"]
            latency_count += 1

    avg_latency = total_latency / latency_count if latency_count > 0 else 0

    # 缓存命中率（模拟）
    cache_size = stats.get("cache_size", 0)
    cache_hit_rate = min(cache_size * 10, 85) if cache_size > 0 else 0  # 简化计算

    return {
        "total_requests": total_requests,
        "success_rate": round(success_rate, 1),
        "avg_latency": round(avg_latency, 2),
        "cache_hit_rate": round(cache_hit_rate, 1),
        "healthy_workers": stats.get("healthy_workers", 0),
        "total_workers": stats.get("worker_count", 0)
    }


@router.post("/test-worker")
async def test_worker(request: WorkerTestRequest):
    """测试特定 Worker 节点"""
    provider = get_data_provider()

    if request.url not in provider.worker_urls:
        raise HTTPException(status_code=404, detail="Worker 不存在")

    try:
        # 执行健康检查
        health = await provider._check_worker_health(request.url)

        if health:
            # 尝试获取测试数据
            test_result = await provider._fetch_with_fallback(
                "/health",
                {},
                max_retries=1
            )

            return {
                "success": True,
                "message": "Worker 测试成功",
                "health": health,
                "response": test_result
            }
        else:
            return {
                "success": False,
                "message": "Worker 健康检查失败",
                "health": health
            }

    except Exception as e:
        logger.error(f"Worker 测试失败: {e}")
        return {
            "success": False,
            "message": str(e),
            "health": False
        }


@router.post("/fetch")
async def fetch_data(request: DataRequest):
    """获取数据"""
    provider = get_data_provider()

    try:
        if request.data_type == "realtime":
            data = await provider.get_realtime_data(request.symbols)
            return data

        elif request.data_type == "history":
            if not request.symbols or len(request.symbols) != 1:
                raise HTTPException(
                    status_code=400,
                    detail="历史数据请求需要指定单个股票代码"
                )

            df = await provider.get_history_data(
                request.symbols[0],
                request.start_date,
                request.end_date,
                request.period
            )

            # 转换 DataFrame 为 JSON
            return {
                "symbol": request.symbols[0],
                "data": df.to_dict(orient="records") if not df.empty else []
            }

        else:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的数据类型: {request.data_type}"
            )

    except Exception as e:
        logger.error(f"数据获取失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket 日志流"""
    await websocket.accept()

    try:
        # 模拟日志流（实际应该从日志系统获取）
        log_id = 0
        while True:
            import asyncio
            import random

            await asyncio.sleep(random.uniform(1, 5))

            # 生成模拟日志
            log_levels = ["info", "warning", "error", "debug"]
            log_messages = [
                "获取实时数据成功",
                "Worker 节点响应缓慢",
                "缓存命中",
                "正在重试请求",
                "数据解析完成"
            ]

            log_entry = {
                "id": log_id,
                "timestamp": datetime.now().isoformat(),
                "level": random.choice(log_levels),
                "worker": random.choice(["us-east", "eu-west", "asia-ne"]),
                "message": random.choice(log_messages)
            }

            await websocket.send_json(log_entry)
            log_id += 1

    except WebSocketDisconnect:
        logger.info("WebSocket 日志连接断开")
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        await websocket.close()


@router.get("/config")
async def get_config():
    """获取数据源配置"""
    provider = get_data_provider()

    return {
        "provider_name": provider.name,
        "display_name": provider.display_name,
        "worker_urls": provider.worker_urls,
        "cache_ttl": provider._cache_ttl,
        "features": {
            "proxy_enabled": True,
            "cache_enabled": True,
            "health_monitoring": True,
            "auto_failover": True
        }
    }


@router.post("/refresh")
async def refresh_workers():
    """刷新 Worker 状态"""
    provider = get_data_provider()

    # 重新检查所有 Worker 健康状态
    for url in provider.worker_urls:
        health = await provider._check_worker_health(url)
        provider.worker_health[url] = health

    return {
        "message": "Worker 状态已刷新",
        "healthy_count": sum(1 for h in provider.worker_health.values() if h),
        "total_count": len(provider.worker_urls)
    }
