"""
缓存调度器

统一管理缓存任务的调度和执行
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional, Union

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from core.core.scheduler.tasks.base import CacheTask
from loguru import logger


class CacheScheduler:
    """
    缓存调度器

    管理多个缓存任务的定时刷新
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.tasks: Dict[str, CacheTask] = {}
        self._started = False
        self._redis_store = None
        self._db_store = None

    def register_task(self, task: CacheTask) -> None:
        """
        注册缓存任务

        Args:
            task: 缓存任务实例
        """
        if task.name in self.tasks:
            logger.warning(f"[Scheduler] 任务 {task.name} 已存在，将被覆盖")

        self.tasks[task.name] = task
        logger.info(f"[Scheduler] 注册任务: {task.name}")

        # 如果已启动且任务有刷新间隔，添加定时任务
        if self._started and task.refresh_interval > 0:
            self._add_job(task)

    def _add_job(self, task: CacheTask) -> None:
        """添加定时任务到调度器"""
        job_id = f"cache_task_{task.name}"

        # 移除已存在的任务
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        # 添加新任务
        trigger: Union[CronTrigger, IntervalTrigger]
        if task.refresh_interval >= 86400:  # >= 1天使用 cron
            # 每天凌晨 2 点执行
            trigger = CronTrigger(hour=2, minute=0)
        else:
            trigger = IntervalTrigger(seconds=task.refresh_interval)

        self.scheduler.add_job(
            self._run_task,
            trigger=trigger,
            id=job_id,
            args=[task.name],
            replace_existing=True,
        )
        logger.info(f"[Scheduler] 添加定时任务: {task.name}, 间隔: {task.refresh_interval}秒")

    async def _run_task(self, task_name: str) -> None:
        """执行单个任务"""
        task = self.tasks.get(task_name)
        if not task:
            logger.warning(f"[Scheduler] 任务不存在: {task_name}")
            return

        try:
            logger.info(f"[Scheduler] 开始执行任务: {task_name}")

            # 获取数据
            data = await task.fetch_data()
            if data is None:
                logger.warning(f"[Scheduler] 任务 {task_name} 返回空数据")
                return

            # 转换数据
            data = task.transform_data(data)

            # 计算数据量
            count = len(data) if isinstance(data, (list, dict)) else 1

            # 存储到 Redis
            await self._store_to_redis(task, data)

            # 持久化到数据库
            if task.persist_to_db:
                await self._store_to_db(task, data)

            # 回调
            await task.on_refresh_success(data, count)

        except Exception as e:
            await task.on_refresh_error(e)

    async def _store_to_redis(self, task: CacheTask, data: Any) -> None:
        """存储数据到 Redis"""
        try:
            from apps.api.api.cache.unified import get_cache

            cache = get_cache()
            cache.set(task.cache_key, data, ttl=task.cache_ttl)
            logger.debug(f"[Scheduler] Redis 存储成功: {task.cache_key}")
        except Exception as e:
            logger.error(f"[Scheduler] Redis 存储失败: {e}")

    async def _store_to_db(self, task: CacheTask, data: Any) -> None:
        """持久化数据到数据库"""
        try:
            from core.core.scheduler.storage.db_store import DBStore

            db_store = DBStore()
            records = task.get_db_records(data)
            if records:
                await db_store.save_records(task.name, records)
                logger.debug(f"[Scheduler] DB 持久化成功: {task.name}, {len(records)} 条")
        except Exception as e:
            logger.error(f"[Scheduler] DB 持久化失败: {e}")

    async def start(self) -> None:
        """启动调度器"""
        if self._started:
            return

        logger.info("[Scheduler] 启动调度器...")

        # 为所有任务添加定时任务
        for task in self.tasks.values():
            if task.refresh_interval > 0:
                self._add_job(task)

        # 启动 APScheduler
        self.scheduler.start()
        self._started = True

        logger.info(f"[Scheduler] 调度器已启动, 共 {len(self.tasks)} 个任务")

    async def check_and_refresh_stale(self) -> None:
        """
        检查并刷新过期的缓存任务

        适用于：系统在非凌晨启动时，检查上次刷新是否已过期
        """
        logger.info("[Scheduler] 检查过期缓存...")

        for task in self.tasks.values():
            needs_refresh = False
            reason = ""

            # 检查是否有上次刷新记录
            if task.last_refresh is None:
                # 没有刷新记录，需要刷新
                needs_refresh = True
                reason = "无刷新记录"
            elif task.refresh_interval > 0:
                # 检查是否超过刷新间隔
                elapsed = (datetime.now() - task.last_refresh).total_seconds()
                if elapsed > task.refresh_interval:
                    needs_refresh = True
                    reason = f"已过期 {elapsed/3600:.1f} 小时"

            # 也检查 Redis 缓存是否存在
            if not needs_refresh:
                try:
                    from apps.api.api.cache.unified import get_cache

                    cache = get_cache()
                    if cache.get(task.cache_key) is None:
                        needs_refresh = True
                        reason = "Redis 缓存不存在"
                except Exception:
                    pass

            if needs_refresh:
                logger.info(f"[Scheduler] 任务 {task.name} 需要刷新: {reason}")
                asyncio.create_task(self._run_task(task.name))

    async def stop(self) -> None:
        """停止调度器"""
        if not self._started:
            return

        self.scheduler.shutdown()
        self._started = False
        logger.info("[Scheduler] 调度器已停止")

    async def refresh_task(self, task_name: str) -> bool:
        """立即刷新指定任务"""
        if task_name not in self.tasks:
            logger.warning(f"[Scheduler] 任务不存在: {task_name}")
            return False

        await self._run_task(task_name)
        return True

    async def refresh_all(self) -> None:
        """刷新所有任务"""
        logger.info(f"[Scheduler] 刷新所有任务 ({len(self.tasks)} 个)")
        for task_name in self.tasks:
            await self._run_task(task_name)

    async def restore_from_db(self) -> None:
        """从数据库恢复缓存"""
        logger.info("[Scheduler] 从数据库恢复缓存...")
        try:
            from core.core.scheduler.storage.db_store import DBStore

            from apps.api.api.cache.unified import get_cache

            db_store = DBStore()
            cache = get_cache()

            for task in self.tasks.values():
                if task.persist_to_db:
                    data = await db_store.load_records(task.name)
                    if data:
                        cache.set(task.cache_key, data, ttl=task.cache_ttl)

                        # 获取并设置最后更新时间（用于过期检查）
                        last_update = await db_store.get_last_update_time(task.name)
                        if last_update:
                            task.last_refresh = last_update
                            task.data_count = len(data) if isinstance(data, list) else 1

                        logger.info(
                            f"[Scheduler] 恢复缓存: {task.name}, {len(data)} 条, 更新于 {last_update}"
                        )
        except Exception as e:
            logger.error(f"[Scheduler] 恢复缓存失败: {e}")

    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        return {
            "started": self._started,
            "task_count": len(self.tasks),
            "tasks": {name: task.get_status() for name, task in self.tasks.items()},
        }


# 全局调度器实例
_scheduler_instance: Optional[CacheScheduler] = None


def get_scheduler() -> CacheScheduler:
    """获取全局调度器实例"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = CacheScheduler()
    return _scheduler_instance
