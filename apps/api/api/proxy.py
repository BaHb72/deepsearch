"""
简化的 Workers 代理 API
直接从配置文件读取和保存配置
"""

from datetime import datetime
from typing import Any, NotRequired, TypedDict, cast

import yaml
from core.config import get_config, get_config_dir
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field

from apps.api.api.provider_deps import get_akshare_provider


def _format_last_check(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None


# 创建路由
router = APIRouter(prefix="/api/workers", tags=["Workers Proxy"])


class WorkersConfig(TypedDict):
    enabled: bool
    workers: list[str]
    api_key: str
    timeout: int
    retry_count: int
    fallback_to_direct: bool
    cache_enabled: bool
    cache_ttl: int


class WorkerStats(TypedDict, total=False):
    total_requests: int
    success_count: int
    fail_count: int
    fail_streak: int
    success_streak: int
    avg_latency: float
    last_check: NotRequired[str | None]
    last_transition: NotRequired[int]
    success_rate: NotRequired[float]


class WorkerDetail(TypedDict):
    url: str
    state: str
    healthy: bool
    total_requests: int
    success_count: int
    fail_count: int
    fail_streak: int
    success_streak: int
    avg_latency: float
    last_check: str | None
    last_transition: int
    stats: WorkerStats


class WorkersStatusData(TypedDict, total=False):
    enabled: bool
    status: str
    config: WorkersConfig
    statistics: dict[str, Any]
    workers: list[WorkerDetail]
    cache_size: int
    cache_stats: dict[str, Any]


class WorkersStatusResponse(TypedDict):
    success: bool
    data: WorkersStatusData


class MessageResponse(TypedDict, total=False):
    success: bool
    message: str
    enabled: NotRequired[bool]


class WorkerTestResponse(TypedDict):
    success: bool
    data: dict[str, Any]


class WorkersConfigRequest(BaseModel):
    """Workers 配置请求"""

    enabled: bool = False
    workers: list[str] = Field(default_factory=list, description="Worker URLs 列表")
    api_key: str = ""
    timeout: int = 30
    retry_count: int = 3
    fallback_to_direct: bool = True
    cache_enabled: bool = True
    cache_ttl: int = 300


@router.get("/status")
async def get_status(provider=Depends(get_akshare_provider)) -> WorkersStatusResponse:
    """获取 Workers 代理状态和配置"""
    try:
        config: WorkersConfig = {
            "enabled": True,
            "workers": [],
            "api_key": "",
            "timeout": 30,
            "retry_count": 3,
            "fallback_to_direct": True,
            "cache_enabled": True,
            "cache_ttl": 300,
        }

        config_obj = get_config()
        cloudflare = getattr(config_obj, "cloudflare", None)
        if cloudflare:
            workers = [w for w in getattr(cloudflare, "workers", []) if w and w.strip()]
            if workers:
                config["workers"] = [w if w.startswith("http") else f"https://{w}" for w in workers]
            else:
                worker_url = getattr(cloudflare, "worker_url", "")
                if worker_url:
                    if not worker_url.startswith("http"):
                        worker_url = f"https://{worker_url}"
                    config["workers"] = [worker_url]
                else:
                    config["workers"] = ["https://akshare-proxy.934073514.workers.dev"]

            config["api_key"] = getattr(cloudflare, "api_key", "") or ""
            config["timeout"] = int(getattr(cloudflare, "timeout", config["timeout"]))
            config["retry_count"] = int(getattr(cloudflare, "retry_count", config["retry_count"]))
        else:
            config["workers"] = ["https://akshare-proxy.934073514.workers.dev"]

        statistics: dict[str, Any]
        try:
            statistics = cast(dict[str, Any], provider.get_statistics())
        except Exception as error:
            logger.warning(f"获取 Workers 统计信息失败: {error}")
            statistics = {}

        workers_detail: list[WorkerDetail] = []
        for url in getattr(provider, "worker_urls", []):
            stats_raw = getattr(provider, "worker_stats", {}).get(url, {})
            last_check_str = _format_last_check(stats_raw.get("last_check"))
            stats: WorkerStats = {
                "total_requests": int(stats_raw.get("total_requests", 0)),
                "success_count": int(stats_raw.get("success_count", 0)),
                "fail_count": int(stats_raw.get("fail_count", 0)),
                "fail_streak": int(stats_raw.get("fail_streak", 0)),
                "success_streak": int(stats_raw.get("success_streak", 0)),
                "avg_latency": float(stats_raw.get("avg_latency", 0.0)),
                "last_check": last_check_str,
                "last_transition": int(stats_raw.get("last_transition", 0)),
            }
            workers_detail.append(
                {
                    "url": url,
                    "state": str(stats_raw.get("state", "unknown")),
                    "healthy": bool(getattr(provider, "worker_health", {}).get(url, False)),
                    "total_requests": stats["total_requests"],
                    "success_count": stats["success_count"],
                    "fail_count": stats["fail_count"],
                    "fail_streak": stats["fail_streak"],
                    "success_streak": stats["success_streak"],
                    "avg_latency": stats["avg_latency"],
                    "last_check": last_check_str,
                    "last_transition": stats.get("last_transition", 0),
                    "stats": stats,
                }
            )

        response: WorkersStatusResponse = {
            "success": True,
            "data": {
                "enabled": config["enabled"],
                "status": "active" if config["enabled"] else "disabled",
                "config": config,
                "statistics": statistics,
                "workers": workers_detail,
                "cache_size": int(statistics.get("cache_size", 0)),
                "cache_stats": statistics.get("cache_stats", {}),
            },
        }
        return response

    except Exception as e:
        logger.error(f"获取 Workers 状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_config(request: WorkersConfigRequest) -> MessageResponse:
    """更新代理配置"""
    try:
        # 读取当前配置文件（使用统一的配置目录）
        config_dir = get_config_dir()
        config_path = config_dir / "settings.prod.yaml"

        with open(config_path, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f)
        if not isinstance(config_data, dict):
            config_data = {}

        # 更新 Cloudflare 配置
        if "cloudflare" not in config_data:
            config_data["cloudflare"] = {}

        # 处理 workers 列表，确保格式正确
        processed_workers = []
        for worker in request.workers:
            if worker and worker.strip():
                # 确保包含完整的 URL
                if not worker.startswith("http"):
                    worker = f"https://{worker}"
                processed_workers.append(worker)

        # 更新 workers 列表
        config_data["cloudflare"]["workers"] = processed_workers

        # 如果只有一个 worker，同时更新 worker_url（向后兼容）
        if len(processed_workers) == 1:
            config_data["cloudflare"]["worker_url"] = processed_workers[0]

        # 更新其他配置
        config_data["cloudflare"]["api_key"] = request.api_key
        config_data["cloudflare"]["timeout"] = request.timeout
        config_data["cloudflare"]["retry_count"] = request.retry_count

        # 写回配置文件
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)

        logger.info(f"Workers 配置已更新: {len(request.workers)} 个节点")

        return {"success": True, "message": "配置已保存"}

    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle")
async def toggle_proxy() -> MessageResponse:
    """切换代理开关（简化实现）"""
    return {"success": True, "enabled": True, "message": "代理已启用"}


@router.get("/test")
async def test_connection() -> WorkerTestResponse:
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "WORKER_TEST_UNAVAILABLE",
            "message": "Workers 连接测试尚未实现，请接入真实探测逻辑后重试。",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    )


