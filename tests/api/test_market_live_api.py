"""市场实时行情 API 基本连通性与缓存回退测试"""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.applications import Starlette
from starlette.requests import Request

from apps.api.api.endpoints.market_data import live_api


@pytest.mark.parametrize(
    "path",
    [
        "/api/market/live/strength",
        "/api/market/live/board-overview",
        "/api/market/live/board-drivers",
        "/api/market/live/order-imbalance",
        "/api/market/live/auction-quality",
    ],
)
def test_market_live_endpoints_registered(test_client, path):
    """基础保障：接口已注册。"""
    response = test_client.get(path)
    assert response.status_code != 404, f"Endpoint {path} should be registered"


def test_resolve_fallback_timeout_uses_cold_start_budget_in_no_trade_when_not_warm():
    manager = SimpleNamespace(is_source_warm=lambda source: False)
    app_state = SimpleNamespace(market_data_fallback_manager=manager)

    timeout_seconds = live_api._resolve_fallback_timeout_seconds(
        app_state,
        "miniqmt",
        phase="no_trade",
        warm_timeout_seconds=10.0,
    )

    assert timeout_seconds == live_api._LIVE_FALLBACK_COLD_START_TIMEOUT_SECONDS


def test_resolve_fallback_timeout_keeps_warm_budget_when_source_ready():
    manager = SimpleNamespace(is_source_warm=lambda source: True)
    app_state = SimpleNamespace(market_data_fallback_manager=manager)

    timeout_seconds = live_api._resolve_fallback_timeout_seconds(
        app_state,
        "amazingdata",
        phase="off_day",
        warm_timeout_seconds=12.0,
    )

    assert timeout_seconds == 12.0


def test_resolve_fallback_timeout_uses_cold_budget_when_handle_warm_but_not_ready():
    manager = SimpleNamespace(
        is_source_ready=lambda source: False,
        is_source_warm=lambda source: True,
    )
    app_state = SimpleNamespace(market_data_fallback_manager=manager)

    timeout_seconds = live_api._resolve_fallback_timeout_seconds(
        app_state,
        "miniqmt",
        phase="no_trade",
        warm_timeout_seconds=30.0,
    )

    assert timeout_seconds == live_api._LIVE_FALLBACK_COLD_START_TIMEOUT_SECONDS


def test_resolve_fallback_timeout_keeps_warm_budget_for_amazingdata_when_not_ready():
    manager = SimpleNamespace(is_source_ready=lambda source: False)
    app_state = SimpleNamespace(market_data_fallback_manager=manager)

    timeout_seconds = live_api._resolve_fallback_timeout_seconds(
        app_state,
        "amazingdata",
        phase="no_trade",
        warm_timeout_seconds=20.0,
    )

    assert timeout_seconds == 20.0


def test_resolve_fallback_timeout_keeps_cold_budget_for_akshare_after_hours_when_ready():
    manager = SimpleNamespace(is_source_ready=lambda source: True)
    app_state = SimpleNamespace(market_data_fallback_manager=manager)

    timeout_seconds = live_api._resolve_fallback_timeout_seconds(
        app_state,
        "akshare",
        phase="no_trade",
        warm_timeout_seconds=12.0,
    )

    assert timeout_seconds == live_api._LIVE_FALLBACK_AKSHARE_TIMEOUT_SECONDS


def test_unready_source_block_detail_marks_amazingdata_offline_when_dask_not_ready():
    app_state = SimpleNamespace(
        backend_runtime=SimpleNamespace(
            dask_init_manager=SimpleNamespace(
                amazingdata_ready=False,
                phase=SimpleNamespace(value="initializing"),
            )
        )
    )

    detail = live_api._unready_source_block_detail(
        app_state,
        source="amazingdata",
        phase="no_trade",
    )

    assert detail is not None
    assert detail["code"] == "DATA_SOURCE_OFFLINE"
    assert detail["runtime_phase"] == "initializing"


def test_unready_source_block_detail_ignores_non_amazingdata_sources():
    app_state = SimpleNamespace(
        backend_runtime=SimpleNamespace(
            dask_init_manager=SimpleNamespace(amazingdata_ready=False),
        )
    )

    detail = live_api._unready_source_block_detail(
        app_state,
        source="akshare",
        phase="no_trade",
    )

    assert detail is None


def test_auto_fallback_sources_keeps_amazingdata_before_akshare_in_no_trade():
    fallback_a = SimpleNamespace(
        source="amazingdata",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    fallback_b = SimpleNamespace(
        source="akshare",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "strength": SimpleNamespace(
                    enable_auto_fallback=True,
                    fallbacks=(fallback_a, fallback_b),
                )
            }
        )
    )
    app_state = SimpleNamespace(
        market_data_fallback_manager=SimpleNamespace(
            # no_trade 下即使 amazingdata 未 ready，也不允许后移到 akshare 之后
            is_source_ready=lambda source: source
            != "amazingdata",
        )
    )

    sources = live_api._auto_fallback_sources(
        settings,
        "strength",
        app_state=app_state,
        phase="no_trade",
        error_code="DATA_SOURCE_EMPTY",
    )

    assert sources == ["amazingdata", "miniqmt", "akshare"]


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

        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
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
async def test_market_strength_returns_recent_success_payload_when_empty_in_no_trade(monkeypatch):
    """盘后主源空结果时，应回退最近一次成功快照而不是返回空表。"""

    live_api._RECENT_SUCCESS_PAYLOADS.clear()

    class EmptyResult:
        def __init__(self):
            self.items: list[dict[str, object]] = []
            self.as_of = None
            self.stale = False
            self.cached_at = None
            self.expires_at = None

    class DummyReader:
        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            return EmptyResult()

    async def fake_ensure_runtime(app_state, settings):
        return None

    refresh_calls = {"count": 0}

    async def fake_refresh(app_state):
        refresh_calls["count"] += 1

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "refresh_market_data_once", fake_refresh)
    monkeypatch.setattr(live_api, "_resolve_market_phase", lambda: "no_trade")

    live_api._set_recent_success_payload(
        "strength:1m:*:all:auto",
        {
            "windows": ["1m"],
            "boards": ["人工智能"],
            "items": [
                {
                    "board": "人工智能",
                    "window": "1m",
                    "speed_per_min": 1.23,
                    "amount_total": 4.56,
                    "data_source": "amazingdata",
                }
            ],
            "asOf": "2025-01-01T15:00:00Z",
            "stale": False,
            "retrieved_at": "2025-01-01T15:00:01Z",
            "data_source": "amazingdata",
        },
    )

    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=DummyReader(),
        market_data_pipeline=SimpleNamespace(
            boards=["人工智能"],
            capital_windows=(SimpleNamespace(name="1m"),),
        ),
        market_data_provider=SimpleNamespace(is_connected=lambda: True),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = SimpleNamespace(market_data=SimpleNamespace(modules={}))

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
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"], "应回退最近一次成功快照"
    assert payload["stale"] is True
    assert payload["detail"]["cache_fallback"]["code"] == "DATA_SOURCE_EMPTY"
    assert payload["detail"]["latest_failure"]["code"] == "DATA_SOURCE_EMPTY"
    assert refresh_calls["count"] == 0


