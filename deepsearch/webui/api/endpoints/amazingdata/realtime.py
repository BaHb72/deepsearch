"""
AmazingData 实时行情API模块
包含各类证券的实时快照和K线订阅接口
"""

import asyncio
import json
from typing import Dict, List, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel, Field

from .base import JSONDict, format_response, get_amazingdata_provider, handle_api_error

# 创建路由器
router = APIRouter(tags=["AmazingData-实时行情"])


# ================== 请求模型 ==================


class SubscribeRequest(BaseModel):
    """订阅请求基类"""

    code_list: List[str] = Field(..., description="代码列表")
    period: Optional[str] = Field(None, description="订阅周期")


class KlineSubscribeRequest(BaseModel):
    """K线订阅请求"""

    code_list: List[str] = Field(..., description="代码列表")
    period: str = Field("1min", description="K线周期: 1min/5min/15min/30min/60min/daily")


# ================== 全局订阅管理器 ==================


class SubscriptionManager:
    """订阅管理器"""

    def __init__(self):
        self.subscriptions: Dict[str, Dict] = {}  # subscription_id -> subscription_info
        self.websockets: Dict[str, WebSocket] = {}  # client_id -> websocket
        self.active_tasks: Dict[str, asyncio.Task] = {}  # subscription_id -> task

    async def add_subscription(
        self, client_id: str, subscription_type: str, code_list: List[str], callback=None, **kwargs
    ) -> str:
        """添加订阅"""
        subscription_id = f"{client_id}_{subscription_type}_{','.join(code_list)}"

        if subscription_id in self.subscriptions:
            logger.warning(f"订阅已存在: {subscription_id}")
            return subscription_id

        self.subscriptions[subscription_id] = {
            "client_id": client_id,
            "type": subscription_type,
            "code_list": code_list,
            "callback": callback,
            "status": "active",
            **kwargs,
        }

        logger.info(f"添加订阅: {subscription_id}")
        return subscription_id

    async def remove_subscription(self, subscription_id: str):
        """移除订阅"""
        if subscription_id in self.subscriptions:
            # 取消任务
            if subscription_id in self.active_tasks:
                task = self.active_tasks[subscription_id]
                task.cancel()
                del self.active_tasks[subscription_id]

            del self.subscriptions[subscription_id]
            logger.info(f"移除订阅: {subscription_id}")

    async def remove_client_subscriptions(self, client_id: str):
        """移除客户端的所有订阅"""
        to_remove = [
            sub_id for sub_id, info in self.subscriptions.items() if info["client_id"] == client_id
        ]

        for subscription_id in to_remove:
            await self.remove_subscription(subscription_id)

    def get_subscription_status(self) -> Dict:
        """获取订阅状态"""
        return {
            "total_subscriptions": len(self.subscriptions),
            "active_tasks": len(self.active_tasks),
            "connected_clients": len(self.websockets),
            "subscriptions": [
                {
                    "id": sub_id,
                    "type": info["type"],
                    "codes": info["code_list"],
                    "status": info["status"],
                }
                for sub_id, info in self.subscriptions.items()
            ],
        }


# 全局订阅管理器实例
subscription_manager = SubscriptionManager()


# ================== API接口 ==================


@router.post("/subscribe/index", summary="订阅指数实时快照")
async def subscribe_index(request: SubscribeRequest) -> JSONDict:
    """
    订阅指数实时快照数据

    Args:
        request: 订阅请求

    Returns:
        订阅成功信息
    """
    try:
        provider = await get_amazingdata_provider()

        # 创建回调函数
        async def on_snapshot(data):
            # 处理快照数据
            logger.debug(f"收到指数快照: {data}")

        # 订阅数据
        subscription_id = await subscription_manager.add_subscription(
            client_id="api_client",
            subscription_type="index",
            code_list=request.code_list,
            callback=on_snapshot,
        )

        # 调用SDK订阅
        await provider.subscribe_index_snapshot(code_list=request.code_list, callback=on_snapshot)

        return format_response(
            success=True,
            data={
                "subscription_id": subscription_id,
                "type": "index",
                "code_list": request.code_list,
                "status": "active",
            },
        )
    except Exception as e:
        return handle_api_error("subscribe_index", e)


