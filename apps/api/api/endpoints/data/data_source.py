"""
数据源管理 API
提供数据源监控、测试和管理功能
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel

from apps.api.api.provider_deps import get_akshare_provider

router = APIRouter(prefix="/api/data-source", tags=["数据源"])


def _worker_urls(provider: Any) -> list[str]:
    raw = getattr(provider, "worker_urls", [])
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    return []


def _worker_stats(provider: Any) -> Dict[str, Dict[str, Any]]:
    raw = getattr(provider, "worker_stats", {})
    return raw if isinstance(raw, dict) else {}


def _worker_health(provider: Any) -> Dict[str, bool]:
    raw = getattr(provider, "worker_health", {})
    return raw if isinstance(raw, dict) else {}


def _provider_name(provider: Any) -> str:
    name = getattr(provider, "name", None)
    if isinstance(name, str) and name.strip():
        return name
    return provider.__class__.__name__


def _provider_display_name(provider: Any) -> str:
    display_name = getattr(provider, "display_name", None)
    if isinstance(display_name, str) and display_name.strip():
        return display_name
    return _provider_name(provider)


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
async def get_worker_status(provider=Depends(get_akshare_provider)):
    """获取所有 Worker 节点状态"""

    workers = []
    worker_stats = _worker_stats(provider)
    worker_health = _worker_health(provider)
    for url in _worker_urls(provider):
        stats = worker_stats.get(url, {})
        health = worker_health.get(url, False)

        success_rate = 0
        if stats.get("total_requests", 0) > 0:
            success_rate = stats["success_count"] / stats["total_requests"]

        workers.append(
            {
                "url": url,
                "region": url.split(".")[0].split("-")[-1] if "-" in url else "unknown",
                "healthy": health,
                "latency": round(stats.get("avg_latency", 0), 2),
                "success_rate": round(success_rate, 3),
                "total_requests": stats.get("total_requests", 0),
                "last_check": (
                    stats.get("last_check").isoformat() if stats.get("last_check") else None
                ),
            }
        )

    return workers


@router.get("/stats")
async def get_statistics(provider=Depends(get_akshare_provider)):
    """获取数据源统计信息"""
    get_statistics_fn = getattr(provider, "get_statistics", None)
    stats = get_statistics_fn() if callable(get_statistics_fn) else {}
    if not isinstance(stats, dict):
        stats = {}

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
        "total_workers": stats.get("worker_count", 0),
    }


@router.post("/test-worker")
async def test_worker(request: WorkerTestRequest, provider=Depends(get_akshare_provider)):
    """测试特定 Worker 节点"""

    worker_urls = _worker_urls(provider)
    if request.url not in worker_urls:
        raise HTTPException(status_code=404, detail="Worker 不存在")

    try:
        if not hasattr(provider, "_check_worker_health"):
            raise HTTPException(status_code=400, detail="当前 Provider 不支持 Worker 健康检查")

        # 执行健康检查
        health = await provider._check_worker_health(request.url)

        if health:
            # 尝试获取测试数据
            test_result = await provider._fetch_with_fallback("/health", {}, max_retries=1)

            return {
                "success": True,
                "message": "Worker 测试成功",
                "health": health,
                "response": test_result,
            }
        else:
            return {"success": False, "message": "Worker 健康检查失败", "health": health}

    except Exception as e:
        logger.error(f"Worker 测试失败: {e}")
        return {"success": False, "message": str(e), "health": False}


@router.post("/fetch")
async def fetch_data(request: DataRequest, provider=Depends(get_akshare_provider)):
    """获取数据"""

    try:
        if request.data_type == "realtime":
            data = await provider.get_realtime_data(request.symbols)
            return data

        elif request.data_type == "history":
            if not request.symbols or len(request.symbols) != 1:
                raise HTTPException(status_code=400, detail="历史数据请求需要指定单个股票代码")

            df = await provider.get_history_data(
                request.symbols[0], request.start_date, request.end_date, request.period
            )

            # 转换 DataFrame 为 JSON
            return {
                "symbol": request.symbols[0],
                "data": df.to_dict(orient="records") if not df.empty else [],
            }

        else:
            raise HTTPException(status_code=400, detail=f"不支持的数据类型: {request.data_type}")

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

            await asyncio.sleep(random.uniform(1, 5))  # nosec B311 - 仅模拟退避延迟

            # 生成模拟日志
            log_levels = ["info", "warning", "error", "debug"]
            log_messages = [
                "获取实时数据成功",
                "Worker 节点响应缓慢",
                "缓存命中",
                "正在重试请求",
                "数据解析完成",
            ]

            log_entry = {
                "id": log_id,
                "timestamp": datetime.now().isoformat(),
                "level": random.choice(log_levels),  # nosec B311 - 模拟日志级别
                "worker": random.choice(["us-east", "eu-west", "asia-ne"]),  # nosec B311 - 模拟节点
                "message": random.choice(log_messages),  # nosec B311 - 模拟日志内容
            }

            await websocket.send_json(log_entry)
            log_id += 1

    except WebSocketDisconnect:
        logger.info("WebSocket 日志连接断开")
    except Exception as e:
        logger.error(f"WebSocket 错误: {e}")
        await websocket.close()


@router.get("/config")
async def get_config(provider=Depends(get_akshare_provider)):
    """获取数据源配置"""

    worker_urls = _worker_urls(provider)
    cache_ttl = getattr(provider, "_cache_ttl", {})
    if not isinstance(cache_ttl, dict):
        cache_ttl = {}

    supports_worker_health = hasattr(provider, "_check_worker_health")

    return {
        "provider_name": _provider_name(provider),
        "display_name": _provider_display_name(provider),
        "worker_urls": worker_urls,
        "cache_ttl": cache_ttl,
        "features": {
            "proxy_enabled": bool(worker_urls),
            "cache_enabled": True,
            "health_monitoring": supports_worker_health,
            "auto_failover": supports_worker_health,
        },
    }


@router.post("/refresh")
async def refresh_workers(provider=Depends(get_akshare_provider)):
    """刷新 Worker 状态"""

    worker_urls = _worker_urls(provider)
    worker_health = _worker_health(provider)
    if not hasattr(provider, "_check_worker_health"):
        return {
            "message": "当前 Provider 不支持 Worker 刷新，已跳过",
            "healthy_count": 0,
            "total_count": 0,
        }

    # 重新检查所有 Worker 健康状态
    for url in worker_urls:
        health = await provider._check_worker_health(url)
        worker_health[url] = health

    return {
        "message": "Worker 状态已刷新",
        "healthy_count": sum(1 for h in worker_health.values() if h),
        "total_count": len(worker_urls),
    }