@pytest.mark.asyncio
async def test_market_strength_off_hours_prefers_recent_snapshot_before_fallback(monkeypatch):
    """盘后有最近快照时，应直接返回，不阻塞在 fallback 拉取。"""

    live_api._RECENT_SUCCESS_PAYLOADS.clear()

    class EmptyResult:
        def __init__(self):
            self.items: list[dict[str, object]] = []
            self.as_of = None
            self.stale = False
            self.cached_at = None
            self.expires_at = None

    class DummyReader:
        def __init__(self):
            self.calls: list[str | None] = []

        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            self.calls.append(source)
            return EmptyResult()

    async def fake_ensure_runtime(app_state, settings):
        return None

    fallback_calls = {"count": 0}

    async def fake_fallback(app_state, module, target_source, *, phase=None):
        fallback_calls["count"] += 1
        return {"writer_source": target_source}

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "_ensure_fallback_data", fake_fallback)
    monkeypatch.setattr(live_api, "_resolve_market_phase", lambda: "no_trade")

    live_api._set_recent_success_payload(
        "strength:1m:*:all:auto",
        {
            "windows": ["1m"],
            "boards": ["人工智能"],
            "items": [
                {
                    "board": "人工智能",
                    "window": "1m",
                    "speed_per_min": 1.23,
                    "amount_total": 4.56,
                    "data_source": "amazingdata",
                }
            ],
            "asOf": "2025-01-01T15:00:00Z",
            "stale": False,
            "retrieved_at": "2025-01-01T15:00:01Z",
            "data_source": "amazingdata",
        },
    )

    fallback_rule = SimpleNamespace(
        source="akshare",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "strength": SimpleNamespace(enable_auto_fallback=True, fallbacks=(fallback_rule,))
            }
        )
    )
    reader = DummyReader()
    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=reader,
        market_data_pipeline=SimpleNamespace(
            boards=["人工智能"],
            capital_windows=(SimpleNamespace(name="1m"),),
        ),
        market_data_provider=SimpleNamespace(is_connected=lambda: True),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = settings

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
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"], "应优先返回最近快照"
    assert payload["stale"] is True
    assert payload["detail"]["latest_failure"]["code"] == "DATA_SOURCE_EMPTY"
    assert fallback_calls["count"] == 0
    assert reader.calls == [None]


@pytest.mark.asyncio
async def test_market_strength_probes_other_cached_sources_when_primary_empty(monkeypatch):
    live_api._RECENT_SUCCESS_PAYLOADS.clear()

    class Result:
        def __init__(self, items):
            self.items = items
            self.as_of = "2025-01-01T15:00:00Z"
            self.stale = True
            self.cached_at = "2025-01-01T15:00:01Z"
            self.expires_at = "2025-01-01T15:03:00Z"

    class DummyReader:
        def __init__(self):
            self.calls: list[str | None] = []

        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            self.calls.append(source)
            if source == "akshare":
                return Result(
                    [
                        {
                            "board": "人工智能",
                            "window": "1m",
                            "speed_per_min": 2.34,
                            "amount_total": 5.67,
                            "data_source": "akshare",
                        }
                    ]
                )
            return Result([])

    async def fake_ensure_runtime(app_state, settings):
        return None

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)

    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "strength": SimpleNamespace(enable_auto_fallback=False, fallbacks=()),
            }
        )
    )
    reader = DummyReader()
    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=reader,
        market_data_pipeline=SimpleNamespace(
            boards=["人工智能"],
            capital_windows=(SimpleNamespace(name="1m"),),
        ),
        market_data_provider=SimpleNamespace(name="miniqmt", is_connected=lambda: False),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = settings

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
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"], "应从其他 source 的缓存中命中非空快照"
    assert payload["data_source"] == "akshare"
    assert payload["detail"]["cache_probe"]["source"] == "akshare"
    assert reader.calls == ["miniqmt", "miniqmt", "amazingdata", "akshare"]


@pytest.mark.asyncio
async def test_market_strength_prefers_runtime_active_source_when_module_primary_missing(
    monkeypatch,
):
    live_api._RECENT_SUCCESS_PAYLOADS.clear()

    class Result:
        def __init__(self, items):
            self.items = items
            self.as_of = "2025-01-01T15:00:00Z"
            self.stale = False
            self.cached_at = "2025-01-01T15:00:01Z"
            self.expires_at = "2025-01-01T15:03:00Z"

    class DummyReader:
        def __init__(self):
            self.calls: list[str | None] = []

        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            self.calls.append(source)
            if source == "miniqmt":
                return Result(
                    [
                        {
                            "board": "人工智能",
                            "window": "1m",
                            "speed_per_min": 1.23,
                            "amount_total": 4.56,
                            "data_source": "miniqmt",
                        }
                    ]
                )
            return Result([])

    async def fake_ensure_runtime(app_state, settings):
        return None

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)

    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "strength": SimpleNamespace(enable_auto_fallback=False, fallbacks=()),
            }
        )
    )
    reader = DummyReader()
    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=reader,
        market_data_pipeline=SimpleNamespace(
            boards=["人工智能"],
            capital_windows=(SimpleNamespace(name="1m"),),
        ),
        market_data_provider=SimpleNamespace(name="miniqmt", is_connected=lambda: False),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = settings

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
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"], "应命中 runtime active source 的首轮读取"
    assert payload["data_source"] == "miniqmt"
    assert reader.calls and reader.calls[0] == "miniqmt"


