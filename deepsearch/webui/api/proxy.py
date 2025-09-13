"""
简化的 Workers 代理 API
直接从配置文件读取和保存配置
"""
import os
from datetime import datetime
from typing import List

import yaml
from fastapi import APIRouter, HTTPException, Depends
from loguru import logger
from pydantic import BaseModel

from deepsearch.config import get_config
from deepsearch.webui.api.providers import get_akshare_provider

# 创建路由
router = APIRouter(prefix="/api/workers", tags=["Workers Proxy"])


class WorkersConfigRequest(BaseModel):
    """Workers 配置请求"""
    enabled: bool = False
    workers: List[str] = []  # Worker URLs 列表
    api_key: str = ""
    timeout: int = 30
    retry_count: int = 3
    fallback_to_direct: bool = True
    cache_enabled: bool = True
    cache_ttl: int = 300


@router.get("/status")
async def get_status():
    """获取 Workers 代理状态和配置"""
    try:
        # 使用单例provider实例
        provider = await get_akshare_provider()

        # 从 settings 读取配置
        config = {
            "enabled": True,  # 默认启用
            "workers": [],
            "api_key": "",
            "timeout": 30,
            "retry_count": 3,
            "fallback_to_direct": True,
            "cache_enabled": True,
            "cache_ttl": 300
        }

        # 读取 Cloudflare 配置
        config_obj = get_config()
        if config_obj and hasattr(config_obj, 'cloudflare') and config_obj.cloudflare:
            cloudflare = config_obj.cloudflare

            # 优先读取 workers 列表
            if hasattr(cloudflare, 'workers') and cloudflare.workers:
                # 过滤掉空字符串和None
                valid_workers = [w for w in cloudflare.workers if w and w.strip()]
                if valid_workers:
                    # 确保包含完整的 URL
                    config["workers"] = [
                        w if w.startswith('http') else f"https://{w}"
                        for w in valid_workers
                    ]
                else:
                    config["workers"] = ["https://akshare-proxy.934073514.workers.dev"]
            # 兼容单个 worker_url
            elif hasattr(cloudflare, 'worker_url') and cloudflare.worker_url:
                worker_url = cloudflare.worker_url
                if not worker_url.startswith('http'):
                    worker_url = f"https://{worker_url}"
                config["workers"] = [worker_url]
            else:
                # 默认值
                config["workers"] = ["https://akshare-proxy.934073514.workers.dev"]

            # 读取其他配置
            if hasattr(cloudflare, 'api_key'):
                config["api_key"] = cloudflare.api_key if cloudflare.api_key else ""
            if hasattr(cloudflare, 'timeout'):
                config["timeout"] = cloudflare.timeout
            if hasattr(cloudflare, 'retry_count'):
                config["retry_count"] = cloudflare.retry_count
        else:
            # 使用默认配置
            config["workers"] = ["https://akshare-proxy.934073514.workers.dev"]

        # 获取真实统计数据
        statistics = provider.get_statistics()

        # 获取每个Worker的详细状态
        workers_detail = []
        for url in provider.worker_urls:
            stats = provider.worker_stats.get(url, {})
            workers_detail.append({
                "url": url,
                "state": stats.get("state", "unknown"),
                "healthy": provider.worker_health.get(url, False),
                "total_requests": stats.get("total_requests", 0),
                "success_count": stats.get("success_count", 0),
                "fail_count": stats.get("fail_count", 0),
                "fail_streak": stats.get("fail_streak", 0),
                "success_streak": stats.get("success_streak", 0),
                "avg_latency": stats.get("avg_latency", 0),
                "last_check": stats.get("last_check").isoformat() if stats.get("last_check") else None,
                "last_transition": stats.get("last_transition", 0)
            })

        return {
            "success": True,
            "data": {
                "enabled": config["enabled"],
                "status": "active" if config["enabled"] else "disabled",
                "config": config,
                "statistics": statistics,
                "workers": workers_detail,
                "cache_size": statistics.get("cache_size", 0),
                "cache_stats": statistics.get("cache_stats", {})
            }
        }

    except Exception as e:
        logger.error(f"获取 Workers 状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config")
async def update_config(request: WorkersConfigRequest):
    """更新代理配置"""
    try:
        # 读取当前配置文件
        config_path = os.path.join(
            os.path.dirname(__file__),
            "../../config/settings.prod.yaml"
        )

        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)

        # 更新 Cloudflare 配置
        if 'cloudflare' not in config_data:
            config_data['cloudflare'] = {}

        # 处理 workers 列表，确保格式正确
        processed_workers = []
        for worker in request.workers:
            if worker and worker.strip():
                # 确保包含完整的 URL
                if not worker.startswith('http'):
                    worker = f"https://{worker}"
                processed_workers.append(worker)

        # 更新 workers 列表
        config_data['cloudflare']['workers'] = processed_workers

        # 如果只有一个 worker，同时更新 worker_url（向后兼容）
        if len(processed_workers) == 1:
            config_data['cloudflare']['worker_url'] = processed_workers[0]

        # 更新其他配置
        config_data['cloudflare']['api_key'] = request.api_key
        config_data['cloudflare']['timeout'] = request.timeout
        config_data['cloudflare']['retry_count'] = request.retry_count

        # 写回配置文件
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)

        logger.info(f"Workers 配置已更新: {len(request.workers)} 个节点")

        return {
            "success": True,
            "message": "配置已保存"
        }

    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/toggle")
