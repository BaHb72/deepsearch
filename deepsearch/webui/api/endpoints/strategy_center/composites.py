"""
Composite Strategy API

Endpoints for managing composite (ensemble) strategies:
- List composites
- Create/update composites
- Test composite signals
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import yaml
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from deepsearch.strategies.interfaces.models import (
    AggregationMethod,
    CompositeSignal,
    CompositeStrategy,
    SignalDirection,
    StrategyWeight,
)

router = APIRouter(prefix="/composites", tags=["composites"])

# 组合策略配置目录
COMPOSITES_DIR = (
    Path(__file__).parent.parent.parent.parent.parent / "strategies" / "config" / "composites"
)


# ============================================
# Request/Response Models
# ============================================


class CreateCompositeRequest(BaseModel):
    """创建组合策略请求"""

    name: str
    description: Optional[str] = None
    components: List[StrategyWeight] = Field(default_factory=list)
    aggregation: AggregationMethod = AggregationMethod.WEIGHTED_AVG
    signal_threshold: float = Field(ge=0.0, le=1.0, default=0.5)
    tags: List[str] = Field(default_factory=list)


class UpdateCompositeRequest(BaseModel):
    """更新组合策略请求"""

    name: Optional[str] = None
    description: Optional[str] = None
    components: Optional[List[StrategyWeight]] = None
    aggregation: Optional[AggregationMethod] = None
    signal_threshold: Optional[float] = None
    tags: Optional[List[str]] = None


class CompositeListResponse(BaseModel):
    """组合策略列表响应"""

    composites: List[CompositeStrategy]
    total: int


class TestSignalRequest(BaseModel):
    """测试信号请求"""

    composite_id: str
    symbol: str
    # 模拟各子策略信号 (用于测试)
    mock_signals: Optional[Dict[str, float]] = None


# ============================================
# Helper Functions
# ============================================


def _load_composite(composite_id: str) -> Optional[CompositeStrategy]:
    """从 YAML 文件加载组合策略"""
    file_path = COMPOSITES_DIR / f"{composite_id}.yaml"
    if not file_path.exists():
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # 转换 components
        if "components" in data:
            data["components"] = [StrategyWeight(**c) for c in data["components"]]

        # 转换 aggregation
        if "aggregation" in data:
            data["aggregation"] = AggregationMethod(data["aggregation"])

        return CompositeStrategy(**data)

    except Exception as e:
        logger.error(f"Failed to load composite {composite_id}: {e}")
        return None


def _save_composite(composite: CompositeStrategy) -> bool:
    """保存组合策略到 YAML 文件"""
    COMPOSITES_DIR.mkdir(parents=True, exist_ok=True)
    file_path = COMPOSITES_DIR / f"{composite.id}.yaml"

    try:
        data = composite.model_dump()
        # 转换 datetime
        data["created_at"] = data["created_at"].isoformat()
        data["updated_at"] = data["updated_at"].isoformat()
        # 转换 enum
        data["aggregation"] = (
            data["aggregation"].value
            if isinstance(data["aggregation"], AggregationMethod)
            else data["aggregation"]
        )

        with open(file_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

        return True

    except Exception as e:
        logger.error(f"Failed to save composite {composite.id}: {e}")
        return False


def _list_composites() -> List[CompositeStrategy]:
    """列出所有组合策略"""
    composites: List[CompositeStrategy] = []

    if not COMPOSITES_DIR.exists():
        return composites

    for yaml_file in COMPOSITES_DIR.glob("*.yaml"):
        composite = _load_composite(yaml_file.stem)
        if composite:
            composites.append(composite)

    return composites


def _delete_composite(composite_id: str) -> bool:
    """删除组合策略"""
    file_path = COMPOSITES_DIR / f"{composite_id}.yaml"
    if not file_path.exists():
        return False

    try:
        file_path.unlink()
        return True
    except Exception as e:
        logger.error(f"Failed to delete composite {composite_id}: {e}")
        return False


# ============================================
# Signal Aggregation Logic
# ============================================


def aggregate_signals(
    signals: Dict[str, float],
    weights: Dict[str, float],
    method: AggregationMethod = AggregationMethod.WEIGHTED_AVG,
) -> float:
    """
    聚合多策略信号

    weighted_avg: 加权平均
    vote: 投票（信号方向计数）
    unanimous: 一致性（所有策略同向才触发）
    """
    if method == AggregationMethod.WEIGHTED_AVG:
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 0.0
        return sum(signals.get(sid, 0) * w for sid, w in weights.items()) / total_weight

    elif method == AggregationMethod.VOTE:
        buy_weight = sum(w for sid, w in weights.items() if signals.get(sid, 0) > 0)
        sell_weight = sum(w for sid, w in weights.items() if signals.get(sid, 0) < 0)
        total = buy_weight + sell_weight
        return (buy_weight - sell_weight) / total if total > 0 else 0.0

    elif method == AggregationMethod.UNANIMOUS:
        active = [signals.get(sid, 0) for sid in weights if weights[sid] > 0]
        if not active:
            return 0.0
        if all(s > 0 for s in active):
            return sum(active) / len(active)
        elif all(s < 0 for s in active):
            return sum(active) / len(active)
        return 0.0

    return 0.0


# ============================================
# Endpoints
# ============================================


@router.get("", response_model=CompositeListResponse)
async def list_composites():
    """获取组合策略列表"""
    composites = _list_composites()
    return CompositeListResponse(
        composites=composites,
        total=len(composites),
    )


@router.get("/{composite_id}", response_model=CompositeStrategy)
async def get_composite(composite_id: str):
    """获取组合策略详情"""
    composite = _load_composite(composite_id)
    if composite is None:
        raise HTTPException(status_code=404, detail=f"Composite not found: {composite_id}")
    return composite


@router.post("", response_model=CompositeStrategy)
async def create_composite(request: CreateCompositeRequest):
    """创建组合策略"""
    # 生成 ID
    composite_id = str(uuid4())[:8]

    composite = CompositeStrategy(
        id=composite_id,
        name=request.name,
        description=request.description,
        components=request.components,
        aggregation=request.aggregation,
        signal_threshold=request.signal_threshold,
        tags=request.tags,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )

    if not _save_composite(composite):
        raise HTTPException(status_code=500, detail="Failed to save composite strategy")

    logger.info(f"Created composite strategy: {composite_id}")
    return composite


@router.put("/{composite_id}", response_model=CompositeStrategy)
async def update_composite(composite_id: str, request: UpdateCompositeRequest):
    """更新组合策略"""
    composite = _load_composite(composite_id)
    if composite is None:
        raise HTTPException(status_code=404, detail=f"Composite not found: {composite_id}")

    # 更新字段
    if request.name is not None:
        composite.name = request.name
    if request.description is not None:
        composite.description = request.description
    if request.components is not None:
        composite.components = request.components
    if request.aggregation is not None:
        composite.aggregation = request.aggregation
    if request.signal_threshold is not None:
        composite.signal_threshold = request.signal_threshold
    if request.tags is not None:
        composite.tags = request.tags

    composite.updated_at = datetime.now()

    if not _save_composite(composite):
        raise HTTPException(status_code=500, detail="Failed to update composite strategy")

    logger.info(f"Updated composite strategy: {composite_id}")
    return composite


@router.delete("/{composite_id}")
async def delete_composite(composite_id: str):
    """删除组合策略"""
    if not _delete_composite(composite_id):
        raise HTTPException(status_code=404, detail=f"Composite not found: {composite_id}")

    logger.info(f"Deleted composite strategy: {composite_id}")
    return {"message": f"Composite {composite_id} deleted successfully"}


@router.post("/test-signal", response_model=CompositeSignal)
async def test_composite_signal(request: TestSignalRequest):
    """测试组合策略信号（用于调试）"""
    composite = _load_composite(request.composite_id)
    if composite is None:
        raise HTTPException(status_code=404, detail=f"Composite not found: {request.composite_id}")

    # 使用模拟信号或生成随机信号
    if request.mock_signals:
        component_signals = request.mock_signals
    else:
        import random

        component_signals = {
            c.strategy_id: random.uniform(-1, 1) for c in composite.components if c.enabled
        }

    # 构建权重字典
    weights = {c.strategy_id: c.weight for c in composite.components if c.enabled}

    # 聚合信号
    aggregated = aggregate_signals(component_signals, weights, composite.aggregation)

    # 确定方向
    if aggregated > composite.signal_threshold:
        direction = SignalDirection.BUY
    elif aggregated < -composite.signal_threshold:
        direction = SignalDirection.SELL
    else:
        direction = SignalDirection.HOLD

    return CompositeSignal(
        composite_id=request.composite_id,
        symbol=request.symbol,
        component_signals=component_signals,
        aggregated_signal=aggregated,
        direction=direction,
        confidence=abs(aggregated),
    )