@pytest.mark.asyncio
async def test_market_strength_auto_fallback_tries_next_source_when_first_fails(monkeypatch):
    live_api._RECENT_SUCCESS_PAYLOADS.clear()
    fallback_ready = {"akshare": False}

    class Result:
        def __init__(self, items):
            self.items = items
            self.as_of = "2025-01-01T15:00:00Z"
            self.stale = True
            self.cached_at = "2025-01-01T15:00:01Z"
            self.expires_at = "2025-01-01T15:03:00Z"

    class DummyReader:
        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            if source == "akshare" and fallback_ready["akshare"]:
                return Result(
                    [
                        {
                            "board": "人工智能",
                            "window": "1m",
                            "speed_per_min": 2.34,
                            "amount_total": 5.67,
                            "data_source": "akshare",
                        }
                    ]
                )
            return Result([])

    async def fake_ensure_runtime(app_state, settings):
        return None

    async def fake_fallback(app_state, module, target_source, *, phase=None):
        if target_source == "amazingdata":
            raise HTTPException(status_code=502, detail={"message": "adapter unavailable"})
        if target_source == "akshare":
            fallback_ready["akshare"] = True
        return {"writer_source": target_source, "phase": phase}

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "_ensure_fallback_data", fake_fallback)
    monkeypatch.setattr(live_api, "_resolve_market_phase", lambda: "no_trade")

    fallback_a = SimpleNamespace(
        source="amazingdata",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    fallback_b = SimpleNamespace(
        source="akshare",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "strength": SimpleNamespace(
                    enable_auto_fallback=True, fallbacks=(fallback_a, fallback_b)
                )
            }
        )
    )

    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=DummyReader(),
        market_data_pipeline=SimpleNamespace(
            boards=["人工智能"],
            capital_windows=(SimpleNamespace(name="1m"),),
        ),
        market_data_provider=SimpleNamespace(is_connected=lambda: True),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = settings

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
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"], "应在第二个 fallback source 命中数据"
    assert payload["data_source"] == "akshare"
    assert payload["detail"]["fallback"]["writer_source"] == "akshare"


@pytest.mark.asyncio
async def test_market_strength_auto_fallback_blocks_akshare_after_timeout(monkeypatch):
    live_api._RECENT_SUCCESS_PAYLOADS.clear()
    fallback_ready = {"akshare": False}
    fallback_sources: list[str] = []

    class Result:
        def __init__(self, items):
            self.items = items
            self.as_of = "2025-01-01T15:00:00Z"
            self.stale = True
            self.cached_at = "2025-01-01T15:00:01Z"
            self.expires_at = "2025-01-01T15:03:00Z"

    class DummyReader:
        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            if source == "akshare" and fallback_ready["akshare"]:
                return Result(
                    [
                        {
                            "board": "人工智能",
                            "window": "1m",
                            "speed_per_min": 2.34,
                            "amount_total": 5.67,
                            "data_source": "akshare",
                        }
                    ]
                )
            return Result([])

    async def fake_ensure_runtime(app_state, settings):
        return None

    async def fake_fallback(app_state, module, target_source, *, phase=None):
        fallback_sources.append(target_source)
        if target_source == "amazingdata":
            raise asyncio.TimeoutError
        if target_source == "akshare":
            fallback_ready["akshare"] = True
        return {"writer_source": target_source, "phase": phase}

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "_ensure_fallback_data", fake_fallback)
    monkeypatch.setattr(live_api, "_resolve_market_phase", lambda: "no_trade")

    fallback_a = SimpleNamespace(
        source="amazingdata",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    fallback_b = SimpleNamespace(
        source="akshare",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "strength": SimpleNamespace(
                    enable_auto_fallback=True, fallbacks=(fallback_a, fallback_b)
                )
            }
        )
    )
    dask_status_payload = {
        "phase": "ready",
        "message": "Dask 集群完全就绪",
        "progress_percent": 100,
        "components": {
            "amazingdata": {
                "ready": True,
                "error": None,
            }
        },
    }
    dask_init_manager = SimpleNamespace(
        phase=SimpleNamespace(value="ready"),
        is_ready=True,
        is_partial=False,
        is_usable=True,
        scheduler_ready=True,
        amazingdata_ready=True,
        get_status=lambda: SimpleNamespace(to_dict=lambda: dask_status_payload),
    )

    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=DummyReader(),
        market_data_pipeline=SimpleNamespace(
            boards=["人工智能"],
            capital_windows=(SimpleNamespace(name="1m"),),
        ),
        market_data_provider=SimpleNamespace(name="miniqmt", is_connected=lambda: True),
        backend_runtime=SimpleNamespace(dask_init_manager=dask_init_manager),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = settings

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
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"] == []
    attempts = payload["detail"]["fallback"]["attempts"]
    attempt_codes = {item.get("code") for item in attempts}
    assert "FALLBACK_TIMEOUT" in attempt_codes
    assert "AKSHARE_GUARD_BLOCKED" in attempt_codes
    assert fallback_sources == ["amazingdata"]
    assert payload["detail"]["source_failures"]["amazingdata"] == "FALLBACK_TIMEOUT"
    assert payload["detail"]["source_failures"]["akshare"] in {
        "DATA_SOURCE_EMPTY",
        "AKSHARE_GUARD_BLOCKED",
    }
    assert payload["detail"]["amazingdata_runtime"]["phase"] == "ready"
    assert payload["detail"]["amazingdata_runtime"]["amazingdata_ready"] is True


