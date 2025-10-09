"""数据清洗模块

提供行情数据清洗和标准化功能
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Literal, cast

import numpy as np
import pandas as pd

from deepsearch.data.types import (
    BoolSeries,
    DatetimeScalar,
    NumericSeries,
    StringSeries,
    TimedeltaScalar,
    TimedeltaSeries,
    TimestampSeries,
)
from deepsearch.observability.logger import logger

FillMethod = Literal["ffill", "bfill", "interpolate"]
OutlierMethod = Literal["iqr", "zscore", "mad"]


class DataCleaner:
    """数据清洗器
    
    提供各种数据清洗和预处理功能
    """

    def __init__(self):
        self.logger = logger.bind(module="数据清洗")

    def clean_tick_data(
        self,
        df: pd.DataFrame,
        price_change_limit: float = 0.2,
        remove_zero_volume: bool = True,
        remove_auction: bool = True,
    ) -> pd.DataFrame:
        """清洗 Tick 数据
        
        Args:
            df: 原始 Tick 数据
            price_change_limit: 价格变动限制（默认 20%）
            remove_zero_volume: 是否移除零成交量记录
            remove_auction: 是否移除集合竞价数据
            
        Returns:
            清洗后的 DataFrame
        """
        if df.empty:
            return df

        original_count = len(df)
        df = df.copy()

        # 1. 移除重复数据
        df = df.drop_duplicates(subset=["time", "symbol"], keep="last")

        # 2. 移除价格异常值
        if "last_price" in df.columns:
            # 计算价格变动率
            price_change_series = cast(
                NumericSeries, df.groupby("symbol")["last_price"].pct_change()
            )
            df["price_change"] = price_change_series

            # 移除异常变动
            mask = cast(BoolSeries, price_change_series.abs() <= price_change_limit)
            valid_mask = cast(BoolSeries, mask | price_change_series.isna())
            df = df.loc[valid_mask]

            # 删除临时列
            df = df.drop(columns=["price_change"])

        # 3. 移除零成交量记录
        if remove_zero_volume and "volume" in df.columns:
            positive_volume = cast(BoolSeries, df["volume"] > 0)
            df = df.loc[positive_volume]

        # 4. 移除集合竞价时段数据
        if remove_auction and "time" in df.columns:
            # 转换时间列
            df["hour"] = pd.to_datetime(df["time"]).dt.hour
            df["minute"] = pd.to_datetime(df["time"]).dt.minute

            # 移除 9:15-9:25 和 14:57-15:00 的数据
            morning_auction = cast(
                BoolSeries, (df["hour"] == 9) & (df["minute"] >= 15) & (df["minute"] < 25)
            )
            afternoon_auction = cast(
                BoolSeries, (df["hour"] == 14) & (df["minute"] >= 57)
            )
            valid_trading = cast(BoolSeries, ~(morning_auction | afternoon_auction))

            df = df.loc[valid_trading]
            df = df.drop(columns=["hour", "minute"])

        # 5. 标准化时间戳
        if "time" in df.columns:
            df["time"] = pd.to_datetime(df["time"])

        # 6. 排序
        df = df.sort_values(["symbol", "time"])

        cleaned_count = len(df)
        removed_count = original_count - cleaned_count

        self.logger.info(
            f"Tick 数据清洗完成: 原始 {original_count} 条, "
            f"清洗后 {cleaned_count} 条, 移除 {removed_count} 条"
        )

        return df

    def clean_kline_data(
        self,
        df: pd.DataFrame,
        fix_ohlc: bool = True,
        remove_zero_volume: bool = True,
        fill_missing: bool = True,
    ) -> pd.DataFrame:
        """清洗 K 线数据
        
        Args:
            df: 原始 K 线数据
            fix_ohlc: 是否修正 OHLC 关系
            remove_zero_volume: 是否移除零成交量记录
            fill_missing: 是否填充缺失数据
            
        Returns:
            清洗后的 DataFrame
        """
        if df.empty:
            return df

        original_count = len(df)
        df = df.copy()

        # 1. 移除重复数据
        time_col = "time" if "time" in df.columns else "date"
        df = df.drop_duplicates(subset=[time_col, "symbol"], keep="last")

        # 2. 修正 OHLC 关系
        if fix_ohlc and all(col in df.columns for col in ["open", "high", "low", "close"]):
            # 确保 high >= max(open, close) 且 low <= min(open, close)
            df["high"] = df[["high", "open", "close"]].max(axis=1)
            df["low"] = df[["low", "open", "close"]].min(axis=1)

        # 3. 移除零成交量记录
        if remove_zero_volume and "volume" in df.columns:
            positive_volume = cast(BoolSeries, df["volume"] > 0)
            df = df.loc[positive_volume]

        # 4. 填充缺失数据
        if fill_missing:
            df = self.fill_missing_klines(df, time_col)

        # 5. 标准化时间戳
        df[time_col] = pd.to_datetime(df[time_col])

        # 6. 排序
        df = df.sort_values(["symbol", time_col])

        cleaned_count = len(df)
        removed_count = original_count - cleaned_count

        self.logger.info(
            f"K线数据清洗完成: 原始 {original_count} 条, "
            f"清洗后 {cleaned_count} 条, 移除 {removed_count} 条"
        )

        return df

    def fill_missing_klines(
        self,
        df: pd.DataFrame,
        time_col: str = "time",
        method: FillMethod = "ffill",
    ) -> pd.DataFrame:
        """补齐缺失的 K 线数据
        
        Args:
            df: K 线数据
            time_col: 时间列名
            method: 填充方式 ('ffill', 'bfill', 'interpolate')
        
        Returns:
            补完后的 DataFrame
        """
        if df.empty:
            return df

        working_df = df.copy()
        working_df[time_col] = pd.to_datetime(working_df[time_col])

        filled_dfs: list[pd.DataFrame] = []

        for symbol, group in working_df.groupby("symbol"):
            time_series = cast(TimestampSeries, group[time_col])
            frequency = self._infer_frequency(time_series)
            time_range = pd.date_range(
                start=cast(DatetimeScalar, time_series.min()),
                end=cast(DatetimeScalar, time_series.max()),
                freq=frequency,
            )

            group_aligned = group.set_index(time_col).reindex(time_range)
            group_aligned = group_aligned.copy()
            group_aligned["symbol"] = symbol

            if method == "ffill":
                filled = group_aligned.ffill()
            elif method == "bfill":
                filled = group_aligned.bfill()
            elif method == "interpolate":
                filled = group_aligned.copy()
                numeric_cols = list(filled.select_dtypes(include=[np.number]).columns)
                if numeric_cols:
                    interpolated = filled[numeric_cols].interpolate()
                    filled.loc[:, numeric_cols] = interpolated
                filled = filled.ffill()
            else:
                filled = group_aligned

            filled_reset = filled.reset_index().rename(columns={"index": time_col})
            filled_dfs.append(filled_reset)

        if not filled_dfs:
            return working_df.reset_index(drop=True)

        return pd.concat(filled_dfs, ignore_index=True)

    def _infer_frequency(self, time_series: TimestampSeries) -> str:
        """推断时间序列的频率
        
        Args:
            time_series: 时间序列
            
        Returns:
            频率字符串
        """
        # 计算时间差
        diffs = cast(TimedeltaSeries, time_series.diff().dropna())
        if diffs.empty:
            return "1D"

        modes = cast(TimedeltaSeries, diffs.mode(dropna=True))
        if modes.empty:
            return "1D"

        # 获取最常见的时间差
        mode_raw = cast(object, modes.iloc[0])
        if isinstance(mode_raw, pd.Timedelta):
            mode_diff = mode_raw
        elif isinstance(mode_raw, np.timedelta64):
            mode_diff = pd.Timedelta(mode_raw)
        elif isinstance(mode_raw, timedelta):
            mode_diff = pd.Timedelta(mode_raw)
        else:
            normalized = str(mode_raw) if isinstance(mode_raw, (int, float)) else mode_raw
            mode_diff = cast(
                pd.Timedelta,
                pd.to_timedelta(cast(TimedeltaScalar, normalized)),
            )

        # 推断频率
        if mode_diff <= pd.Timedelta(minutes=1):
            return "1min"
        elif mode_diff <= pd.Timedelta(minutes=5):
            return "5min"
        elif mode_diff <= pd.Timedelta(minutes=30):
            return "30min"
        elif mode_diff <= pd.Timedelta(hours=1):
            return "1H"
        else:
            return "1D"

    def remove_outliers(
        self,
        df: pd.DataFrame,
        columns: Sequence[str],
        method: OutlierMethod = "iqr",
        threshold: float = 3.0,
    ) -> pd.DataFrame:
        """移除异常值
        
        Args:
            df: 数据框
            columns: 要检查的列
            method: 检测方法 ('iqr', 'zscore', 'mad')
            threshold: 阈值
            
        Returns:
            移除异常值后的 DataFrame
        """
        df = df.copy()
        mask = cast(BoolSeries, pd.Series(True, index=df.index, dtype=bool))

        for col in columns:
            if col not in df.columns:
                continue

            column = df[col]
            if not pd.api.types.is_numeric_dtype(column):
                continue
            numeric_column = cast(NumericSeries, column.astype(float, copy=False))

            if method == 'iqr':
                # IQR 方法
                q1 = float(numeric_column.quantile(0.25))
                q3 = float(numeric_column.quantile(0.75))
                iqr = q3 - q1
                lower_bound = q1 - threshold * iqr
                upper_bound = q3 + threshold * iqr
                mask = cast(
                    BoolSeries,
                    mask & (numeric_column >= lower_bound) & (numeric_column <= upper_bound),
                )

            elif method == 'zscore':
                # Z-score 方法
                std = float(numeric_column.std())
                if std == 0 or pd.isna(std):
                    continue
                mean = float(numeric_column.mean())
                z_scores: NumericSeries = ((numeric_column - mean) / std).abs()
                mask = cast(BoolSeries, mask & (z_scores <= threshold))

            elif method == 'mad':
                # MAD (Median Absolute Deviation) 方法
                median = float(numeric_column.median())
                mad = float(np.median(np.abs(numeric_column - median)))
                if mad == 0:
                    continue
                modified_z_scores: NumericSeries = (0.6745 * (numeric_column - median) / mad).abs()
                mask = cast(BoolSeries, mask & (modified_z_scores <= threshold))

        outliers_count = int((~mask).sum())
        if outliers_count > 0:
            self.logger.info(f"移除 {outliers_count} 个异常值")

        filtered_df = cast(pd.DataFrame, df.loc[mask].copy())
        return filtered_df

    def standardize_symbols(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化股票代码格式
        
        Args:
            df: 包含 symbol 列的数据框
            
        Returns:
            标准化后的 DataFrame
        """
        if "symbol" not in df.columns:
            return df

        df = df.copy()
        symbols = cast(StringSeries, df["symbol"].astype("string"))

        def normalize(symbol: str) -> str:
            normalized = symbol.strip().upper()
            if not normalized:
                return normalized

            if "." not in normalized:
                if normalized.startswith("6"):
                    return f"{normalized}.SH"
                if normalized.startswith(("0", "3")):
                    return f"{normalized}.SZ"
                return normalized

            normalized = normalized.replace(".SS", ".SH")
            normalized = normalized.replace(".XSHG", ".SH")
            normalized = normalized.replace(".XSHE", ".SZ")
            return normalized

        filled = cast(StringSeries, symbols.fillna(""))
        standardized = cast(StringSeries, filled.map(normalize))
        valid_mask = cast(BoolSeries, filled != "")
        df["symbol"] = standardized.where(valid_mask, pd.NA)

        return df

    def validate_data(
        self,
        df: pd.DataFrame,
        required_columns: Sequence[str],
        check_types: bool = True,
    ) -> tuple[bool, list[str]]:
        """验证数据完整性
        
        Args:
            df: 要验证的数据框
            required_columns: 必需的列
            check_types: 是否检查数据类型
            
        Returns:
            (是否有效, 错误信息列表)
        """
        errors: list[str] = []

        # 检查是否为空
        if df.empty:
            return False, ["数据框为空"]

        # 检查必需列
        missing_cols = set(required_columns) - set(df.columns)
        if missing_cols:
            errors.append(f"缺少列: {missing_cols}")

        # 检查数据类型
        if check_types:
            # 检查时间列
            time_cols = ["time", "date", "datetime"]
            for col in time_cols:
                if col in df.columns:
                    try:
                        pd.to_datetime(df[col])
                    except (ValueError, TypeError) as e:
                        errors.append(f"列 {col} 无法转换为时间类型: {str(e)}")

            # 检查数值列
            numeric_cols = ["open", "high", "low", "close", "volume", "turnover"]
            for col in numeric_cols:
                if col in df.columns:
                    if not pd.api.types.is_numeric_dtype(df[col]):
                        errors.append(f"列 {col} 不是数值类型")

        # 检查空值
        available_required_columns = [col for col in required_columns if col in df.columns]
        if available_required_columns:
            null_counts = df[available_required_columns].isnull().sum()
            null_cols = null_counts[null_counts > 0]
            if not null_cols.empty:
                for col_key, count in null_cols.items():
                    errors.append(f"列 {str(col_key)} 有 {int(count)} 个空值")

        is_valid = len(errors) == 0
        return is_valid, errors
