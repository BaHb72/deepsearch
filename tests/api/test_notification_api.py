import asyncio
from typing import Dict

import pytest
from core.config import get_config, reload_config
from core.config.loader import ensure_env_config_file
from core.config.models.notifications import NotificationsConfig
from core.core.runtime.context import get_context
from core.infrastructure.notifications import NotificationQuotaGuard, NotificationService

from apps.api.api.endpoints.notifications import push as notification_push

CONFIG_PATH = ensure_env_config_file("dev")


def _refresh_notification_service() -> None:
    context = get_context()

    async def _reset() -> None:
        if context.has_service("notifications"):
            service = context.get_service("notifications")
            if isinstance(service, NotificationService):
                await service.shutdown()
        config = get_config().notifications or NotificationsConfig()
        context.register_service(
            "notifications", NotificationService(config, quota_guard=NotificationQuotaGuard())
        )

    asyncio.get_event_loop().run_until_complete(_reset())


@pytest.fixture(autouse=True)
def restore_notification_config():
    # Backup notification config before each test and restore afterward.
    backup_text = CONFIG_PATH.read_text(encoding="utf-8")
    yield
    CONFIG_PATH.write_text(backup_text, encoding="utf-8")
    reload_config()
    _refresh_notification_service()


@pytest.mark.asyncio
async def test_get_notification_config(async_client):
    response = await async_client.get("/api/notification/config")
    assert response.status_code == 200
    data: Dict = response.json()
    assert "enabled" in data
    assert "titleTemplate" in data
    assert "bodyTemplate" in data
    assert "baseUrls" in data
    assert "categories" in data


@pytest.mark.asyncio
async def test_update_notification_config(async_client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(notification_push, "_get_config_path", lambda: CONFIG_PATH)

    payload = {
        "enabled": True,
        "defaultChannel": ["wechat"],
        "wechatToken": "unit-test-token",
        "barkToken": "unit-test-token",
        "requestTimeout": 6.5,
        "retryAttempts": 2,
        "retryDelay": 1.0,
        "titleTemplate": "测试默认标题 {symbol}",
        "bodyTemplate": "最新价格：{price}",
        "baseUrls": {"wechat": "https://wx.xtuis.cn", "bark": "https://bark.xtuis.cn"},
        "categories": [
            {
                "name": "alert",
                "enabled": True,
                "maxPerWindow": 3,
                "windowSeconds": 180,
                "channels": ["wechat"],
            },
            {
                "name": "info",
                "enabled": True,
                "maxPerWindow": 10,
                "windowSeconds": 600,
                "channels": ["wechat", "bark"],
            },
        ],
    }

    response = await async_client.put("/api/notification/config", json=payload)
    assert response.status_code == 200
    updated = response.json()
    assert updated["defaultChannel"] == ["wechat"]
    assert updated["wechatToken"] == "unit-test-token"
    assert updated["barkToken"] == "unit-test-token"
    assert updated["titleTemplate"] == "测试默认标题 {symbol}"
    assert updated["bodyTemplate"] == "最新价格：{price}"
    assert updated["hasWechatToken"] is True
    assert any(item["name"] == "info" for item in updated["categories"])

    check_resp = await async_client.get("/api/notification/config")
    assert check_resp.status_code == 200
    check_data = check_resp.json()
    assert check_data["hasWechatToken"] is True
    assert check_data["titleTemplate"] == "测试默认标题 {symbol}"
    assert check_data["bodyTemplate"] == "最新价格：{price}"
    assert any(cat["name"] == "info" for cat in check_data["categories"])


@pytest.mark.asyncio
async def test_quota_endpoints(async_client):
    reset_resp = await async_client.post("/api/notification/quotas/reset")
    assert reset_resp.status_code == 200
    data = reset_resp.json()
    assert data.get("success") is True

    quota_resp = await async_client.get("/api/notification/quotas")
    assert quota_resp.status_code == 200
    quota_data = quota_resp.json()
    assert "data" in quota_data
