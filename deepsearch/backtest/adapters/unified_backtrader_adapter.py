# encoding:utf-8
"""
Unified Backtrader Adapter
统一的Backtrader数据适配器 - 整合QMT/MiniQMT/AkShare数据源
Author: DeepSearch Team
Version: 1.0.0
"""

import asyncio
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

from deepsearch.infrastructure.providers.managers.enhanced_manager import get_data_manager
from ..data.data_bridge import DataBridge


class UnifiedBacktraderAdapter:
    """
    统一的Backtrader数据适配器
    
    特性：
    1. 自动选择最佳数据源（QMT/MiniQMT/AkShare）
    2. 智能格式转换
    3. 数据验证和清洗
    4. 缓存优化
    """

    def __init__(self, source: str = 'auto'):
        """
        初始化适配器
        
        Args:
            source: 数据源选择 ('auto', 'qmt', 'akshare')
        """
        if not HAS_BACKTRADER:
            raise ImportError("请先安装 backtrader: pip install backtrader")

        self.source = source
        self.data_manager = None
        self.data_bridge = DataBridge()
        self._cache = {}
        self._initialized = False

    async def initialize(self):
        """异步初始化"""
        if not self._initialized:
            logger.info("初始化Unified Backtrader Adapter...")
            self.data_manager = await get_data_manager()
            self._initialized = True
            logger.info("✅ 适配器初始化完成")

    def initialize_sync(self):
        """同步初始化（用于Backtrader）"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.initialize())
        loop.close()

    async def get_data(
            self,
            symbol: str,
            start_date: Union[str, datetime],
            end_date: Union[str, datetime],
            timeframe: str = '1d',
            adjust: str = 'qfq'
    ) -> pd.DataFrame:
        """
        获取历史数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            timeframe: 时间周期 (1m, 5m, 15m, 30m, 60m, 1d, 1w)
            adjust: 复权方式 (qfq: 前复权, hfq: 后复权, none: 不复权)
            
        Returns:
            标准化的DataFrame
        """
        if not self._initialized:
            await self.initialize()

        # 转换日期格式
        if isinstance(start_date, datetime):
            start_str = start_date.strftime('%Y%m%d')
        else:
            start_str = start_date.replace('-', '')

        if isinstance(end_date, datetime):
            end_str = end_date.strftime('%Y%m%d')
        else:
            end_str = end_date.replace('-', '')

        # 生成缓存键
        cache_key = f"{symbol}_{start_str}_{end_str}_{timeframe}_{adjust}"

        # 检查缓存
        if cache_key in self._cache:
            logger.debug(f"使用缓存数据: {symbol}")
            return self._cache[cache_key]

        logger.info(f"获取数据: {symbol} [{start_str} - {end_str}] {timeframe}")

        # 根据时间周期选择不同的获取方法
        if timeframe == '1d':
            # 获取日线数据
            df = await self.data_manager.get_stock_daily(
                symbol=symbol,
                start_date=start_str,
                end_date=end_str,
                source=self.source,
                adjust=adjust,
                use_cache=True
            )
        elif timeframe in ['1m', '5m', '15m', '30m', '60m']:
            # 获取分钟数据
            df = await self._get_minute_data(
                symbol, start_str, end_str, timeframe, adjust
            )
        elif timeframe == '1w':
            # 获取周线数据
            df = await self._get_weekly_data(
                symbol, start_str, end_str, adjust
            )
        else:
            raise ValueError(f"不支持的时间周期: {timeframe}")

        # 使用DataBridge进行格式转换和验证
        df = self.data_bridge.convert_to_backtrader(df, symbol)

        # 缓存数据
        if not df.empty:
            self._cache[cache_key] = df
            logger.info(f"✅ 获取到 {len(df)} 条数据")
        else:
            logger.warning(f"⚠️ 未获取到数据: {symbol}")

        return df

    async def _get_minute_data(
            self,
            symbol: str,
            start_date: str,
            end_date: str,
            timeframe: str,
            adjust: str
    ) -> pd.DataFrame:
        """获取分钟数据"""
        # 转换时间周期格式
        period_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '60m': '60m'
        }
        period = period_map.get(timeframe, '5m')

        # 尝试通过QMT获取
        if self.source in ['auto', 'qmt']:
            try:
                if hasattr(self.data_manager, '_qmt_provider') and self.data_manager._qmt_provider:
                    df = await self.data_manager._qmt_provider.get_kline(
                        symbol=symbol,
                        period=period,
                        start_date=start_date,
                        end_date=end_date,
                        adjust=adjust
                    )
                    if not df.empty:
                        return df
            except Exception as e:
                logger.warning(f"QMT获取分钟数据失败: {e}")

        # 降级到日线数据
        logger.warning(f"分钟数据不可用，降级到日线数据")
        return await self.data_manager.get_stock_daily(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            source=self.source,
            adjust=adjust
        )

    async def _get_weekly_data(
            self,
            symbol: str,
            start_date: str,
            end_date: str,
            adjust: str
    ) -> pd.DataFrame:
        """获取周线数据"""
        # 获取日线数据并转换为周线
        df = await self.data_manager.get_stock_daily(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            source=self.source,
            adjust=adjust
        )

        if not df.empty:
            # 转换为周线
            df = self._resample_to_weekly(df)

        return df

    def _resample_to_weekly(self, df: pd.DataFrame) -> pd.DataFrame:
        """将日线数据转换为周线"""
        if df.empty:
            return df

        # 确保索引是datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            if 'date' in df.columns:
                df.set_index('date', inplace=True)

        # 重采样规则
        agg_rules = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }

        # 只聚合存在的列
        rules = {k: v for k, v in agg_rules.items() if k in df.columns}

        # 重采样为周线
        weekly = df.resample('W').agg(rules)

        return weekly

    def create_backtrader_feed(
            self,
            dataframe: pd.DataFrame,
            name: Optional[str] = None,
            **kwargs
    ) -> bt.feeds.PandasData:
        """
        创建Backtrader数据源
        
        Args:
            dataframe: 数据DataFrame
            name: 数据源名称
            **kwargs: 其他参数
            
        Returns:
            Backtrader数据源对象
        """
        # 使用DataBridge创建数据源
        feed = self.data_bridge.create_backtrader_feed(dataframe, **kwargs)

        # 注意：不能直接用 if feed 判断 Backtrader 对象
        if feed is not None and name:
            feed._name = name

        return feed

    def get_data_sync(
            self,
            symbol: str,
            start_date: Union[str, datetime],
            end_date: Union[str, datetime],
            timeframe: str = '1d',
            adjust: str = 'qfq'
    ) -> pd.DataFrame:
        """
        同步获取数据（用于Backtrader回调）
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            timeframe: 时间周期
            adjust: 复权方式
            
        Returns:
            标准化的DataFrame
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            self.get_data(symbol, start_date, end_date, timeframe, adjust)
        )
        loop.close()
        return result

    async def get_multi_data(
            self,
            symbols: List[str],
            start_date: Union[str, datetime],
            end_date: Union[str, datetime],
            timeframe: str = '1d',
            adjust: str = 'qfq'
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取多只股票数据
        
        Args:
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            timeframe: 时间周期
            adjust: 复权方式
            
        Returns:
            {symbol: DataFrame}
        """
        if not self._initialized:
            await self.initialize()

        logger.info(f"批量获取 {len(symbols)} 只股票数据")

        # 并发获取数据
        tasks = []
        for symbol in symbols:
            task = self.get_data(symbol, start_date, end_date, timeframe, adjust)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 整理结果
        data_dict = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.error(f"获取 {symbol} 失败: {result}")
                data_dict[symbol] = pd.DataFrame()
            else:
                data_dict[symbol] = result

        success_count = sum(1 for df in data_dict.values() if not df.empty)
        logger.info(f"✅ 成功获取 {success_count}/{len(symbols)} 只股票数据")

        return data_dict

    def validate_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        验证数据质量
        
        Args:
            df: 数据DataFrame
            
        Returns:
            验证结果
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'stats': {}
        }

        if df.empty:
            validation_result['is_valid'] = False
            validation_result['errors'].append("数据为空")
            return validation_result

        # 检查必要字段
        required_fields = ['open', 'high', 'low', 'close']
        missing_fields = [f for f in required_fields if f not in df.columns]
        if missing_fields:
            validation_result['is_valid'] = False
            validation_result['errors'].append(f"缺少必要字段: {missing_fields}")

        # 检查OHLC关系
        if all(f in df.columns for f in ['open', 'high', 'low', 'close']):
            # High应该是最高价
            invalid_high = df['high'] < df[['open', 'close']].max(axis=1)
            if invalid_high.any():
                validation_result['warnings'].append(
                    f"发现 {invalid_high.sum()} 条high价格异常"
                )

            # Low应该是最低价
            invalid_low = df['low'] > df[['open', 'close']].min(axis=1)
            if invalid_low.any():
                validation_result['warnings'].append(
                    f"发现 {invalid_low.sum()} 条low价格异常"
                )

        # 统计信息
        validation_result['stats'] = {
            'rows': len(df),
            'columns': list(df.columns),
            'date_range': f"{df.index[0]} to {df.index[-1]}" if len(df) > 0 else "N/A",
            'null_values': df.isnull().sum().to_dict()
        }

        return validation_result

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        if self.data_manager:
            self.data_manager.clear_cache()
        logger.info("缓存已清空")

    def get_diagnostics(self) -> Dict[str, Any]:
        """获取诊断信息"""
        return {
            'initialized': self._initialized,
            'source': self.source,
            'cache_size': len(self._cache),
            'cached_symbols': list(set(
                key.split('_')[0] for key in self._cache.keys()
            )),
            'bridge_diagnostics': self.data_bridge.get_diagnostics(),
            'manager_status': self.data_manager.get_status() if self.data_manager else None
        }


# 便捷函数
async def create_adapter(source: str = 'auto') -> UnifiedBacktraderAdapter:
    """
    创建并初始化适配器
    
    Args:
        source: 数据源选择
        
    Returns:
        初始化后的适配器
    """
    adapter = UnifiedBacktraderAdapter(source)
    await adapter.initialize()
    return adapter
