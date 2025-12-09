"""覆盖数据源运行时接口(runtime.py)的工厂函数。"""

from __future__ import annotations

from deepsearch.infrastructure.providers.interfaces import runtime


def test_create_empty_batch_stats_returns_pristine_template() -> None:
    stats = runtime.create_empty_batch_stats()

    assert stats == {
        "total_requests": 0,
        "total_batches": 0,
        "successful_batches": 0,
        "failed_batches": 0,
        "by_key": {},
    }

    stats["by_key"]["foo"] = {"requests": 1}
    assert runtime.create_empty_batch_stats()["by_key"] == {}


def test_create_provider_runtime_stats_uses_fresh_batch_stats() -> None:
    runtime_stats = runtime.create_provider_runtime_stats()

    assert runtime_stats["requests"] == 0
    assert runtime_stats["successes"] == 0
    assert runtime_stats["failures"] == 0
    assert runtime_stats["cache_hits"] == 0
    assert runtime_stats["provider_usage"] == {}
    assert runtime_stats["batch_stats"] == runtime.create_empty_batch_stats()

    runtime_stats["batch_stats"]["by_key"]["symbol"] = {"batches": 2}
    assert runtime.create_provider_runtime_stats()["batch_stats"]["by_key"] == {}
