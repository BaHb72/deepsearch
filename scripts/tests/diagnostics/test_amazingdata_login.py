"""
诊断脚本：复现 dev 环境下 AmazingData 登录异常与数据源状态。

使用方式：
    uv run python scripts/tests/diagnostics/test_amazingdata_login.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, Dict

from loguru import logger

os.environ.setdefault("APP__ENV", "dev")


async def _run() -> None:
    from deepsearch.ports.data_sources import DataSourceType
    from deepsearch.utils.data_sources import initialize_data_sources

    logger.info("加载 dev 配置并初始化数据源管理器...")
    manager = await initialize_data_sources()

    status: Dict[str, Any] = {
        source_type.value: snapshot
        for source_type, snapshot in manager.get_status_report().items()
    }
    logger.info("数据源状态快照:\n{}", json.dumps(status, ensure_ascii=False, indent=2))

    try:
        logger.info("尝试获取股票列表（优先使用 AmazingData）...")
        result = await manager.get_stock_list(limit=5)
        if result is None:
            logger.warning("未能获取到股票列表——可能所有数据源都不可用。")
        else:
            logger.info(
                "成功返回 {} 条记录，来源：{}",
                len(result.records) or len(result.legacy),
                result.source,
            )
    except Exception as exc:  # pragma: no cover - 诊断脚本保留完整异常信息
        logger.exception("获取股票列表时出现异常: {}", exc)


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.warning("测试被手动中断")


if __name__ == "__main__":
    sys.exit(main())
