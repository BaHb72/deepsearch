"""
Backtest Service

Service for running backtests with Backtrader and generating visualizations.
"""

import base64
import io
from datetime import datetime
from types import ModuleType
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Type, cast

from loguru import logger

try:
    import backtrader as _bt
    import matplotlib

    matplotlib.use("Agg")  # Use non-interactive backend
    import matplotlib.pyplot as _plt

    HAS_BACKTRADER = True
except ImportError:
    HAS_BACKTRADER = False
    _bt = None
    _plt = None

bt: Optional[ModuleType] = cast(Optional[ModuleType], _bt)
plt: Optional[ModuleType] = cast(Optional[ModuleType], _plt)

if TYPE_CHECKING:  # pragma: no cover
    import backtrader as bt  # type: ignore
    from matplotlib.figure import Figure

from deepsearch.backtest.adapters.unified_backtrader_adapter import UnifiedBacktraderAdapter
from deepsearch.backtest.interfaces.strategy import BacktraderStrategyAdapter
from deepsearch.strategies.interfaces.protocols import BacktestStrategy


class BacktestResult:
    """Backtest result container"""

    def __init__(self):
        self.strategy_name: str = ""
        self.start_date: Optional[datetime] = None
        self.end_date: Optional[datetime] = None
        self.initial_capital: float = 0.0
        self.final_value: float = 0.0
        self.total_return: float = 0.0
        self.annual_return: float = 0.0
        self.sharpe_ratio: float = 0.0
        self.max_drawdown: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0
        self.win_rate: float = 0.0
        self.profit_factor: float = 0.0
        self.trades: List[Dict[str, Any]] = []
        self.equity_curve: List[Dict[str, Any]] = []
        self.plot_base64: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "initial_capital": self.initial_capital,
            "final_value": self.final_value,
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "trades": self.trades,
            "equity_curve": self.equity_curve,
            "plot_base64": self.plot_base64,
        }


