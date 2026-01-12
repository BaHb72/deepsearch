"""
诊断脚本：检查数据同步服务所需的数据库接口是否在 dev 环境实现。

使用方式：
    uv run python scripts/tests/diagnostics/test_datasync_requirements.py
"""

from __future__ import annotations

import os
import sys
from typing import Iterable, List

from loguru import logger

os.environ.setdefault("APP__ENV", "dev")

REQUIRED_METHODS: Iterable[str] = (
    "fetch_kline_history",
    "fetch_stock_info",
    "fetch_all_stock_info",
    "get_stock_info",
)


def main() -> int:
    from deepsearch.core.components.data_components import DatabaseComponent
    from deepsearch.infrastructure.providers.managers.data_sync_service import DataSyncService

    db_component = DatabaseComponent()
    service = DataSyncService(database_component=db_component)

    missing: List[str] = [name for name in REQUIRED_METHODS if not hasattr(db_component, name)]
    if missing:
        logger.error(
            "DatabaseComponent 缺少数据同步所需的方法: {}",
            ", ".join(missing),
        )
    else:
        logger.success("DatabaseComponent 已实现全部所需方法。")

    logger.info(
        "DataSyncService 使用的数据库组件类型: {}",
        type(service._database_component).__name__,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