@pytest.mark.asyncio
async def test_market_strength_requested_fallback_failure_returns_200(monkeypatch):
    live_api._RECENT_SUCCESS_PAYLOADS.clear()

    class Result:
        def __init__(self):
            self.items: list[dict[str, object]] = []
            self.as_of = None
            self.stale = True
            self.cached_at = None
            self.expires_at = None

    class DummyReader:
        def __init__(self):
            self.calls: list[str | None] = []

        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            self.calls.append(source)
            return Result()

    async def fake_ensure_runtime(app_state, settings):
        return None

    async def fake_fallback(app_state, module, target_source, *, phase=None):
        raise HTTPException(status_code=502, detail={"message": "adapter unavailable"})

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "_ensure_fallback_data", fake_fallback)
    monkeypatch.setattr(live_api, "_resolve_market_phase", lambda: "no_trade")

    fallback_rule = SimpleNamespace(
        source="amazingdata",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "strength": SimpleNamespace(enable_auto_fallback=True, fallbacks=(fallback_rule,))
            }
        )
    )

    reader = DummyReader()
    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=reader,
        market_data_pipeline=SimpleNamespace(
            boards=["人工智能"],
            capital_windows=(SimpleNamespace(name="1m"),),
        ),
        market_data_provider=SimpleNamespace(is_connected=lambda: True),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = settings

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/strength",
            "headers": [],
            "query_string": b"source=amazingdata",
        },
        empty_receive,
    )

    response = await live_api.get_market_strength(
        request,
        windows=None,
        boards=None,
        limit=None,
        source="amazingdata",
    )
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["stale"] is True
    assert payload["items"] == []
    assert payload["detail"]["requested_source"] == "amazingdata"
    assert payload["detail"]["effective_source"] == "amazingdata"
    assert payload["detail"]["latest_failure"]["code"] in {
        "DATA_SOURCE_EMPTY",
        "DATA_SOURCE_OFFLINE",
    }
    assert "fallback" not in payload["detail"]
    assert set(reader.calls) == {"amazingdata"}


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

        async def fetch_order_imbalance(self, window, *, limit=None, module=None, source=None):
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
async def test_board_overview_auto_fallbacks_in_no_trade_when_primary_empty(monkeypatch):
    """盘后主源在线但返回空结果时，board_overview 应按 DATA_SOURCE_EMPTY 自动切到 fallback。"""

    live_api._RECENT_SUCCESS_PAYLOADS.clear()
    fallback_ready = {"akshare": False}

    class Result:
        def __init__(self, items):
            self.items = items
            self.as_of = "2025-01-01T15:00:00Z"
            self.stale = False
            self.cached_at = "2025-01-01T15:00:01Z"
            self.expires_at = "2025-01-01T15:02:00Z"

    class DummyReader:
        def __init__(self):
            self.calls: list[str | None] = []

        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            self.calls.append(source)
            if source == "akshare" and fallback_ready["akshare"]:
                return Result(
                    [
                        {
                            "board": "人工智能",
                            "window": "1m",
                            "speed_per_min": 1.23,
                            "amount_total": 4.56,
                            "data_source": "akshare",
                        }
                    ]
                )
            return Result([])

        async def fetch_board_universe(self, *, module="boards", source=None):
            return {"人工智能": ("000001.SZ",)}, None

    async def fake_ensure_runtime(app_state, settings):
        return None

    async def fake_fallback(app_state, module, target_source, *, phase=None):
        assert module == "board_overview"
        assert target_source == "akshare"
        assert phase == "no_trade"
        fallback_ready["akshare"] = True
        return {"writer_source": target_source, "mode": "fallback"}

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "_ensure_fallback_data", fake_fallback)
    monkeypatch.setattr(live_api, "_resolve_market_phase", lambda: "no_trade")

    fallback_rule = SimpleNamespace(
        source="akshare",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "board_overview": SimpleNamespace(
                    enable_auto_fallback=True,
                    fallbacks=(fallback_rule,),
                )
            }
        )
    )

    reader = DummyReader()
    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=reader,
        market_data_pipeline=SimpleNamespace(capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_provider=SimpleNamespace(is_connected=lambda: True),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = settings

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/board-overview",
            "headers": [],
            "query_string": b"",
        },
        empty_receive,
    )

    response = await live_api.get_board_overview(request, type_="concept", window=None, limit=12)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"], "应在盘后命中 fallback 数据"
    assert payload["data_source"] == "akshare"
    assert payload["detail"]["fallback"]["writer_source"] == "akshare"
    assert reader.calls[0] is None
    assert reader.calls[-1] == "akshare"
    assert "akshare" in reader.calls[1:]


@pytest.mark.asyncio
async def test_board_overview_auto_fallback_blocks_akshare_after_timeout(monkeypatch):
    live_api._RECENT_SUCCESS_PAYLOADS.clear()
    fallback_ready = {"akshare": False}
    fallback_sources: list[str] = []

    class Result:
        def __init__(self, items):
            self.items = items
            self.as_of = "2025-01-01T15:00:00Z"
            self.stale = False
            self.cached_at = "2025-01-01T15:00:01Z"
            self.expires_at = "2025-01-01T15:02:00Z"

    class DummyReader:
        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            if source == "akshare" and fallback_ready["akshare"]:
                return Result(
                    [
                        {
                            "board": "人工智能",
                            "window": "1m",
                            "speed_per_min": 1.23,
                            "amount_total": 4.56,
                            "data_source": "akshare",
                        }
                    ]
                )
            return Result([])

        async def fetch_board_universe(self, *, module="boards", source=None):
            return {"人工智能": ("000001.SZ",)}, None

    async def fake_ensure_runtime(app_state, settings):
        return None

    async def fake_fallback(app_state, module, target_source, *, phase=None):
        fallback_sources.append(target_source)
        if target_source == "amazingdata":
            raise asyncio.TimeoutError
        if target_source == "akshare":
            fallback_ready["akshare"] = True
        return {"writer_source": target_source, "phase": phase}

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "_ensure_fallback_data", fake_fallback)
    monkeypatch.setattr(live_api, "_resolve_market_phase", lambda: "no_trade")

    fallback_a = SimpleNamespace(
        source="amazingdata",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    fallback_b = SimpleNamespace(
        source="akshare",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "board_overview": SimpleNamespace(
                    enable_auto_fallback=True,
                    fallbacks=(fallback_a, fallback_b),
                )
            }
        )
    )
    dask_status_payload = {
        "phase": "ready",
        "message": "Dask 集群完全就绪",
        "progress_percent": 100,
        "components": {
            "amazingdata": {
                "ready": True,
                "error": None,
            }
        },
    }
    dask_init_manager = SimpleNamespace(
        phase=SimpleNamespace(value="ready"),
        is_ready=True,
        is_partial=False,
        is_usable=True,
        scheduler_ready=True,
        amazingdata_ready=True,
        get_status=lambda: SimpleNamespace(to_dict=lambda: dask_status_payload),
    )

    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=DummyReader(),
        market_data_pipeline=SimpleNamespace(capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_provider=SimpleNamespace(name="miniqmt", is_connected=lambda: True),
        backend_runtime=SimpleNamespace(dask_init_manager=dask_init_manager),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = settings

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/board-overview",
            "headers": [],
            "query_string": b"",
        },
        empty_receive,
    )

    response = await live_api.get_board_overview(request, type_="concept", window=None, limit=12)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"] == []
    attempts = payload["detail"]["fallback"]["attempts"]
    attempt_codes = {item.get("code") for item in attempts}
    assert "FALLBACK_TIMEOUT" in attempt_codes
    assert "AKSHARE_GUARD_BLOCKED" in attempt_codes
    assert fallback_sources == ["amazingdata"]
    assert payload["detail"]["source_failures"]["amazingdata"] == "FALLBACK_TIMEOUT"
    assert payload["detail"]["source_failures"]["akshare"] in {
        "DATA_SOURCE_EMPTY",
        "AKSHARE_GUARD_BLOCKED",
    }
    assert payload["detail"]["amazingdata_runtime"]["phase"] == "ready"
    assert payload["detail"]["amazingdata_runtime"]["amazingdata_ready"] is True