class BacktestService:
    """
    Service for running strategy backtests

    Features:
    - Run backtests with Backtrader
    - Generate performance metrics
    - Create visualization charts
    - Export results for WebUI
    """

    def __init__(self):
        """Initialize backtest service"""
        if not HAS_BACKTRADER:
            raise ImportError("Backtrader not installed. Run: pip install backtrader matplotlib")

        self.adapter: Optional[UnifiedBacktraderAdapter] = None
        self.results_cache: Dict[str, BacktestResult] = {}

    async def initialize(self):
        """Initialize service"""
        if not self.adapter:
            self.adapter = UnifiedBacktraderAdapter(source="auto")
            await self.adapter.initialize()
            logger.info("BacktestService initialized")

    async def run_backtest(
        self,
        strategy_class: Type[BacktestStrategy],
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000,
        strategy_params: Optional[Dict[str, Any]] = None,
        commission: float = 0.001,
        plot: bool = True,
    ) -> BacktestResult:
        """
        Run a backtest for a strategy

        Args:
            strategy_class: Strategy class to test
            symbols: List of symbols to trade
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            initial_capital: Initial capital
            strategy_params: Strategy parameters
            commission: Commission rate
            plot: Whether to generate plot

        Returns:
            BacktestResult object
        """
        if not self.adapter:
            await self.initialize()

        if self.adapter is None:
            raise RuntimeError("Backtest adapter is not initialized")

        adapter = self.adapter

        logger.info(f"Running backtest for {strategy_class.__name__} on {symbols}")

        # Create result object
        result = BacktestResult()
        result.strategy_name = strategy_class.__name__
        result.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        result.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        result.initial_capital = initial_capital

        try:
            if bt is None:
                raise RuntimeError("Backtrader module is not available")

            # Create Cerebro engine
            cerebro = bt.Cerebro()

            # Set initial capital
            cerebro.broker.setcash(initial_capital)
            cerebro.broker.setcommission(commission=commission)

            # Add data feeds
            for symbol in symbols:
                df = await adapter.get_data(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    timeframe="1d",
                    adjust="qfq",
                )

                if not df.empty:
                    data = adapter.create_backtrader_feed(df, name=symbol)
                    cerebro.adddata(data)
                    logger.info(f"Added data for {symbol}: {len(df)} bars")
                else:
                    logger.warning(f"No data available for {symbol}")

            # Create and add strategy
            strategy_instance: BacktestStrategy = strategy_class(params=strategy_params)
            bt_strategy_class = BacktraderStrategyAdapter.create_backtrader_strategy(
                strategy_instance
            )
            cerebro.addstrategy(bt_strategy_class)

            # Add analyzers
            cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
            cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
            cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
            cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
            cerebro.addanalyzer(bt.analyzers.TimeReturn, _name="timereturn")

            # Run backtest
            logger.info("Starting backtest...")
            strategies = cerebro.run()
            strategy = strategies[0]

            # Get results
            result.final_value = cerebro.broker.getvalue()
            result.total_return = (result.final_value - initial_capital) / initial_capital

            # Get analyzer results
            if hasattr(strategy.analyzers, "sharpe"):
                sharpe = strategy.analyzers.sharpe.get_analysis()
                result.sharpe_ratio = sharpe.get("sharperatio", 0) or 0

            if hasattr(strategy.analyzers, "drawdown"):
                dd = strategy.analyzers.drawdown.get_analysis()
                result.max_drawdown = dd.get("max", {}).get("drawdown", 0) / 100

            if hasattr(strategy.analyzers, "returns"):
                returns = strategy.analyzers.returns.get_analysis()
                result.annual_return = returns.get("rnorm100", 0) / 100

            if hasattr(strategy.analyzers, "trades"):
                trades = strategy.analyzers.trades.get_analysis()
                total = trades.get("total", {})
                result.total_trades = total.get("total", 0)

                won = trades.get("won", {})
                lost = trades.get("lost", {})
                result.winning_trades = won.get("total", 0)
                result.losing_trades = lost.get("total", 0)

                if result.total_trades > 0:
                    result.win_rate = result.winning_trades / result.total_trades

                # Calculate profit factor
                if lost.get("pnl", {}).get("total", 0) != 0:
                    result.profit_factor = abs(
                        won.get("pnl", {}).get("total", 0) / lost.get("pnl", {}).get("total", 0)
                    )

            # Get equity curve
            if hasattr(strategy.analyzers, "timereturn"):
                time_returns = strategy.analyzers.timereturn.get_analysis()
                equity = initial_capital
                equity_curve = [{"date": start_date, "value": equity}]

                for date, ret in time_returns.items():
                    equity *= 1 + ret
                    equity_curve.append(
                        {
                            "date": date.isoformat() if hasattr(date, "isoformat") else str(date),
                            "value": round(equity, 2),
                        }
                    )

                result.equity_curve = equity_curve

            # Generate plot if requested
            if plot:
                result.plot_base64 = self._generate_plot(cerebro)

            logger.info(
                f"Backtest completed. Final value: {result.final_value:.2f}, "
                f"Return: {result.total_return:.2%}"
            )

        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            raise

        return result

    def _generate_plot(self, cerebro: Any) -> Optional[str]:
        """
        Generate backtest plot and return as base64

        Args:
            cerebro: Backtrader Cerebro instance

        Returns:
            Base64 encoded plot image
        """
        if plt is None:
            return None

        try:
            # Create figure
            fig = cerebro.plot(
                style="candlestick",
                barup="green",
                bardown="red",
                volume=True,
                numfigs=1,
                plotdist=0.1,
                grid=True,
            )[0][0]

            # Save to bytes buffer
            buffer = io.BytesIO()
            fig.savefig(buffer, format="png", dpi=100, bbox_inches="tight")
            buffer.seek(0)

            # Convert to base64
            image_base64 = base64.b64encode(buffer.read()).decode("utf-8")

            # Clean up
            plt.close(fig)
            buffer.close()

            return f"data:image/png;base64,{image_base64}"

        except Exception as e:
            logger.error(f"Failed to generate plot: {e}")
            return None

    async def compare_strategies(
        self,
        strategies: List[Dict[str, Any]],
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000,
    ) -> List[BacktestResult]:
        """
        Compare multiple strategies

        Args:
            strategies: List of strategy configurations
                       [{'class': StrategyClass, 'params': {...}, 'name': 'Strategy1'}, ...]
            symbols: Symbols to test
            start_date: Start date
            end_date: End date
            initial_capital: Initial capital

        Returns:
            List of BacktestResult objects
        """
        results = []

        for strategy_config in strategies:
            strategy_class = cast(Type[BacktestStrategy], strategy_config["class"])
            strategy_params = strategy_config.get("params", {})

            result = await self.run_backtest(
                strategy_class=strategy_class,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                strategy_params=strategy_params,
                plot=True,
            )

            # Override name if provided
            if "name" in strategy_config:
                result.strategy_name = strategy_config["name"]

            results.append(result)

        return results

    def get_cached_result(self, cache_key: str) -> Optional[BacktestResult]:
        """Get cached backtest result"""
        return self.results_cache.get(cache_key)

    def cache_result(self, cache_key: str, result: BacktestResult):
        """Cache backtest result"""
        self.results_cache[cache_key] = result

        # Limit cache size
        if len(self.results_cache) > 10:
            # Remove oldest entry
            oldest_key = next(iter(self.results_cache))
            del self.results_cache[oldest_key]


# Global service instance
_backtest_service: Optional[BacktestService] = None


def get_backtest_service() -> BacktestService:
    """Get global backtest service instance"""
    global _backtest_service
    if _backtest_service is None:
        _backtest_service = BacktestService()
    return _backtest_service
