"""Notification service unit tests."""

from __future__ import annotations

import pytest
from httpx import Request, Response
from typing import cast

from deepsearch.config.models.notifications import NotificationCategoryConfig, NotificationsConfig
from deepsearch.infrastructure.notifications import (
    NotificationQuotaGuard,
    NotificationService,
    QuotaExceededError,
)
from deepsearch.infrastructure.notifications.client import XtuisClient


class DummyClient:
    """Simple mock client for tests."""

    def __init__(self, status_code: int = 200, payload: dict | None = None):
        self.status_code = status_code
        self.payload = payload or {"ok": True}
        self.calls: list[dict] = []

    async def send(
        self, *, channel: str, token: str, title: str, content: str | None = None
    ) -> Response:
        self.calls.append(
            {
                "channel": channel,
                "token": token,
                "title": title,
                "content": content,
            }
        )
        request = Request("GET", f"https://{channel}.example/send")
        return Response(self.status_code, content=b"", request=request)

    async def aclose(self) -> None:  # pragma: no cover - tests不会触发
        pass


@pytest.mark.asyncio
async def test_quota_guard_enforces_limit() -> None:
    guard = NotificationQuotaGuard()
    category = NotificationCategoryConfig(enabled=True, max_per_window=2, window_seconds=60)

    decision1 = await guard.check_and_consume("wechat", "alert", category)
    assert decision1.allowed
    assert decision1.current_count == 1
    assert decision1.remaining == 1

    decision2 = await guard.check_and_consume("wechat", "alert", category)
    assert decision2.allowed
    assert decision2.current_count == 2
    assert decision2.remaining == 0

    decision3 = await guard.check_and_consume("wechat", "alert", category)
    assert not decision3.allowed
    assert decision3.remaining == 0


@pytest.mark.asyncio
async def test_notification_service_send_success() -> None:
    config = NotificationsConfig(
        enabled=True,
        wechat_token="test-token",
        categories={
            "alert": NotificationCategoryConfig(
                enabled=True,
                max_per_window=3,
                window_seconds=60,
                channels=["wechat"],
            )
        },
    )
    client = DummyClient(status_code=200, payload={"message": "ok"})
    service = NotificationService(
        config, client=cast(XtuisClient, client), quota_guard=NotificationQuotaGuard()
    )

    result = await service.send(title="Test", content="Body", channel="wechat", category="alert")

    assert result.success
    assert result.status_code == 200
    assert result.channel == "wechat"
    assert result.category == "alert"
    assert client.calls and client.calls[0]["token"] == "test-token"


@pytest.mark.asyncio
async def test_notification_service_quota_exceeded() -> None:
    config = NotificationsConfig(
        enabled=True,
        wechat_token="token",
        categories={
            "alert": NotificationCategoryConfig(
                enabled=True,
                max_per_window=1,
                window_seconds=300,
                channels=["wechat"],
            )
        },
    )
    client = DummyClient()
    service = NotificationService(
        config, client=cast(XtuisClient, client), quota_guard=NotificationQuotaGuard()
    )

    await service.send(title="First", content="Body", channel="wechat", category="alert")

    with pytest.raises(QuotaExceededError):
        await service.send(title="Second", content="Body", channel="wechat", category="alert")
