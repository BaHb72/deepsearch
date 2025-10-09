"""
PerformanceAnalyzer - 性能分析器

提供回测结果的深度分析功能
"""

from typing import TYPE_CHECKING, Any, Dict, List

import numpy as np
import pandas as pd

from deepsearch.data.types import NumericSeries

if TYPE_CHECKING:
    from deepsearch.backtest.utils.results import BacktestResult


class PerformanceAnalyzer:
    """
    性能分析器

    提供各种回测性能指标的计算和分析
    """

    @staticmethod
    def calculate_sharpe_ratio(
        returns: NumericSeries, risk_free_rate: float = 0.03, periods: int = 252
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
        series = returns.dropna()

        if len(series) == 0:
            return 0.0

        values = np.asarray(series, dtype=float)
        excess_returns = values - (risk_free_rate / periods)
        std_value = float(np.std(excess_returns, ddof=1))

        if std_value == 0:
            return 0.0

        mean_value = float(np.mean(excess_returns))
        return float(np.sqrt(periods) * mean_value / std_value)

    @staticmethod
    def calculate_sortino_ratio(
        returns: NumericSeries, risk_free_rate: float = 0.03, periods: int = 252
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
        series = returns.dropna()

        if len(series) == 0:
            return 0.0

        values = np.asarray(series, dtype=float)
        excess_returns = values - (risk_free_rate / periods)
        downside_returns = excess_returns[excess_returns < 0]

        if downside_returns.size == 0:
            return float("inf")

        downside_std = float(np.sqrt(np.mean(downside_returns**2)))

        if downside_std == 0:
            return 0.0

        mean_value = float(np.mean(excess_returns))
        return float(np.sqrt(periods) * mean_value / downside_std)

    @staticmethod
    def calculate_max_drawdown(equity_curve: NumericSeries) -> Dict[str, Any]:
        """
        计算最大回撤

        Args:
            equity_curve: 权益曲线

        Returns:
            包含最大回撤信息的字典
        """
        series = equity_curve.dropna()

        if len(series) == 0:
            return {"max_drawdown": 0.0, "max_drawdown_duration": 0}

        values = np.asarray(series, dtype=float)
        cummax = np.maximum.accumulate(values)
        drawdowns = np.divide(
            values - cummax,
            cummax,
            out=np.zeros_like(values),
            where=cummax != 0,
        )

        min_index = int(np.argmin(drawdowns))
        max_drawdown = float(drawdowns[min_index])
        index = series.index
        drawdown_start = index[min_index]
        peak_value = cummax[min_index]

        recovery_index: int | None = None
        for offset in range(min_index, len(values)):
            if values[offset] >= peak_value:
                recovery_index = offset
                break

        if recovery_index is not None:
            recovery_date = index[recovery_index]
            duration = int((recovery_date - drawdown_start).days)
        else:
            recovery_date = None
            duration = int((index[-1] - drawdown_start).days)

        return {
            "max_drawdown": abs(max_drawdown),
            "max_drawdown_duration": duration,
            "drawdown_start": drawdown_start,
            "recovery_date": recovery_date,
        }

    @staticmethod
    def calculate_calmar_ratio(total_return: float, max_drawdown: float, years: float) -> float:
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
            return 0.0

        annualized_return = (1 + total_return) ** (1 / years) - 1
        return float(annualized_return / abs(max_drawdown))

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
            return 0.0

        winning_trades = sum(1 for t in trades if t.get("pnl", 0) > 0)
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
            return 0.0

        gross_profit = sum(t["pnl"] for t in trades if t.get("pnl", 0) > 0)
        gross_loss = abs(sum(t["pnl"] for t in trades if t.get("pnl", 0) < 0))

        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0

        return float(gross_profit / gross_loss)

    @staticmethod
    def calculate_risk_metrics(
        returns: NumericSeries, confidence_level: float = 0.95
    ) -> Dict[str, float]:
        """
        计算风险指标

        Args:
            returns: 收益率序列
            confidence_level: 置信水平

        Returns:
            风险指标字典
        """
        series = returns.dropna()

        if len(series) == 0:
            return {}

        values = np.asarray(series, dtype=float)
        mean_value = float(np.mean(values))
        centered = values - mean_value
        std_sample = float(np.std(values, ddof=1))
        volatility = std_sample * np.sqrt(252)

        if std_sample == 0:
            skewness = 0.0
            kurtosis = 0.0
        else:
            normalized = centered / std_sample
            skewness = float(np.mean(normalized**3))
            kurtosis = float(np.mean(normalized**4))

        var_threshold = float(np.quantile(values, 1 - confidence_level))
        tail_values = values[values <= var_threshold]
        cvar = float(tail_values.mean()) if tail_values.size > 0 else 0.0

        metrics = {
            "volatility": float(volatility),
            "skewness": skewness,
            "kurtosis": kurtosis,
            "var": var_threshold,
            "cvar": cvar,
        }

        return metrics

    @staticmethod
    def calculate_rolling_metrics(equity_curve: NumericSeries, window: int = 30) -> pd.DataFrame:
        """
        计算滚动指标

        Args:
            equity_curve: 权益曲线
            window: 滚动窗口大小

        Returns:
            滚动指标 DataFrame
        """
        series = equity_curve.dropna()

        if len(series) < window:
            return pd.DataFrame()

        values = np.asarray(series, dtype=float)
        returns_values = np.diff(values) / values[:-1]
        returns_index = series.index[1:]

        if len(returns_values) < window:
            return pd.DataFrame()

        returns_series = pd.Series(returns_values, index=returns_index)
        rolling_return = np.asarray(returns_series.rolling(window).mean(), dtype=float) * 252.0
        rolling_volatility = (
            np.asarray(returns_series.rolling(window).std(), dtype=float) * np.sqrt(252.0)
        )

        with np.errstate(divide="ignore", invalid="ignore"):
            rolling_sharpe = np.divide(
                rolling_return,
                rolling_volatility,
                out=np.zeros_like(rolling_return),
                where=rolling_volatility != 0,
            )

        rolling_metrics = pd.DataFrame(
            {
                "rolling_return": rolling_return,
                "rolling_volatility": rolling_volatility,
                "rolling_sharpe": rolling_sharpe,
            },
            index=returns_index,
        )

        return rolling_metrics.dropna()

    @staticmethod
    def generate_report(result: "BacktestResult") -> str:
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
    def _calculate_annualized_return(result: "BacktestResult") -> float:
        """计算年化收益率"""
        days = (result.end_date - result.start_date).days
        if days <= 0:
            return 0
        years = days / 365
        return ((1 + result.total_return) ** (1 / years)) - 1 if years > 0 else 0

    @staticmethod
    def _estimate_total_cost(result: "BacktestResult") -> float:
        """估算总交易成本"""
        if not result.total_trades:
            return 0

        # 假设平均每笔交易金额为总资金的10%
        avg_trade_value = result.initial_cash * 0.1

        # 双边交易成本（买入+卖出）
        commission_cost = float(
            avg_trade_value * result.commission * 2 * result.total_trades
        )

        # 滑点成本
        slippage_cost = float(
            avg_trade_value * result.slippage * 2 * result.total_trades
        )

        return float(commission_cost + slippage_cost)
