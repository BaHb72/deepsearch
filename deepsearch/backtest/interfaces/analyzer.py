"""
PerformanceAnalyzer - 性能分析器

提供回测结果的深度分析功能
"""
from typing import Dict, Any, List

import numpy as np
import pandas as pd


class PerformanceAnalyzer:
    """
    性能分析器
    
    提供各种回测性能指标的计算和分析
    """

    @staticmethod
    def calculate_sharpe_ratio(
            returns: pd.Series,
            risk_free_rate: float = 0.03,
            periods: int = 252
    ) -> float:
        """
        计算夏普比率
        
        Args:
            returns: 收益率序列
            risk_free_rate: 无风险利率（年化）
            periods: 年化周期数（日:252, 周:52, 月:12）
            
        Returns:
            夏普比率
        """
        if len(returns) == 0:
            return 0

        excess_returns = returns - risk_free_rate / periods

        if excess_returns.std() == 0:
            return 0

        return np.sqrt(periods) * excess_returns.mean() / excess_returns.std()

    @staticmethod
    def calculate_sortino_ratio(
            returns: pd.Series,
            risk_free_rate: float = 0.03,
            periods: int = 252
    ) -> float:
        """
        计算索提诺比率
        
        Args:
            returns: 收益率序列
            risk_free_rate: 无风险利率（年化）
            periods: 年化周期数
            
        Returns:
            索提诺比率
        """
        if len(returns) == 0:
            return 0

        excess_returns = returns - risk_free_rate / periods
        downside_returns = excess_returns[excess_returns < 0]

        if len(downside_returns) == 0:
            return float('inf')

        downside_std = np.sqrt(np.mean(downside_returns ** 2))

        if downside_std == 0:
            return 0

        return np.sqrt(periods) * excess_returns.mean() / downside_std

    @staticmethod
    def calculate_max_drawdown(equity_curve: pd.Series) -> Dict[str, Any]:
        """
        计算最大回撤
        
        Args:
            equity_curve: 权益曲线
            
        Returns:
            包含最大回撤信息的字典
        """
        if len(equity_curve) == 0:
            return {'max_drawdown': 0, 'max_drawdown_duration': 0}

        # 计算累计最大值
        cummax = equity_curve.expanding().max()

        # 计算回撤
        drawdown = (equity_curve - cummax) / cummax

        # 找到最大回撤
        max_drawdown = drawdown.min()

        # 计算最大回撤持续时间
        drawdown_start = drawdown[drawdown == max_drawdown].index[0]

        # 找到恢复点
        recovery_date = None
        peak_value = cummax[drawdown_start]

        for date in equity_curve[drawdown_start:].index:
            if equity_curve[date] >= peak_value:
                recovery_date = date
                break

        if recovery_date:
            duration = (recovery_date - drawdown_start).days
        else:
            duration = (equity_curve.index[-1] - drawdown_start).days

        return {
            'max_drawdown': abs(max_drawdown),
            'max_drawdown_duration': duration,
            'drawdown_start': drawdown_start,
            'recovery_date': recovery_date
        }

    @staticmethod
    def calculate_calmar_ratio(
            total_return: float,
            max_drawdown: float,
            years: float
    ) -> float:
        """
        计算卡尔玛比率
        
        Args:
            total_return: 总收益率
            max_drawdown: 最大回撤
            years: 投资年数
            
        Returns:
            卡尔玛比率
        """
        if max_drawdown == 0 or years == 0:
            return 0

        annualized_return = (1 + total_return) ** (1 / years) - 1
        return annualized_return / abs(max_drawdown)

    @staticmethod
    def calculate_win_rate(trades: List[Dict[str, Any]]) -> float:
        """
        计算胜率
        
        Args:
            trades: 交易记录列表
            
        Returns:
            胜率
        """
        if not trades:
            return 0

        winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        return winning_trades / len(trades)

    @staticmethod
    def calculate_profit_factor(trades: List[Dict[str, Any]]) -> float:
        """
        计算盈亏比
        
        Args:
            trades: 交易记录列表
            
        Returns:
            盈亏比
        """
        if not trades:
            return 0

        gross_profit = sum(t['pnl'] for t in trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t['pnl'] for t in trades if t.get('pnl', 0) < 0))

        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0

        return gross_profit / gross_loss

    @staticmethod
    def calculate_risk_metrics(
            returns: pd.Series,
            confidence_level: float = 0.95
    ) -> Dict[str, float]:
        """
        计算风险指标
        
        Args:
            returns: 收益率序列
            confidence_level: 置信水平
            
        Returns:
            风险指标字典
        """
        if len(returns) == 0:
            return {}

        metrics = {
            'volatility': returns.std() * np.sqrt(252),  # 年化波动率
            'skewness': returns.skew(),  # 偏度
            'kurtosis': returns.kurtosis(),  # 峰度
            'var': returns.quantile(1 - confidence_level),  # 风险价值
            'cvar': returns[returns <= returns.quantile(1 - confidence_level)].mean()  # 条件风险价值
        }

        return metrics

    @staticmethod
    def calculate_rolling_metrics(
            equity_curve: pd.Series,
            window: int = 30
    ) -> pd.DataFrame:
        """
        计算滚动指标
        
        Args:
            equity_curve: 权益曲线
            window: 滚动窗口大小
            
        Returns:
            滚动指标 DataFrame
        """
        if len(equity_curve) < window:
            return pd.DataFrame()

        returns = equity_curve.pct_change().dropna()

        rolling_metrics = pd.DataFrame(index=equity_curve.index[window:])

        # 滚动收益率
        rolling_metrics['rolling_return'] = returns.rolling(window).mean() * 252

        # 滚动波动率
        rolling_metrics['rolling_volatility'] = returns.rolling(window).std() * np.sqrt(252)

        # 滚动夏普比率
        rolling_metrics['rolling_sharpe'] = (
                rolling_metrics['rolling_return'] / rolling_metrics['rolling_volatility']
        )

        return rolling_metrics

    @staticmethod
    def generate_report(result: 'BacktestResult') -> str:
        """
        生成详细的分析报告
        
        Args:
            result: 回测结果对象
            
        Returns:
            分析报告字符串
        """
        report = f"""
================================================================================
                            回测分析报告
================================================================================

基本信息
--------------------------------------------------------------------------------
策略名称: {result.strategy_name}
交易标的: {result.symbol}
回测期间: {result.start_date.date()} 至 {result.end_date.date()}
交易天数: {(result.end_date - result.start_date).days}

收益分析
--------------------------------------------------------------------------------
初始资金: ¥{result.initial_cash:,.2f}
最终资金: ¥{result.final_cash:,.2f}
总收益额: ¥{result.final_cash - result.initial_cash:,.2f}
总收益率: {result.total_return:.2%}
年化收益: {PerformanceAnalyzer._calculate_annualized_return(result):.2%}

风险指标
--------------------------------------------------------------------------------
夏普比率: {result.sharpe_ratio:.3f}
索提诺比率: {result.sortino_ratio:.3f if result.sortino_ratio else 'N/A'}
卡尔玛比率: {result.calmar_ratio:.3f if result.calmar_ratio else 'N/A'}
最大回撤: {result.max_drawdown:.2%}

交易统计
--------------------------------------------------------------------------------
总交易次数: {result.total_trades}
盈利次数: {result.profit_trades}
亏损次数: {result.loss_trades}
胜率: {result.win_rate:.2%}
盈亏比: {result.profit_factor:.2f if result.profit_factor else 'N/A'}

单笔交易分析
--------------------------------------------------------------------------------
平均盈利: ¥{result.average_win:,.2f if result.average_win else 0}
平均亏损: ¥{result.average_loss:,.2f if result.average_loss else 0}
最大盈利: ¥{result.largest_win:,.2f if result.largest_win else 0}
最大亏损: ¥{result.largest_loss:,.2f if result.largest_loss else 0}

交易成本
--------------------------------------------------------------------------------
手续费率: {result.commission:.3%}
滑点设置: {result.slippage:.3%}
估算总成本: ¥{PerformanceAnalyzer._estimate_total_cost(result):,.2f}

年度收益分布
--------------------------------------------------------------------------------
"""

        if result.annual_returns:
            for year, ret in sorted(result.annual_returns.items()):
                report += f"  {year}年: {ret:.2%}\n"
        else:
            report += "  无年度数据\n"

        report += """
================================================================================
                              报告结束
================================================================================
"""

        return report

    @staticmethod
    def _calculate_annualized_return(result: 'BacktestResult') -> float:
        """计算年化收益率"""
        days = (result.end_date - result.start_date).days
        if days <= 0:
            return 0
        years = days / 365
        return ((1 + result.total_return) ** (1 / years)) - 1 if years > 0 else 0

    @staticmethod
    def _estimate_total_cost(result: 'BacktestResult') -> float:
        """估算总交易成本"""
        if not result.total_trades:
            return 0

        # 假设平均每笔交易金额为总资金的10%
        avg_trade_value = result.initial_cash * 0.1

        # 双边交易成本（买入+卖出）
        commission_cost = avg_trade_value * result.commission * 2 * result.total_trades

        # 滑点成本
        slippage_cost = avg_trade_value * result.slippage * 2 * result.total_trades

        return commission_cost + slippage_cost