@pytest.mark.asyncio
async def test_board_overview_returns_recent_success_payload_when_empty_in_no_trade(monkeypatch):
    """盘后无新鲜板块数据时，应回退最近一次成功快照。"""

    live_api._RECENT_SUCCESS_PAYLOADS.clear()

    class Result:
        def __init__(self):
            self.items: list[dict[str, object]] = []
            self.as_of = None
            self.stale = False
            self.cached_at = None
            self.expires_at = None

    class DummyReader:
        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            return Result()

        async def fetch_board_universe(self, *, module="boards", source=None):
            return {}, None

    async def fake_ensure_runtime(app_state, settings):
        return None

    async def fake_refresh(app_state):
        return None

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "refresh_market_data_once", fake_refresh)
    monkeypatch.setattr(live_api, "_resolve_market_phase", lambda: "no_trade")

    live_api._set_recent_success_payload(
        "board_overview:concept:1m:12:auto",
        {
            "type": "concept",
            "window": "1m",
            "items": [
                {
                    "board": "人工智能",
                    "stock_count": 1,
                    "inflow_speed": 1.23,
                    "inflow_net": 4.56,
                }
            ],
            "asOf": "2025-01-01T15:00:00Z",
            "stale": False,
            "retrieved_at": "2025-01-01T15:00:01Z",
            "data_source": "amazingdata",
        },
    )

    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=DummyReader(),
        market_data_pipeline=SimpleNamespace(capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_provider=SimpleNamespace(is_connected=lambda: True),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={"board_overview": SimpleNamespace(enable_auto_fallback=False, fallbacks=())}
        )
    )

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/board-overview",
            "headers": [],
            "query_string": b"",
        },
        empty_receive,
    )

    response = await live_api.get_board_overview(request, type_="concept", window=None, limit=12)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"], "应回退最近一次板块概览快照"
    assert payload["stale"] is True
    assert payload["detail"]["cache_fallback"]["code"] == "DATA_SOURCE_EMPTY"
    assert payload["detail"]["latest_failure"]["code"] == "DATA_SOURCE_EMPTY"


@pytest.mark.asyncio
async def test_board_overview_off_hours_prefers_recent_snapshot_before_fallback(monkeypatch):
    """盘后有最近板块快照时，应先返回快照，不阻塞 fallback。"""

    live_api._RECENT_SUCCESS_PAYLOADS.clear()

    class EmptyResult:
        def __init__(self):
            self.items: list[dict[str, object]] = []
            self.as_of = None
            self.stale = False
            self.cached_at = None
            self.expires_at = None

    class DummyReader:
        def __init__(self):
            self.calls: list[str | None] = []

        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            self.calls.append(source)
            return EmptyResult()

        async def fetch_board_universe(self, *, module="boards", source=None):
            return {}, None

    async def fake_ensure_runtime(app_state, settings):
        return None

    fallback_calls = {"count": 0}

    async def fake_fallback(app_state, module, target_source, *, phase=None):
        fallback_calls["count"] += 1
        return {"writer_source": target_source}

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "_ensure_fallback_data", fake_fallback)
    monkeypatch.setattr(live_api, "_resolve_market_phase", lambda: "no_trade")

    live_api._set_recent_success_payload(
        "board_overview:concept:1m:12:auto",
        {
            "type": "concept",
            "window": "1m",
            "items": [
                {
                    "board": "人工智能",
                    "stock_count": 1,
                    "inflow_speed": 1.23,
                    "inflow_net": 4.56,
                }
            ],
            "asOf": "2025-01-01T15:00:00Z",
            "stale": False,
            "retrieved_at": "2025-01-01T15:00:01Z",
            "data_source": "amazingdata",
        },
    )

    fallback_rule = SimpleNamespace(
        source="akshare",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "board_overview": SimpleNamespace(
                    enable_auto_fallback=True,
                    fallbacks=(fallback_rule,),
                )
            }
        )
    )
    reader = DummyReader()
    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=reader,
        market_data_pipeline=SimpleNamespace(capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_provider=SimpleNamespace(is_connected=lambda: True),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = settings

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/board-overview",
            "headers": [],
            "query_string": b"",
        },
        empty_receive,
    )

    response = await live_api.get_board_overview(request, type_="concept", window=None, limit=12)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"], "应优先返回最近板块快照"
    assert payload["stale"] is True
    assert payload["detail"]["latest_failure"]["code"] == "DATA_SOURCE_EMPTY"
    assert fallback_calls["count"] == 0
    assert reader.calls == [None]


