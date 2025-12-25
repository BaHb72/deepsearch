"""
T-Trading 日内做T策略 API 端点

提供策略管理、信号管理和通知测试接口。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing_extensions import Literal

from deepsearch.infrastructure.trading.ttrading_service import (
    TTradingService,
    TTradingStrategy,
    TradingSignal,
    get_ttrading_service,
    set_ttrading_notification_callback,
)
from deepsearch.webui.dependencies import get_notification_service

router = APIRouter(prefix="/api/ttrading", tags=["T-Trading"])


# ==================== 请求/响应模型 ====================


class CreateStrategyRequest(BaseModel):
    """创建策略请求"""

    symbol: str = Field(..., min_length=1, description="股票代码")
    name: str = Field(..., min_length=1, description="策略名称")
    notify_enabled: bool = Field(default=True, description="是否发送通知")


class UpdateStrategyRequest(BaseModel):
    """更新策略请求"""

    name: Optional[str] = None
    notify_enabled: Optional[bool] = None
    status: Optional[Literal["active", "paused", "completed"]] = None


class CreateSignalRequest(BaseModel):
    """创建信号请求"""

    signal_type: Literal["buy", "sell"] = Field(..., description="买入/卖出")
    trigger_price: float = Field(..., gt=0, description="触发价格")
    position_ratio: float = Field(..., ge=0, le=100, description="仓位比例")
    enabled: bool = Field(default=True, description="是否启用")


class UpdateSignalRequest(BaseModel):
    """更新信号请求"""

    trigger_price: Optional[float] = None
    position_ratio: Optional[float] = None
    enabled: Optional[bool] = None


class CheckPriceRequest(BaseModel):
    """检查价格请求"""

    current_price: float = Field(..., gt=0, description="当前价格")


class ApiResponse(BaseModel):
    """通用 API 响应"""

    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None


# ==================== 依赖注入 ====================


async def get_service() -> TTradingService:
    """获取 TTradingService 实例并配置通知回调"""
    service = get_ttrading_service()

    # 配置通知回调
    try:
        notification_service = get_notification_service()

        async def send_notification(title: str, content: str):
            await notification_service.send(
                title=title,
                content=content,
                category="ttrading",
            )

        set_ttrading_notification_callback(send_notification)
    except Exception:
        # 通知服务不可用时继续工作
        pass

    return service


# ==================== 策略管理 API ====================


@router.get("/strategies", response_model=ApiResponse)
async def list_strategies(
    service: TTradingService = Depends(get_service),
):
    """获取所有策略列表"""
    strategies = await service.list_strategies()
    return ApiResponse(
        success=True,
        data=[s.model_dump() for s in strategies],
    )


@router.post("/strategies", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    request: CreateStrategyRequest,
    service: TTradingService = Depends(get_service),
):
    """创建新策略"""
    strategy = TTradingStrategy(
        symbol=request.symbol,
        name=request.name,
        notify_enabled=request.notify_enabled,
    )
    created = await service.create_strategy(strategy)
    return ApiResponse(
        success=True,
        message="策略创建成功",
        data=created.model_dump(),
    )


@router.get("/strategies/{strategy_id}", response_model=ApiResponse)
async def get_strategy(
    strategy_id: str,
    service: TTradingService = Depends(get_service),
):
    """获取策略详情"""
    strategy = await service.get_strategy(strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略不存在",
        )
    return ApiResponse(
        success=True,
        data=strategy.model_dump(),
    )


@router.put("/strategies/{strategy_id}", response_model=ApiResponse)
async def update_strategy(
    strategy_id: str,
    request: UpdateStrategyRequest,
    service: TTradingService = Depends(get_service),
):
    """更新策略"""
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有需要更新的字段",
        )

    strategy = await service.update_strategy(strategy_id, updates)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略不存在",
        )
    return ApiResponse(
        success=True,
        message="策略更新成功",
        data=strategy.model_dump(),
    )


@router.delete("/strategies/{strategy_id}", response_model=ApiResponse)
async def delete_strategy(
    strategy_id: str,
    service: TTradingService = Depends(get_service),
):
    """删除策略"""
    deleted = await service.delete_strategy(strategy_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略不存在",
        )
    return ApiResponse(
        success=True,
        message="策略删除成功",
    )


@router.post("/strategies/{strategy_id}/toggle", response_model=ApiResponse)
async def toggle_strategy(
    strategy_id: str,
    service: TTradingService = Depends(get_service),
):
    """切换策略状态"""
    strategy = await service.toggle_strategy(strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略不存在",
        )
    return ApiResponse(
        success=True,
        message=f"策略状态已切换为 {strategy.status}",
        data=strategy.model_dump(),
    )


# ==================== 信号管理 API ====================


@router.post("/strategies/{strategy_id}/signals", response_model=ApiResponse)
async def add_signal(
    strategy_id: str,
    request: CreateSignalRequest,
    service: TTradingService = Depends(get_service),
):
    """添加买卖点信号"""
    signal = TradingSignal(
        signal_type=request.signal_type,
        trigger_price=request.trigger_price,
        position_ratio=request.position_ratio,
        enabled=request.enabled,
    )
    strategy = await service.add_signal(strategy_id, signal)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略不存在",
        )
    return ApiResponse(
        success=True,
        message="信号添加成功",
        data=strategy.model_dump(),
    )


@router.put("/strategies/{strategy_id}/signals/{signal_id}", response_model=ApiResponse)
async def update_signal(
    strategy_id: str,
    signal_id: str,
    request: UpdateSignalRequest,
    service: TTradingService = Depends(get_service),
):
    """更新买卖点信号"""
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有需要更新的字段",
        )

    strategy = await service.update_signal(strategy_id, signal_id, updates)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略或信号不存在",
        )
    return ApiResponse(
        success=True,
        message="信号更新成功",
        data=strategy.model_dump(),
    )


@router.delete("/strategies/{strategy_id}/signals/{signal_id}", response_model=ApiResponse)
async def remove_signal(
    strategy_id: str,
    signal_id: str,
    service: TTradingService = Depends(get_service),
):
    """移除买卖点信号"""
    strategy = await service.remove_signal(strategy_id, signal_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="策略不存在",
        )
    return ApiResponse(
        success=True,
        message="信号删除成功",
        data=strategy.model_dump(),
    )


# ==================== 价格检查 API ====================


@router.post("/strategies/{strategy_id}/check-price", response_model=ApiResponse)
async def check_price(
    strategy_id: str,
    request: CheckPriceRequest,
    service: TTradingService = Depends(get_service),
):
    """检查价格是否触发信号"""
    triggered = await service.check_signals(strategy_id, request.current_price)
    return ApiResponse(
        success=True,
        message=f"触发了 {len(triggered)} 个信号" if triggered else "没有触发信号",
        data=[s.model_dump() for s in triggered],
    )


# ==================== 通知测试 API ====================


@router.post("/test-notify", response_model=ApiResponse)
async def test_notify(
    symbol: str = "测试股票",
    service: TTradingService = Depends(get_service),
):
    """发送测试通知"""
    success = await service.send_test_notification(symbol)
    return ApiResponse(
        success=success,
        message="测试通知已发送" if success else "发送失败，请检查通知配置",
    )
