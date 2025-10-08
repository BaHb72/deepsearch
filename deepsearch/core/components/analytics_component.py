"""
分析组件

管理 DuckDB 分析数据库的生命周期
"""

import inspect
from typing import Any, Dict, Optional

from loguru import logger

from deepsearch.config import get_config
from deepsearch.infrastructure.persistence.duckdb_analytics import DuckDBAnalytics, get_analytics_db
from deepsearch.infrastructure.providers.managers.data_sync_service import (
    DataSyncService,
    get_sync_service,
)

from ..async_component import AsyncComponent


class AnalyticsComponent(AsyncComponent):
    """DuckDB 分析组件"""

    def __init__(self, database_component=None):
        """
        初始化分析组件

        Args:
            database_component: 主数据库组件（用于数据同步）
        """
        from ..interfaces import ComponentType

        super().__init__("Analytics", ComponentType.SUPPORTING)
        self.config = get_config()
        self.analytics_config = self.config.database.analytics

        self.analytics_db: Optional[DuckDBAnalytics] = None
        self.sync_service: Optional[DataSyncService] = None
        self.database_component = database_component

        # 同步任务
        self._sync_task = None

    async def _do_initialize(self) -> Optional[Any]:
        """初始化组件"""
        # 初始化逻辑移到 _do_start 中
        return None

    async def _do_start(self):
        """启动组件"""
        if not self.analytics_config.enabled:
            logger.info("分析数据库已禁用")
            self._state_manager.state.metadata["status"] = "disabled"
            return

        try:
            logger.info("正在启动分析组件...")

            # 初始化 DuckDB
            self.analytics_db = get_analytics_db(
                db_path=self.analytics_config.path,
                memory_limit=self.analytics_config.memory_limit,
                threads=self.analytics_config.threads,
            )

            # 初始化表结构
            await self.analytics_db.init_tables()

            # 初始化同步服务
            if self.analytics_config.auto_sync:
                self.sync_service = get_sync_service(self.database_component)
                self.sync_service.sync_interval = self.analytics_config.sync_interval
                # 设置DuckDB实例到同步服务
                self.sync_service.set_analytics_db(self.analytics_db)
                await self.sync_service.start()
                logger.info(
                    f"数据同步服务已启动，同步间隔: {self.analytics_config.sync_interval}秒"
                )

            logger.info("分析组件启动成功")

        except Exception as e:
            logger.error(f"分析组件启动失败: {e}")
            self._state_manager.state.error_message = str(e)
            raise

    async def _do_stop(self):
        """停止组件"""
        logger.info("开始停止分析组件...")

        try:
            # 停止同步服务
            if self.sync_service:
                await self.sync_service.stop()

            # 关闭 DuckDB 连接
            if self.analytics_db:
                await self.analytics_db.close()

            logger.info("分析组件已停止")

        except Exception as e:
            logger.error(f"分析组件停止失败: {e}")
            self._state_manager.state.error_message = str(e)

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        if not self.analytics_config.enabled:
            return {"healthy": True, "status": "disabled", "message": "分析数据库已禁用"}

        try:
            if self.analytics_db:
                stats_result = self.analytics_db.get_statistics()
                if inspect.isawaitable(stats_result):
                    stats = await stats_result
                else:
                    stats = stats_result

                # 检查同步状态
                sync_status = None
                if self.sync_service:
                    sync_status = await self.sync_service.get_sync_status()

                return {
                    "healthy": True,
                    "status": self.status.value,
                    "database": {
                        "path": self.analytics_config.path,
                        "memory_limit": self.analytics_config.memory_limit,
                        "threads": self.analytics_config.threads,
                        "statistics": stats,
                    },
                    "sync": sync_status,
                }
            else:
                return {
                    "healthy": False,
                    "status": self.status.value,
                    "error": "分析数据库未初始化",
                }

        except Exception as e:
            logger.error(f"分析组件健康检查失败: {e}")
            return {"healthy": False, "status": "error", "error": str(e)}

    async def trigger_sync(self, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """
        手动触发数据同步

        Args:
            start_date: 开始日期
            end_date: 结束日期
        """
        if not self.sync_service:
            raise RuntimeError("同步服务未启动")

        await self.sync_service.sync_historical_data(start_date, end_date)

    async def optimize(self):
        """优化数据库"""
        if self.analytics_db:
            # 执行VACUUM和ANALYZE操作
            if hasattr(self.analytics_db, "conn"):
                self.analytics_db.conn.execute("PRAGMA optimize")
            logger.info("分析数据库优化完成")

    async def clean_old_data(self, days_to_keep: int = 365):
        """
        清理旧数据

        Args:
            days_to_keep: 保留天数
        """
        if self.analytics_db:
            from datetime import datetime, timedelta

            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime("%Y-%m-%d")
            # 清理K线历史数据
            await self.analytics_db.query(
                "DELETE FROM kline_history WHERE time < ?", (cutoff_date,)
            )
            logger.info(f"已清理 {days_to_keep} 天前的数据")

    def get_dependencies(self) -> list:
        """获取组件依赖"""
        # 分析组件依赖数据库组件（用于数据同步）
        return ["Database"]
