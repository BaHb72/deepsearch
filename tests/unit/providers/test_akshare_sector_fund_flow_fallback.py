"""AkShare 板块资金流回退策略测试。"""

import pandas as pd
from core.infrastructure.providers.implementations.akshare.akshare_direct import AkShareProvider


class _FakeAkshareModule:
    def stock_sector_fund_flow_rank(self, indicator: str, sector_type: str):
        raise ConnectionError("remote closed")

    def stock_fund_flow_concept(self):
        return pd.DataFrame(
            [
                {
                    "行业": "AI应用",
                    "行业-涨跌幅": 2.35,
                    "净额": 12.5,
                    "领涨股": "示例A",
                },
                {
                    "行业": "机器人",
                    "行业-涨跌幅": 1.12,
                    "净额": 8.1,
                    "领涨股": "示例B",
                },
            ]
        )


def test_sector_capital_flow_rank_fallbacks_to_concept_snapshot(monkeypatch):
    provider = AkShareProvider(
        config={},
        akshare_module=_FakeAkshareModule(),
        pandas_module=pd,
    )
    provider.initialized = True

    monkeypatch.setattr(provider, "_fetch_sector_capital_flow_rank_raw_sync", lambda *_: [])

    rows = provider._fetch_sector_capital_flow_rank_sync("今日", "概念资金流")

    assert len(rows) == 2
    assert rows[0]["name"] == "AI应用"
    assert rows[0]["source"] == "akshare_direct_concept_snapshot"
    assert rows[0]["rank"] == 1


def test_sector_capital_flow_rank_non_concept_keeps_empty_when_all_fallbacks_fail(monkeypatch):
    provider = AkShareProvider(
        config={},
        akshare_module=_FakeAkshareModule(),
        pandas_module=pd,
    )
    provider.initialized = True

    monkeypatch.setattr(provider, "_fetch_sector_capital_flow_rank_raw_sync", lambda *_: [])

    rows = provider._fetch_sector_capital_flow_rank_sync("今日", "行业资金流")

    assert rows == []
