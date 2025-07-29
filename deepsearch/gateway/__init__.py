"""
网关模块

提供外部系统接入的抽象网关接口。
"""
from .gateway import (
    BaseGateway,
    Gateway,
    GatewayStatus,
)

__all__ = [
    "BaseGateway",
    "Gateway",
    "GatewayStatus",
]
