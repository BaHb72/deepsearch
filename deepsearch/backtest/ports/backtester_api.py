from __future__ import annotations

"""Backtrader 接口抽象."""

from collections.abc import Mapping, Sequence
from typing import IO, Protocol, TypeVar


StrategyT_co = TypeVar("StrategyT_co", covariant=True)
AnalyzerResultT_co = TypeVar("AnalyzerResultT_co", covariant=True)
DataFeedT = TypeVar("DataFeedT")


class AnalyzerResultProto(Protocol):
    """回测分析器结果的最小接口."""

    def get_analysis(self) -> Mapping[object, object]:
        """返回分析数据."""


class AnalyzerCollectionProto(Protocol):
    """Backtrader 策略附带的分析器集合."""

    def __getattr__(self, name: str) -> AnalyzerResultProto:
        """按名称访问分析器."""


class StrategyProto(Protocol):
    """回测策略在运行结束后的公共能力."""

    analyzers: AnalyzerCollectionProto


class BrokerProto(Protocol):
    """经纪人对象需要暴露的能力."""

    def setcash(self, cash: float) -> None:
        """设置初始资金."""

    def setcommission(self, commission: float) -> None:
        """设置手续费."""

    def set_slippage_perc(self, perc: float) -> None:
        """设置滑点百分比."""

    def getvalue(self) -> float:
        """获取账户当前权益."""


class FigureProto(Protocol):
    """绘图对象最小接口."""

    def savefig(
        self,
        buffer: IO[bytes],
        *,
        format: str,
        dpi: int,
        bbox_inches: str,
    ) -> None:
        """保存图像到二进制缓冲区."""


class CerebroProto(Protocol[StrategyT_co, AnalyzerResultT_co, DataFeedT]):
    """Backtrader 核心调度器抽象."""

    broker: BrokerProto

    def adddata(self, data: DataFeedT, name: str | None = None) -> None:
        """添加数据源."""

    def addstrategy(
        self,
        strategy: type[StrategyT_co],
        *args: object,
        **kwargs: object,
    ) -> None:
        """注册策略."""

    def addanalyzer(
        self,
        analyzer: type[AnalyzerResultT_co],
        *args: object,
        **kwargs: object,
    ) -> None:
        """注册分析器."""

    def run(self) -> Sequence[StrategyT_co]:
        """执行回测并返回策略实例列表."""

    def plot(self, *args: object, **kwargs: object) -> Sequence[Sequence[FigureProto]]:
        """生成图表."""


class AnalyzerNamespaceProto(Protocol[AnalyzerResultT_co]):
    """Backtrader 自带的分析器命名空间."""

    SharpeRatio: type[AnalyzerResultT_co]
    DrawDown: type[AnalyzerResultT_co]
    Returns: type[AnalyzerResultT_co]
    TradeAnalyzer: type[AnalyzerResultT_co]
    TimeReturn: type[AnalyzerResultT_co]
    AnnualReturn: type[AnalyzerResultT_co]


class BacktesterAPI(Protocol[StrategyT_co, AnalyzerResultT_co, DataFeedT]):
    """Backtrader 模块在领域层暴露的能力边界."""

    Cerebro: type[CerebroProto[StrategyT_co, AnalyzerResultT_co, DataFeedT]]
    analyzers: AnalyzerNamespaceProto[AnalyzerResultT_co]
