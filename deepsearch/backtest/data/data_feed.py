"""
DeepSearchDataFeed - Backtrader 数据适配器

将 DeepSearch 的数据源适配为 Backtrader 可用的数据格式
"""

import os
from datetime import datetime
from typing import Any, Dict, TYPE_CHECKING, cast

import numpy as np
import pandas as pd

bt: Any

try:
    import backtrader as _backtrader

    HAS_BACKTRADER = True
    bt = _backtrader
except ImportError:
    HAS_BACKTRADER = False
    bt = None

if TYPE_CHECKING:
    from backtrader.feeds import PandasData as BacktraderPandasData
else:
    BacktraderPandasData = Any


def _allow_mock_data() -> bool:
    """Return True only during automated tests to allow mock data generation."""
    return bool(os.getenv("PYTEST_CURRENT_TEST"))



class DeepSearchDataFeed:
    """
    DeepSearch 数据源到 Backtrader 的适配器

    支持从多种数据源加载数据：
    1. AkShare 数据源
    2. QMT 数据源
    3. 数据库历史数据
    4. CSV 文件
    """

    def __init__(self, data_provider=None):
        """
        初始化数据适配器

        Args:
            data_provider: DeepSearch 数据提供者实例
        """
        if not HAS_BACKTRADER:
            raise ImportError("请先安装 backtrader: pip install backtrader")

        self.data_provider = data_provider
        self._cache: Dict[str, pd.DataFrame] = {}

    def _ensure_dataframe(self, data: Any) -> pd.DataFrame:
        """确保返回结果是 DataFrame"""
        if isinstance(data, pd.DataFrame):
            return data.copy()
        if data is None:
            return pd.DataFrame()
        return pd.DataFrame(data)

    async def get_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1d",
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """获取历史数据"""
        cache_key = f"{symbol}_{start_date}_{end_date}_{timeframe}_{adjust}"
        if cache_key in self._cache:
            return self._cache[cache_key].copy()

        if self.data_provider:
            raw_df = await self._fetch_from_provider(symbol, start_date, end_date, timeframe, adjust)
        else:
            if not _allow_mock_data():
                raise RuntimeError(
                    "DeepSearchDataFeed requires a data_provider; mock data is only permitted during automated tests.")
            raw_df = self._generate_mock_data(symbol, start_date, end_date, timeframe)

        df = self._standardize_dataframe(self._ensure_dataframe(raw_df))
        self._cache[cache_key] = df.copy()
        return df

    async def _fetch_from_provider(
        self, symbol: str, start_date: datetime, end_date: datetime, timeframe: str, adjust: str
    ) -> pd.DataFrame:
        """从数据提供者获取数据"""
        # 转换日期格式
        start_str = start_date.strftime("%Y%m%d")
        end_str = end_date.strftime("%Y%m%d")

        # 检查数据提供者类型并调用相应的方法
        provider_class_name = self.data_provider.__class__.__name__

        # 处理 AkShareDataFeed
        if hasattr(self.data_provider, "get_kline"):
            from deepsearch.infrastructure.providers.datafeed.base import KlineParams

            params = KlineParams(
                symbol=symbol,
                timeframe=timeframe,
                start_date=start_str,
                end_date=end_str,
                adjust=adjust,
            )
            result = await self.data_provider.get_kline(params)

            # 转换为 DataFrame
            if isinstance(result, list):
                return pd.DataFrame(result)
            return self._ensure_dataframe(result)

        # 处理旧版接口
        elif hasattr(self.data_provider, "get_stock_history"):
            if timeframe == "1d":
                # 获取日线数据
                df = await self.data_provider.get_stock_history(
                    symbol=symbol, start_date=start_str, end_date=end_str, adjust=adjust
                )
            elif timeframe in ["1m", "5m", "15m", "30m", "60m"]:
                # 获取分钟数据
                period = timeframe.replace("m", "")
                df = await self.data_provider.get_stock_minute(
                    symbol=symbol, period=period, adjust=adjust
                )
            else:
                # 尝试其他周期
                period_map = {"1w": "weekly", "1mo": "monthly"}
                period = period_map.get(timeframe, "daily")
                df = await self.data_provider.get_stock_history(
                    symbol=symbol,
                    start_date=start_str,
                    end_date=end_str,
                    adjust=adjust,
                    period=period,
                )
            return self._ensure_dataframe(df)

        # 处理其他数据提供者
        else:
            raise ValueError(f"Unsupported data provider: {provider_class_name}")

        return pd.DataFrame()

    def _generate_mock_data(
        self, symbol: str, start_date: datetime, end_date: datetime, timeframe: str
    ) -> pd.DataFrame:
        """Generate deterministic mock data for tests only."""
        dates = pd.date_range(start=start_date, end=end_date, freq="D")

        # 生成随机价格数据
        n = len(dates)
        np.random.seed(42)  # 固定随机种子以获得可重复的结果

        # 使用随机游走生成价格
        returns = np.random.randn(n) * 0.02  # 2% 日波动率
        price = 100 * np.exp(np.cumsum(returns))

        # 生成 OHLCV 数据
        df = pd.DataFrame(
            {
                "date": dates,
                "open": price * (1 + np.random.randn(n) * 0.005),
                "high": price * (1 + np.abs(np.random.randn(n)) * 0.01),
                "low": price * (1 - np.abs(np.random.randn(n)) * 0.01),
                "close": price,
                "volume": np.random.randint(1000000, 10000000, n),
            }
        )

        # 确保 high >= max(open, close) 且 low <= min(open, close)
        df["high"] = df[["open", "high", "close"]].max(axis=1)
        df["low"] = df[["open", "low", "close"]].min(axis=1)

        return df

    def _standardize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化 DataFrame 格式

        确保包含必要的列：date, open, high, low, close, volume
        """
        # 列名映射
        column_mapping = {
            "日期": "date",
            "Date": "date",
            "datetime": "date",
            "开盘": "open",
            "Open": "open",
            "开盘价": "open",
            "最高": "high",
            "High": "high",
            "最高价": "high",
            "最低": "low",
            "Low": "low",
            "最低价": "low",
            "收盘": "close",
            "Close": "close",
            "收盘价": "close",
            "成交量": "volume",
            "Volume": "volume",
            "成交额": "turnover",
            "Amount": "turnover",
        }

        # 重命名列
        df = df.rename(columns=column_mapping)

        # 确保必要的列存在
        required_columns = ["date", "open", "high", "low", "close", "volume"]
        for col in required_columns:
            if col not in df.columns:
                if col == "volume":
                    # 如果没有成交量，使用默认值
                    df[col] = 1000000
                else:
                    raise ValueError(f"数据缺少必要的列: {col}")

        # 设置日期为索引
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

        # 按日期排序
        df = df.sort_index()

        # 处理缺失值
        df = df.ffill()

        return df

    def create_backtrader_feed(self, dataframe: pd.DataFrame, **kwargs) -> "BacktraderPandasData":
        """
        创建 Backtrader 数据源对象

        Args:
            dataframe: 包含 OHLCV 数据的 DataFrame
            **kwargs: 传递给 PandasData 的其他参数

        Returns:
            bt.feeds.PandasData: Backtrader 数据源对象
        """
        if not HAS_BACKTRADER:
            raise ImportError("请先安装 backtrader: pip install backtrader")

        assert bt is not None
        # 创建 Backtrader 数据源
        feed = cast(
            BacktraderPandasData,
            bt.feeds.PandasData(
                dataname=dataframe,
                datetime=None,  # 使用索引作为日期
                open="open",
                high="high",
                low="low",
                close="close",
                volume="volume",
                openinterest=-1,  # 不使用持仓量
                **kwargs,
            ),
        )

        return feed

    async def get_backtrader_feed(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1d",
        adjust: str = "qfq",
        **kwargs,
    ) -> "BacktraderPandasData":
        """
        直接获取 Backtrader 数据源对象

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            timeframe: 时间周期
            adjust: 复权方式
            **kwargs: 传递给 PandasData 的其他参数

        Returns:
            bt.feeds.PandasData: Backtrader 数据源对象
        """
        # 获取数据
        df = await self.get_data(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe=timeframe,
            adjust=adjust,
        )

        # 创建 Backtrader 数据源
        return self.create_backtrader_feed(df, **kwargs)

    def clear_cache(self):
        """清空数据缓存"""
        self._cache.clear()

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存信息"""
        return {
            "cache_size": len(self._cache),
            "cached_symbols": list(set(key.split("_")[0] for key in self._cache.keys())),
        }
