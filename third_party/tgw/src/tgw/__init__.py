"""TGW SDK 的轻量级占位实现，用于在缺乏二进制扩展时维持导入稳定。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

__all__ = ["ILogSpi", "TGWClient", "login", "logout"]


class ILogSpi(Protocol):
    """日志回调协议，占位提供接口签名。"""

    def on_log(self, message: str) -> None:
        ...


@dataclass(slots=True)
class TGWClient:
    """TGW 客户端的占位实现，记录连接信息。"""

    host: str
    port: int
    username: str

    def connect(self) -> None:  # pragma: no cover - 仅用于补全接口
        """模拟连接操作。"""

    def disconnect(self) -> None:  # pragma: no cover - 仅用于补全接口
        """模拟断连操作。"""


def login(username: str, password: str, host: str, port: int) -> TGWClient:
    """返回一个占位客户端对象，模拟登录流程。"""

    return TGWClient(host=host, port=port, username=username)


def logout(client: TGWClient) -> None:
    """模拟登出流程。"""

    client.disconnect()
