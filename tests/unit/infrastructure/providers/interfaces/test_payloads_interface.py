"""覆盖数据源 payload 接口的导出与前向声明。"""

from __future__ import annotations

from core.infrastructure.providers.interfaces import payloads


def test_payloads_module_exports_expected_symbols() -> None:
    expected = {
        "ReceiverStats",
        "DataFramePayload",
        "DataPayload",
        "MappingPayload",
        "SequencePayload",
        "TimeseriesPayload",
        "TimeseriesPoint",
        "QuotePayload",
        "QuotePayloadMap",
    }
    assert set(payloads.__all__) == expected


def test_data_payload_keeps_forward_ref_string() -> None:
    assert isinstance(payloads.DataPayload, str)
    assert "pd.DataFrame" in payloads.DataPayload
    assert "MappingPayload" in payloads.DataPayload
