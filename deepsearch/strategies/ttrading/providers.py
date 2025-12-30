"""
MiniQMT Intraday Data Provider

Implements IntradayDataProvider protocol by directly using MiniQMTPollingStreamPort
(the proven working implementation).
"""

import asyncio
from datetime import datetime
from typing import Any, Callable, Optional, Sequence

import pandas as pd
from loguru import logger

from deepsearch.strategies.ttrading.interfaces import IntradayDataProvider, QuoteSnapshot

# Try to import from the polling adapter (proven working)
MiniQMTPollingStreamPort: Any = None

try:
    from deepsearch.adapters.market_data.miniqmt_polling_adapter import MiniQMTPollingStreamPort

    MINIQMT_AVAILABLE = True
except ImportError:
    MINIQMT_AVAILABLE = False


class MiniQMTIntradayDataProvider(IntradayDataProvider):
    """
    MiniQMT 分时数据提供者

    直接使用 MiniQMTPollingStreamPort（经过验证的实现）获取实时数据
    所有方法都是 async 以匹配 MockIntradayDataProvider 接口
    """

    def __init__(self):
        """初始化"""
        if not MINIQMT_AVAILABLE:
            raise ImportError(
                "MiniQMT polling adapter not available. " "Please ensure xtquant is installed."
            )

        self._stream_port = MiniQMTPollingStreamPort()
        self._subscriptions: dict[str, Callable] = {}

        logger.info("MiniQMTIntradayDataProvider initialized (using MiniQMTPollingStreamPort)")

    @property
    def is_connected(self) -> bool:
        """检查连接状态"""
        return MINIQMT_AVAILABLE

    async def get_intraday_bars(
        self,
        symbol: str,
        minutes: int = 240,
    ) -> pd.DataFrame:
        """
        获取分时K线数据 - 使用MiniQMT真实数据
        """
        from concurrent.futures import ThreadPoolExecutor

        from deepsearch.infrastructure.providers.datafeed.miniqmt.miniqmt_collector import (
            MiniQMTCollector,
        )

        try:
            # 获取MiniQMTCollector实例
            collector = MiniQMTCollector()

            if not collector.connected:
                logger.warning("MiniQMT not connected, returning empty data")
                return pd.DataFrame()

            # 使用日期格式YYYYMMDD
            today_str = datetime.now().strftime("%Y%m%d")

            logger.info(f"Fetching real intraday data for {symbol}, date={today_str}, period=1m")

            # 在线程池中执行同步操作
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor,
                    lambda: collector.download_history_data(
                        stock_code=symbol,
                        period="1m",  # 1分钟K线
                        start_time=today_str,
                        end_time=today_str,
                    ),
                )

            logger.info(
                f"Download result for {symbol}: success={result.get('success')}, count={result.get('count', 0)}"
            )

            if result.get("success") and result.get("data"):
                df = pd.DataFrame(result["data"])

                # 格式化时间列 - 确保输出北京时间
                if "time" in df.columns:
                    # 将时间转换为 datetime
                    df["datetime"] = pd.to_datetime(df["time"])

                    # 如果没有时区信息，假设是 UTC 并转换为北京时间
                    # MiniQMT 返回的时间戳是毫秒级 Unix 时间（UTC）
                    if df["datetime"].dt.tz is None:
                        # 添加 UTC 时区信息
                        df["datetime"] = df["datetime"].dt.tz_localize("UTC")
                    # 转换为北京时间 (Asia/Shanghai)
                    df["datetime"] = df["datetime"].dt.tz_convert("Asia/Shanghai")
                    # 格式化为 HH:MM 字符串（去掉时区信息）
                    df["time"] = df["datetime"].dt.strftime("%H:%M")
                    # 添加日期字段，用于前端区分不同交易日
                    df["date"] = df["datetime"].dt.strftime("%Y-%m-%d")

                logger.info(f"获取到 {symbol} 真实分时数据: {len(df)} 条")
                return df
            else:
                logger.warning(
                    f"Failed to get real intraday data for {symbol}: {result.get('error')}"
                )
                # 不返回模拟数据，返回空 DataFrame
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"Error getting intraday bars for {symbol}: {e}")
            # 不返回模拟数据，返回空 DataFrame
            return pd.DataFrame()

    async def _generate_synthetic_bars(self, symbol: str, minutes: int) -> pd.DataFrame:
        """生成基于真实价格的合成分时数据（备用）"""
        import numpy as np

        quote = await self.get_current_quote(symbol)
        if quote is None:
            return pd.DataFrame()

        base_price = quote.price
        np.random.seed(hash(symbol) % 2**32)

        dates = pd.date_range(
            datetime.now().replace(hour=9, minute=30),
            periods=minutes,
            freq="1min",
        )

        returns = np.random.randn(minutes) * 0.001
        prices = base_price * np.exp(np.cumsum(returns))
        prices[-1] = base_price

        df = pd.DataFrame(
            {
                "datetime": dates,
                "time": [d.strftime("%H:%M") for d in dates],
                "open": prices - 0.01,
                "high": prices + np.abs(np.random.randn(minutes) * 0.02),
                "low": prices - np.abs(np.random.randn(minutes) * 0.02),
                "close": prices,
                "volume": np.random.randint(1000, 10000, minutes).astype(float),
                "amount": prices * np.random.randint(1000, 10000, minutes),
            }
        )

        logger.debug(f"Generated synthetic {len(df)} bars for {symbol}")
        return df

    async def get_current_quote(self, symbol: str) -> Optional[QuoteSnapshot]:
        """
        获取当前实时行情 (async版本)
        """
        try:
            # 使用轮询适配器获取实时行情
            snapshots = await self._stream_port.fetch_latest([symbol])

            if not snapshots:
                logger.warning(f"No snapshot data for {symbol}")
                return None

            # 转换MarketSnapshot为QuoteSnapshot
            snap = snapshots[0]

            quote = QuoteSnapshot(
                symbol=symbol,
                datetime=snap.ts.replace(tzinfo=None) if snap.ts else datetime.now(),
                price=float(snap.last),
                open=float(snap.open),
                high=float(snap.high),
                low=float(snap.low),
                prev_close=float(snap.prev_close),
                volume=float(snap.volume),
                amount=float(snap.amount),
                bid_price=float(snap.bid_prices[0]) if snap.bid_prices else 0.0,
                ask_price=float(snap.ask_prices[0]) if snap.ask_prices else 0.0,
                bid_volume=int(snap.bid_volumes[0]) if snap.bid_volumes else 0,
                ask_volume=int(snap.ask_volumes[0]) if snap.ask_volumes else 0,
            )

            logger.debug(f"Got quote for {symbol}: price={quote.price}")
            return quote

        except Exception as e:
            logger.error(f"get_current_quote failed for {symbol}: {e}")
            return None

    async def subscribe(
        self,
        symbols: Sequence[str],
        callback: Any,
    ) -> None:
        """订阅实时行情"""
        for symbol in symbols:
            self._subscriptions[symbol] = callback
        logger.info(f"Subscribed to {len(symbols)} symbols")

    async def unsubscribe(self, symbols: Sequence[str]) -> None:
        """取消订阅"""
        for symbol in symbols:
            self._subscriptions.pop(symbol, None)


def get_miniqmt_provider() -> Optional[MiniQMTIntradayDataProvider]:
    """
    安全获取 MiniQMT 数据提供者

    Returns:
        MiniQMTIntradayDataProvider 实例，不可用时返回 None
    """
    if not MINIQMT_AVAILABLE:
        logger.warning("MiniQMT not available")
        return None

    try:
        return MiniQMTIntradayDataProvider()
    except Exception as e:
        logger.error(f"Failed to create MiniQMT provider: {e}")
        return None


def get_best_data_provider() -> Optional[IntradayDataProvider]:
    """
    获取最佳可用的数据提供者（带回退机制）

    回退顺序: MiniQMT → None (调用方使用Mock)

    Returns:
        可用的 IntradayDataProvider 实例，或 None
    """
    if MINIQMT_AVAILABLE:
        provider = get_miniqmt_provider()
        if provider is not None:
            logger.info("Using MiniQMT data provider (via polling adapter)")
            return provider

    logger.warning("No real-time data provider available")
    return None
