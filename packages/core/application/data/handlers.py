"""
数据处理器模块。

提供 KlineResponse → DataFrame/Arrow/NumPy 的类型转换，
实现 Decimal → float 的精度转换策略。

用法:
    from core.application.data.handlers import KlineDataHandler

    # 从响应创建处理器
    handler = KlineDataHandler(response)

    # 策略层使用 (float64)
    df = handler.to_dataframe()

    # TA-Lib 使用
    ohlcv = handler.ohlcv

    # 缓存层使用
    table = handler.to_arrow()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Sequence

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    pass

from core.ports.data.responses import KlineBar, KlineResponse
from core.ports.data.semantic_types import AssetSpec, Timeframe


@dataclass
class KlineDataHandler:
    """
    K线数据处理器。

    负责将 KlineResponse (Decimal 精度) 转换为策略层所需的格式：
    - to_dataframe(): 返回 float64 DataFrame (策略计算)
    - to_arrow(): 返回 Arrow Table (L1 缓存写入)
    - to_numpy(): 返回 NumPy array (TA-Lib / L2 写入)
    """

    response: KlineResponse
    _df_cache: pd.DataFrame | None = field(default=None, repr=False)

    @property
    def asset(self) -> AssetSpec:
        return self.response.asset

    @property
    def timeframe(self) -> Timeframe:
        return self.response.timeframe

    @property
    def bars(self) -> Sequence[KlineBar]:
        return self.response.bars

    def __len__(self) -> int:
        return len(self.response.bars)

    def to_dataframe(self, as_float: bool = True) -> pd.DataFrame:
        """
        转换为 DataFrame。

        Args:
            as_float: True 返回 float64 (策略层), False 保留 Decimal (存储层)

        Returns:
            包含 OHLCV 数据的 DataFrame，索引为 timestamp
        """
        if self._df_cache is not None and as_float:
            return self._df_cache

        records = []
        for bar in self.bars:
            record = {
                "timestamp": bar.timestamp,
                "open": float(bar.open) if as_float else bar.open,
                "high": float(bar.high) if as_float else bar.high,
                "low": float(bar.low) if as_float else bar.low,
                "close": float(bar.close) if as_float else bar.close,
                "volume": bar.volume,
                "amount": float(bar.amount) if as_float else bar.amount,
            }
            if bar.turnover is not None:
                record["turnover"] = float(bar.turnover) if as_float else bar.turnover
            records.append(record)

        df = pd.DataFrame(records)
        if not df.empty:
            df.set_index("timestamp", inplace=True)

        if as_float:
            self._df_cache = df

        return df

    def to_arrow(self) -> Any:
        """
        转换为 Arrow Table (零拷贝缓存写入)。

        Returns:
            Arrow Table，列类型为 float64
        """
        try:
            import pyarrow as pa
        except ImportError as e:
            raise ImportError("需要 pyarrow: pip install pyarrow") from e

        df = self.to_dataframe(as_float=True).reset_index()
        return pa.Table.from_pandas(df, preserve_index=False)  # type: ignore[attr-defined, return-value]

    def to_numpy(self, columns: list[str] | None = None) -> Any:
        """
        转换为 NumPy 数组。

        Args:
            columns: 要包含的列，None 表示 OHLCV

        Returns:
            shape (N, len(columns)) 的 float64 数组
        """
        if columns is None:
            columns = ["open", "high", "low", "close", "volume"]

        df = self.to_dataframe(as_float=True)
        return np.asarray(df[columns].values, dtype=np.float64)

    @property
    def ohlcv(self) -> Any:
        """返回 OHLCV 5列数组 (N, 5)，供 TA-Lib 使用。"""
        return self.to_numpy(["open", "high", "low", "close", "volume"])

    @property
    def ohlc(self) -> Any:
        """返回 OHLC 4列数组 (N, 4)。"""
        return self.to_numpy(["open", "high", "low", "close"])

    @property
    def close(self) -> Any:
        """返回收盘价 1D 数组。"""
        return np.asarray(self.to_numpy(["close"])).flatten()  # type: ignore[attr-defined]

    @property
    def volume(self) -> Any:
        """返回成交量 1D 数组。"""
        return np.asarray(self.to_numpy(["volume"])).flatten()  # type: ignore[attr-defined]

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        asset: AssetSpec,
        timeframe: Timeframe,
    ) -> "KlineDataHandler":
        """
        从 DataFrame 创建处理器 (反向转换)。

        Args:
            df: 包含 OHLCV 的 DataFrame，索引为 timestamp
            asset: 资产规格
            timeframe: 时间周期

        Returns:
            KlineDataHandler 实例
        """
        from core.ports.data_sources import DataSourceType

        bars = []
        for ts, row in df.iterrows():
            bar = KlineBar(
                timestamp=ts if isinstance(ts, datetime) else pd.to_datetime(ts),  # type: ignore[arg-type]
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=int(row.get("volume", 0)),
                amount=Decimal(str(row.get("amount", 0))),
                turnover=(
                    Decimal(str(row["turnover"]))
                    if "turnover" in row and pd.notna(row["turnover"])
                    else None
                ),
            )
            bars.append(bar)

        response = KlineResponse(
            asset=asset,
            timeframe=timeframe,
            bars=bars,
            source=DataSourceType.CUSTOM,  # 从 DataFrame 创建的数据源
        )
        return cls(response=response)


__all__ = ["KlineDataHandler"]
