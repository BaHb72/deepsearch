"""覆盖数据源基础接口层（base.py）的行为。"""

from __future__ import annotations

from types import MappingProxyType

from core.infrastructure.providers.interfaces.base import (
    DataProviderConfig,
    DataRequest,
    DataResponse,
    DataSourceType,
    ProxyConfig,
)


def test_data_provider_config_normalizes_source_type_strings() -> None:
    config = DataProviderConfig(source_type="  AMAZINGDATA  ")
    assert config.source_type is DataSourceType.AMAZINGDATA

    fallback = DataProviderConfig(source_type="unknown-provider")
    assert fallback.source_type is DataSourceType.CUSTOM


def test_data_provider_config_normalizes_config_mapping() -> None:
    config = DataProviderConfig(config=[("token", "demo")])
    assert config.config == {"token": "demo"}

    none_config = DataProviderConfig(config=None)
    assert none_config.config == {}


def test_proxy_config_as_http_url_variants() -> None:
    assert ProxyConfig().as_http_url() is None

    assert ProxyConfig(host="127.0.0.1", port=8080).as_http_url() == "http://127.0.0.1:8080"
    assert (
        ProxyConfig(host="10.0.0.8", port=9000, username="user", password="pass").as_http_url()
        == "http://user:pass@10.0.0.8:9000"
    )


def test_data_request_populates_fields_from_params_and_strings() -> None:
    request = DataRequest(
        request_type=None,
        symbols="000002.SZ",
        params={
            "symbol": "000001.SZ",
            "period": "1m",
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "adjust": "qfq",
            "source": "akshare",
            "request_type": "kline",
            "custom_flag": True,
        },
    )

    assert request.symbol == "000001.SZ"
    assert request.symbols == ["000002.SZ"]
    assert request.request_type == "kline"
    assert request.source is DataSourceType.AKSHARE

    assert request.params["symbol"] == "000001.SZ"
    assert request.params["symbols"] == ["000002.SZ"]
    assert request.params["source"] == "akshare"
    assert request.params["custom_flag"] is True


def test_data_request_extra_params_merge_and_override_behavior() -> None:
    request = DataRequest(
        symbol="000001.SZ",
        extra_params={"trace_id": "abc", "symbol": "override"},
    )

    assert request.params["symbol"] == "000001.SZ"
    assert request.extra_params["symbol"] == "override"
    assert request.extra_params["trace_id"] == "abc"
    assert request.extra_params["request_type"] == "generic"


def test_data_request_source_accepts_mapping_proxy() -> None:
    proxy_params = MappingProxyType({"source": "database", "symbol": "US.AAPL"})
    request = DataRequest(params=proxy_params)

    assert request.source is DataSourceType.DATABASE
    assert request.symbol == "US.AAPL"


def test_data_response_copies_metadata() -> None:
    metadata = {"latency_ms": 12}
    response = DataResponse(success=True, metadata=metadata)

    metadata["latency_ms"] = 999
    assert response.metadata == {"latency_ms": 12}
    assert response.metadata is not metadata
