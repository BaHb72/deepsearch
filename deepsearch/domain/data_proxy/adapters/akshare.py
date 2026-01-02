"""
AkShare Data Source Adapter

基于 AkShare 库的数据源适配器。
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
    CAPABILITY_STOCK_LIST,
)

if TYPE_CHECKING:
    import pandas as pd


# ==================== Dask 任务定义 ====================


@requires_windows  # 优先 Windows Worker，与其他数据源对齐
def _fetch_kline(
    symbol: str,
    period: str,
    start_date: str | None,
    end_date: str | None,
    adjust: str,
) -> dict[str, list]:
    """获取 K 线数据"""
    import akshare as ak

    # AkShare 需要纯数字代码
    code = symbol.split(".")[0] if "." in symbol else symbol

    # 周期映射
    try:
        if period in ("1d", "day"):
            # 日线
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=start_date or "",
                end_date=end_date or "",
                adjust=adjust,
            )
        elif period in ("1w", "week"):
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="weekly",
                start_date=start_date or "",
                end_date=end_date or "",
                adjust=adjust,
            )
        elif period in ("1M", "month"):
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="monthly",
                start_date=start_date or "",
                end_date=end_date or "",
                adjust=adjust,
            )
        else:
            # 分钟线
            df = ak.stock_zh_a_hist_min_em(
                symbol=code,
                period=period.replace("m", ""),
                adjust=adjust,
            )
    except Exception as e:
        logger.warning("AkShare K 线获取失败: {} {}: {}", symbol, period, e)
        return {}

    if df is None or df.empty:
        return {}

    # 统一列名
    result = {}
    for col in df.columns:
        result[col] = df[col].tolist()
    return result


@requires_windows
def _fetch_calendar() -> list[int]:
    """获取交易日历"""
    import akshare as ak

    try:
        df = ak.tool_trade_date_hist_sina()
        if df is not None and not df.empty:
            # 列名可能是 'trade_date'
            col = df.columns[0]
            dates = df[col].tolist()
            return [int(str(d).replace("-", "")) for d in dates if d]
    except Exception as e:
        logger.warning("AkShare 交易日历获取失败: {}", e)

    return []


@requires_windows
def _fetch_stock_list() -> list[dict[str, str]]:
    """获取 A 股股票列表"""
    import akshare as ak

    try:
        df = ak.stock_info_a_code_name()
        if df is not None and not df.empty:
            result = []
            for _, row in df.iterrows():
                code = str(row.get("code", ""))
                name = str(row.get("name", ""))
                # 推断交易所
                if code.startswith("6"):
                    exchange = "SH"
                elif code.startswith(("0", "3")):
                    exchange = "SZ"
                elif code.startswith(("4", "8")):
                    exchange = "BJ"
                else:
                    exchange = "SH"
                result.append({"symbol": code, "name": name, "exchange": exchange})
            return result
    except Exception as e:
        logger.warning("AkShare 股票列表获取失败: {}", e)

    return []


# ==================== 适配器实现 ====================


class AkShareAdapter:
    """AkShare 数据源适配器

    通过 Dask Worker 执行 AkShare 调用。
    优先使用 Windows Worker 以与其他数据源对齐。
    """

    def __init__(self):
        self._latencies: deque[float] = deque(maxlen=10)
        self._available: bool | None = None
        self._last_check: float = 0
        self._calendar_cache: list[int] = []
        self._calendar_cache_time: float = 0

    @property
    def name(self) -> str:
        return "akshare"

    @property
    def capabilities(self) -> set[str]:
        return {
            CAPABILITY_KLINE,
            CAPABILITY_CALENDAR,
            CAPABILITY_STOCK_LIST,
        }

    async def is_available(self) -> bool:
        """检查 AkShare 是否可用"""
        # 缓存 60 秒
        now = time.time()
        if self._available is not None and now - self._last_check < 60:
            return self._available

        try:
            client = await get_dask_client()
            future = client.submit(_fetch_calendar, resources={"WIN": 1})
            result = await asyncio.wait_for(
                asyncio.wrap_future(future), timeout=30.0
            )
            self._available = bool(result)
        except Exception as e:
            logger.warning("AkShare 可用性检查失败: {}", e)
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
        adjust: str = "qfq",
    ) -> "pd.DataFrame":
        """获取 K 线数据

        Args:
            symbol: 股票代码
            period: 周期
            start_date: 开始日期
            end_date: 结束日期
            limit: 数量限制
            adjust: 复权类型 (qfq=前复权, hfq=后复权, "")

        Returns:
            K 线 DataFrame
        """
        import pandas as pd

        client = await get_dask_client()

        start_time = time.perf_counter()
        future = client.submit(
            _fetch_kline,
            symbol,
            period,
            start_date,
            end_date,
            adjust,
            resources={"WIN": 1},
        )
        result = await asyncio.wrap_future(future)
        latency = (time.perf_counter() - start_time) * 1000
        self._latencies.append(latency)

        if not result:
            return pd.DataFrame()

        df = pd.DataFrame(result)

        # 标准化列名
        column_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "pct_chg",
            "涨跌额": "change",
            "换手率": "turnover",
        }
        df = df.rename(columns=column_map)

        # 限制数量
        if limit and len(df) > limit:
            df = df.tail(limit)

        return df

    async def get_calendar(
        self,
        market: str = "SH",
    ) -> list[int]:
        """获取交易日历

        注: AkShare 不区分市场，返回统一的 A 股交易日历
        """
        # 缓存 1 小时
        now = time.time()
        if self._calendar_cache and now - self._calendar_cache_time < 3600:
            return self._calendar_cache

        client = await get_dask_client()

        start_time = time.perf_counter()
        future = client.submit(_fetch_calendar, resources={"WIN": 1})
        result = await asyncio.wrap_future(future)
        latency = (time.perf_counter() - start_time) * 1000
        self._latencies.append(latency)

        if result:
            self._calendar_cache = result
            self._calendar_cache_time = now

        return result or []

    async def get_stock_list(
        self,
        market: str | None = None,
        board: str | None = None,
    ) -> Sequence[dict[str, Any]]:
        """获取股票列表"""
        client = await get_dask_client()

        start_time = time.perf_counter()
        future = client.submit(_fetch_stock_list, resources={"WIN": 1})
        result = await asyncio.wrap_future(future)
        latency = (time.perf_counter() - start_time) * 1000
        self._latencies.append(latency)

        if not result:
            return []

        # 市场过滤
        if market:
            result = [s for s in result if s.get("exchange") == market]

        return result