@router.post("/subscribe/stock", summary="订阅股票实时快照")
async def subscribe_stock(request: SubscribeRequest) -> JSONDict:
    """
    订阅股票实时快照数据

    Args:
        request: 订阅请求

    Returns:
        订阅成功信息
    """
    try:
        provider = await get_amazingdata_provider()

        async def on_snapshot(data):
            logger.debug(f"收到股票快照: {data}")

        subscription_id = await subscription_manager.add_subscription(
            client_id="api_client",
            subscription_type="stock",
            code_list=request.code_list,
            callback=on_snapshot,
        )

        await provider.subscribe_stock_snapshot(code_list=request.code_list, callback=on_snapshot)

        return format_response(
            success=True,
            data={
                "subscription_id": subscription_id,
                "type": "stock",
                "code_list": request.code_list,
                "status": "active",
            },
        )
    except Exception as e:
        return handle_api_error("subscribe_stock", e)


@router.post("/subscribe/future", summary="订阅期货实时快照")
async def subscribe_future(request: SubscribeRequest) -> JSONDict:
    """
    订阅期货实时快照数据

    Args:
        request: 订阅请求

    Returns:
        订阅成功信息
    """
    try:
        provider = await get_amazingdata_provider()

        async def on_snapshot(data):
            logger.debug(f"收到期货快照: {data}")

        subscription_id = await subscription_manager.add_subscription(
            client_id="api_client",
            subscription_type="future",
            code_list=request.code_list,
            callback=on_snapshot,
        )

        await provider.subscribe_future_snapshot(code_list=request.code_list, callback=on_snapshot)

        return format_response(
            success=True,
            data={
                "subscription_id": subscription_id,
                "type": "future",
                "code_list": request.code_list,
                "status": "active",
            },
        )
    except Exception as e:
        return handle_api_error("subscribe_future", e)


@router.post("/subscribe/etf", summary="订阅ETF实时快照")
async def subscribe_etf(request: SubscribeRequest) -> JSONDict:
    """
    订阅ETF实时快照数据

    Args:
        request: 订阅请求

    Returns:
        订阅成功信息
    """
    try:
        provider = await get_amazingdata_provider()

        async def on_snapshot(data):
            logger.debug(f"收到ETF快照: {data}")

        subscription_id = await subscription_manager.add_subscription(
            client_id="api_client",
            subscription_type="etf",
            code_list=request.code_list,
            callback=on_snapshot,
        )

        await provider.subscribe_etf_snapshot(code_list=request.code_list, callback=on_snapshot)

        return format_response(
            success=True,
            data={
                "subscription_id": subscription_id,
                "type": "etf",
                "code_list": request.code_list,
                "status": "active",
            },
        )
    except Exception as e:
        return handle_api_error("subscribe_etf", e)


@router.post("/subscribe/kzz", summary="订阅可转债实时快照")
async def subscribe_kzz(request: SubscribeRequest) -> JSONDict:
    """
    订阅可转债实时快照数据

    Args:
        request: 订阅请求

    Returns:
        订阅成功信息
    """
    try:
        provider = await get_amazingdata_provider()

        async def on_snapshot(data):
            logger.debug(f"收到可转债快照: {data}")

        subscription_id = await subscription_manager.add_subscription(
            client_id="api_client",
            subscription_type="kzz",
            code_list=request.code_list,
            callback=on_snapshot,
        )

        await provider.subscribe_kzz_snapshot(code_list=request.code_list, callback=on_snapshot)

        return format_response(
            success=True,
            data={
                "subscription_id": subscription_id,
                "type": "kzz",
                "code_list": request.code_list,
                "status": "active",
            },
        )
    except Exception as e:
        return handle_api_error("subscribe_kzz", e)


