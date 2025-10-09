from __future__ import annotations

import asyncio

import pytest

from deepsearch.webui.api.middleware.deduplication import RequestDeduplicator


@pytest.mark.asyncio
async def test_deduplicator_handles_list_params_without_hash_errors():
    deduplicator = RequestDeduplicator(ttl_seconds=1)

    params = {
        "symbols": ["AAPL", "MSFT"],
        "filters": {
            "exchange": ["NASDAQ", "NYSE"],
            "range": {"start": "2024-01-01", "end": "2024-01-31"},
        },
    }

    key = deduplicator.get_request_key("/api/data/realtime", params)

    reordered_params = {
        "filters": {
            "range": {"end": "2024-01-31", "start": "2024-01-01"},
            "exchange": ["NASDAQ", "NYSE"],
        },
        "symbols": ["AAPL", "MSFT"],
    }

    assert key == deduplicator.get_request_key(
        "/api/data/realtime", reordered_params
    ), "同结构参数应生成稳定的请求键"

    async def fetch():
        await asyncio.sleep(0)
        return {"status": "ok"}

    result = await deduplicator.deduplicate(key, fetch)
    assert result == {"status": "ok"}

    # 第二次调用应命中去重逻辑并返回同一结果
    deduped_result = await deduplicator.deduplicate(key, fetch)
    assert deduped_result == result
    assert deduplicator.dedup_count == 1
