"""
QMT股票订阅管理API

提供动态管理QMT客户端订阅股票列表的功能
"""

import time
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/qmt/subscription", tags=["QMT订阅管理"])


class SubscriptionRequest(BaseModel):
    """订阅请求模型"""

    symbols: List[str] = Field(..., description="股票代码列表")
    action: str = Field("add", description="操作类型: add/remove/replace")
    client_id: Optional[str] = Field(None, description="客户端ID，None表示所有客户端")


class SubscriptionResponse(BaseModel):
    """订阅响应模型"""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class SubscriptionManager:
    """订阅管理器（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # 订阅列表
        self.subscriptions: Dict[str, Set[str]] = {}  # client_id -> set of symbols
        self.global_symbols: Set[str] = set()  # 全局订阅列表

        # 默认订阅列表（空列表，完全由服务器端控制）
        self.default_symbols = []

        # 连接的QMT客户端
        self.connected_clients: Dict[str, Dict] = {}  # client_id -> client_info

        # 待推送的订阅更新
        self.pending_updates: Dict[str, List[Dict]] = {}  # client_id -> list of updates

        # 统计信息
        self.stats = {
            "total_symbols": 0,
            "total_clients": 0,
            "last_update_time": None,
            "update_count": 0,
        }

        self._initialized = True
        logger.info("订阅管理器初始化完成")

    def add_client(self, client_id: str, client_info: Dict) -> None:
        """
        添加客户端

        Args:
            client_id: 客户端ID
            client_info: 客户端信息
        """
        self.connected_clients[client_id] = client_info

        # 为新客户端初始化订阅列表
        if client_id not in self.subscriptions:
            self.subscriptions[client_id] = set(self.default_symbols)

        self.stats["total_clients"] = len(self.connected_clients)
        logger.info(f"添加QMT客户端: {client_id}")

    def remove_client(self, client_id: str) -> None:
        """
        移除客户端

        Args:
            client_id: 客户端ID
        """
        if client_id in self.connected_clients:
            del self.connected_clients[client_id]

        if client_id in self.pending_updates:
            del self.pending_updates[client_id]

        self.stats["total_clients"] = len(self.connected_clients)
        logger.info(f"移除QMT客户端: {client_id}")

    def update_subscription(
        self, symbols: List[str], action: str = "add", client_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        更新订阅列表

        Args:
            symbols: 股票代码列表
            action: 操作类型 (add/remove/replace)
            client_id: 客户端ID，None表示全局

        Returns:
            更新结果
        """
        symbols_set = set(symbols)
        affected_clients = []

        if client_id:
            # 更新特定客户端
            if client_id not in self.subscriptions:
                self.subscriptions[client_id] = set()

            if action == "add":
                self.subscriptions[client_id].update(symbols_set)
            elif action == "remove":
                self.subscriptions[client_id] -= symbols_set
            elif action == "replace":
                self.subscriptions[client_id] = symbols_set

            affected_clients = [client_id]

        else:
            # 更新全局订阅
            if action == "add":
                self.global_symbols.update(symbols_set)
            elif action == "remove":
                self.global_symbols -= symbols_set
            elif action == "replace":
                self.global_symbols = symbols_set

            # 应用到所有客户端
            for cid in self.subscriptions:
                if action == "add":
                    self.subscriptions[cid].update(symbols_set)
                elif action == "remove":
                    self.subscriptions[cid] -= symbols_set
                elif action == "replace":
                    self.subscriptions[cid] = symbols_set.copy()

            affected_clients = list(self.subscriptions.keys())

            # 重要：全局更新时，也要为所有已连接的客户端创建更新
            # 即使他们不在subscriptions中
            for cid in self.connected_clients.keys():
                if cid not in affected_clients:
                    affected_clients.append(cid)
                    # 确保客户端有订阅列表
                    if cid not in self.subscriptions:
                        self.subscriptions[cid] = symbols_set.copy()

        # 创建更新消息
        update_msg = {
            "type": "SUBSCRIPTION_UPDATE",
            "action": action,
            "symbols": list(symbols_set),
            "timestamp": time.time(),
        }

        # 添加到待推送队列
        for cid in affected_clients:
            if cid not in self.pending_updates:
                self.pending_updates[cid] = []
            self.pending_updates[cid].append(update_msg)

        # 更新统计
        self.stats["total_symbols"] = len(self.global_symbols)
        self.stats["last_update_time"] = time.time()
        self.stats["update_count"] += 1

        return {
            "affected_clients": affected_clients,
            "action": action,
            "symbols_count": len(symbols_set),
            "total_symbols": sum(len(s) for s in self.subscriptions.values()),
        }

    def get_client_symbols(self, client_id: str) -> List[str]:
        """
        获取客户端的订阅列表

        Args:
            client_id: 客户端ID

        Returns:
            股票代码列表
        """
        # 如果客户端不存在，先添加到订阅列表
        if client_id not in self.subscriptions:
            # 使用全局订阅作为初始订阅
            self.subscriptions[client_id] = self.global_symbols.copy()
            logger.info(f"为新客户端 {client_id} 设置初始订阅: {list(self.global_symbols)}")

        # 返回全局订阅和客户端特定订阅的并集
        client_symbols = self.subscriptions.get(client_id, set())
        combined_symbols = self.global_symbols | client_symbols
        return list(combined_symbols)

    def get_pending_updates(self, client_id: str) -> List[Dict]:
        """
        获取并清空客户端的待推送更新

        Args:
            client_id: 客户端ID

        Returns:
            更新消息列表
        """
        if client_id in self.pending_updates:
            updates = self.pending_updates[client_id]
            del self.pending_updates[client_id]
            return updates
        return []

    def get_status(self) -> Dict[str, Any]:
        """
        获取订阅管理器状态

        Returns:
            状态信息
        """
        return {
            "global_symbols": list(self.global_symbols),
            "global_symbols_count": len(self.global_symbols),
            "total_clients": len(self.connected_clients),
            "active_subscriptions": {
                cid: {"symbols_count": len(symbols), "symbols": list(symbols)[:10]}  # 只显示前10个
                for cid, symbols in self.subscriptions.items()
            },
            "pending_updates_count": sum(len(updates) for updates in self.pending_updates.values()),
            "stats": self.stats,
        }


