"""AkShare direct provider fallback behavior tests."""

from __future__ import annotations

import pandas as pd
from core.infrastructure.providers.implementations.akshare.akshare_direct import AkShareProvider


class _FakeAkshareModule:
    def __init__(self) -> None:
        self.em_calls = 0
        self.spot_calls = 0

    def stock_zh_a_spot_em(self):
        self.em_calls += 1
        raise RuntimeError("eastmoney unavailable")

    def stock_zh_a_spot(self):
        self.spot_calls += 1
        return pd.DataFrame(
            [
                {
                    "代码": 1,
                    "名称": "平安银行",
                    "最新价": 10.1,
                    "昨收": 10.0,
                    "今开": 10.0,
                    "最高": 10.3,
                    "最低": 9.9,
                    "成交量": 1000,
                    "成交额": 1000000,
                    "涨跌额": 0.1,
                    "涨跌幅": 1.0,
                    "振幅": 2.0,
                    "换手率": 1.2,
                    "市盈率-动态": 9.0,
                    "市净率": 1.0,
                    "总市值": 100000000,
                    "流通市值": 80000000,
                },
                {
                    "代码": 2,
                    "名称": "万科A",
                    "最新价": 9.8,
                    "昨收": 9.9,
                    "今开": 9.9,
                    "最高": 10.0,
                    "最低": 9.7,
                    "成交量": 2000,
                    "成交额": 2000000,
                    "涨跌额": -0.1,
                    "涨跌幅": -1.0,
                    "振幅": 2.5,
                    "换手率": 1.5,
                    "市盈率-动态": 8.5,
                    "市净率": 0.9,
                    "总市值": 90000000,
                    "流通市值": 70000000,
                },
            ]
        )

    def stock_individual_info_em(self, symbol: str):
        raise RuntimeError(f"individual info unavailable for {symbol}")


def test_fetch_realtime_quotes_sync_falls_back_to_stock_zh_a_spot_with_cache() -> None:
    fake_module = _FakeAkshareModule()
    provider = AkShareProvider(akshare_module=fake_module)
    provider.initialized = True

    first = provider._fetch_realtime_quotes_sync(["000001", "000002"])
    second = provider._fetch_realtime_quotes_sync(["000001"])

    assert len(first) == 2
    assert first[0]["symbol"] == "000001"
    assert first[1]["symbol"] == "000002"
    assert len(second) == 1
    assert second[0]["symbol"] == "000001"
    assert fake_module.em_calls == 1
    assert fake_module.spot_calls == 1


def test_fetch_realtime_quote_sync_uses_market_spot_fallback() -> None:
    fake_module = _FakeAkshareModule()
    provider = AkShareProvider(akshare_module=fake_module)
    provider.initialized = True

    quote = provider._fetch_realtime_quote_sync("000001")

    assert quote["symbol"] == "000001"
    assert quote["name"] == "平安银行"
    assert quote["current"] == 10.1
    assert quote["source"] == "akshare_direct"
    assert fake_module.em_calls == 1
    assert fake_module.spot_calls == 1


def test_fetch_stock_list_sync_uses_market_spot_fallback() -> None:
    fake_module = _FakeAkshareModule()
    provider = AkShareProvider(akshare_module=fake_module)
    provider.initialized = True

    stocks = provider._fetch_stock_list_sync()

    assert len(stocks) == 2
    assert stocks[0]["代码"] == "000001"
    assert stocks[0]["名称"] == "平安银行"
    assert stocks[1]["代码"] == "000002"
    assert stocks[1]["名称"] == "万科A"
    assert fake_module.em_calls == 1
    assert fake_module.spot_calls == 1
