"""市场实时行情 API 基本连通性与缓存回退测试"""

import json
from types import SimpleNamespace

import pytest
from starlette.applications import Starlette
from starlette.requests import Request

from deepsearch.webui.api.endpoints.market_data import live_api


@pytest.mark.parametrize(
    "path",
    [
        "/api/market/live/strength",
        "/api/market/live/board-overview",
        "/api/market/live/order-imbalance",
        "/api/market/live/auction-quality",
    ],
)
def test_market_live_endpoints_registered(test_client, path):
    """基础保障：接口已注册。"""
    response = test_client.get(path)
    assert response.status_code != 404, f"Endpoint {path} should be registered"


@pytest.mark.asyncio
async def test_market_strength_returns_cached_when_provider_offline(monkeypatch):
    """provider 断开时应直接返回缓存数据，而不是抛 503。"""

    class DummyResult:
        def __init__(self):
            self.items = [
                {
                    "board": "人工智能",
                    "window": "1m",
                    "speed_per_min": 1.23,
                    "amount_total": 4.56,
                }
            ]
            self.as_of = "2025-01-01T09:30:00Z"
            self.stale = True
            self.cached_at = "2025-01-01T09:31:00Z"
            self.expires_at = "2025-01-01T09:32:00Z"

    class DummyReader:
        def __init__(self):
            self.result = DummyResult()

        async def fetch_strength(self, windows, *, boards=None, limit=None):
            return self.result

    async def fake_ensure_runtime(app_state, settings):
        return None

    refresh_calls = {"count": 0}

    async def fake_refresh(app_state):
        refresh_calls["count"] += 1

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "refresh_market_data_once", fake_refresh)

    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=DummyReader(),
        market_data_pipeline=SimpleNamespace(
            boards=["人工智能"],
            capital_windows=(SimpleNamespace(name="1m"),),
        ),
        market_data_provider=SimpleNamespace(is_connected=lambda: False),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = SimpleNamespace()

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/strength",
            "headers": [],
            "query_string": b"",
        },
        empty_receive,
    )

    response = await live_api.get_market_strength(request, windows=None, boards=None, limit=None)
    assert response.status_code == 200
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["items"], "应返回缓存的行情数据"
    assert payload["stale"] is True
    assert refresh_calls["count"] == 0, "断连状态下不应触发刷新"


@pytest.mark.asyncio
async def test_order_imbalance_returns_offline_payload_when_cache_empty(monkeypatch):
    """���ݻ�����ʧ��ʱӦ���� 200 + DATA_SOURCE_OFFLINE ǳ¾ɲ�����"""

    class EmptyResult:
        def __init__(self):
            self.items: list[dict[str, object]] = []
            self.as_of = None
            self.stale = False
            self.cached_at = None
            self.expires_at = None

    class DummyReader:
        def __init__(self):
            self.result = EmptyResult()

        async def fetch_order_imbalance(self, window, *, limit=None):
            return self.result

    async def fake_ensure_runtime(app_state, settings):
        return None

    async def fake_refresh(app_state):
        raise AssertionError("provider offline should not refresh")

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "refresh_market_data_once", fake_refresh)

    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_order_window=SimpleNamespace(name="1m")),
        market_data_reader=DummyReader(),
        market_data_pipeline=None,
        market_data_provider=SimpleNamespace(name="akshare", is_connected=lambda: False),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = SimpleNamespace()

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/order-imbalance",
            "headers": [],
            "query_string": b"",
        },
        empty_receive,
    )

    response = await live_api.get_order_imbalance(request, window=None, limit=50)
    assert response.status_code == 200
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["items"] == []
    assert payload["detail"]["code"] == "DATA_SOURCE_OFFLINE"
    assert payload["stale"] is True
    assert payload["data_source"] == "akshare"


@pytest.mark.asyncio
async def test_data_source_status_endpoint(monkeypatch):
    """/api/market/live/data-source/status ����Ӧ��������Ϣ��"""

    class DummyOrchestrator:
        def __init__(self):
            self.snapshot = {
                "active": "akshare",
                "adapters": {"akshare": {"status": "healthy"}},
            }

        def get_status_snapshot(self):
            return self.snapshot

    async def fake_ensure_runtime(app_state, settings):
        return None

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(
        live_api,
        "_enabled_adapter_names",
        lambda settings: ["amazingdata", "akshare"],
    )

    app_state = SimpleNamespace(
        market_data_orchestrator=DummyOrchestrator(),
        market_data_active_source=None,
        market_data_health={"sources": {"akshare": {"status": "healthy"}}},
    )
    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = SimpleNamespace()

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/data-source/status",
            "headers": [],
            "query_string": b"",
        },
        empty_receive,
    )

    response = await live_api.get_data_source_status(request)
    assert response.status_code == 200
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["active"] == "akshare"
    assert payload["available"] == ["amazingdata", "akshare"]
    assert payload["adapters"]["akshare"]["status"] == "healthy"
    assert payload["detail"]["sources"]["akshare"]["status"] == "healthy"
    assert payload["timestamp"]