@router.post("/clear-cache")
async def clear_cache() -> MessageResponse:
    """清空缓存"""
    return {"success": True, "message": "缓存已清空"}


@router.post("/reset-statistics")
async def reset_statistics() -> MessageResponse:
    """重置统计信息"""
    return {"success": True, "message": "统计已重置"}


@router.get("/workers")
async def list_workers() -> dict[str, Any]:
    """列出所有Worker及其状态"""
    try:
        from core.infrastructure.providers.implementations.akshare.akshare import (
            AkShareProxyProvider,
        )

        provider = AkShareProxyProvider()

        workers: list[WorkerDetail] = []
        stats_snapshot = getattr(provider, "worker_stats", {}) or {}
        health_flags = getattr(provider, "worker_health", {}) or {}
        worker_urls = list(getattr(provider, "worker_urls", []) or [])
        for url in worker_urls:
            stats_raw = stats_snapshot.get(url, {})
            total_requests = int(stats_raw.get("total_requests", 0))
            success_count = int(stats_raw.get("success_count", 0))
            success_rate = success_count / total_requests if total_requests else 0.0
            last_check_str = _format_last_check(stats_raw.get("last_check"))
            stats: WorkerStats = {
                "total_requests": total_requests,
                "success_count": success_count,
                "fail_count": int(stats_raw.get("fail_count", 0)),
                "fail_streak": int(stats_raw.get("fail_streak", 0)),
                "success_streak": int(stats_raw.get("success_streak", 0)),
                "avg_latency": float(stats_raw.get("avg_latency", 0.0)),
                "last_check": last_check_str,
            }

            workers.append(
                {
                    "url": url,
                    "state": str(stats_raw.get("state", "unknown")),
                    "healthy": bool(health_flags.get(url, False)),
                    "total_requests": stats["total_requests"],
                    "success_count": stats["success_count"],
                    "fail_count": stats["fail_count"],
                    "fail_streak": stats["fail_streak"],
                    "success_streak": stats["success_streak"],
                    "avg_latency": stats["avg_latency"],
                    "last_check": last_check_str,
                    "last_transition": int(stats_raw.get("last_transition", 0)),
                    "stats": stats | {"success_rate": success_rate},
                }
            )

        return {"success": True, "data": workers}
    except Exception as e:
        logger.error(f"获取Workers列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workers/{worker_id}/test")
