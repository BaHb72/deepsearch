"""
AkShare API 映射加载测试
"""

from core.infrastructure.providers.implementations.akshare.akshare_api_mapping import (
    AkShareAPIMapping,
)


def test_catalog_loaded_and_contains_expected_entries():
    api_names = AkShareAPIMapping.get_all_api_names()
    assert len(api_names) >= 700
    assert "fund_aum_em" in api_names
    assert "macro_australia_cpi_yearly" in api_names


def test_transform_params_applies_defaults():
    params = {}
    transformed = AkShareAPIMapping.transform_params("stock_zh_a_hist", params)
    assert transformed["start_date"] == "19900101"
    assert transformed["end_date"] == "20500101"
