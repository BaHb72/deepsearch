"""分析组件模块，负责 DuckDB 数据分析与同步。"""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional

from deepsearch.config import get_config
from deepsearch.config.models.database import AnalyticsDatabaseConfig
from ..async_component import AsyncComponent
from ..interfaces import ComponentType
from ..utils.exceptions import error_context
from ..utils.timeout_config import TimeoutCategory, get_timeout_manager

if TYPE_CHECKING:  # pragma: no cover - 仅用于类型检查
    from deepsearch.infrastructure.persistence.duckdb_analytics import DuckDBAnalytics
    from deepsearch.infrastructure.providers.managers.data_sync_service import DataSyncService
    from deepsearch.infrastructure.providers.managers.data_sync_pipeline import DataSyncPipeline
    from .data_components import DatabaseComponent


class AnalyticsComponent(AsyncComponent):
    """分析组件 - DuckDB数据分析"""

    def __init__(self):
        super().__init__("analytics", ComponentType.INFRASTRUCTURE, "数据分析")
        self._analytics_db: DuckDBAnalytics | None = None
        self._sync_service: DataSyncService | None = None
        self._sync_pipeline: DataSyncPipeline | None = None  # 新版简化管道
        self._database_component: DatabaseComponent | None = None
        self._config: AnalyticsDatabaseConfig | None = None
        self._timeout_manager = get_timeout_manager()
        self._auto_sync_pending: bool = False

    async def _do_initialize(self) -> None:
        """初始化分析组件"""
        from deepsearch.infrastructure.persistence.duckdb_analytics import get_analytics_db
        from deepsearch.infrastructure.providers.managers.data_sync_service import get_sync_service
        from deepsearch.infrastructure.providers.managers.pipeline_setup import create_sync_pipeline


        with error_context(self.name, "initialize"):
            # 获取配置
            config = get_config()
            analytics_config = (
                config.database.analytics if config and config.database else None
            )
            self._config = analytics_config

            if True: # Force disable for now
                self._logger.info("分析数据库强制已禁用")
                return

            if not analytics_config or not analytics_config.enabled:
                self._logger.info("分析数据库已禁用")
                return

            # 使用超时控制初始化 DuckDB
            init_timeout = self._timeout_manager.get_timeout(TimeoutCategory.DB_CONNECT)
            try:

                async def _init_db():
                    # 初始化 DuckDB
                    self._analytics_db = get_analytics_db(
                        db_path=analytics_config.path,
                        memory_limit=analytics_config.memory_limit,
                        threads=analytics_config.threads,
                    )

                    # 初始化表结构
                    await self._analytics_db.init_tables()

                await asyncio.wait_for(_init_db(), timeout=init_timeout)
            except asyncio.TimeoutError:
                raise RuntimeError(
                    f"Analytics DB initialization timeout after {init_timeout} seconds"
                )

            # 初始化同步服务
            self._auto_sync_pending = False
            if analytics_config.auto_sync:
                # 创建新版简化管道
                self._sync_pipeline = create_sync_pipeline(
                    target_db=self._analytics_db,
                    database_component=self._database_component,
                )
                self._logger.info(
                    "数据同步管道已初始化，已注册数据源: %s",
                    self._sync_pipeline.sources,
                )
                
                # 保留旧版服务用于兼容（将在后续版本移除）
                self._sync_service = get_sync_service(self._database_component)
                self._sync_service.sync_interval = analytics_config.sync_interval
                # 将 DuckDB 实例注入同步服务
                self._sync_service.set_analytics_db(self._analytics_db)
                if self._database_component:
                    self._sync_service.set_database_component(self._database_component)
                    await self._sync_service.start()
                    self._logger.info(
                        "数据同步服务已启动，间隔: %s秒",
                        analytics_config.sync_interval,
                    )
                else:
                    self._auto_sync_pending = True
                    self._logger.info(
                        "自动同步服务暂未启动，因未配置数据库组件，将在组件注入后再尝试"
                    )

            self._instance = self
            self._logger.info("分析组件初始化完成")

    def set_database_component(self, database_component: DatabaseComponent | None) -> None:
        """设置数据库组件（用于数据同步）"""
        self._database_component = database_component
        if self._sync_service and database_component:
            self._sync_service.set_database_component(database_component)
            if self._auto_sync_pending and not getattr(self._sync_service, "_running", False):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    return

                async def _start_sync_service() -> None:
                    sync_service = self._sync_service
                    if sync_service is None or getattr(sync_service, "_running", False):
                        return
                    await sync_service.start()
                    if self._config:
                        self._logger.info(
                            "数据同步服务已启动，间隔: %s秒",
                            self._config.sync_interval,
                        )

                loop.create_task(_start_sync_service())
                self._auto_sync_pending = False

    async def _do_start(self) -> None:
        """启动分析组件"""
        with error_context(self.name, "start"):
            if not self._config or not self._config.enabled:
                return

            # 使用超时控制启动
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_START)
            try:

                async def _start_analytics():
                    if self._auto_sync_pending and self._sync_service:
                        sync_service = self._sync_service
                        if self._database_component and sync_service is not None:
                            sync_service.set_database_component(self._database_component)
                            if not getattr(sync_service, "_running", False):
                                await sync_service.start()
                                if self._config:
                                    self._logger.info(
                                        "数据同步服务已启动，间隔: %s秒",
                                        self._config.sync_interval,
                                    )
                            self._auto_sync_pending = False
                        else:
                            self._logger.warning(
                                "自动同步已启用，但尚未配置数据库组件，将继续等待注入"
                            )
                    # 启动阶段的自检逻辑占位
                    self._logger.info("分析组件启动")

                await asyncio.wait_for(_start_analytics(), timeout=timeout)
            except asyncio.TimeoutError:
                self._logger.warning(f"Analytics start timeout after {timeout} seconds")

    async def _do_stop(self) -> None:
        """停止分析组件"""
        with error_context(self.name, "stop"):
            stop_timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_STOP)

            try:

                async def _stop_analytics():
                    # 停止同步服务
                    if self._sync_service:
                        await self._sync_service.stop()

                    # 关闭 DuckDB 连接
                    if self._analytics_db:
                        await self._analytics_db.close()

                    self._logger.info("分析组件已停止")

                await asyncio.wait_for(_stop_analytics(), timeout=stop_timeout)
            except asyncio.TimeoutError:
                self._logger.warning(f"Analytics stop timeout after {stop_timeout} seconds")

    def _health_check(self) -> bool:
        """检查分析组件健康状态"""
        if not self._config or not self._config.enabled:
            return True  # 禁用状态下认为是健康的

        return self._analytics_db is not None

    async def health_check_async(self) -> bool:
        """异步健康检查（带超时）"""
        timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_HEALTH)
        try:

            async def _check():
                if not self._config or not self._config.enabled:
                    return True

                if not self._analytics_db:
                    return False

                # 执行简单查询测试连接
                if hasattr(self._analytics_db, "execute"):
                    await self._analytics_db.execute("SELECT 1")
                    return True

                return self._health_check()

            return await asyncio.wait_for(_check(), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning(f"Health check timeout after {timeout} seconds")
            return False
        except Exception as e:
            self._logger.error(f"Health check failed: {e}")
            return False

    def _get_extra_status_info(self) -> Dict[str, Any]:
        """提供额外的状态信息"""
        if not self._config:
            return {"enabled": False}

        info = {
            "enabled": self._config.enabled,
            "path": self._config.path,
            "memory_limit": self._config.memory_limit,
            "threads": self._config.threads,
            "auto_sync": self._config.auto_sync,
        }

        if self._sync_service:
            info["sync_interval"] = self._config.sync_interval
            info["sync_running"] = getattr(self._sync_service, "_running", False)
        
        # 新版管道信息
        if self._sync_pipeline:
            info["pipeline_sources"] = self._sync_pipeline.sources
            info["pipeline_states"] = {
                k: {
                    "last_timestamp": str(v.last_timestamp) if v.last_timestamp else None,
                    "rows_synced": v.rows_synced,
                }
                for k, v in self._sync_pipeline.get_all_states().items()
            }

        return info
    
    @property
    def sync_pipeline(self) -> "DataSyncPipeline | None":
        """获取数据同步管道实例"""
        return self._sync_pipeline
    
    async def sync_data(
        self,
        table: str = "kline_history",
        sources: list | None = None,
        force_full: bool = False,
    ) -> dict:
        """使用新管道同步数据
        
        Args:
            table: 目标表名
            sources: 数据源列表，None 表示全部
            force_full: 是否强制全量同步
            
        Returns:
            同步结果字典
        """
        if not self._sync_pipeline:
            self._logger.warning("数据同步管道未初始化")
            return {"error": "Pipeline not initialized"}
        
        try:
            results = await self._sync_pipeline.sync(
                table=table,
                sources=sources,
                force_full=force_full,
            )
            return {
                source: {
                    "rows_synced": r.rows_synced,
                    "duration_ms": r.duration_ms,
                    "success": r.success,
                    "error": r.error,
                }
                for source, r in results.items()
            }
        except Exception as e:
            self._logger.error(f"数据同步失败: {e}", exc_info=True)
            return {"error": str(e)}

    def _normalize_statistics(self, result: Any) -> Dict[str, Any]:
        """将统计结果规范化为字典，避免向外暴露 Any。"""

        if isinstance(result, dict):
            return result
        if isinstance(result, Mapping):
            return dict(result)
        if result is None:
            return {}

        self._logger.debug("未识别的统计结果类型: %s", type(result).__name__)
        return {"value": result}

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self._analytics_db and hasattr(self._analytics_db, "get_statistics"):

            stats_method = self._analytics_db.get_statistics

            # 检查是否是协程函数
            if inspect.iscoroutinefunction(stats_method):
                try:
                    # 尝试获取当前事件循环
                    asyncio.get_running_loop()
                    # 在异步环境中，使用线程池避免阻塞
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        # 使用 lambda 包装以正确处理协程
                        future = executor.submit(lambda: asyncio.run(stats_method()))
                        return self._normalize_statistics(future.result())
                except RuntimeError:
                    # 不在异步环境中，直接运行
                    return self._normalize_statistics(asyncio.run(stats_method()))
            else:
                # 同步方法，直接调用
                return self._normalize_statistics(stats_method())
        return {}

    async def get_statistics_async(self) -> Dict[str, Any]:
        """异步获取统计信息（包含超时处理）"""
        if not self._analytics_db or not hasattr(self._analytics_db, "get_statistics"):
            return {}

        stats_callable = getattr(self._analytics_db, "get_statistics")
        timeout = self._timeout_manager.get_timeout(TimeoutCategory.DB_QUERY)

        try:
            if inspect.iscoroutinefunction(stats_callable):
                result = await asyncio.wait_for(stats_callable(), timeout=timeout)
            else:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, stats_callable), timeout=timeout
                )
                if inspect.isawaitable(result):
                    result = await asyncio.wait_for(result, timeout=timeout)
            return self._normalize_statistics(result)
        except asyncio.TimeoutError:
            self._logger.warning(f"Get statistics timeout after {timeout} seconds")
            return {"error": "Timeout getting statistics"}
        except Exception as e:
            self._logger.error(f"Failed to get statistics: {e}")
            return {"error": str(e)}

    async def execute_query(
        self, query: str, params: Optional[Mapping[str, Any]] = None
    ) -> Any:
        """执行分析查询（带超时）"""
        if not self._analytics_db:
            raise RuntimeError("Analytics DB not initialized")

        # 根据查询类型选择超时
        is_complex = any(
            keyword in query.upper() for keyword in ["JOIN", "GROUP BY", "ORDER BY", "UNION"]
        )
        timeout = self._timeout_manager.get_timeout(
            TimeoutCategory.DB_TRANSACTION if is_complex else TimeoutCategory.DB_QUERY
        )

        try:

            async def _execute():
                if hasattr(self._analytics_db, "execute"):
                    return await self._analytics_db.execute(query, params)
                else:
                    raise RuntimeError("Analytics DB does not support execute")

            return await asyncio.wait_for(_execute(), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Query execution timeout after {timeout} seconds")

    def get_instance(self) -> Optional[Any]:
        """获取DuckDB实例（供其他组件使用）"""
        return self._analytics_db

    async def sync_now(self) -> Dict[str, Any]:
        """手动触发数据同步（带超时）- 使用旧版同步服务"""
        if not self._sync_service:
            return {"error": "Sync service not initialized"}

        timeout = self._timeout_manager.get_timeout(TimeoutCategory.DB_TRANSACTION)
        try:

            async def _sync():
                if hasattr(self._sync_service, "sync_now"):
                    return await self._sync_service.sync_now()
                else:
                    return {"error": "Sync service does not support manual sync"}

            return await asyncio.wait_for(_sync(), timeout=timeout)
        except asyncio.TimeoutError:
            return {"error": f"Sync timeout after {timeout} seconds"}
        except Exception as e:
            self._logger.error(f"Data sync failed: {e}")
            return {"error": str(e)}
