"""
MiniQMT Data Source Adapter

基于 xtquant SDK 的 MiniQMT 数据源适配器。
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Sequence

from loguru import logger

from deepsearch.compute import get_dask_client, requires_windows

from ..interfaces import (
    CAPABILITY_CALENDAR,
    CAPABILITY_KLINE,
    CAPABILITY_REALTIME,
    CAPABILITY_STOCK_LIST,
)

if TYPE_CHECKING:
    import pandas as pd

    from deepsearch.ports.market_data import MarketSnapshot


# ==================== Dask 任务定义 ====================


@requires_windows
def _fetch_kline(
    symbol: str,
    period: str,
    start_date: str | None,
    end_date: str | None,
    count: int,
) -> dict[str, Any]:
    """在 Windows Worker 获取 K 线数据"""
    from xtquant import xtdata

    # 规范化股票代码
    if "." not in symbol:
        if symbol.startswith("6"):
            symbol = f"{symbol}.SH"
        elif symbol.startswith(("0", "3")):
            symbol = f"{symbol}.SZ"
        elif symbol.startswith(("4", "8")):
            symbol = f"{symbol}.BJ"

    # 周期映射
    period_map = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "60m": "60m",
        "1d": "1d",
        "1w": "1w",
        "1M": "1mon",
    }
    xt_period = period_map.get(period, "1d")

    # 获取数据
    result = xtdata.get_market_data(
        field_list=["time", "open", "high", "low", "close", "volume", "amount"],
        stock_list=[symbol],
        period=xt_period,
        count=count,
    )

    if not result or symbol not in result.get("close", {}):
        return {}

    # 转换格式
    data = {
        "time": list(result.get("time", {}).get(symbol, [])),
        "open": list(result.get("open", {}).get(symbol, [])),
        "high": list(result.get("high", {}).get(symbol, [])),
        "low": list(result.get("low", {}).get(symbol, [])),
        "close": list(result.get("close", {}).get(symbol, [])),
        "volume": list(result.get("volume", {}).get(symbol, [])),
        "amount": list(result.get("amount", {}).get(symbol, [])),
    }
    return data


@requires_windows
def _fetch_calendar(market: str) -> list[int]:
    """在 Windows Worker 获取交易日历"""
    from xtquant import xtdata

    dates = xtdata.get_trading_dates(market.upper())
    if dates:
        return [int(d) for d in dates if d and str(d).isdigit()]
    return []


@requires_windows
def _fetch_realtime_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """在 Windows Worker 获取实时行情"""
    from xtquant import xtdata

    # 规范化股票代码
    normalized = []
    for s in symbols:
        if "." not in s:
            if s.startswith("6"):
                normalized.append(f"{s}.SH")
            elif s.startswith(("0", "3")):
                normalized.append(f"{s}.SZ")
            elif s.startswith(("4", "8")):
                normalized.append(f"{s}.BJ")
            else:
                normalized.append(s)
        else:
            normalized.append(s)

    return xtdata.get_full_tick(normalized)


@requires_windows
def _fetch_stock_list(sector: str) -> list[str]:
    """在 Windows Worker 获取股票列表"""
    from xtquant import xtdata

    return xtdata.get_stock_list_in_sector(sector)


# ==================== 适配器实现 ====================


class MiniQMTAdapter:
    """MiniQMT 数据源适配器

    通过 Dask Windows Worker 执行 xtquant SDK 调用。
    """

    def __init__(self):
        self._latencies: deque[float] = deque(maxlen=10)
        self._available: bool | None = None
        self._last_check: float = 0

    @property
    def name(self) -> str:
        return "miniqmt"

    @property
    def capabilities(self) -> set[str]:
        return {
            CAPABILITY_KLINE,
            CAPABILITY_REALTIME,
            CAPABILITY_CALENDAR,
            CAPABILITY_STOCK_LIST,
        }

    async def is_available(self) -> bool:
        """检查 MiniQMT 是否可用"""
        # 缓存 60 秒
        now = time.time()
        if self._available is not None and now - self._last_check < 60:
            return self._available

        try:
            client = await get_dask_client()
            # 尝试获取一个简单数据验证连接
            future = client.submit(_fetch_calendar, "SH", resources={"WIN": 1})
            result = await asyncio.wait_for(asyncio.wrap_future(future), timeout=10.0)
            self._available = bool(result)
        except Exception as e:
            logger.warning("MiniQMT 可用性检查失败: {}", e)
            self._available = False

        self._last_check = now
        return self._available

    async def get_latency(self) -> float:
        """获取平均延迟"""
        if not self._latencies:
            return 999.0
        return sum(self._latencies) / len(self._latencies)

    async def get_kline(
        self,
        symbol: str,
        period: str = "1d",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> "pd.DataFrame":
        """获取 K 线数据"""
        import pandas as pd

        client = await get_dask_client()

        start_time = time.perf_counter()
        future = client.submit(
            _fetch_kline,
            symbol,
            period,
            start_date,
            end_date,
            limit,
            resources={"WIN": 1},
        )
        result = await asyncio.wrap_future(future)
        latency = (time.perf_counter() - start_time) * 1000
        self._latencies.append(latency)

        if not result:
            return pd.DataFrame()

        df = pd.DataFrame(result)
        if "time" in df.columns:
            df["datetime"] = pd.to_datetime(df["time"], unit="ms")
        return df

    async def get_realtime_quotes(
        self,
        symbols: Sequence[str],
    ) -> Sequence["MarketSnapshot"]:
        """获取实时行情"""
        from datetime import datetime, timezone
        from decimal import Decimal

        from deepsearch.ports.market_data import MarketSnapshot

        client = await get_dask_client()

        start_time = time.perf_counter()
        future = client.submit(
            _fetch_realtime_quotes,
            list(symbols),
            resources={"WIN": 1},
        )
        result = await asyncio.wrap_future(future)
        latency = (time.perf_counter() - start_time) * 1000
        self._latencies.append(latency)

        snapshots: list[MarketSnapshot] = []
        if not result:
            return snapshots

        for symbol, data in result.items():
            if not data:
                continue
            code = symbol.split(".")[0] if "." in symbol else symbol
            exchange = symbol.split(".")[1] if "." in symbol else "SH"

            snapshots.append(
                MarketSnapshot(
                    code=code,
                    name=str(data.get("name", code)),
                    exchange=exchange,
                    ts=datetime.now(timezone.utc),
                    last=Decimal(str(data.get("last_price", 0))),
                    open=Decimal(str(data.get("open", 0))),
                    high=Decimal(str(data.get("high", 0))),
                    low=Decimal(str(data.get("low", 0))),
                    prev_close=Decimal(str(data.get("pre_close", 0))),
                    amount=Decimal(str(data.get("amount", 0))),
                    volume=int(data.get("volume", 0)),
                    num_trades=None,
                    bid_prices=[],
                    bid_volumes=[],
                    ask_prices=[],
                    ask_volumes=[],
                    upper_limit=None,
                    lower_limit=None,
                    trading_phase=None,
                )
            )

        return snapshots

    async def get_calendar(
        self,
        market: str = "SH",
    ) -> list[int]:
        """获取交易日历"""
        client = await get_dask_client()

        start_time = time.perf_counter()
        future = client.submit(_fetch_calendar, market, resources={"WIN": 1})
        result = await asyncio.wrap_future(future)
        latency = (time.perf_counter() - start_time) * 1000
        self._latencies.append(latency)

        return result or []

    async def get_stock_list(
        self,
        market: str | None = None,
        board: str | None = None,
    ) -> Sequence[dict[str, Any]]:
        """获取股票列表"""
        client = await get_dask_client()

        # 确定板块
        sector = "沪深A股"
        if market == "BJ":
            sector = "BJ"
        elif board:
            sector = board

        start_time = time.perf_counter()
        future = client.submit(_fetch_stock_list, sector, resources={"WIN": 1})
        symbols = await asyncio.wrap_future(future)
        latency = (time.perf_counter() - start_time) * 1000
        self._latencies.append(latency)

        if not symbols:
            return []

        # 转换为字典格式
        result = []
        for symbol in symbols:
            code = symbol.split(".")[0] if "." in symbol else symbol
            exchange = symbol.split(".")[1] if "." in symbol else "SH"
            result.append(
                {
                    "symbol": code,
                    "exchange": exchange,
                    "name": code,  # 名称需要额外获取
                }
            )
        return result
