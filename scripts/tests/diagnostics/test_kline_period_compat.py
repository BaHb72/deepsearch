"""
诊断脚本：验证 dev 环境下 AmazingData `get_kline_data` 参数兼容性。

使用方式：
    uv run python scripts/tests/diagnostics/test_kline_period_compat.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from loguru import logger

os.environ.setdefault("APP__ENV", "dev")

SYMBOL = "000001.SZ"


async def _run() -> None:
    from deepsearch.utils.data_sources import initialize_data_sources

    manager = await initialize_data_sources()

    logger.info("使用 period='daily' 调用 AmazingData.get_kline_data ...")
    result: Any = await manager.execute_with_fallback(
        "get_kline_data",
        SYMBOL,
        period="daily",
    )
    if result is None:
        logger.warning("所有数据源均未返回 K 线数据，可能是参数不兼容导致。")
    else:
        logger.info("返回结果：{}", result)

    logger.info("改用 period='1d' 再次尝试 ...")
    result_alt: Any = await manager.execute_with_fallback(
        "get_kline_data",
        SYMBOL,
        period="1d",
    )
    if result_alt is None:
        logger.error("fallback 仍然失败，请检查日志了解具体原因。")
    else:
        logger.info("period='1d' 返回结果：{}", result_alt)


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.warning("测试被手动中断")


if __name__ == "__main__":
    sys.exit(main())
