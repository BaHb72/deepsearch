"""Protocol definitions used across AmazingData integrations."""

from __future__ import annotations

from typing import Any, Callable, Mapping, Protocol


class ProviderPayloadConvertible(Protocol):
    """����װ�������ṩ������ʽ�Ķ���."""

    def to_provider_payload(self) -> Mapping[str, Any]:
        ...


class AmazingDataSDKProtocol(Protocol):
    """AmazingData SDK ģ���ĵ��·��������Ҫ�Ĳ���."""

    constant: Any
    BaseData: Any
    MarketData: Any
    InfoData: Any
    KLine: Any
    SubscribeData: Callable[..., Any]

    def login(self, username: str, password: str, host: str, port: int) -> int | bool:
        ...

    def logout(self, username: str | None = None) -> bool | None:
        ...

    def update_password(self, username: str, old_password: str, new_password: str) -> bool:
        ...


__all__ = ["ProviderPayloadConvertible", "AmazingDataSDKProtocol"]