@pytest.mark.asyncio
async def test_board_overview_probes_other_cached_sources_when_primary_empty(monkeypatch):
    live_api._RECENT_SUCCESS_PAYLOADS.clear()

    class Result:
        def __init__(self, items):
            self.items = items
            self.as_of = "2025-01-01T15:00:00Z"
            self.stale = True
            self.cached_at = "2025-01-01T15:00:01Z"
            self.expires_at = "2025-01-01T15:03:00Z"

    class DummyReader:
        def __init__(self):
            self.calls: list[str | None] = []

        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            self.calls.append(source)
            if source == "akshare":
                return Result(
                    [
                        {
                            "board": "人工智能",
                            "window": "1m",
                            "speed_per_min": 3.21,
                            "amount_total": 6.54,
                            "data_source": "akshare",
                        }
                    ]
                )
            return Result([])

        async def fetch_board_universe(self, *, module="boards", source=None):
            return {"人工智能": ("000001.SZ", "000002.SZ")}, None

    async def fake_ensure_runtime(app_state, settings):
        return None

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)

    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "board_overview": SimpleNamespace(enable_auto_fallback=False, fallbacks=()),
            }
        )
    )
    reader = DummyReader()
    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=reader,
        market_data_pipeline=SimpleNamespace(capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_provider=SimpleNamespace(name="miniqmt", is_connected=lambda: False),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = settings

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/board-overview",
            "headers": [],
            "query_string": b"",
        },
        empty_receive,
    )

    response = await live_api.get_board_overview(request, type_="concept", window="1m", limit=12)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"], "应从其他 source 的缓存中命中板块概览数据"
    assert payload["data_source"] == "akshare"
    assert payload["detail"]["cache_probe"]["source"] == "akshare"
    assert reader.calls == ["miniqmt", "miniqmt", "amazingdata", "akshare"]


@pytest.mark.asyncio
async def test_market_strength_explicit_non_fallback_source_does_not_raise_400(monkeypatch):
    live_api._RECENT_SUCCESS_PAYLOADS.clear()

    class Result:
        def __init__(self):
            self.items: list[dict[str, object]] = []
            self.as_of = None
            self.stale = False
            self.cached_at = None
            self.expires_at = None

    class DummyReader:
        def __init__(self):
            self.calls: list[str | None] = []

        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            self.calls.append(source)
            return Result()

    async def fake_ensure_runtime(app_state, settings):
        return None

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)

    fallback_rule = SimpleNamespace(
        source="akshare",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "strength": SimpleNamespace(
                    enable_auto_fallback=True,
                    fallbacks=(fallback_rule,),
                )
            }
        )
    )
    reader = DummyReader()
    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=reader,
        market_data_pipeline=SimpleNamespace(
            boards=["人工智能"],
            capital_windows=(SimpleNamespace(name="1m"),),
        ),
        market_data_provider=SimpleNamespace(name="miniqmt", is_connected=lambda: True),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = settings

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/strength",
            "headers": [],
            "query_string": b"source=amazingdata",
        },
        empty_receive,
    )

    response = await live_api.get_market_strength(
        request,
        windows=None,
        boards=None,
        limit=None,
        source="amazingdata",
    )
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"] == []
    assert payload["data_source"] == "amazingdata"
    assert payload["stale"] is True
    assert payload["detail"]["code"] in {"DATA_SOURCE_EMPTY", "DATA_SOURCE_OFFLINE"}
    assert set(reader.calls) == {"amazingdata"}


@pytest.mark.asyncio
async def test_board_overview_explicit_non_fallback_source_does_not_raise_400(monkeypatch):
    live_api._RECENT_SUCCESS_PAYLOADS.clear()

    class Result:
        def __init__(self):
            self.items: list[dict[str, object]] = []
            self.as_of = None
            self.stale = False
            self.cached_at = None
            self.expires_at = None

    class DummyReader:
        def __init__(self):
            self.calls: list[str | None] = []

        async def fetch_strength(
            self, windows, *, boards=None, limit=None, module=None, source=None
        ):
            self.calls.append(source)
            return Result()

        async def fetch_board_universe(self, *, module="boards", source=None):
            return {}, None

    async def fake_ensure_runtime(app_state, settings):
        return None

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)

    fallback_rule = SimpleNamespace(
        source="akshare",
        phases=("off_day", "no_trade"),
        trigger_errors=("DATA_SOURCE_OFFLINE", "DATA_SOURCE_EMPTY"),
    )
    settings = SimpleNamespace(
        market_data=SimpleNamespace(
            modules={
                "board_overview": SimpleNamespace(
                    enable_auto_fallback=True,
                    fallbacks=(fallback_rule,),
                )
            }
        )
    )
    reader = DummyReader()
    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=reader,
        market_data_pipeline=SimpleNamespace(capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_provider=SimpleNamespace(name="miniqmt", is_connected=lambda: True),
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = settings

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/board-overview",
            "headers": [],
            "query_string": b"source=amazingdata",
        },
        empty_receive,
    )

    response = await live_api.get_board_overview(
        request,
        type_="concept",
        window="1m",
        limit=12,
        source="amazingdata",
    )
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"] == []
    assert payload["data_source"] == "amazingdata"
    assert payload["stale"] is True
    assert payload["detail"]["code"] == "DATA_SOURCE_EMPTY"
    assert set(reader.calls) == {"amazingdata"}


@pytest.mark.asyncio
async def test_board_drivers_returns_rows_with_coverage(monkeypatch):
    class DummyProvider:
        name = "amazingdata"

        async def get_realtime_quote(self, symbols=None):
            symbols = symbols or []
            return {
                str(symbol): {
                    "code": str(symbol),
                    "name": f"股票{idx}",
                    "last": 10.0 + idx,
                    "change_pct": 1.0 + idx,
                    "amount": 1000000 * (idx + 1),
                    "trade_time": f"2026-03-26 13:0{idx}:00",
                }
                for idx, symbol in enumerate(symbols)
            }

    class DummyReader:
        async def fetch_board_universe(self, *, module="boards", source=None):
            return {"人工智能": ("000001.SZ", "000002.SZ", "000003.SZ")}, None

    async def fake_ensure_runtime(app_state, settings):
        return None

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "_resolve_market_phase", lambda: "continuous")
    monkeypatch.setattr(live_api, "_is_trading_hours", lambda: True)

    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=DummyReader(),
        market_data_pipeline=SimpleNamespace(capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_provider=DummyProvider(),
        market_data_active_source="amazingdata",
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = SimpleNamespace(market_data=SimpleNamespace(modules={}))

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/board-drivers",
            "headers": [],
            "query_string": b"",
        },
        empty_receive,
    )

    response = await live_api.get_board_drivers(
        request,
        board="人工智能",
        type_="concept",
        window="1m",
        limit=2,
        source=None,
    )
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["board"] == "人工智能"
    assert payload["data_source"] == "amazingdata"
    assert payload["stale"] is False
    assert len(payload["items"]) == 2
    assert payload["coverage"]["total_components"] == 3
    assert payload["coverage"]["available_snapshots"] == 2
    assert payload["detail"]["requested_source"] == "auto"
    assert payload["detail"]["effective_source"] == "amazingdata"


