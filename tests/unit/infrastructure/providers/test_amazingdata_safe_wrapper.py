from typing import Any, Mapping

import pytest

from deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_safe_wrapper import (
    AmazingDataSafeWrapper,
)
from deepsearch.infrastructure.providers.implementations.amazingdata.subscription import (
    SubscriptionInfo,
)


class _DummyProxy:
    is_running = True

    def start(self) -> bool:
        return True

    def execute(self, method: str, *args: Any, **kwargs: Any) -> Any:
        return {"success": True, "result": None, "error": None, "error_type": None, "timestamp": 0.0}

    def health_check(self) -> Mapping[str, Any]:
        return {"status": "ok"}

    def get_stats(self) -> Mapping[str, Any]:
        return {}


class _DummyPool:
    def __init__(self) -> None:
        self.proxy = _DummyProxy()

    def get_or_create(self, *args: Any, **kwargs: Any) -> _DummyProxy:
        return self.proxy

    def stop(self, *args: Any, **kwargs: Any) -> None:
        return None

    def wait_for_login_slot(self, *args: Any, **kwargs: Any) -> None:
        return None

    def record_login_result(self, *args: Any, **kwargs: Any) -> None:
        return None


class _DummyBridge:
    def __init__(self) -> None:
        self.restored: list[Mapping[str, SubscriptionInfo]] = []

    async def snapshot_subscriptions(self) -> Mapping[str, SubscriptionInfo]:
        return {"000001": SubscriptionInfo(data_type="snapshot")}

    async def drain_subscriptions(self) -> Mapping[str, SubscriptionInfo]:
        return {"000002": SubscriptionInfo(data_type="snapshot")}

    async def restore_subscriptions(self, snapshot: Mapping[str, SubscriptionInfo]) -> None:
        self.restored.append(dict(snapshot))


@pytest.mark.asyncio
async def test_safe_wrapper_subscription_bridge_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_pool = _DummyPool()
    monkeypatch.setattr(
        "deepsearch.infrastructure.providers.implementations.amazingdata.amazingdata_safe_wrapper.get_global_pool",
        lambda: dummy_pool,
    )

    wrapper = AmazingDataSafeWrapper(datasource_id="bridge-test", auto_restart=False)
    bridge = _DummyBridge()
    wrapper.register_subscription_bridge(bridge)

    snapshot = await wrapper.snapshot_subscriptions()
    assert snapshot == {"000001": SubscriptionInfo(data_type="snapshot")}

    drained = await wrapper.drain_subscriptions()
    assert drained == {"000002": SubscriptionInfo(data_type="snapshot")}

    await wrapper.restore_subscriptions(snapshot)
    assert bridge.restored and bridge.restored[-1] == snapshot

    wrapper.unregister_subscription_bridge(bridge)

    empty_snapshot = await wrapper.snapshot_subscriptions()
    assert empty_snapshot == {}