@router.post("/subscribe/hkt", summary="订阅港股通实时快照")
async def subscribe_hkt(request: SubscribeRequest) -> JSONDict:
    """
    订阅港股通实时快照数据

    Args:
        request: 订阅请求

    Returns:
        订阅成功信息
    """
    try:
        provider = await get_amazingdata_provider()

        async def on_snapshot(data):
            logger.debug(f"收到港股通快照: {data}")

        subscription_id = await subscription_manager.add_subscription(
            client_id="api_client",
            subscription_type="hkt",
            code_list=request.code_list,
            callback=on_snapshot,
        )

        await provider.subscribe_hkt_snapshot(code_list=request.code_list, callback=on_snapshot)

        return format_response(
            success=True,
            data={
                "subscription_id": subscription_id,
                "type": "hkt",
                "code_list": request.code_list,
                "status": "active",
            },
        )
    except Exception as e:
        return handle_api_error("subscribe_hkt", e)


@router.post("/subscribe/kline", summary="订阅实时K线")
async def subscribe_kline(request: KlineSubscribeRequest) -> JSONDict:
    """
    订阅实时K线数据

    Args:
        request: K线订阅请求

    Returns:
        订阅成功信息
    """
    try:
        provider = await get_amazingdata_provider()

        async def on_kline(data):
            logger.debug(f"收到K线数据: {data}")

        subscription_id = await subscription_manager.add_subscription(
            client_id="api_client",
            subscription_type="kline",
            code_list=request.code_list,
            callback=on_kline,
            period=request.period,
        )

        await provider.subscribe_kline(
            code_list=request.code_list, period=request.period, callback=on_kline
        )

        return format_response(
            success=True,
            data={
                "subscription_id": subscription_id,
                "type": "kline",
                "code_list": request.code_list,
                "period": request.period,
                "status": "active",
            },
        )
    except Exception as e:
        return handle_api_error("subscribe_kline", e)


@router.post("/unsubscribe", summary="停止所有订阅")
async def unsubscribe_all() -> JSONDict:
    """
    停止所有实时数据订阅

    Returns:
        取消订阅的信息
    """
    try:
        provider = await get_amazingdata_provider()

        # 获取当前订阅数量
        current_count = len(subscription_manager.subscriptions)

        # 停止所有订阅
        await provider.unsubscribe_all()

        # 清理管理器
        for subscription_id in list(subscription_manager.subscriptions.keys()):
            await subscription_manager.remove_subscription(subscription_id)

        return format_response(
            success=True,
            data={"message": "All subscriptions stopped", "cancelled_count": current_count},
        )
    except Exception as e:
        return handle_api_error("unsubscribe_all", e)


@router.get("/subscription-status", summary="获取订阅状态")
async def get_subscription_status() -> JSONDict:
    """
    获取当前所有订阅的状态

    Returns:
        订阅状态信息
    """
    try:
        status = subscription_manager.get_subscription_status()
        return format_response(success=True, data=status)
    except Exception as e:
        return handle_api_error("subscription_status", e)


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str) -> None:
    """
    WebSocket实时数据推送端点

    Args:
        websocket: WebSocket连接
        client_id: 客户端ID
    """
    await websocket.accept()
    subscription_manager.websockets[client_id] = websocket

    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            message = json.loads(data)

            # 处理订阅请求
            if message.get("action") == "subscribe":
                code_list = message.get("codes", [])
                sub_type = message.get("type", "stock")

                # 创建订阅回调
                async def push_data(data):
                    await websocket.send_json({"type": sub_type, "data": data})

                # 添加订阅
                await subscription_manager.add_subscription(
                    client_id=client_id,
                    subscription_type=sub_type,
                    code_list=code_list,
                    callback=push_data,
                )

                # 发送确认消息
                await websocket.send_json({"type": "subscription_confirmed", "codes": code_list})

            elif message.get("action") == "unsubscribe":
                # 取消订阅
                await subscription_manager.remove_client_subscriptions(client_id)
                await websocket.send_json({"type": "unsubscribed"})

    except WebSocketDisconnect:
        # 清理断开连接的客户端
        if client_id in subscription_manager.websockets:
            del subscription_manager.websockets[client_id]
        await subscription_manager.remove_client_subscriptions(client_id)
        logger.info(f"WebSocket客户端断开: {client_id}")
