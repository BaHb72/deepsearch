"""数据清洗模块

提供行情数据清洗和标准化功能
"""
from typing import List, Tuple

import numpy as np
import pandas as pd

from deepsearch.observability.logger import logger


class DataCleaner:
    """数据清洗器
    
    提供各种数据清洗和预处理功能
    """

    def __init__(self):
        self.logger = logger.bind(module="data_cleaner")

    def clean_tick_data(
            self,
            df: pd.DataFrame,
            price_change_limit: float = 0.2,
            remove_zero_volume: bool = True,
            remove_auction: bool = True
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
        df = df.drop_duplicates(subset=['time', 'symbol'], keep='last')

        # 2. 移除价格异常值
        if 'last_price' in df.columns:
            # 计算价格变动率
            df['price_change'] = df.groupby('symbol')['last_price'].pct_change()

            # 移除异常变动
            mask = df['price_change'].abs() <= price_change_limit
            df = df[mask | df['price_change'].isna()]

            # 删除临时列
            df = df.drop(columns=['price_change'])

        # 3. 移除零成交量记录
        if remove_zero_volume and 'volume' in df.columns:
            df = df[df['volume'] > 0]

        # 4. 移除集合竞价时段数据
        if remove_auction and 'time' in df.columns:
            # 转换时间列
            df['hour'] = pd.to_datetime(df['time']).dt.hour
            df['minute'] = pd.to_datetime(df['time']).dt.minute

            # 移除 9:15-9:25 和 14:57-15:00 的数据
            morning_auction = (df['hour'] == 9) & (df['minute'] >= 15) & (df['minute'] < 25)
            afternoon_auction = (df['hour'] == 14) & (df['minute'] >= 57)

            df = df[~(morning_auction | afternoon_auction)]
            df = df.drop(columns=['hour', 'minute'])

        # 5. 标准化时间戳
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])

        # 6. 排序
        df = df.sort_values(['symbol', 'time'])

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
            fill_missing: bool = True
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
        time_col = 'time' if 'time' in df.columns else 'date'
        df = df.drop_duplicates(subset=[time_col, 'symbol'], keep='last')

        # 2. 修正 OHLC 关系
        if fix_ohlc and all(col in df.columns for col in ['open', 'high', 'low', 'close']):
            # 确保 high >= max(open, close) 且 low <= min(open, close)
            df['high'] = df[['high', 'open', 'close']].max(axis=1)
            df['low'] = df[['low', 'open', 'close']].min(axis=1)

        # 3. 移除零成交量记录
        if remove_zero_volume and 'volume' in df.columns:
            df = df[df['volume'] > 0]

        # 4. 填充缺失数据
        if fill_missing:
            df = self.fill_missing_klines(df, time_col)

        # 5. 标准化时间戳
        df[time_col] = pd.to_datetime(df[time_col])

        # 6. 排序
        df = df.sort_values(['symbol', time_col])

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
            time_col: str = 'time',
            method: str = 'ffill'
    ) -> pd.DataFrame:
        """填充缺失的 K 线数据
        
        Args:
            df: K 线数据
            time_col: 时间列名
            method: 填充方法 ('ffill', 'bfill', 'interpolate')
            
        Returns:
            填充后的 DataFrame
        """
        if df.empty:
            return df

        filled_dfs = []

        # 按股票分组处理
        for symbol, group in df.groupby('symbol'):
            # 创建完整的时间索引
            time_range = pd.date_range(
                start=group[time_col].min(),
                end=group[time_col].max(),
                freq=self._infer_frequency(group[time_col])
            )

            # 重新索引
            group = group.set_index(time_col)
            group = group.reindex(time_range)

            # 填充缺失值
            if method == 'ffill':
                group = group.fillna(method='ffill')
            elif method == 'bfill':
                group = group.fillna(method='bfill')
            elif method == 'interpolate':
                # 数值列使用插值
                numeric_cols = group.select_dtypes(include=[np.number]).columns
                group[numeric_cols] = group[numeric_cols].interpolate()
                # 非数值列使用前向填充
                group = group.fillna(method='ffill')

            # 恢复 symbol 列
            group['symbol'] = symbol
            group = group.reset_index()
            group = group.rename(columns={'index': time_col})

            filled_dfs.append(group)

        return pd.concat(filled_dfs, ignore_index=True)

    def _infer_frequency(self, time_series: pd.Series) -> str:
        """推断时间序列的频率
        
        Args:
            time_series: 时间序列
            
        Returns:
            频率字符串
        """
        # 计算时间差
        diffs = time_series.diff().dropna()
        if diffs.empty:
            return '1D'

        # 获取最常见的时间差
        mode_diff = diffs.mode()[0]

        # 推断频率
        if mode_diff <= pd.Timedelta(minutes=1):
            return '1min'
        elif mode_diff <= pd.Timedelta(minutes=5):
            return '5min'
        elif mode_diff <= pd.Timedelta(minutes=30):
            return '30min'
        elif mode_diff <= pd.Timedelta(hours=1):
            return '1H'
        else:
            return '1D'

    def remove_outliers(
            self,
            df: pd.DataFrame,
            columns: List[str],
            method: str = 'iqr',
            threshold: float = 3.0
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
        mask = pd.Series(True, index=df.index)

        for col in columns:
            if col not in df.columns:
                continue

            if method == 'iqr':
                # IQR 方法
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - threshold * IQR
                upper_bound = Q3 + threshold * IQR
                mask &= (df[col] >= lower_bound) & (df[col] <= upper_bound)

            elif method == 'zscore':
                # Z-score 方法
                z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
                mask &= z_scores <= threshold

            elif method == 'mad':
                # MAD (Median Absolute Deviation) 方法
                median = df[col].median()
                mad = np.median(np.abs(df[col] - median))
                modified_z_scores = 0.6745 * (df[col] - median) / mad
                mask &= np.abs(modified_z_scores) <= threshold

        outliers_count = (~mask).sum()
        if outliers_count > 0:
            self.logger.info(f"移除 {outliers_count} 个异常值")

        return df[mask]

    def standardize_symbols(self, df: pd.DataFrame) -> pd.DataFrame:
        """标准化股票代码格式
        
        Args:
            df: 包含 symbol 列的数据框
            
        Returns:
            标准化后的 DataFrame
        """
        if 'symbol' not in df.columns:
            return df

        df = df.copy()

        # 移除空格
        df['symbol'] = df['symbol'].str.strip()

        # 转换为大写
        df['symbol'] = df['symbol'].str.upper()

        # 标准化后缀
        def standardize_suffix(symbol):
            if not isinstance(symbol, str):
                return symbol

            # 如果没有后缀，根据代码判断
            if '.' not in symbol:
                if symbol.startswith('6'):
                    return f"{symbol}.SH"
                elif symbol.startswith(('0', '3')):
                    return f"{symbol}.SZ"
                else:
                    return symbol

            # 标准化已有后缀
            symbol = symbol.replace('.SS', '.SH')
            symbol = symbol.replace('.XSHG', '.SH')
            symbol = symbol.replace('.XSHE', '.SZ')

            return symbol

        df['symbol'] = df['symbol'].apply(standardize_suffix)

        return df

    def validate_data(
            self,
            df: pd.DataFrame,
            required_columns: List[str],
            check_types: bool = True
    ) -> Tuple[bool, List[str]]:
        """验证数据完整性
        
        Args:
            df: 要验证的数据框
            required_columns: 必需的列
            check_types: 是否检查数据类型
            
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []

        # 检查是否为空
        if df.empty:
            errors.append("数据框为空")
            return False, errors

        # 检查必需列
        missing_cols = set(required_columns) - set(df.columns)
        if missing_cols:
            errors.append(f"缺少列: {missing_cols}")

        # 检查数据类型
        if check_types:
            # 检查时间列
            time_cols = ['time', 'date', 'datetime']
            for col in time_cols:
                if col in df.columns:
                    try:
                        pd.to_datetime(df[col])
                    except (ValueError, TypeError) as e:
                        errors.append(f"列 {col} 无法转换为时间类型: {str(e)}")

            # 检查数值列
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'turnover']
            for col in numeric_cols:
                if col in df.columns:
                    if not pd.api.types.is_numeric_dtype(df[col]):
                        errors.append(f"列 {col} 不是数值类型")

        # 检查空值
        null_counts = df[required_columns].isnull().sum()
        null_cols = null_counts[null_counts > 0]
        if not null_cols.empty:
            for col, count in null_cols.items():
                errors.append(f"列 {col} 有 {count} 个空值")

        is_valid = len(errors) == 0
        return is_valid, errors
