"""
运行时配置模型。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

RuntimeModeSetting = Literal["all", "engine", "webui", "full"]


class RuntimeConfig(BaseModel):
    """运行时配置。"""

    mode: RuntimeModeSetting = "full"
