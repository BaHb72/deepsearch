"""
复权因子服务

处理股票的前复权、后复权和不复权数据转换
支持从多个数据源获取复权因子
"""
import asyncio
from typing import Optional

import pandas as pd
from loguru import logger


class AdjustFactorService:
    """复权因子服务"""

    def __init__(self):
        """初始化服务"""
        self.factor_cache = {}  # 缓存复权因子

    async def get_adjust_factors(
            self,
            symbol: str,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取复权因子数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            复权因子DataFrame，包含date和factor列
        """
        try:
            # 尝试从AkShare获取复权因子
            import akshare as ak

            # 新的AkShare API: 通过比较复权和不复权数据计算复权因子
            # 获取不复权数据
            df_no_adjust = await asyncio.get_event_loop().run_in_executor(
                None,
                ak.stock_zh_a_hist,
                symbol,
                "daily",
                start_date.replace("-", "") if start_date else "19900101",
                end_date.replace("-", "") if end_date else "21000101",
                ""  # 不复权
            )
            
            # 获取前复权数据
            df_qfq = await asyncio.get_event_loop().run_in_executor(
                None,
                ak.stock_zh_a_hist,
                symbol,
                "daily",
                start_date.replace("-", "") if start_date else "19900101",
                end_date.replace("-", "") if end_date else "21000101",
                "qfq"  # 前复权
            )

            if df_no_adjust is not None and df_qfq is not None and not df_no_adjust.empty and not df_qfq.empty:
                # 计算复权因子
                factor_df = pd.DataFrame()
                factor_df['date'] = pd.to_datetime(df_no_adjust['日期'])
                
                # 计算复权因子: 前复权价格 / 不复权价格
                factor_df['factor'] = df_qfq['收盘'] / df_no_adjust['收盘']
                
                # 填充缺失值
                factor_df['factor'].fillna(1.0, inplace=True)
                
                # 筛选日期范围
                if start_date:
                    factor_df = factor_df[factor_df['date'] >= pd.to_datetime(start_date)]
                if end_date:
                    factor_df = factor_df[factor_df['date'] <= pd.to_datetime(end_date)]

                return factor_df

        except Exception as e:
            logger.warning(f"获取AkShare复权因子失败: {e}")

        # 备用方案：从QMT获取
        try:
            from deepsearch.data_providers.datafeed.qmt import QMTDataFeed
            qmt = QMTDataFeed()

            if hasattr(qmt, 'get_adjust_factor'):
                factors = qmt.get_adjust_factor(symbol, start_date, end_date)
                if factors:
                    return pd.DataFrame(factors)
        except Exception as e:
            logger.warning(f"获取QMT复权因子失败: {e}")

        # 返回空DataFrame
        return pd.DataFrame(columns=['date', 'factor'])

    def apply_adjust(
            self,
            bars_df: pd.DataFrame,
            adjust_type: str = "none",
            factors_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        应用复权处理
        
        Args:
            bars_df: K线数据DataFrame
            adjust_type: 复权类型 (none, qfq, hfq)
            factors_df: 复权因子DataFrame
            
        Returns:
            复权后的K线数据
        """
        if adjust_type == "none" or factors_df is None or factors_df.empty:
            return bars_df

        # 复制数据避免修改原始数据
        adjusted_df = bars_df.copy()

        # 合并复权因子
        if 'date' in adjusted_df.columns and 'date' in factors_df.columns:
            # 确保日期格式一致
            adjusted_df['date'] = pd.to_datetime(adjusted_df['date'])
            factors_df['date'] = pd.to_datetime(factors_df['date'])

            # 合并数据
            adjusted_df = adjusted_df.merge(
                factors_df[['date', 'factor']],
                on='date',
                how='left'
            )

            # 填充缺失的因子（使用前向填充）
            adjusted_df['factor'].fillna(method='ffill', inplace=True)
            adjusted_df['factor'].fillna(1.0, inplace=True)  # 默认因子为1

            if adjust_type == "qfq":  # 前复权
                # 前复权：将历史价格调整到当前价格水平
                # 使用最新的因子作为基准
                latest_factor = adjusted_df['factor'].iloc[-1] if len(adjusted_df) > 0 else 1.0

                # 计算相对因子
                adjusted_df['rel_factor'] = adjusted_df['factor'] / latest_factor

                # 调整价格
                for col in ['open', 'high', 'low', 'close']:
                    if col in adjusted_df.columns:
                        adjusted_df[col] = adjusted_df[col] * adjusted_df['rel_factor']

            elif adjust_type == "hfq":  # 后复权
                # 后复权：保持历史价格不变，调整后续价格
                # 使用最早的因子作为基准
                earliest_factor = adjusted_df['factor'].iloc[0] if len(adjusted_df) > 0 else 1.0

                # 计算相对因子
                adjusted_df['rel_factor'] = adjusted_df['factor'] / earliest_factor

                # 调整价格
                for col in ['open', 'high', 'low', 'close']:
                    if col in adjusted_df.columns:
                        adjusted_df[col] = adjusted_df[col] * adjusted_df['rel_factor']

            # 删除临时列
            adjusted_df.drop(['factor', 'rel_factor'], axis=1, errors='ignore', inplace=True)

        return adjusted_df

    async def get_adjusted_kline(
            self,
            symbol: str,
            bars_df: pd.DataFrame,
            adjust_type: str = "none"
    ) -> pd.DataFrame:
        """
        获取复权后的K线数据
        
        Args:
            symbol: 股票代码
            bars_df: 原始K线数据
            adjust_type: 复权类型
            
        Returns:
            复权后的K线数据
        """
        if adjust_type == "none":
            return bars_df

        # 获取复权因子
        start_date = bars_df['date'].min() if 'date' in bars_df.columns else None
        end_date = bars_df['date'].max() if 'date' in bars_df.columns else None

        factors_df = await self.get_adjust_factors(symbol, start_date, end_date)

        # 应用复权
        return self.apply_adjust(bars_df, adjust_type, factors_df)


# 全局服务实例
_adjust_service: Optional[AdjustFactorService] = None


def get_adjust_service() -> AdjustFactorService:
    """获取全局复权服务实例"""
    global _adjust_service
    if _adjust_service is None:
        _adjust_service = AdjustFactorService()
    return _adjust_service
