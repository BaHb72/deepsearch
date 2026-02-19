from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from apps.api.api.endpoints.amazingdata import basic_data, option


@pytest.mark.asyncio
async def test_basic_data_future_code_list_uses_provider_method(monkeypatch):
    provider = Mock()
    provider.get_future_code_list = AsyncMock(return_value=["IF2406", "IH2406"])
    monkeypatch.setattr(basic_data, "get_amazingdata_provider", AsyncMock(return_value=provider))

    payload = await basic_data.get_future_code_list()
    assert payload["success"] is True
    provider.get_future_code_list.assert_awaited_once()


@pytest.mark.asyncio
async def test_basic_data_option_code_list_uses_provider_method(monkeypatch):
    provider = Mock()
    provider.get_option_code_list = AsyncMock(return_value=["10000001.SH"])
    monkeypatch.setattr(basic_data, "get_amazingdata_provider", AsyncMock(return_value=provider))

    payload = await basic_data.get_option_code_list()
    assert payload["success"] is True
    provider.get_option_code_list.assert_awaited_once()


@pytest.mark.asyncio
async def test_basic_data_adj_factor_calls_provider(monkeypatch):
    provider = Mock()
    provider.get_adj_factor = AsyncMock(return_value=None)
    monkeypatch.setattr(basic_data, "get_amazingdata_provider", AsyncMock(return_value=provider))

    request = basic_data.FactorRequest(
        code_list=["000001.SZ"],
        begin_date=20240101,
        end_date=20240131,
        is_local=True,
    )
    payload = await basic_data.get_adj_factor(request)
    assert payload["success"] is True
    provider.get_adj_factor.assert_awaited_once()


@pytest.mark.asyncio
async def test_option_mon_ctr_specs_uses_new_method_name(monkeypatch):
    provider = Mock()
    provider.get_option_mon_ctr_specs = AsyncMock(return_value=None)
    monkeypatch.setattr(option, "get_amazingdata_provider", AsyncMock(return_value=provider))

    request = option.OptionMonCtrRequest(code_list=["10000001.SH"], is_local=True)
    payload = await option.get_option_mon_ctr_specs(request)
    assert payload["success"] is True
    provider.get_option_mon_ctr_specs.assert_awaited_once()
