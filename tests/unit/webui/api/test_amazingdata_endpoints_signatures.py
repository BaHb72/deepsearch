import os

os.environ.setdefault("DEEPSEARCH_AMAZINGDATA_STUB", "tests.stubs.amazingdata_stub")
import pandas as pd
import pytest

from apps.api.api.endpoints.amazingdata import basic_data, history, margin, shareholder
from apps.api.api.endpoints.amazingdata.base import DEFAULT_LOCAL_PATH


@pytest.mark.asyncio
async def test_get_calendar_filters_results(monkeypatch):
    calls = {}

    class DummyProvider:
        async def get_calendar(self, market: str = "SH"):
            # 实际 Actor 只接受 market 参数，data_type 在 API 层处理
            calls["args"] = {"market": market}
            # 混合符合与不符合过滤条件的数据
            return [20240102, 20240103, 20240105]

    provider = DummyProvider()

    async def fake_provider():
        return provider

    monkeypatch.setattr(basic_data, "get_amazingdata_provider", fake_provider)

    response = await basic_data.get_calendar(
        market="SZ", data_type="str", begin_date=20240103, end_date=20240104
    )

    assert calls["args"] == {"market": "SZ"}
    assert response["success"] is True
    assert response["data"]["data"] == [20240103]


@pytest.mark.asyncio
async def test_get_backward_factor_filters_by_date(monkeypatch):
    captured = {}

    class DummyProvider:
        async def get_backward_factor(self, code_list, local_path, is_local):
            captured.update(
                {
                    "code_list": code_list,
                    "local_path": local_path,
                    "is_local": is_local,
                }
            )
            return pd.DataFrame({"factor": [1.0, 1.1, 1.2]}, index=[20240101, 20240102, 20240105])

    provider = DummyProvider()

    async def fake_provider():
        return provider

    monkeypatch.setattr(basic_data, "get_amazingdata_provider", fake_provider)

    request = basic_data.FactorRequest(
        code_list=["SH.600000"],
        begin_date=20240101,
        end_date=20240103,
    )
    response = await basic_data.get_backward_factor(request)

    assert captured == {
        "code_list": ["SH.600000"],
        "local_path": DEFAULT_LOCAL_PATH,
        "is_local": True,
    }
    assert response["success"] is True
    assert response["data"]["count"] == 2  # 仅保留日期范围内的数据


@pytest.mark.asyncio
async def test_query_kline_uses_filtered_mapping(monkeypatch):
    class DummyProvider:
        async def query_kline(self, *, code_list, begin_date, end_date, period):
            assert code_list == ["SZ.000001"]
            assert begin_date == 20240101
            assert end_date == 20240105
            assert period == "daily"
            df = pd.DataFrame({"close": [10, 11, 12]}, index=[20240101, 20240103, 20240107])
            return {"SZ.000001": df}

    provider = DummyProvider()

    async def fake_provider():
        return provider

    monkeypatch.setattr(history, "get_amazingdata_provider", fake_provider)

    request = history.QueryKlineRequest(
        code_list=["SZ.000001"],
        begin_date=20240101,
        end_date=20240105,
        period="daily",
    )
    response = await history.query_kline(request)

    assert response["success"] is True
    dataset = response["data"]["SZ.000001"]
    assert len(dataset["data"]) == 2  # 超出范围的 20240107 已被过滤


@pytest.mark.asyncio
async def test_margin_detail_filters_columns(monkeypatch):
    captured = {}

    class DummyProvider:
        async def get_margin_detail(self, code_list):
            captured["code_list"] = code_list
            return pd.DataFrame(
                {
                    "trade_date": ["2024-01-02", "2024-01-05"],
                    "code": ["SH.600000", "SH.600000"],
                    "balance": [1.0, 2.0],
                    "extra": [100, 200],
                }
            )

    provider = DummyProvider()

    async def fake_provider():
        return provider

    monkeypatch.setattr(margin, "get_amazingdata_provider", fake_provider)

    response = await margin.get_margin_detail(
        code="SH.600000",
        start_date="2024-01-01",
        end_date="2024-01-03",
        fields=["trade_date", "balance"],
    )

    assert captured["code_list"] == ["SH.600000"]
    assert response["success"] is True
    rows = response["data"]["data"]
    assert len(rows) == 1
    assert set(rows[0].keys()) == {"trade_date", "balance"}


@pytest.mark.asyncio
async def test_share_holder_applies_topn(monkeypatch):
    class DummyProvider:
        async def get_share_holder(self, code_list):
            assert code_list == ["SH.600000"]
            return pd.DataFrame(
                {
                    "report_date": ["2024-03-31", "2024-03-31", "2024-03-31"],
                    "holder": ["A", "B", "C"],
                    "ratio": [10, 9, 8],
                }
            )

    provider = DummyProvider()

    async def fake_provider():
        return provider

    monkeypatch.setattr(shareholder, "get_amazingdata_provider", fake_provider)

    response = await shareholder.get_share_holder(
        code="SH.600000", report_date="2024-03-31", top_n=2
    )

    assert response["success"] is True
    rows = response["data"]["data"]
    assert len(rows) == 2
    assert [row["holder"] for row in rows] == ["A", "B"]
