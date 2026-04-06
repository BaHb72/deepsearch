"""AkShare adapter normalization tests."""

from core.infrastructure.providers.implementations.akshare.akshare_adapter import AkShareAdapter


def test_normalize_stock_list_normalizes_list_payload_rows() -> None:
    payload = [
        {"代码": "000001", "名称": "平安银行"},
        {"SECURITY_CODE": "600000", "SECURITY_NAME": "浦发银行"},
    ]

    normalized = AkShareAdapter._normalize_stock_list(payload)

    assert len(normalized) == 2
    assert normalized[0]["symbol"] == "000001"
    assert normalized[0]["name"] == "平安银行"
    assert normalized[1]["symbol"] == "600000"
    assert normalized[1]["name"] == "浦发银行"


def test_normalize_stock_list_skips_rows_without_symbol() -> None:
    payload = {
        "data": [
            {"名称": "无代码"},
            {"name": "missing_code"},
            {"code": "300750", "name": "宁德时代"},
        ]
    }

    normalized = AkShareAdapter._normalize_stock_list(payload)

    assert len(normalized) == 1
    assert normalized[0]["symbol"] == "300750"
    assert normalized[0]["name"] == "宁德时代"


def test_normalize_stock_list_pads_numeric_symbol_to_six_digits() -> None:
    payload = [{"代码": 1, "名称": "平安银行"}]

    normalized = AkShareAdapter._normalize_stock_list(payload)

    assert len(normalized) == 1
    assert normalized[0]["symbol"] == "000001"
    assert normalized[0]["name"] == "平安银行"
