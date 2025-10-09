from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None  # type: ignore

from deepsearch.infrastructure.providers.datafeed.base import IDataFeed, KlineParams
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
            else data_list[: params.limit]
        )

    async def get_realtime(self, symbols: List[str]) -> Dict[str, Any]:
        return await self.provider.get_realtime_data(symbols)

    def normalize_bars(self, data: List[Dict[str, Any]]) -> "pd.DataFrame | List[Dict[str, Any]]":
        if not HAS_PANDAS:
            # Basic mapping for list of dicts
            out: List[Dict[str, Any]] = []
            for row in data:
                r = dict(row)
                # map possible keys
                ts = (
                    r.get("ts")
                    or r.get("日期")
                    or r.get("时间")
                    or r.get("date")
                    or r.get("datetime")
                    or r.get("time")
                )
                r["ts"] = ts
                # rename
                for cn, en in [
                    ("开盘", "open"),
                    ("收盘", "close"),
                    ("最高", "high"),
                    ("最低", "low"),
                    ("成交量", "volume"),
                    ("成交额", "amount"),
                ]:
                    if cn in r and en not in r:
                        r[en] = r[cn]
                out.append(r)
            return out

        import pandas as pd  # type: ignore

        df = pd.DataFrame(data)
        if df.empty:
            return df
        rename_map = {
            "日期": "ts",
            "时间": "ts",
            "date": "ts",
            "datetime": "ts",
            "time": "ts",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
        }
        df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
        if "ts" not in df.columns:
            for cand in ["日期", "时间", "date", "datetime", "time"]:
                if cand in df.columns:
                    df["ts"] = df[cand]
                    break
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
