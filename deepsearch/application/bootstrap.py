"""
系统引导模块。

负责系统启动时执行必要的初始化逻辑，如触发后台数据预取等。
"""

from __future__ import annotations

from loguru import logger

from deepsearch.application.services.data_sources import DataSourcePrefetchScheduler

_prefetch_scheduler: DataSourcePrefetchScheduler | None = None


async def bootstrap_system() -> None:
    """
    执行系统引导逻辑。

    应由 MainEngine 在启动后调用。
    """

    global _prefetch_scheduler

    if _prefetch_scheduler is not None:
        return

    logger.info("开始执行系统引导流程...")

    try:
        scheduler = DataSourcePrefetchScheduler()
        started = await scheduler.start()
        if started:
            _prefetch_scheduler = scheduler
            logger.info("数据源后台预取调度器已启动")
        else:
            logger.info("数据源后台预取调度器关闭，跳过启动")
    except Exception as exc:
        logger.error(f"系统引导执行失败: {exc}")
