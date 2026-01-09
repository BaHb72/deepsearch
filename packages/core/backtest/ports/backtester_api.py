"""Backtrader 接口抽象."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import IO, Any, Protocol


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

    def addcommissioninfo(self, comminfo: Any, name: Any = None) -> None:
        """添加佣金配置."""

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


class CerebroProto(Protocol):
    """Backtrader 核心调度器抽象.

    使用Any类型简化，因为泛型参数在Protocol中存在协变/逆变冲突。
    """

    broker: BrokerProto

    def adddata(self, data: Any, name: str | None = None) -> None:
        """添加数据源."""

    def addstrategy(
        self,
        strategy: type[Any],
        *args: object,
        **kwargs: object,
    ) -> None:
        """注册策略."""

    def addanalyzer(
        self,
        analyzer: type[Any],
        *args: object,
        **kwargs: object,
    ) -> None:
        """注册分析器."""

    def run(self) -> Sequence[Any]:
        """执行回测并返回策略实例列表."""

    def plot(self, *args: object, **kwargs: object) -> Sequence[Sequence[FigureProto]]:
        """生成图表."""


class AnalyzerNamespaceProto(Protocol):
    """Backtrader 自带的分析器命名空间."""

    SharpeRatio: type[Any]
    DrawDown: type[Any]
    Returns: type[Any]
    TradeAnalyzer: type[Any]
    TimeReturn: type[Any]
    AnnualReturn: type[Any]


class BacktesterAPI(Protocol):
    """Backtrader 模块在领域层暴露的能力边界."""

    Cerebro: type[CerebroProto]
    analyzers: AnalyzerNamespaceProto
