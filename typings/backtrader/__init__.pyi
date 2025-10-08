from typing import Any


class Lines:
    def __getitem__(self, key: Any) -> Any: ...
    def __setitem__(self, key: Any, value: Any) -> None: ...


class Indicator:
    lines: Any
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Cerebro:
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def addstrategy(self, strategy: type[Any], *args: Any, **kwargs: Any) -> None: ...
    def adddata(self, data: Any) -> None: ...
    def run(self) -> list[Any]: ...

class Strategy:
    params: Any
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class Analyzer:
    params: Any
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

class feeds:
    class PandasData:
        params: Any
        def __init__(self, *args: Any, **kwargs: Any) -> None: ...


class indicators:
    ROC: type[Indicator]
    SMA: type[Indicator]
    Highest: type[Indicator]
    ATR: type[Indicator]
    MACD: type[Indicator]
    WilliamsR: type[Indicator]

__all__ = ["Cerebro", "Strategy", "Analyzer", "feeds", "Indicator", "indicators"]