@pytest.mark.asyncio
async def test_board_drivers_strict_source_returns_structured_failure(monkeypatch):
    class DummyReader:
        async def fetch_board_universe(self, *, module="boards", source=None):
            return {"人工智能": ("000001.SZ", "000002.SZ")}, None

    async def fake_ensure_runtime(app_state, settings):
        return None

    async def fake_resolve_provider(_name, request=None, *, strict=True):
        raise HTTPException(status_code=503, detail="provider unavailable")

    monkeypatch.setattr(live_api, "ensure_market_data_runtime", fake_ensure_runtime)
    monkeypatch.setattr(live_api, "_resolve_market_phase", lambda: "continuous")
    monkeypatch.setattr(live_api, "_is_trading_hours", lambda: True)
    monkeypatch.setattr("apps.api.api.provider_deps.resolve_provider", fake_resolve_provider)

    app_state = SimpleNamespace(
        market_data_service=SimpleNamespace(default_capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_reader=DummyReader(),
        market_data_pipeline=SimpleNamespace(capital_windows=(SimpleNamespace(name="1m"),)),
        market_data_provider=SimpleNamespace(name="miniqmt"),
        market_data_active_source="miniqmt",
    )

    app = Starlette()
    app.state.app_state = app_state
    app.state.settings = SimpleNamespace(market_data=SimpleNamespace(modules={}))

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/board-drivers",
            "headers": [],
            "query_string": b"source=amazingdata",
        },
        empty_receive,
    )

    response = await live_api.get_board_drivers(
        request,
        board="人工智能",
        type_="concept",
        window="1m",
        limit=20,
        source="amazingdata",
    )
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["items"] == []
    assert payload["stale"] is True
    assert payload["data_source"] == "amazingdata"
    assert payload["detail"]["requested_source"] == "amazingdata"
    assert payload["detail"]["effective_source"] == "amazingdata"
    assert payload["detail"]["latest_failure"]["code"] == "DATA_SOURCE_UNAVAILABLE"


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


@pytest.mark.asyncio
async def test_concept_flow_realtime_singleflight(monkeypatch):
    """相同参数并发请求应复用同一次上游调用。"""

    from apps.api.api.endpoints.amazingdata import concept as concept_endpoint

    calls = {"count": 0}
    live_api._CONCEPT_FLOW_BREAKERS.clear()
    live_api._CONCEPT_FLOW_SINGLEFLIGHT.clear()

    async def fake_get_concept_velocity(limit: int):
        calls["count"] += 1
        await asyncio.sleep(0.05)
        return {
            "success": True,
            "data": [
                {
                    "name": "人工智能",
                    "code": "BK001",
                    "main_net_inflow": 12345.0,
                    "velocity": 12345.0,
                    "lead_stock": "000001",
                    "change_pct": 1.5,
                }
            ],
        }

    monkeypatch.setattr(concept_endpoint, "get_concept_velocity", fake_get_concept_velocity)

    app = Starlette()
    app.state.app_state = SimpleNamespace()
    app.state.settings = SimpleNamespace()

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "app": app,
        "method": "GET",
        "path": "/api/market/live/concept-flow",
        "headers": [],
        "query_string": b"period=realtime&limit=10",
    }

    req_a = Request(scope, empty_receive)
    req_b = Request(scope, empty_receive)

    response_a, response_b = await asyncio.gather(
        live_api.get_concept_flow(req_a, period="realtime", limit=10, source=None),
        live_api.get_concept_flow(req_b, period="realtime", limit=10, source=None),
    )

    payload_a = json.loads(response_a.body.decode("utf-8"))
    payload_b = json.loads(response_b.body.decode("utf-8"))

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert calls["count"] == 1
    assert payload_a["count"] == 1
    assert payload_b["count"] == 1


@pytest.mark.asyncio
async def test_concept_flow_today_fallbacks_to_ths_concept_list(monkeypatch):
    """今日概念资金流为空时，应回退到 THS 概念列表，避免页面空白。"""
    live_api._CONCEPT_FLOW_BREAKERS.clear()
    live_api._CONCEPT_FLOW_SINGLEFLIGHT.clear()

    async def fake_fetch_akshare(limit: int, indicator_label: str):
        return []

    async def fake_fetch_ths(limit: int):
        return [
            {
                "concept_name": "人工智能",
                "concept_code": "BK001",
                "main_net_inflow": None,
                "main_net_inflow_pct": None,
                "change_pct": None,
                "leading_stock": "",
                "flow_speed": None,
            }
        ]

    async def fake_fetch_snapshot_empty(limit: int):
        return []

    monkeypatch.setattr(
        live_api,
        "_fetch_concept_flow_from_akshare_singleflight",
        fake_fetch_akshare,
    )
    monkeypatch.setattr(
        live_api,
        "_fetch_concept_flow_from_akshare_snapshot_singleflight",
        fake_fetch_snapshot_empty,
    )
    monkeypatch.setattr(
        live_api,
        "_fetch_concept_flow_from_ths_singleflight",
        fake_fetch_ths,
    )

    app = Starlette()
    app.state.app_state = SimpleNamespace()
    app.state.settings = SimpleNamespace()

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/concept-flow",
            "headers": [],
            "query_string": b"period=today&limit=10",
        },
        empty_receive,
    )

    response = await live_api.get_concept_flow(request, period="today", limit=10, source=None)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["data_source"] == "ths_direct"
    assert payload["stale"] is True
    assert payload["count"] == 1
    assert payload["items"][0]["concept_name"] == "人工智能"
    assert payload["detail"]["code"] == "DATA_SOURCE_DEGRADED"