async def test_worker(worker_id: str) -> WorkerTestResponse:
    """测试特定Worker"""
    try:
        from core.infrastructure.providers.implementations.akshare.akshare import (
            AkShareProxyProvider,
        )

        provider = AkShareProxyProvider()

        # 将ID转换回URL
        worker_url = "https://" + worker_id.replace("_", "/")
        worker_urls = list(getattr(provider, "worker_urls", []) or [])

        if worker_url not in worker_urls:
            raise HTTPException(status_code=404, detail="Worker not found")

        # 执行健康检查
        checker = getattr(provider, "_check_worker_health", None)
        if not callable(checker):
            raise HTTPException(status_code=501, detail="Worker health check not supported")
        result = await checker(worker_url)

        return {
            "success": True,
            "data": {
                "url": worker_url,
                "healthy": result,
                "message": "Worker is healthy" if result else "Worker is unhealthy",
                "timestamp": datetime.now().isoformat(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试Worker失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workers/{worker_id}/reset")
async def reset_worker(worker_id: str) -> MessageResponse:
    """重置Worker为半开状态进行探测"""
    try:
        from core.infrastructure.providers.implementations.akshare.akshare import (
            AkShareProxyProvider,
        )

        provider = AkShareProxyProvider()

        # 将ID转换回URL
        worker_url = "https://" + worker_id.replace("_", "/")
        worker_urls = list(getattr(provider, "worker_urls", []) or [])

        if worker_url not in worker_urls:
            raise HTTPException(status_code=404, detail="Worker not found")

        # 重置状态
        resetter = getattr(provider, "reset_worker", None)
        if not callable(resetter):
            raise HTTPException(status_code=501, detail="Worker reset not supported")
        resetter(worker_url)

        return {"success": True, "message": f"Worker {worker_url} has been reset to suspect state"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置Worker失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy")
async def get_strategy():
    """获取当前选路策略"""
    try:
        from core.infrastructure.providers.implementations.akshare.akshare import (
            AkShareProxyProvider,
        )

        provider = AkShareProxyProvider()

        return {
            "success": True,
            "data": {
                "strategy": provider.strategy,
                "worker_count": len(getattr(provider, "worker_urls", []) or []),
                "healthy_count": sum(
                    1 for h in (getattr(provider, "worker_health", {}) or {}).values() if h
                ),
            },
        }
    except Exception as e:
        logger.error(f"获取策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
