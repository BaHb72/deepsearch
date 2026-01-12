"""Shared constants and logging hooks for the AmazingData provider."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Union

from core.observability.logger import logger_manager
from platformdirs import user_data_dir

datasource_logger = logger_manager.get_datasource_logger("amazingdata")

DEFAULT_HIST_CODE_LIST_START = 20130101


def get_default_local_data_path() -> str:
    """返回当前平台的 AmazingData 缓存目录默认路径。"""

    base_dir = Path(user_data_dir(appname="DeepSearch", appauthor="DeepSearch"))
    return str(base_dir.joinpath("AmazingData"))


# 保留兼容性常量：外部引用仍可用，内部模块已改用 get_default_local_data_path()。
DEFAULT_LOCAL_DATA_PATH = get_default_local_data_path()
BOARD_FIELD_CANDIDATES: tuple[str, ...] = ("LISTPLATE_NAME", "board", "board_name")

SubscriptionCallback = Callable[[Any], Awaitable[None] | None]
StatsValue = Union[int, float, datetime, dict[str, Any], list[dict[str, str]], None]

__all__ = [
    "datasource_logger",
    "DEFAULT_HIST_CODE_LIST_START",
    "DEFAULT_LOCAL_DATA_PATH",
    "get_default_local_data_path",
    "BOARD_FIELD_CANDIDATES",
    "SubscriptionCallback",
    "StatsValue",
]