@pytest.mark.asyncio
async def test_concept_flow_today_fallbacks_to_akshare_snapshot_before_ths(monkeypatch):
    """今日概念资金流主接口失败时，应先回退 AKShare 概念快照。"""
    live_api._CONCEPT_FLOW_BREAKERS.clear()
    live_api._CONCEPT_FLOW_SINGLEFLIGHT.clear()

    async def fake_fetch_akshare(limit: int, indicator_label: str):
        return []

    async def fake_fetch_snapshot(limit: int):
        return [
            {
                "concept_name": "AI应用",
                "concept_code": "AKS-1",
                "main_net_inflow": 12.5,
                "main_net_inflow_pct": None,
                "change_pct": 2.35,
                "leading_stock": "示例A",
                "flow_speed": 12.5,
            }
        ]

    async def fake_fetch_ths(limit: int):
        raise AssertionError("有 AKShare 概念快照时不应再回退 THS")

    monkeypatch.setattr(
        live_api,
        "_fetch_concept_flow_from_akshare_singleflight",
        fake_fetch_akshare,
    )
    monkeypatch.setattr(
        live_api,
        "_fetch_concept_flow_from_akshare_snapshot_singleflight",
        fake_fetch_snapshot,
    )
    monkeypatch.setattr(
        live_api,
        "_fetch_concept_flow_from_ths_singleflight",
        fake_fetch_ths,
    )

    app = Starlette()
    app.state.app_state = SimpleNamespace()
    app.state.settings = SimpleNamespace()

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/concept-flow",
            "headers": [],
            "query_string": b"period=today&limit=10",
        },
        empty_receive,
    )

    response = await live_api.get_concept_flow(request, period="today", limit=10, source=None)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["data_source"] == "akshare.stock_fund_flow_concept"
    assert payload["stale"] is False
    assert payload["count"] == 1
    assert payload["items"][0]["concept_name"] == "AI应用"
    assert payload["detail"]["code"] == "DATA_SOURCE_DEGRADED"


@pytest.mark.asyncio
async def test_concept_flow_week_does_not_retry_today_rank_when_week_rank_empty(monkeypatch):
    """周口径为空时不应再次调用今日 rank 主链路，直接降级到快照。"""
    live_api._CONCEPT_FLOW_BREAKERS.clear()
    live_api._CONCEPT_FLOW_SINGLEFLIGHT.clear()

    indicator_calls: list[str] = []

    async def fake_fetch_akshare(limit: int, indicator_label: str):
        indicator_calls.append(indicator_label)
        return []

    async def fake_fetch_snapshot(limit: int):
        return [
            {
                "concept_name": "AI应用",
                "concept_code": "AKS-1",
                "main_net_inflow": 21.5,
                "main_net_inflow_pct": None,
                "change_pct": 1.25,
                "leading_stock": "示例A",
                "flow_speed": 21.5,
            }
        ]

    async def fake_fetch_ths(limit: int):
        raise AssertionError("有 AKShare 概念快照时不应再回退 THS")

    monkeypatch.setattr(
        live_api,
        "_fetch_concept_flow_from_akshare_singleflight",
        fake_fetch_akshare,
    )
    monkeypatch.setattr(
        live_api,
        "_fetch_concept_flow_from_akshare_snapshot_singleflight",
        fake_fetch_snapshot,
    )
    monkeypatch.setattr(
        live_api,
        "_fetch_concept_flow_from_ths_singleflight",
        fake_fetch_ths,
    )

    app = Starlette()
    app.state.app_state = SimpleNamespace()
    app.state.settings = SimpleNamespace()

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/concept-flow",
            "headers": [],
            "query_string": b"period=week&limit=10",
        },
        empty_receive,
    )

    response = await live_api.get_concept_flow(request, period="week", limit=10, source=None)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert indicator_calls == ["5日"]
    assert payload["data_source"] == "akshare.stock_fund_flow_concept"
    assert payload["stale"] is True
    assert payload["count"] == 1
    assert payload["detail"]["code"] == "DATA_SOURCE_DEGRADED"


@pytest.mark.asyncio
async def test_concept_flow_realtime_skips_akshare_rank_when_breaker_open(monkeypatch):
    """实时口径回退时，若 akshare 今日 rank 熔断开启，应直接走快照降级。"""
    live_api._CONCEPT_FLOW_BREAKERS.clear()
    live_api._CONCEPT_FLOW_SINGLEFLIGHT.clear()

    breaker = live_api._get_concept_flow_breaker("今日")

    async def always_fail():
        raise RuntimeError("mock failure")

    for _ in range(live_api._CONCEPT_FLOW_BREAKER_FAILURE_THRESHOLD):
        with pytest.raises(RuntimeError):
            await breaker.async_call(always_fail)

    async def fake_realtime_fail(limit: int):
        raise RuntimeError("amazingdata unavailable")

    async def fake_fetch_akshare(limit: int, indicator_label: str):
        raise AssertionError("熔断开启时不应调用 akshare rank 主链路")

    async def fake_fetch_snapshot(limit: int):
        return [
            {
                "concept_name": "AI应用",
                "concept_code": "AKS-1",
                "main_net_inflow": 9.9,
                "main_net_inflow_pct": None,
                "change_pct": 0.88,
                "leading_stock": "示例A",
                "flow_speed": 9.9,
            }
        ]

    async def fake_fetch_ths(limit: int):
        raise AssertionError("有 AKShare 概念快照时不应再回退 THS")

    monkeypatch.setattr(live_api, "_fetch_realtime_concept_flow", fake_realtime_fail)
    monkeypatch.setattr(
        live_api,
        "_fetch_concept_flow_from_akshare_singleflight",
        fake_fetch_akshare,
    )
    monkeypatch.setattr(
        live_api,
        "_fetch_concept_flow_from_akshare_snapshot_singleflight",
        fake_fetch_snapshot,
    )
    monkeypatch.setattr(
        live_api,
        "_fetch_concept_flow_from_ths_singleflight",
        fake_fetch_ths,
    )

    app = Starlette()
    app.state.app_state = SimpleNamespace()
    app.state.settings = SimpleNamespace()

    async def empty_receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    request = Request(
        {
            "type": "http",
            "app": app,
            "method": "GET",
            "path": "/api/market/live/concept-flow",
            "headers": [],
            "query_string": b"period=realtime&limit=10",
        },
        empty_receive,
    )

    response = await live_api.get_concept_flow(request, period="realtime", limit=10, source=None)
    payload = json.loads(response.body.decode("utf-8"))

    assert response.status_code == 200
    assert payload["data_source"] == "akshare.stock_fund_flow_concept"
    assert payload["stale"] is False
    assert payload["count"] == 1
    assert payload["detail"]["code"] == "DATA_SOURCE_DEGRADED"
