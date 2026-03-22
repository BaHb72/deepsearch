"""
策略中心配置模型。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TTradingBacktestModeSetting = Literal["legacy", "shadow", "backtrader"]


class StrategyCenterConfig(BaseModel):
    """策略中心配置。"""

    ttrading_backtest_mode: TTradingBacktestModeSetting = Field(
        default="shadow",
        description="做T回测执行模式：legacy | shadow | backtrader",
    )
