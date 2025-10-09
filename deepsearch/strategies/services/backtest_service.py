from __future__ import annotations

"""回测服务，提供 Backtrader 集成的类型安全封装."""

import base64
import io
from dataclasses import dataclass, field
from datetime import datetime
from importlib import import_module
from importlib.util import find_spec
from typing import Callable, Mapping, Sequence, TypedDict, cast

from loguru import logger

from deepsearch.backtest.adapters.unified_backtrader_adapter import UnifiedBacktraderAdapter
from deepsearch.backtest.interfaces.strategy import BacktraderStrategyAdapter
from deepsearch.backtest.ports import (
    AnalyzerResultProto,
    BacktesterAPI,
    CerebroProto,
    FigureProto,
    StrategyProto,
)
from deepsearch.strategies.interfaces.protocols import BacktestStrategy

HAS_MATPLOTLIB = find_spec("matplotlib") is not None

StrategyParameters = Mapping[str, object]

StrategyComparisonConfig = TypedDict(
    "StrategyComparisonConfig",
    {
        "class": type[BacktestStrategy],
        "params": StrategyParameters,
        "name": str,
    },
    total=False,
)

PlotClose = Callable[[FigureProto], None]


@dataclass(frozen=True)
class EquityPoint:
    """权益曲线中的单个节点."""

    date: str
    value: float

    def to_dict(self) -> dict[str, object]:
        """转换为可序列化字典."""

        return {"date": self.date, "value": self.value}


@dataclass
class BacktestResult:
    """结构化的回测结果."""

    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_value: float = 0.0
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    equity_curve: list[EquityPoint] = field(default_factory=list)
    plot_base64: str | None = None

    def to_dict(self) -> dict[str, object]:
        """转换为字典结果，供 WebUI 序列化使用."""

        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
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
            "equity_curve": [point.to_dict() for point in self.equity_curve],
            "plot_base64": self.plot_base64,
        }


