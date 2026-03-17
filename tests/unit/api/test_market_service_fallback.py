from __future__ import annotations

import pytest

from apps.api.api import providers


@pytest.mark.asyncio
async def test_fallback_market_service_anomalies_from_akshare_changes(monkeypatch) -> None:
    """当市场服务实现缺失时，fallback 应提供异动数据而非空数组。"""

    class _FakeAkshareProvider:
        async def call_api(self, api_name: str, params: dict[str, str]):
            assert api_name == "stock_changes_em"
            if params.get("symbol") == "封跌停板":
                return {"success": True, "data": []}
            return {
                "success": True,
                "data": [
                    {
                        "时间": "14:55:28",
                        "代码": "301228",
                        "名称": "实朴检测",
                        "板块": params.get("symbol") or "大笔买入",
                        "相关信息": "120300,44.05000,-0.025738,5299215.00",
                    }
                ],
            }

    async def _fake_get_provider():
        return _FakeAkshareProvider()

    monkeypatch.setattr(providers, "_EastMoneyServiceImpl", None)
    monkeypatch.setattr(providers, "_AkShareDirectServiceImpl", None)
    monkeypatch.setattr(providers, "_MarketServiceImpl", None)
    monkeypatch.setattr(providers, "_get_fallback_akshare_direct_provider", _fake_get_provider)

    service = await providers.get_market_service()
    anomalies = await service.get_anomalies(kind="all", min_change=0, min_amount=0)

    assert isinstance(anomalies, list)
    assert anomalies, "fallback 异动列表不应为空"
    row = anomalies[0]
    assert row["symbol"] == "301228"
    assert row["name"] == "实朴检测"
    assert row["reason"]
    assert isinstance(row["extra"], dict)
    assert row["extra"]["source"] == "akshare.stock_changes_em"
