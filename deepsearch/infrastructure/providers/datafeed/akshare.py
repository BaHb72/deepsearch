from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None  # type: ignore

from deepsearch.infrastructure.providers.datafeed.base import IDataFeed, KlineParams
from deepsearch.infrastructure.providers.datafeed.normalizer import DataNormalizer
from deepsearch.infrastructure.providers.implementations.akshare.akshare import AkShareProxyProvider


class AkShareDataFeed(IDataFeed):
    """AkShare-backed DataFeed with schema normalization to DeepSearch format.

    Standard bar schema:
      ts: pandas.Timestamp or ISO string
      open, high, low, close: float
      volume, amount: float (optional)
    """

    def __init__(self, provider: Optional[AkShareProxyProvider] = None) -> None:
        self.provider = provider or AkShareProxyProvider()
        schema_mapping = {
            "ts": "日期",
            "open": "开盘",
            "close": "收盘",
            "high": "最高",
            "low": "最低",
            "volume": "成交量",
            "amount": "成交额",
        }
        self.normalizer = DataNormalizer(schema_mapping)

    async def get_kline(self, params: KlineParams) -> "pd.DataFrame | List[Dict[str, Any]]":
        # Reuse provider's fallback routing to Worker or direct akshare
        timeframe = params.timeframe
        symbol = params.symbol
        adjust = params.adjust
        start = params.start_date
        end = params.end_date

        if timeframe in ["1m", "3m", "5m", "15m", "30m", "60m"]:
            period_map = {"1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30", "60m": "60"}
            resp = await self.provider._fetch_with_fallback(
                "stock_zh_a_hist_min_em",
                {
                    "symbol": symbol,
                    "period": period_map[timeframe],
                    "start_date": start or "2020-01-01 09:30:00",
                    "end_date": end,
                    "adjust": "" if adjust == "none" else adjust,
                },
            )
        else:
            period_map = {"1d": "daily", "1w": "weekly", "1mo": "monthly"}
            resp = await self.provider._fetch_with_fallback(
                "stock_zh_a_hist",
                {
                    "symbol": symbol,
                    "period": period_map.get(timeframe, "daily"),
                    "start_date": start or "20200101",
                    "end_date": end,
                    "adjust": "" if adjust == "none" else adjust,
                },
            )

        data = resp.get("data") if isinstance(resp, dict) else None
        data_list = data if isinstance(data, list) else []
        return (
            self.normalize_bars(data_list)[: params.limit]
            if HAS_PANDAS
            else self.normalizer.normalize(data_list)[: params.limit]
        )

    async def get_realtime(self, symbols: List[str]) -> Dict[str, Any]:
        return await self.provider.get_realtime_data(symbols)

    def normalize_bars(self, data: List[Dict[str, Any]]) -> "pd.DataFrame | List[Dict[str, Any]]":
        normalized_data = self.normalizer.normalize(data)
        if not HAS_PANDAS:
            return normalized_data

        import pandas as pd

        df = pd.DataFrame(normalized_data)
        if df.empty:
            return df

        if "ts" in df.columns:
            try:
                df["ts"] = pd.to_datetime(df["ts"])
            except Exception:
                df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
        for col in ["open", "high", "low", "close", "volume", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "ts" in df.columns:
            df = df.sort_values("ts").reset_index(drop=True)
        return df
