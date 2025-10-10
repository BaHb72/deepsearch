from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, IO, Protocol


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


class CerebroProto(Protocol):
    broker: BrokerProto

    def adddata(self, data: Any, name: str | None = ...) -> None: ...

    def addstrategy(
        self,
        strategy: type[Any],
        *args: object,
        **kwargs: object,
    ) -> None: ...

    def addanalyzer(
        self,
        analyzer: type[Any],
        *args: object,
        **kwargs: object,
    ) -> None: ...

    def run(self) -> Sequence[Any]: ...

    def plot(self, *args: object, **kwargs: object) -> Sequence[Sequence[FigureProto]]: ...


class AnalyzerNamespaceProto(Protocol):
    SharpeRatio: type[Any]
    DrawDown: type[Any]
    Returns: type[Any]
    TradeAnalyzer: type[Any]
    TimeReturn: type[Any]
    AnnualReturn: type[Any]


class BacktesterAPI(Protocol):
    Cerebro: type[CerebroProto]
    analyzers: AnalyzerNamespaceProto