class BacktestService:
    """统一的回测编排服务."""

    def __init__(
        self,
        backtester: BacktesterAPI[StrategyProto, AnalyzerResultProto, object],
        *,
        plot_close: PlotClose | None = None,
    ) -> None:
        """注入 Backtrader 端口及可选的绘图关闭函数."""

        self._backtester = backtester
        self._plot_close = plot_close
        self.adapter: UnifiedBacktraderAdapter | None = None
        self.results_cache: dict[str, BacktestResult] = {}

    async def initialize(self) -> None:
        """初始化底层数据适配器."""

        if self.adapter is None:
            self.adapter = UnifiedBacktraderAdapter(source="auto")
            await self.adapter.initialize()
            logger.info("BacktestService 初始化完成")

    async def run_backtest(
        self,
        strategy_class: type[BacktestStrategy],
        symbols: Sequence[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000,
        strategy_params: StrategyParameters | None = None,
        commission: float = 0.001,
        plot: bool = True,
    ) -> BacktestResult:
        """执行单个策略的回测."""

        if self.adapter is None:
            await self.initialize()

        if self.adapter is None:
            raise RuntimeError("回测数据适配器初始化失败")

        cerebro = self._backtester.Cerebro()
        cerebro.broker.setcash(initial_capital)
        cerebro.broker.setcommission(commission=commission)

        for symbol in symbols:
            df = await self.adapter.get_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                timeframe="1d",
                adjust="qfq",
            )

            if df.empty:
                logger.warning(f"{symbol} 无可用数据，已跳过")
                continue

            data_feed = self.adapter.create_backtrader_feed(df, name=symbol)
            cerebro.adddata(data_feed, name=symbol)
            logger.info(f"已加载 {symbol} 的 {len(df)} 条数据")

        strategy_instance = strategy_class(
            params=dict(strategy_params) if strategy_params else None
        )
        bt_strategy_class = BacktraderStrategyAdapter.create_backtrader_strategy(
            strategy_instance
        )
        cerebro.addstrategy(bt_strategy_class)

        analyzers = self._backtester.analyzers
        cerebro.addanalyzer(analyzers.SharpeRatio, _name="sharpe")
        cerebro.addanalyzer(analyzers.DrawDown, _name="drawdown")
        cerebro.addanalyzer(analyzers.Returns, _name="returns")
        cerebro.addanalyzer(analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(analyzers.TimeReturn, _name="timereturn")

        result = BacktestResult(
            strategy_name=strategy_class.__name__,
            start_date=datetime.strptime(start_date, "%Y-%m-%d"),
            end_date=datetime.strptime(end_date, "%Y-%m-%d"),
            initial_capital=initial_capital,
        )

        logger.info(
            f"开始回测 {strategy_class.__name__}，标的：{', '.join(symbols)}"
        )

        strategies = cerebro.run()
        if not strategies:
            raise RuntimeError("回测返回结果为空")

        strategy = cast(StrategyProto, strategies[0])

        result.final_value = cerebro.broker.getvalue()
        result.total_return = _to_float(
            (result.final_value - initial_capital) / initial_capital
        )

        result.sharpe_ratio = _extract_ratio(strategy, "sharpe", "sharperatio")
        result.max_drawdown = _extract_nested_ratio(
            strategy, "drawdown", "max", "drawdown", scale=0.01
        )
        result.annual_return = _extract_ratio(
            strategy, "returns", "rnorm100", scale=0.01
        )

        trades_summary = _extract_analysis(strategy, "trades")
        total_section = _as_mapping(trades_summary.get("total"))
        won_section = _as_mapping(trades_summary.get("won"))
        lost_section = _as_mapping(trades_summary.get("lost"))

        result.total_trades = _to_int(total_section.get("total"))
        result.winning_trades = _to_int(won_section.get("total"))
        result.losing_trades = _to_int(lost_section.get("total"))

        if result.total_trades > 0:
            result.win_rate = result.winning_trades / result.total_trades

        lost_total = _to_float(_as_mapping(lost_section.get("pnl")).get("total"))
        won_total = _to_float(_as_mapping(won_section.get("pnl")).get("total"))

        if lost_total != 0:
            result.profit_factor = abs(won_total / lost_total)

        time_returns = _extract_analysis(strategy, "timereturn")
        if time_returns:
            equity = initial_capital
            equity_curve: list[EquityPoint] = [
                EquityPoint(start_date, round(equity, 2))
            ]
            for date_value, daily_return in time_returns.items():
                equity *= 1.0 + _to_float(daily_return)
                equity_curve.append(
                    EquityPoint(_format_date_label(date_value), round(equity, 2))
                )
            result.equity_curve = equity_curve

        if plot:
            result.plot_base64 = self._generate_plot(cerebro)

        logger.info(
            "回测完成，最终权益 {:.2f}，收益率 {:.2f}%",
            result.final_value,
            result.total_return * 100,
        )

        return result

    def _generate_plot(
        self, cerebro: CerebroProto[StrategyProto, AnalyzerResultProto, object]
    ) -> str | None:
        """生成回测图表并转换为 base64 编码."""

        try:
            plot_result = cerebro.plot(
                style="candlestick",
                barup="green",
                bardown="red",
                volume=True,
                numfigs=1,
                plotdist=0.1,
                grid=True,
            )
        except Exception as exc:  # pragma: no cover
            logger.error(f"生成回测图表失败: {exc}")
            return None

        figure = _pick_first_figure(plot_result)
        if figure is None:
            return None

        buffer = io.BytesIO()
        figure.savefig(
            buffer,
            format="png",
            dpi=100,
            bbox_inches="tight",
        )
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        if self._plot_close is not None:
            self._plot_close(figure)

        return f"data:image/png;base64,{image_base64}"

    async def compare_strategies(
        self,
        strategies: Sequence[StrategyComparisonConfig],
        symbols: Sequence[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100000,
    ) -> list[BacktestResult]:
        """批量比较多个策略的表现."""

        results: list[BacktestResult] = []
        for strategy_config in strategies:
            if "class" not in strategy_config:
                raise ValueError("策略配置缺少 class 字段")

            strategy_class = strategy_config["class"]
            params = strategy_config.get("params")
            result = await self.run_backtest(
                strategy_class=strategy_class,
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                strategy_params=params,
                commission=0.001,
                plot=True,
            )

            custom_name = strategy_config.get("name")
            if custom_name:
                result.strategy_name = custom_name

            results.append(result)

        return results

    def get_cached_result(self, cache_key: str) -> BacktestResult | None:
        """根据缓存键获取历史回测结果."""

        return self.results_cache.get(cache_key)

    def cache_result(self, cache_key: str, result: BacktestResult) -> None:
        """缓存最新的回测结果，最多保留 10 份."""

        self.results_cache[cache_key] = result
        if len(self.results_cache) > 10:
            oldest_key = next(iter(self.results_cache))
            del self.results_cache[oldest_key]


_backtest_service: BacktestService | None = None


def get_backtest_service() -> BacktestService:
    """获取全局回测服务实例."""

    global _backtest_service
    if _backtest_service is None:
        from deepsearch.backtest.adapters.backtrader_api_impl import load_api

        plot_close = _load_default_plot_close()
        _backtest_service = BacktestService(
            backtester=load_api(),
            plot_close=plot_close,
        )
    return _backtest_service


def _load_default_plot_close() -> PlotClose | None:
    """加载 matplotlib 的关闭函数，若依赖缺失则返回 None."""

    if not HAS_MATPLOTLIB:
        return None

    module = import_module("matplotlib.pyplot")
    close_func = getattr(module, "close", None)
    if callable(close_func):
        return cast(PlotClose, close_func)
    return None


def _extract_analysis(strategy: StrategyProto, name: str) -> Mapping[object, object]:
    """安全获取指定分析器的结果."""

    analyzer = getattr(strategy.analyzers, name, None)
    if analyzer is None:
        return {}
    get_analysis = getattr(analyzer, "get_analysis", None)
    if callable(get_analysis):
        try:
            analysis = get_analysis()
        except Exception as exc:  # pragma: no cover
            logger.warning(f"读取分析器 {name} 失败: {exc}")
            return {}
        if isinstance(analysis, Mapping):
            return analysis
    return {}


def _extract_ratio(
    strategy: StrategyProto,
    analyzer_name: str,
    field: str,
    *,
    scale: float = 1.0,
) -> float:
    """从分析器中提取单层字段并转换为浮点数."""

    analysis = _extract_analysis(strategy, analyzer_name)
    return _to_float(analysis.get(field)) * scale


def _extract_nested_ratio(
    strategy: StrategyProto,
    analyzer_name: str,
    first_key: str,
    second_key: str,
    *,
    scale: float = 1.0,
) -> float:
    """从嵌套字典中提取指标."""

    analysis = _extract_analysis(strategy, analyzer_name)
    first_level = _as_mapping(analysis.get(first_key))
    return _to_float(first_level.get(second_key)) * scale


def _as_mapping(value: object) -> Mapping[str, object]:
    """若对象为映射则原样返回，否则给出空字典."""

    if isinstance(value, Mapping):
        return value
    return {}


def _to_float(value: object, default: float = 0.0) -> float:
    """尽量将值转换为浮点数."""

    if isinstance(value, (int, float)):
        return float(value)
    return default


def _to_int(value: object, default: int = 0) -> int:
    """尽量将值转换为整数."""

    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _format_date_label(value: object) -> str:
    """将时间索引统一转为字符串标签."""

    if isinstance(value, datetime):
        return value.isoformat()
    iso_method = getattr(value, "isoformat", None)
    if callable(iso_method):
        try:
            iso_value = iso_method()
        except Exception:  # pragma: no cover
            return str(value)
        if isinstance(iso_value, str):
            return iso_value
    return str(value)


def _pick_first_figure(
    plot_result: Sequence[Sequence[FigureProto]],
) -> FigureProto | None:
    """从 Backtrader 的 plot 结果中挑选首个 Figure."""

    if not plot_result:
        return None
    first_column = plot_result[0]
    if not first_column:
        return None
    return first_column[0]
