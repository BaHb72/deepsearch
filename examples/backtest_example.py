"""
Backtrader 集成示例

展示如何使用 DeepSearch 的回测功能
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from deepsearch.backtest import (
    BacktestEngine,
    BaseStrategy,
    PerformanceAnalyzer,
    SimpleMovingAverageStrategy,
)


async def run_simple_backtest():
    """Run simple moving average strategy backtest"""

    print("=" * 80)
    print("DeepSearch Backtrader Integration Example")
    print("=" * 80)

    # 创建回测引擎（不使用真实数据源，使用模拟数据）
    engine = BacktestEngine(data_provider=None, event_engine=None)

    # 配置回测参数
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)  # 回测一年

    print("\nBacktest Configuration:")
    print("  Strategy: SimpleMovingAverageStrategy")
    print("  Symbol: 000001.SZ (Mock Data)")
    print(f"  Period: {start_date.date()} to {end_date.date()}")
    print("  Initial Cash: 100,000")
    print("  Commission: 0.1%")

    await engine.configure(
        strategy_class=SimpleMovingAverageStrategy,
        symbol="000001.SZ",
        start_date=start_date,
        end_date=end_date,
        initial_cash=100000,
        commission=0.001,
        slippage=0.001,
        strategy_params={"short_period": 10, "long_period": 30},
    )

    # Run backtest
    print("\nRunning backtest...")
    result = await engine.run_async()

    # 显示结果摘要
    print("\n" + "=" * 80)
    print(result.get_summary())

    # 计算额外指标
    result.calculate_additional_metrics()

    # 使用性能分析器生成报告
    analyzer = PerformanceAnalyzer()
    report = analyzer.generate_report(result)

    print("\n" + "=" * 80)
    print("详细分析报告:")
    print(report)

    return result


async def run_comparative_backtest():
    """运行对比回测，比较不同参数的效果"""

    print("\n" + "=" * 80)
    print("参数优化对比测试")
    print("=" * 80)

    # 测试不同的参数组合
    param_sets = [
        {"short_period": 5, "long_period": 20},
        {"short_period": 10, "long_period": 30},
        {"short_period": 20, "long_period": 60},
    ]

    results = []

    for params in param_sets:
        print(f"\n测试参数: 短期={params['short_period']}, 长期={params['long_period']}")

        # 创建新的引擎实例
        engine = BacktestEngine(data_provider=None, event_engine=None)

        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)

        await engine.configure(
            strategy_class=SimpleMovingAverageStrategy,
            symbol="000001.SZ",
            start_date=start_date,
            end_date=end_date,
            initial_cash=100000,
            commission=0.001,
            slippage=0.001,
            strategy_params=params,
        )

        result = await engine.run_async()
        results.append({"params": params, "result": result})

        print(f"  总收益率: {result.total_return:.2%}")
        print(f"  夏普比率: {result.sharpe_ratio:.2f}")
        print(f"  最大回撤: {result.max_drawdown:.2%}")
        print(f"  胜率: {result.win_rate:.2%}")

    # 找出最佳参数
    best = max(results, key=lambda x: x["result"].sharpe_ratio)

    print("\n" + "=" * 80)
    print("最佳参数组合:")
    print(f"  参数: {best['params']}")
    print(f"  夏普比率: {best['result'].sharpe_ratio:.2f}")
    print(f"  总收益率: {best['result'].total_return:.2%}")

    return results


class CustomMomentumStrategy(BaseStrategy):
    """自定义动量策略示例"""

    def __init__(self, params=None):
        super().__init__(params)
        self.lookback = self.params.get("lookback", 20)
        self.threshold = self.params.get("threshold", 0.05)
        self.prices = []
        self.in_position = False

    def on_init(self):
        """初始化策略"""
        self.log(f"初始化动量策略: lookback={self.lookback}, threshold={self.threshold}")

    def on_start(self):
        """策略启动"""
        self.log("动量策略启动")

    def on_bar(self, bar):
        """处理K线数据"""
        self.prices.append(bar["close"])

        # 需要足够的历史数据
        if len(self.prices) < self.lookback:
            return

        # 计算动量
        momentum = (self.prices[-1] - self.prices[-self.lookback]) / self.prices[-self.lookback]

        # 生成交易信号
        if momentum > self.threshold and not self.in_position:
            self.log(f"动量信号 {momentum:.2%} > {self.threshold:.2%}: 买入 @ {bar['close']}")
            self.buy("default", size=100)
            self.in_position = True

        elif momentum < -self.threshold and self.in_position:
            self.log(f"动量信号 {momentum:.2%} < {-self.threshold:.2%}: 卖出 @ {bar['close']}")
            self.sell("default", size=100)
            self.in_position = False

    def on_tick(self, tick):
        """处理Tick数据"""
        pass

    def on_order(self, order):
        """处理订单更新"""
        self.log(f"订单更新: {order['id']} - {order['status']}")

    def on_trade(self, trade):
        """处理成交回报"""
        self.log(f"成交: {trade['size']} @ {trade.get('price', 0)}")

    def on_stop(self):
        """策略停止"""
        self.log("动量策略停止")


async def run_custom_strategy():
    """运行自定义策略回测"""

    print("\n" + "=" * 80)
    print("自定义动量策略回测")
    print("=" * 80)

    engine = BacktestEngine(data_provider=None, event_engine=None)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    await engine.configure(
        strategy_class=CustomMomentumStrategy,
        symbol="000001.SZ",
        start_date=start_date,
        end_date=end_date,
        initial_cash=100000,
        commission=0.001,
        slippage=0.001,
        strategy_params={"lookback": 20, "threshold": 0.05},
    )

    result = await engine.run_async()

    print("\n回测结果:")
    print(f"  总收益率: {result.total_return:.2%}")
    print(f"  夏普比率: {result.sharpe_ratio:.2f}")
    print(f"  最大回撤: {result.max_drawdown:.2%}")
    print(f"  总交易次数: {result.total_trades}")
    print(f"  胜率: {result.win_rate:.2%}")

    return result


async def main():
    """主函数"""

    try:
        # 检查是否安装了 backtrader
        try:
            import backtrader

            print(f"Backtrader 版本: {backtrader.__version__}")
        except ImportError:
            print("错误: 请先安装 backtrader")
            print("运行: pip install backtrader")
            return

        # 1. 运行简单回测
        print("\n1. 简单移动平均线策略回测")
        await run_simple_backtest()

        # 2. 运行参数优化
        print("\n2. 参数优化对比")
        await run_comparative_backtest()

        # 3. 运行自定义策略
        print("\n3. 自定义动量策略")
        await run_custom_strategy()

        print("\n" + "=" * 80)
        print("所有回测完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
