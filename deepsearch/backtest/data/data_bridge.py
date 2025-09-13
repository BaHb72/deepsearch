"""
数据桥接器 - 统一 DeepSearch 和 Backtrader 之间的数据格式

提供自动数据源检测、字段映射和数据验证功能
"""
from datetime import datetime
from typing import Optional, Dict, Any, Union, List

import pandas as pd
from loguru import logger

try:
    import backtrader as bt

    HAS_BACKTRADER = True
except ImportError:
    HAS_BACKTRADER = False
    bt = None


class DataBridge:
    """
    数据桥接器
    
    功能：
    1. 自动检测数据源类型
    2. 统一字段映射
    3. 数据验证和清洗
    4. 格式转换
    """

    # 统一的字段映射表
    FIELD_MAPPINGS = {
        # 时间字段
        '日期': 'date',
        '时间': 'date',
        'Date': 'date',
        'datetime': 'date',
        'time': 'date',
        'ts': 'date',
        'timestamp': 'date',

        # OHLC 字段
        '开盘': 'open',
        '开盘价': 'open',
        'Open': 'open',
        '最高': 'high',
        '最高价': 'high',
        'High': 'high',
        '最低': 'low',
        '最低价': 'low',
        'Low': 'low',
        '收盘': 'close',
        '收盘价': 'close',
        'Close': 'close',

        # 成交量字段
        '成交量': 'volume',
        'Volume': 'volume',
        'vol': 'volume',
        '成交额': 'amount',
        'Amount': 'amount',
        'turnover': 'amount',

        # 其他字段
        '涨跌幅': 'pct_change',
        '涨跌额': 'change',
        '换手率': 'turnover_rate',
        '振幅': 'amplitude'
    }

    def __init__(self):
        """初始化数据桥接器"""
        self.last_source_type = None
        self.validation_errors = []

    def detect_source_type(self, data: Union[pd.DataFrame, List[Dict], Dict]) -> str:
        """
        自动检测数据源类型
        
        Args:
            data: 输入数据
            
        Returns:
            数据源类型标识
        """
        # DataFrame 类型
        if isinstance(data, pd.DataFrame):
            columns = set(data.columns)

            # 检查 AkShare 特征
            if 'ts' in columns or ('日期' in columns and '收盘' in columns):
                return 'akshare'

            # 检查 QMT 特征
            if ('date' in columns or 'time' in columns) and '开盘' in columns:
                return 'qmt'

            # 检查标准格式
            if all(col in columns for col in ['open', 'high', 'low', 'close']):
                return 'standard'

        # List[Dict] 类型
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            first_row = data[0]
            keys = set(first_row.keys())

            if 'ts' in keys:
                return 'akshare'
            elif 'date' in keys or 'time' in keys:
                return 'qmt'

        # 单个 Dict 类型（API 响应）
        elif isinstance(data, dict):
            if 'data' in data:
                return self.detect_source_type(data['data'])

        return 'unknown'

    def convert_to_backtrader(
            self,
            data: Union[pd.DataFrame, List[Dict], Dict],
            symbol: Optional[str] = None
    ) -> pd.DataFrame:
        """
        将各种格式的数据转换为 Backtrader 兼容格式
        
        Args:
            data: 输入数据
            symbol: 股票代码（可选）
            
        Returns:
            Backtrader 兼容的 DataFrame
        """
        # 提取数据
        if isinstance(data, dict) and 'data' in data:
            actual_data = data['data']
        else:
            actual_data = data

        # 转换为 DataFrame
        if not isinstance(actual_data, pd.DataFrame):
            if isinstance(actual_data, list):
                df = pd.DataFrame(actual_data)
            else:
                logger.error(f"Unsupported data type: {type(actual_data)}")
                return pd.DataFrame()
        else:
            df = actual_data.copy()

        if df.empty:
            logger.warning("Empty DataFrame provided")
            return df

        # 检测数据源类型
        source_type = self.detect_source_type(df)
        self.last_source_type = source_type
        logger.debug(f"Detected source type: {source_type}")

        # 标准化字段名
        df = self.standardize_fields(df)

        # 处理时间字段
        df = self.process_datetime(df)

        # 确保数据类型正确
        df = self.ensure_data_types(df)

        # 验证数据
        if not self.validate_data(df):
            logger.warning(f"Data validation failed: {self.validation_errors}")

        # 清洗数据
        df = self.clean_data(df)

        return df

    def standardize_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        标准化字段名
        
        Args:
            df: 输入 DataFrame
            
        Returns:
            标准化后的 DataFrame
        """
        # 应用字段映射
        rename_dict = {}
        for col in df.columns:
            if col in self.FIELD_MAPPINGS:
                new_name = self.FIELD_MAPPINGS[col]
                if new_name not in df.columns:  # 避免重复
                    rename_dict[col] = new_name

        if rename_dict:
            df = df.rename(columns=rename_dict)
            # 直接跳过日志输出，避免所有格式化问题
            # logger.debug(f"Renamed columns: {rename_dict}")

        # 确保必要字段存在
        required_fields = ['open', 'high', 'low', 'close', 'volume']
        missing_fields = [f for f in required_fields if f not in df.columns]

        if missing_fields:
            logger.warning(f"Missing required fields: {missing_fields}")

            # 尝试补充缺失字段
            if 'volume' not in df.columns and 'amount' in df.columns:
                # 如果有成交额但没有成交量，使用成交额
                df['volume'] = df['amount']
            elif 'volume' not in df.columns:
                # 使用默认值
                df['volume'] = 1000000

        return df

    def process_datetime(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理日期时间字段
        
        Args:
            df: 输入 DataFrame
            
        Returns:
            处理后的 DataFrame
        """
        # 查找日期字段
        date_col = None
        for col in ['date', 'datetime', 'time', 'ts']:
            if col in df.columns:
                date_col = col
                break

        if date_col:
            try:
                # 转换为 datetime
                df[date_col] = pd.to_datetime(df[date_col])

                # 设置为索引
                if date_col != df.index.name:
                    df = df.set_index(date_col)

                # 排序
                df = df.sort_index()

                logger.debug(f"Set {date_col} as datetime index")

            except Exception as e:
                logger.error(f"Failed to process datetime: {e}")

        elif df.index.name is None:
            # 如果没有日期字段，创建一个
            logger.warning("No date field found, creating default date index")
            df.index = pd.date_range(end=datetime.now(), periods=len(df), freq='D')

        return df

    def ensure_data_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        确保数据类型正确
        
        Args:
            df: 输入 DataFrame
            
        Returns:
            处理后的 DataFrame
        """
        numeric_fields = ['open', 'high', 'low', 'close', 'volume', 'amount']

        for field in numeric_fields:
            if field in df.columns:
                try:
                    df[field] = pd.to_numeric(df[field], errors='coerce')
                except Exception as e:
                    logger.error(f"Failed to convert {field} to numeric: {e}")

        return df

    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        验证数据有效性
        
        Args:
            df: 输入 DataFrame
            
        Returns:
            是否有效
        """
        self.validation_errors = []

        # 检查是否为空
        if df.empty:
            self.validation_errors.append("DataFrame is empty")
            return False

        # 检查必要字段
        required_fields = ['open', 'high', 'low', 'close']
        for field in required_fields:
            if field not in df.columns:
                self.validation_errors.append(f"Missing required field: {field}")

        # 检查 OHLC 关系
        if all(f in df.columns for f in ['open', 'high', 'low', 'close']):
            # High 应该是最高价
            invalid_high = df['high'] < df[['open', 'close']].max(axis=1)
            if invalid_high.any():
                self.validation_errors.append(f"Invalid high prices: {invalid_high.sum()} rows")

            # Low 应该是最低价
            invalid_low = df['low'] > df[['open', 'close']].min(axis=1)
            if invalid_low.any():
                self.validation_errors.append(f"Invalid low prices: {invalid_low.sum()} rows")

        return len(self.validation_errors) == 0

    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗数据
        
        Args:
            df: 输入 DataFrame
            
        Returns:
            清洗后的 DataFrame
        """
        # 处理缺失值
        df = df.ffill()  # 前向填充
        df = df.bfill()  # 后向填充

        # 处理异常值
        if all(f in df.columns for f in ['open', 'high', 'low', 'close']):
            # 修正 high/low 关系
            df['high'] = df[['open', 'high', 'close']].max(axis=1)
            df['low'] = df[['open', 'low', 'close']].min(axis=1)

        # 处理负值
        numeric_fields = ['open', 'high', 'low', 'close', 'volume']
        for field in numeric_fields:
            if field in df.columns:
                df[field] = df[field].abs()

        # 删除全为 NaN 的行
        df = df.dropna(how='all')

        return df

    def create_backtrader_feed(
            self,
            df: pd.DataFrame,
            **kwargs
    ) -> Optional['bt.feeds.PandasData']:
        """
        创建 Backtrader 数据源对象
        
        Args:
            df: 标准化后的 DataFrame
            **kwargs: 额外参数
            
        Returns:
            Backtrader 数据源对象
        """
        if not HAS_BACKTRADER:
            logger.error("Backtrader not installed")
            return None

        if df.empty:
            logger.error("Cannot create feed from empty DataFrame")
            return None

        try:
            # 创建 Backtrader 数据源
            data = bt.feeds.PandasData(
                dataname=df,
                datetime=None,  # 使用索引作为日期
                open='open' if 'open' in df.columns else -1,
                high='high' if 'high' in df.columns else -1,
                low='low' if 'low' in df.columns else -1,
                close='close' if 'close' in df.columns else -1,
                volume='volume' if 'volume' in df.columns else -1,
                openinterest=-1,  # 不使用持仓量
                **kwargs
            )

            logger.info(f"Created Backtrader feed with {len(df)} bars")
            return data

        except Exception as e:
            logger.error(f"Failed to create Backtrader feed: {e}")
            return None

    def get_diagnostics(self) -> Dict[str, Any]:
        """
        获取诊断信息
        
        Returns:
            诊断信息字典
        """
        return {
            'last_source_type': self.last_source_type,
            'validation_errors': self.validation_errors,
            'field_mappings': self.FIELD_MAPPINGS
        }
