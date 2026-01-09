"""
网关基类

提供外部交易接口的抽象实现。
"""

import logging
from typing import Any, Callable, Dict, Optional


class Gateway:
    """
    交易网关基类

    提供与外部交易系统连接的抽象接口。
    支持模拟和实盘两种模式。
    """

    def __init__(
        self,
        event_engine: Optional[Any] = None,
        message_bus: Optional[Any] = None,
        gateway_name: str = "Gateway",
    ) -> None:
        """
        初始化网关

        Args:
            event_engine: 事件引擎实例
            message_bus: 消息总线实例
            gateway_name: 网关名称
        """
        self._logger = logging.getLogger(f"deepsearch.gateway.{gateway_name}")
        self._event_engine = event_engine
        self._message_bus = message_bus
        self._gateway_name = gateway_name
        self._connected = False
        self._callbacks: Dict[str, Callable] = {}

    @property
    def name(self) -> str:
        """网关名称"""
        return self._gateway_name

    def initialize(self) -> None:
        """初始化网关"""
        self._logger.info(f"Initializing gateway: {self._gateway_name}")

    def connect(self) -> None:
        """连接到交易系统"""
        self._logger.info(f"Connecting gateway: {self._gateway_name}")
        self._connected = True

    def disconnect(self) -> None:
        """断开与交易系统的连接"""
        self._logger.info(f"Disconnecting gateway: {self._gateway_name}")
        self._connected = False

    def close(self) -> None:
        """关闭网关"""
        self.disconnect()
        self._logger.info(f"Gateway closed: {self._gateway_name}")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected

    def register_callback(self, event_type: str, callback: Callable) -> None:
        """注册事件回调"""
        self._callbacks[event_type] = callback

    def send_order(self, order: Dict[str, Any]) -> str:
        """
        发送订单

        Args:
            order: 订单信息

        Returns:
            订单ID
        """
        self._logger.info(f"Sending order: {order}")
        # 模拟模式下返回一个虚拟订单ID
        return f"ORDER_{id(order)}"

    def cancel_order(self, order_id: str) -> bool:
        """
        取消订单

        Args:
            order_id: 订单ID

        Returns:
            是否成功
        """
        self._logger.info(f"Cancelling order: {order_id}")
        return True

    def get_account_info(self) -> Dict[str, Any]:
        """获取账户信息"""
        return {
            "gateway": self._gateway_name,
            "connected": self._connected,
            "balance": 0.0,
            "available": 0.0,
        }

    def get_positions(self) -> list:
        """获取持仓信息"""
        return []
