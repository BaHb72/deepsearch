"""
内存管理 API 端点

提供:
1. 内存使用监控 API
2. 定时垃圾回收任务
3. 手动触发 GC 接口
4. tracemalloc 内存追踪 (检测泄漏)

核心实现位于 deepsearch.infrastructure.memory
"""

from __future__ import annotations

import asyncio
import gc
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# 从 infrastructure 层导入核心类
from core.config import get_config_dir
from core.infrastructure.memory import MemoryConfig, get_memory_manager, get_memory_tracer
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/system/memory", tags=["Memory Management"])


# ==================== API 端点 ====================


@router.get("/stats")
async def get_memory_stats() -> Dict[str, Any]:
    """
    获取当前进程内存统计

    返回 RSS、VMS、线程数、GC 状态等信息
    """
    manager = get_memory_manager()
    stats = manager.get_memory_stats()
    config = manager.get_config()

    return {
        "success": True,
        "data": {
            "current_process": stats,
            "gc_config": config,
        },
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/all-processes")
async def get_all_processes() -> Dict[str, Any]:
    """
    获取所有 Python 进程的内存使用

    用于监控多进程架构下的整体内存占用
    """
    manager = get_memory_manager()
    processes = manager.get_all_python_processes()

    total_rss = sum(p["rss_mb"] for p in processes)
    total_threads = sum(p["threads"] for p in processes)

    return {
        "success": True,
        "data": {
            "processes": processes,
            "summary": {
                "count": len(processes),
                "total_rss_mb": round(total_rss, 2),
                "total_threads": total_threads,
            },
        },
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/gc")
async def trigger_gc(full: bool = True) -> Dict[str, Any]:
    """
    手动触发垃圾回收

    Args:
        full: 是否执行完整 GC (收集所有代)，默认 True
    """
    manager = get_memory_manager()

    # 在线程池中执行以避免阻塞
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: manager.run_gc(full=full))

    return {
        "success": True,
        "data": result,
        "message": f"GC 完成，释放 {result['memory_freed_mb']:.1f} MB",
    }


@router.get("/gc/history")
async def get_gc_history(
    limit: int = 20,
) -> Dict[str, Any]:
    """
    获取 GC 历史记录

    返回最近的 GC 执行情况（从持久化存储读取）

    Args:
        limit: 返回记录数，默认 20
    """
    manager = get_memory_manager()
    history = manager.get_gc_history(limit=limit)

    return {
        "success": True,
        "data": {
            "history": history,
            "count": len(history),
        },
    }


@router.get("/gc/history/query")
async def query_gc_history(
    start: Optional[str] = None,
    end: Optional[str] = None,
    trigger_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    按时间范围查询 GC 历史

    Args:
        start: 开始时间 (ISO 格式，如 2026-01-01T00:00:00)
        end: 结束时间 (ISO 格式)
        trigger_type: 触发类型过滤 (periodic/manual/threshold/shutdown)
        limit: 返回记录数限制，默认 100，最大 1000
        offset: 分页偏移
    """
    manager = get_memory_manager()

    if not manager._gc_persistence:
        raise HTTPException(status_code=503, detail="GC 持久化服务不可用")

    # 解析时间参数
    start_dt = None
    end_dt = None

    if start:
        try:
            start_dt = datetime.fromisoformat(start)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的开始时间格式: {start}")

    if end:
        try:
            end_dt = datetime.fromisoformat(end)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的结束时间格式: {end}")

    # 限制最大返回数量
    limit = min(limit, 1000)

    records = manager._gc_persistence.query(
        start=start_dt,
        end=end_dt,
        trigger_type=trigger_type,  # type: ignore
        limit=limit,
        offset=offset,
    )

    return {
        "success": True,
        "data": {
            "records": records,
            "count": len(records),
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/gc/stats")
async def get_gc_stats(
    period: str = "day",
) -> Dict[str, Any]:
    """
    获取 GC 统计摘要

    Args:
        period: 统计周期 (hour/day/week/month)，默认 day
    """
    manager = get_memory_manager()

    if not manager._gc_persistence:
        raise HTTPException(status_code=503, detail="GC 持久化服务不可用")

    if period not in ("hour", "day", "week", "month"):
        raise HTTPException(status_code=400, detail=f"无效的统计周期: {period}")

    stats = manager._gc_persistence.get_stats(period=period)  # type: ignore

    return {
        "success": True,
        "data": stats,
    }


@router.get("/config")
async def get_memory_config() -> Dict[str, Any]:
    """获取内存管理配置"""
    manager = get_memory_manager()
    return {
        "success": True,
        "data": manager.get_config(),
    }


@router.put("/config")
async def update_memory_config(config: MemoryConfig) -> Dict[str, Any]:
    """
    更新内存管理配置

    可配置项:
    - gc_enabled: 是否启用定时 GC
    - gc_interval_seconds: GC 间隔 (秒)，最小 60 秒
    - gc_log_enabled: 是否记录 GC 日志
    """
    manager = get_memory_manager()
    new_config = manager.update_config(
        gc_enabled=config.gc_enabled,
        gc_interval_seconds=config.gc_interval_seconds,
        gc_log_enabled=config.gc_log_enabled,
    )

    return {
        "success": True,
        "data": new_config,
        "message": "配置已更新",
    }


@router.post("/gc/start")
async def start_periodic_gc() -> Dict[str, Any]:
    """启动定时 GC 任务"""
    manager = get_memory_manager()
    await manager.start_periodic_gc()

    return {
        "success": True,
        "message": f"定时 GC 已启动，间隔 {manager._gc_interval} 秒",
        "data": manager.get_config(),
    }


@router.post("/gc/stop")
async def stop_periodic_gc() -> Dict[str, Any]:
    """停止定时 GC 任务"""
    manager = get_memory_manager()
    await manager.stop_periodic_gc()

    return {
        "success": True,
        "message": "定时 GC 已停止",
        "data": manager.get_config(),
    }


# ==================== tracemalloc API 端点 ====================


@router.get("/trace/status")
async def get_trace_status() -> Dict[str, Any]:
    """获取内存追踪状态"""
    tracer = get_memory_tracer()
    return {
        "success": True,
        "data": tracer.get_status(),
    }


@router.post("/trace/start")
async def start_memory_trace(nframe: int = 25) -> Dict[str, Any]:
    """
    启动 tracemalloc 内存追踪

    Args:
        nframe: 追踪的调用栈深度，默认 25
    """
    tracer = get_memory_tracer()
    return tracer.start_tracing(nframe)


@router.post("/trace/stop")
async def stop_memory_trace() -> Dict[str, Any]:
    """停止内存追踪"""
    tracer = get_memory_tracer()
    return tracer.stop_tracing()


@router.post("/trace/snapshot")
async def take_memory_snapshot(name: str = "default") -> Dict[str, Any]:
    """
    拍摄内存快照

    Args:
        name: 快照名称，用于后续比较
    """
    tracer = get_memory_tracer()
    return tracer.take_snapshot(name)


@router.get("/trace/top")
async def get_top_allocations(
    snapshot: str = "default", limit: int = 20, key_type: str = "lineno"
) -> Dict[str, Any]:
    """
    获取内存分配 Top N

    Args:
        snapshot: 快照名称
        limit: 返回数量
        key_type: 分组方式 (lineno, filename, traceback)
    """
    tracer = get_memory_tracer()
    return tracer.get_top_allocations(snapshot, limit, key_type)


@router.get("/trace/compare")
async def compare_memory_snapshots(
    old: str = "baseline", new: str = "current", limit: int = 20
) -> Dict[str, Any]:
    """
    比较两个内存快照，检测泄漏

    用法:
    1. 在操作前: POST /trace/snapshot?name=baseline
    2. 执行可能泄漏的操作
    3. 在操作后: POST /trace/snapshot?name=current
    4. 比较: GET /trace/compare?old=baseline&new=current
    """
    tracer = get_memory_tracer()
    return tracer.compare_snapshots(old, new, limit)


# ==================== Arrow Cache 管理 API ====================


@router.get("/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """
    获取所有缓存命名空间的统计信息

    Returns:
        缓存目录、各命名空间统计、总大小
    """
    try:
        from core.infrastructure.cache import ArrowCacheManager

        base_dir = ArrowCacheManager.DEFAULT_BASE_DIR
        namespaces = []

        if base_dir.exists():
            for ns_dir in base_dir.iterdir():
                if ns_dir.is_dir() and ns_dir.name != "__pycache__":
                    try:
                        cache = ArrowCacheManager(namespace=ns_dir.name)
                        namespaces.append(cache.get_stats())
                    except Exception as e:
                        logger.warning(f"读取缓存命名空间 {ns_dir.name} 失败: {e}")

        total_size_mb = sum(ns.get("total_size_mb", 0) for ns in namespaces)

        return {
            "base_dir": str(base_dir),
            "platform": sys.platform,
            "namespaces": namespaces,
            "total_size_mb": round(total_size_mb, 2),
            "namespace_count": len(namespaces),
        }
    except ImportError:
        return {"error": "ArrowCacheManager not available", "namespaces": [], "total_size_mb": 0}
    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache/{namespace}")
async def clear_cache_namespace(namespace: str) -> Dict[str, Any]:
    """
    清除指定命名空间的缓存

    Args:
        namespace: 命名空间名称 (如 amazingdata, miniqmt)
    """
    try:
        from core.infrastructure.cache import ArrowCacheManager

        cache = ArrowCacheManager(namespace=namespace)
        count = cache.clear()

        logger.info(f"已清除缓存命名空间 '{namespace}': {count} 条目")

        return {"namespace": namespace, "cleared": count, "success": True}
    except ImportError:
        raise HTTPException(status_code=500, detail="ArrowCacheManager not available")
    except Exception as e:
        logger.error(f"清除缓存命名空间 '{namespace}' 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cache")
async def clear_all_cache() -> Dict[str, Any]:
    """
    清除所有命名空间的缓存
    """
    try:
        from core.infrastructure.cache import ArrowCacheManager

        base_dir = ArrowCacheManager.DEFAULT_BASE_DIR
        total_cleared = 0
        namespaces_cleared = []

        if base_dir.exists():
            for ns_dir in base_dir.iterdir():
                if ns_dir.is_dir() and ns_dir.name != "__pycache__":
                    try:
                        cache = ArrowCacheManager(namespace=ns_dir.name)
                        count = cache.clear()
                        total_cleared += count
                        namespaces_cleared.append({"namespace": ns_dir.name, "cleared": count})
                    except Exception as e:
                        logger.warning(f"清除命名空间 {ns_dir.name} 失败: {e}")

        logger.info(f"已清除所有缓存: {total_cleared} 条目, {len(namespaces_cleared)} 个命名空间")

        return {"total_cleared": total_cleared, "namespaces": namespaces_cleared, "success": True}
    except ImportError:
        raise HTTPException(status_code=500, detail="ArrowCacheManager not available")
    except Exception as e:
        logger.error(f"清除所有缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 对象分析 ====================


@router.get("/objects")
async def analyze_large_objects(limit: int = 20) -> Dict[str, Any]:
    """
    分析进程中的大型对象（DataFrame, ndarray 等）

    用于诊断内存占用来源
    """
    from collections import defaultdict

    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        return {"error": "pandas/numpy not available"}

    gc.collect()

    type_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "size": 0})
    dataframe_details: List[Dict[str, Any]] = []

    for obj in gc.get_objects():
        try:
            if isinstance(obj, pd.DataFrame):
                size = int(obj.memory_usage(deep=True).sum())
                type_stats["DataFrame"]["count"] += 1
                type_stats["DataFrame"]["size"] += size
                # 记录大 DataFrame 详情
                if size > 1024 * 1024:  # > 1MB
                    dataframe_details.append(
                        {
                            "shape": str(obj.shape),
                            "columns": list(obj.columns)[:5],
                            "size_mb": round(size / 1024 / 1024, 2),
                            "dtypes": {str(k): str(v) for k, v in list(obj.dtypes.items())[:3]},
                        }
                    )
            elif isinstance(obj, pd.Series):
                size = int(obj.memory_usage(deep=True))  # type: ignore[attr-defined]
                type_stats["Series"]["count"] += 1
                type_stats["Series"]["size"] += size
            elif isinstance(obj, np.ndarray):
                size = int(obj.nbytes)  # type: ignore[attr-defined]
                type_stats["ndarray"]["count"] += 1
                type_stats["ndarray"]["size"] += size
            elif isinstance(obj, dict):
                size = sys.getsizeof(obj)
                type_stats["dict"]["count"] += 1
                type_stats["dict"]["size"] += size
            elif isinstance(obj, list):
                size = sys.getsizeof(obj)
                type_stats["list"]["count"] += 1
                type_stats["list"]["size"] += size
        except Exception:
            pass

    # 按大小排序
    sorted_stats = sorted(type_stats.items(), key=lambda x: x[1]["size"], reverse=True)[:limit]

    results = []
    for type_name, stats in sorted_stats:
        results.append(
            {
                "type": type_name,
                "count": stats["count"],
                "size_mb": round(stats["size"] / 1024 / 1024, 2),
            }
        )

    total_mb = sum(s["size"] for _, s in type_stats.items()) / 1024 / 1024

    return {
        "success": True,
        "by_type": results,
        "large_dataframes": dataframe_details[:10],  # Top 10 大 DataFrame
        "total_tracked_mb": round(total_mb, 2),
        "timestamp": datetime.now().isoformat(),
    }


# ==================== 缓存配置 API ====================


class CacheNamespaceConfigUpdate(BaseModel):
    """命名空间配置更新"""

    ttl: Optional[int] = Field(None, ge=1, le=86400, description="TTL (秒)")
    enabled: Optional[bool] = Field(None, description="是否启用")


class CacheConfigUpdate(BaseModel):
    """缓存配置更新请求"""

    enabled: Optional[bool] = Field(None, description="是否启用缓存")
    default_ttl: Optional[int] = Field(None, ge=1, le=86400, description="默认 TTL (秒)")
    namespaces: Optional[Dict[str, CacheNamespaceConfigUpdate]] = Field(
        None, description="命名空间配置"
    )


@router.get("/cache/config")
async def get_cache_config() -> Dict[str, Any]:
    """
    获取当前缓存配置

    返回启用状态、默认 TTL 和各命名空间配置
    """
    try:
        from core.config.models.arrow_cache import get_arrow_cache_config

        config = get_arrow_cache_config()

        return {
            "success": True,
            "config": {
                "enabled": config.enabled,
                "base_dir": config.base_dir,
                "default_ttl": config.default_ttl,
                "namespaces": {
                    name: {"ttl": ns.ttl, "enabled": ns.enabled}
                    for name, ns in config.namespaces.items()
                },
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"获取缓存配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/cache/config")
async def update_cache_config(update: CacheConfigUpdate) -> Dict[str, Any]:
    """
    更新缓存配置

    修改 settings.yaml 并触发热重载
    """
    import os

    import yaml

    try:
        # 读取当前配置文件（使用统一的配置目录）
        config_dir = get_config_dir()
        env = os.getenv("APP__ENV", "dev")
        config_path = config_dir / f"settings.{env}.yaml"

        with open(config_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}

        # 确保 cache.arrow 节存在
        if "cache" not in settings:
            settings["cache"] = {}
        if "arrow" not in settings["cache"]:
            settings["cache"]["arrow"] = {"enabled": True, "default_ttl": 300}

        arrow_config = settings["cache"]["arrow"]

        # 更新配置
        if update.enabled is not None:
            arrow_config["enabled"] = update.enabled
        if update.default_ttl is not None:
            arrow_config["default_ttl"] = update.default_ttl
        if update.namespaces:
            if "namespaces" not in arrow_config:
                arrow_config["namespaces"] = {}
            for ns_name, ns_update in update.namespaces.items():
                if ns_name not in arrow_config["namespaces"]:
                    arrow_config["namespaces"][ns_name] = {}
                if ns_update.ttl is not None:
                    arrow_config["namespaces"][ns_name]["ttl"] = ns_update.ttl
                if ns_update.enabled is not None:
                    arrow_config["namespaces"][ns_name]["enabled"] = ns_update.enabled

        # 写回配置文件
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(settings, f, allow_unicode=True, default_flow_style=False)

        logger.info(f"缓存配置已更新: {update.model_dump(exclude_none=True)}")

        return {
            "success": True,
            "message": "缓存配置已更新，下次创建缓存实例时生效",
            "updated": update.model_dump(exclude_none=True),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"更新缓存配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== L2 钉住缓冲区 API ====================


class PinStocksRequest(BaseModel):
    """钉住股票请求"""

    codes: List[str] = Field(..., description="要钉住的股票代码列表")
    capacity: Optional[int] = Field(None, ge=100, le=10000, description="缓冲区容量")


class L2ConfigUpdate(BaseModel):
    """L2 配置更新（所有阈值可通过 UI 调整）"""

    enabled: Optional[bool] = Field(None, description="是否启用")
    max_pinned_stocks: Optional[int] = Field(None, ge=1, le=1000, description="最大钉住数")
    default_capacity: Optional[int] = Field(None, ge=100, le=10000, description="默认容量")
    max_capacity: Optional[int] = Field(None, ge=100, le=50000, description="最大容量")
    auto_unpin_idle_seconds: Optional[int] = Field(
        None, ge=0, le=86400, description="自动取消闲置时间"
    )
    total_memory_limit_mb: Optional[int] = Field(None, ge=10, le=1000, description="内存上限(MB)")


@router.post("/l2/pin")
async def pin_stocks(request: PinStocksRequest) -> Dict[str, Any]:
    """钉住股票到内存（用于打板/实盘交易）"""
    try:
        from core.adapters.market_data.l2_pinned_adapter import get_l2_pinned_buffer

        buffer = get_l2_pinned_buffer()

        pinned = []
        failed = []
        for code in request.codes:
            if buffer.pin(code, request.capacity):
                pinned.append(code)
            else:
                failed.append(code)

        return {
            "success": True,
            "pinned": pinned,
            "failed": failed,
            "message": f"成功钉住 {len(pinned)} 只股票"
            + (f"，{len(failed)} 只失败" if failed else ""),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"钉住股票失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/l2/pin/{code}")
async def unpin_stock(code: str) -> Dict[str, Any]:
    """取消钉住单只股票"""
    try:
        from core.adapters.market_data.l2_pinned_adapter import get_l2_pinned_buffer

        buffer = get_l2_pinned_buffer()

        if buffer.unpin(code):
            return {
                "success": True,
                "code": code,
                "message": f"已取消钉住 {code}",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            raise HTTPException(status_code=404, detail=f"股票 {code} 未被钉住")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取消钉住失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/l2/pinned")
async def get_pinned_stocks() -> Dict[str, Any]:
    """获取所有钉住的股票及统计信息"""
    try:
        from core.adapters.market_data.l2_pinned_adapter import get_l2_pinned_buffer

        buffer = get_l2_pinned_buffer()

        stats = buffer.get_stats()
        return {"success": True, "data": stats, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"获取钉住列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/l2/config")
async def get_l2_config() -> Dict[str, Any]:
    """获取 L2 缓冲区配置（所有阈值可通过 UI 调整）"""
    try:
        from core.adapters.market_data.l2_pinned_adapter import get_l2_pinned_buffer

        buffer = get_l2_pinned_buffer()
        config = buffer.get_config()

        return {
            "success": True,
            "config": {
                "enabled": config.enabled,
                "max_pinned_stocks": config.max_pinned_stocks,
                "default_capacity": config.default_capacity,
                "max_capacity": config.max_capacity,
                "auto_unpin_idle_seconds": config.auto_unpin_idle_seconds,
                "total_memory_limit_mb": config.total_memory_limit_mb,
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"获取 L2 配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/l2/config")
async def update_l2_config(update: L2ConfigUpdate) -> Dict[str, Any]:
    """更新 L2 缓冲区配置（热重载）"""
    try:
        from core.adapters.market_data.l2_pinned_adapter import get_l2_pinned_buffer

        buffer = get_l2_pinned_buffer()

        update_dict = update.model_dump(exclude_none=True)
        if update_dict:
            buffer.update_config(**update_dict)

        logger.info(f"L2 配置已更新: {update_dict}")

        return {
            "success": True,
            "message": "L2 配置已更新",
            "updated": update_dict,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"更新 L2 配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/l2/pinned")
async def clear_all_pinned() -> Dict[str, Any]:
    """清空所有钉住的股票"""
    try:
        from core.adapters.market_data.l2_pinned_adapter import get_l2_pinned_buffer

        buffer = get_l2_pinned_buffer()

        cleared = buffer.clear_all()
        return {
            "success": True,
            "cleared": cleared,
            "message": f"已清空 {cleared} 只钉住股票",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"清空钉住列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 订阅系统 API ====================


@router.get("/subscription/stats")
async def get_subscription_stats() -> Dict[str, Any]:
    """获取订阅系统统计"""
    try:
        from core.adapters.market_data.memory_scheduler import get_memory_scheduler
        from core.adapters.market_data.subscription_manager import get_subscription_manager

        sub_manager = get_subscription_manager()
        scheduler = get_memory_scheduler()

        return {
            "success": True,
            "subscription": sub_manager.get_stats(),
            "scheduler": scheduler.get_stats(),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"获取订阅统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscription/codes/{code}")
async def get_code_subscribers(code: str) -> Dict[str, Any]:
    """获取股票的订阅者列表"""
    try:
        from core.adapters.market_data.memory_scheduler import get_memory_scheduler
        from core.adapters.market_data.subscription_manager import get_subscription_manager

        sub_manager = get_subscription_manager()
        scheduler = get_memory_scheduler()

        subscribers = sub_manager.get_subscribers(code)
        storage = scheduler.get_storage_type(code)

        return {
            "success": True,
            "code": code,
            "storage_type": storage.value,
            "subscribers": [
                {
                    "id": s.subscriber_id,
                    "priority": s.priority.name,
                    "module": s.module_name,
                }
                for s in subscribers
            ],
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"获取订阅者失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
