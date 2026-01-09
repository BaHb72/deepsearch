"""Backtrader 运行时适配器."""

from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:  # pragma: no cover
    from core.backtest.ports.backtester_api import BacktesterAPI


def load_api() -> "BacktesterAPI":
    """加载 Backtrader 模块并以端口类型暴露."""

    if find_spec("backtrader") is None:
        raise ImportError("未检测到 backtrader，请先安装该依赖：pip install backtrader")

    module = import_module("backtrader")
    return cast("BacktesterAPI", module)


__all__ = ["load_api"]
