"""
Strategy Management API

Endpoints for managing strategy files:
- List strategies
- Get strategy details
- Enable/disable strategies
- Scan for new strategies
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from deepsearch.strategies.interfaces.models import (
    StrategyCategory,
    StrategyListResponse,
    StrategyMeta,
)
from deepsearch.strategies.services.registry_service import get_registry_service

router = APIRouter(prefix="/strategies", tags=["strategies"])


# ============================================
# Request/Response Models
# ============================================


class UpdateStrategyRequest(BaseModel):
    """更新策略请求"""

    enabled: Optional[bool] = None
    params: Optional[Dict[str, Any]] = None


class ScanResultResponse(BaseModel):
    """扫描结果响应"""

    discovered: List[Dict[str, Any]]
    new_count: int
    existing_count: int


class StrategyParamsResponse(BaseModel):
    """策略参数响应"""

    strategy_id: str
    params: Dict[str, Any]
    defaults: Dict[str, Any]


# ============================================
# Endpoints
# ============================================


@router.get("", response_model=StrategyListResponse)
async def list_strategies(
    category: Optional[str] = Query(None, description="按分类筛选"),
    enabled_only: bool = Query(False, description="仅显示启用的策略"),
):
    """获取策略列表"""
    try:
        service = get_registry_service()

        # 转换分类
        cat = None
        if category:
            try:
                cat = StrategyCategory(category)
            except ValueError:
                pass

        strategies = service.list_strategies(category=cat, enabled_only=enabled_only)

        # 统计分类
        category_counts = service.get_category_counts()

        return StrategyListResponse(
            strategies=strategies,
            total=len(strategies),
            categories=category_counts,
        )

    except Exception as e:
        logger.error(f"Failed to list strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{strategy_id}", response_model=StrategyMeta)
async def get_strategy(strategy_id: str):
    """获取策略详情"""
    service = get_registry_service()
    strategy = service.get_strategy(strategy_id)

    if strategy is None:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")

    return strategy


@router.put("/{strategy_id}/status")
async def update_strategy_status(strategy_id: str, enabled: bool):
    """更新策略启用状态"""
    service = get_registry_service()

    # 检查策略是否存在
    strategy = service.get_strategy(strategy_id)
    if strategy is None:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")

    # 更新状态
    success = service.update_strategy_status(strategy_id, enabled)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to update strategy status")

    return {
        "strategy_id": strategy_id,
        "enabled": enabled,
        "message": f"Strategy {'enabled' if enabled else 'disabled'} successfully",
    }


@router.get("/{strategy_id}/params", response_model=StrategyParamsResponse)
async def get_strategy_params(strategy_id: str):
    """获取策略参数定义"""
    service = get_registry_service()
    strategy = service.get_strategy(strategy_id)

    if strategy is None:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")

    # 提取参数定义和默认值
    params = {}
    defaults = {}
    for key, param_def in strategy.params.items():
        params[key] = param_def.model_dump()
        defaults[key] = param_def.default

    return StrategyParamsResponse(
        strategy_id=strategy_id,
        params=params,
        defaults=defaults,
    )


@router.post("/scan", response_model=ScanResultResponse)
async def scan_strategies():
    """扫描策略目录，发现新策略"""
    try:
        service = get_registry_service()

        # 扫描发现策略
        discovered = service.scan_implementations()

        # 检查哪些是新的
        existing_registry = service.load_registry()
        existing_ids = set(existing_registry.keys())

        new_strategies = []
        existing_strategies = []

        for item in discovered:
            if item["id"] in existing_ids:
                existing_strategies.append(item)
            else:
                new_strategies.append(item)

        logger.info(
            f"Scan complete: {len(new_strategies)} new, {len(existing_strategies)} existing"
        )

        return ScanResultResponse(
            discovered=discovered,
            new_count=len(new_strategies),
            existing_count=len(existing_strategies),
        )

    except Exception as e:
        logger.error(f"Failed to scan strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload")
async def reload_registry():
    """重新加载策略注册表"""
    try:
        service = get_registry_service()
        registry = service.load_registry(force_reload=True)

        return {
            "message": "Registry reloaded successfully",
            "strategy_count": len(registry),
        }

    except Exception as e:
        logger.error(f"Failed to reload registry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{strategy_id}/code-hash")
async def get_strategy_code_hash(strategy_id: str):
    """获取策略代码哈希（用于版本追踪）"""
    service = get_registry_service()

    code_hash = service.get_strategy_code_hash(strategy_id)
    if code_hash is None:
        raise HTTPException(status_code=404, detail=f"Strategy not found: {strategy_id}")

    return {
        "strategy_id": strategy_id,
        "code_hash": code_hash,
    }
