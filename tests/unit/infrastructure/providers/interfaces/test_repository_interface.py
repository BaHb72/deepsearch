"""覆盖数据源仓储接口（repositories/base.py）的行为。"""

from __future__ import annotations

from types import MappingProxyType

from deepsearch.infrastructure.providers.interfaces.repositories import QueryOptions


def test_query_options_normalizes_inputs() -> None:
    proxy_filters = MappingProxyType({"market": "CN", "sector": "tech"})
    options = QueryOptions(filters=proxy_filters, limit=None, skip=-5)

    assert options.filters == {"market": "CN", "sector": "tech"}
    assert isinstance(options.filters, dict)
    assert options.limit == 100
    assert options.skip == 0


def test_query_options_preserves_explicit_settings() -> None:
    options = QueryOptions(
        filters={"market": "US"}, limit=50, skip=10, sort_by="symbol", sort_desc=True
    )

    assert options.limit == 50
    assert options.skip == 10
    assert options.sort_by == "symbol"
    assert options.sort_desc is True
