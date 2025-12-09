from __future__ import annotations

import json

from deepsearch.infrastructure.providers.implementations.amazingdata.api_catalog import (
    AMAZINGDATA_API_CATALOG,
    catalog_to_json,
)


def test_catalog_contains_expected_namespaces() -> None:
    namespaces = AMAZINGDATA_API_CATALOG.namespaces
    assert "BaseData" in namespaces
    assert "MarketData" in namespaces
    assert "query_snapshot" in namespaces["MarketData"]
    assert "get_code_list" in namespaces["BaseData"]


def test_catalog_to_json_roundtrip() -> None:
    payload = json.loads(catalog_to_json(ensure_ascii=False))
    assert payload["sdk"]["install"][0].startswith("pip install")
    assert "security_type" in payload["enums"]
    assert "notes" in payload
    assert isinstance(payload["notes"], list)
