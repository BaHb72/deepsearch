from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import IO, Protocol, TypeVar


StrategyT = TypeVar("StrategyT")
AnalyzerResultT = TypeVar("AnalyzerResultT")
DataFeedT = TypeVar("DataFeedT")


class AnalyzerResultProto(Protocol):
    def get_analysis(self) -> Mapping[object, object]: ...


class AnalyzerCollectionProto(Protocol):
    def __getattr__(self, name: str) -> AnalyzerResultProto: ...


class StrategyProto(Protocol):
    analyzers: AnalyzerCollectionProto


class BrokerProto(Protocol):
    def setcash(self, cash: float) -> None: ...
    def setcommission(self, commission: float) -> None: ...
    def set_slippage_perc(self, perc: float) -> None: ...
    def getvalue(self) -> float: ...


class FigureProto(Protocol):
    def savefig(
        self,
        buffer: IO[bytes],
        *,
        format: str,
        dpi: int,
        bbox_inches: str,
    ) -> None: ...


class CerebroProto(Protocol[StrategyT, AnalyzerResultT, DataFeedT]):
    broker: BrokerProto

    def adddata(self, data: DataFeedT, name: str | None = ...) -> None: ...

    def addstrategy(
        self,
        strategy: type[StrategyT],
        *args: object,
        **kwargs: object,
    ) -> None: ...

    def addanalyzer(
        self,
        analyzer: type[AnalyzerResultT],
        *args: object,
        **kwargs: object,
    ) -> None: ...

    def run(self) -> Sequence[StrategyT]: ...

    def plot(self, *args: object, **kwargs: object) -> Sequence[Sequence[FigureProto]]: ...


class AnalyzerNamespaceProto(Protocol[AnalyzerResultT]):
    SharpeRatio: type[AnalyzerResultT]
    DrawDown: type[AnalyzerResultT]
    Returns: type[AnalyzerResultT]
    TradeAnalyzer: type[AnalyzerResultT]
    TimeReturn: type[AnalyzerResultT]
    AnnualReturn: type[AnalyzerResultT]


class BacktesterAPI(Protocol[StrategyT, AnalyzerResultT, DataFeedT]):
    Cerebro: type[CerebroProto[StrategyT, AnalyzerResultT, DataFeedT]]
    analyzers: AnalyzerNamespaceProto[AnalyzerResultT]