# 全局订阅管理器实例
subscription_manager = SubscriptionManager()


@router.post("/update", response_model=SubscriptionResponse)
async def update_subscription(request: SubscriptionRequest):
    """
    更新股票订阅列表

    支持三种操作：
    - add: 添加股票到订阅列表
    - remove: 从订阅列表移除股票
    - replace: 替换整个订阅列表
    """
    try:
        result = subscription_manager.update_subscription(
            symbols=request.symbols, action=request.action, client_id=request.client_id
        )

        return SubscriptionResponse(
            success=True,
            message=f"成功更新订阅，影响 {len(result['affected_clients'])} 个客户端",
            data=result,
        )

    except Exception as e:
        logger.error(f"更新订阅失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def get_subscription_list(client_id: Optional[str] = Query(None, description="客户端ID")):
    """
    获取订阅列表

    Args:
        client_id: 客户端ID，None返回全局订阅列表
    """
    try:
        if client_id:
            symbols = subscription_manager.get_client_symbols(client_id)
            return {
                "success": True,
                "client_id": client_id,
                "symbols": symbols,
                "count": len(symbols),
            }
        else:
            return {
                "success": True,
                "global_symbols": list(subscription_manager.global_symbols),
                "default_symbols": subscription_manager.default_symbols,
                "count": len(subscription_manager.global_symbols),
            }

    except Exception as e:
        logger.error(f"获取订阅列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_subscription_status():
    """获取订阅管理器状态"""
    try:
        status = subscription_manager.get_status()
        return {"success": True, "data": status}

    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch")
async def batch_update_subscriptions(updates: List[SubscriptionRequest]):
    """
    批量更新订阅

    Args:
        updates: 批量更新请求列表
    """
    try:
        results = []

        for update in updates:
            result = subscription_manager.update_subscription(
                symbols=update.symbols, action=update.action, client_id=update.client_id
            )
            results.append(result)

        return {
            "success": True,
            "message": f"成功处理 {len(updates)} 个更新请求",
            "results": results,
        }

    except Exception as e:
        logger.error(f"批量更新失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clients")
async def get_connected_clients():
    """获取已连接的QMT客户端列表"""
    try:
        clients = []
        for client_id, client_info in subscription_manager.connected_clients.items():
            clients.append(
                {
                    "client_id": client_id,
                    "info": client_info,
                    "symbols_count": len(subscription_manager.subscriptions.get(client_id, [])),
                    "has_pending_updates": client_id in subscription_manager.pending_updates,
                }
            )

        return {"success": True, "clients": clients, "total": len(clients)}

    except Exception as e:
        logger.error(f"获取客户端列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/updates/{client_id}")
async def get_client_updates(client_id: str):
    """
    获取客户端的待推送更新

    Args:
        client_id: 客户端ID
    """
    try:
        updates = subscription_manager.get_pending_updates(client_id)

        return {"success": True, "client_id": client_id, "updates": updates, "count": len(updates)}

    except Exception as e:
        logger.error(f"获取更新失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