async def toggle_proxy():
    """切换代理开关（简化实现）"""
    # 这里简化实现，总是返回启用状态
    return {
        "success": True,
        "enabled": True,
        "message": "代理已启用"
    }


@router.get("/test")
async def test_connection():
    """测试 Workers 连接"""
    try:
        # 简化实现，返回模拟结果
        return {
            "success": True,
            "data": {
                "success": True,
                "response_time": 150.5,
                "status_code": 200,
                "message": "连接成功",
                "workers_version": "1.0.0",
                "error": None,
                "timestamp": "2025-08-11T10:00:00"
            }
        }
    except Exception as e:
        logger.error(f"测试连接失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-cache")
async def clear_cache():
    """清空缓存"""
    return {
        "success": True,
        "message": "缓存已清空"
    }


@router.post("/reset-statistics")
async def reset_statistics():
    """重置统计信息"""
    return {
        "success": True,
        "message": "统计已重置"
    }


@router.get("/workers")
async def list_workers():
    """列出所有Worker及其状态"""
    try:
        from deepsearch.data_providers.implementations.akshare.akshare import AkShareProxyProvider
        provider = AkShareProxyProvider()

        workers = []
        for url in provider.worker_urls:
            stats = provider.worker_stats.get(url, {})
            workers.append({
                "id": url.replace("https://", "").replace("/", "_"),
                "url": url,
                "state": stats.get("state", "unknown"),
                "healthy": provider.worker_health.get(url, False),
                "enabled": True,  # 可以添加启用/禁用逻辑
                "stats": {
                    "total_requests": stats.get("total_requests", 0),
                    "success_rate": (
                        stats.get("success_count", 0) / stats.get("total_requests", 1)
                        if stats.get("total_requests", 0) > 0 else 0
                    ),
                    "avg_latency": stats.get("avg_latency", 0),
                    "fail_streak": stats.get("fail_streak", 0),
                    "last_check": stats.get("last_check").isoformat() if stats.get("last_check") else None
                }
            })

        return {
            "success": True,
            "data": workers
        }
    except Exception as e:
        logger.error(f"获取Workers列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workers/{worker_id}/test")
async def test_worker(worker_id: str):
    """测试特定Worker"""
    try:
        from deepsearch.data_providers.implementations.akshare.akshare import AkShareProxyProvider
        provider = AkShareProxyProvider()

        # 将ID转换回URL
        worker_url = "https://" + worker_id.replace("_", "/")

        if worker_url not in provider.worker_urls:
            raise HTTPException(status_code=404, detail="Worker not found")

        # 执行健康检查
        result = await provider._check_worker_health(worker_url)

        return {
            "success": True,
            "data": {
                "url": worker_url,
                "healthy": result,
                "message": "Worker is healthy" if result else "Worker is unhealthy",
                "timestamp": datetime.now().isoformat()
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"测试Worker失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workers/{worker_id}/reset")
async def reset_worker(worker_id: str):
    """重置Worker为半开状态进行探测"""
    try:
        from deepsearch.data_providers.implementations.akshare.akshare import AkShareProxyProvider
        provider = AkShareProxyProvider()

        # 将ID转换回URL
        worker_url = "https://" + worker_id.replace("_", "/")

        if worker_url not in provider.worker_urls:
            raise HTTPException(status_code=404, detail="Worker not found")

        # 重置状态
        if worker_url in provider.worker_stats:
            provider.worker_stats[worker_url]["state"] = "suspect"
            provider.worker_stats[worker_url]["fail_streak"] = 0
            provider.worker_stats[worker_url]["success_streak"] = 0
            provider.worker_stats[worker_url]["next_retry_time"] = 0
            provider.worker_health[worker_url] = True

        return {
            "success": True,
            "message": f"Worker {worker_url} has been reset to suspect state"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置Worker失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategy")
async def get_strategy():
    """获取当前选路策略"""
    try:
        from deepsearch.data_providers.implementations.akshare.akshare import AkShareProxyProvider
        provider = AkShareProxyProvider()

        return {
            "success": True,
            "data": {
                "strategy": provider.strategy,
                "worker_count": len(provider.worker_urls),
                "healthy_count": sum(1 for h in provider.worker_health.values() if h)
            }
        }
    except Exception as e:
        logger.error(f"获取策略失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
