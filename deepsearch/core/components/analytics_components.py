"""
分析组件模块

负责DuckDB数据分析和数据同步
从原unified_components.py拆分而来
"""
import asyncio
import concurrent.futures
from typing import Optional, Dict, Any

from deepsearch.config import get_config
from ..async_component import AsyncComponent
from ..utils.exceptions import error_context
from ..interfaces import ComponentType
from ..utils.timeout_config import TimeoutManager, TimeoutCategory


class AnalyticsComponent(AsyncComponent):
    """分析组件 - DuckDB数据分析"""

    def __init__(self):
        super().__init__("analytics", ComponentType.INFRASTRUCTURE, "数据分析")
        self._analytics_db = None
        self._sync_service = None
        self._database_component = None
        self._config = None
        self._timeout_manager = TimeoutManager()

    async def _do_initialize(self) -> None:
        """初始化分析组件"""
        from deepsearch.infrastructure.persistence.duckdb_analytics import get_analytics_db
        from deepsearch.infrastructure.providers.managers.data_sync_service import get_sync_service

        with error_context(self.name, "initialize"):
            # 获取配置
            config = get_config()
            analytics_config = config.database.analytics if config and config.database else None
            self._config = analytics_config

            if not analytics_config.enabled:
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
                        threads=analytics_config.threads
                    )

                    # 初始化表结构
                    await self._analytics_db.init_tables()

                await asyncio.wait_for(_init_db(), timeout=init_timeout)
            except asyncio.TimeoutError:
                raise RuntimeError(f"Analytics DB initialization timeout after {init_timeout} seconds")

            # 初始化同步服务
            if analytics_config.auto_sync:
                self._sync_service = get_sync_service(self._database_component)
                self._sync_service.sync_interval = analytics_config.sync_interval
                # 设置DuckDB实例到同步服务
                self._sync_service.set_analytics_db(self._analytics_db)
                await self._sync_service.start()
                self._logger.info(f"数据同步服务已启动，同步间隔: {analytics_config.sync_interval}秒")

            self._instance = self
            self._logger.info("分析组件初始化完成")

    def set_database_component(self, database_component):
        """设置数据库组件（用于数据同步）"""
        self._database_component = database_component

    async def _do_start(self) -> None:
        """启动分析组件"""
        with error_context(self.name, "start"):
            if not self._config or not self._config.enabled:
                return

            # 使用超时控制启动
            timeout = self._timeout_manager.get_timeout(TimeoutCategory.COMPONENT_START)
            try:
                async def _start_analytics():
                    # 如果有额外的启动逻辑，在这里添加
                    self._logger.info("分析组件已启动")

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
                if hasattr(self._analytics_db, 'execute'):
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
            "auto_sync": self._config.auto_sync
        }

        if self._sync_service:
            info["sync_interval"] = self._config.sync_interval
            info["sync_running"] = getattr(self._sync_service, '_running', False)

        return info

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if self._analytics_db and hasattr(self._analytics_db, 'get_statistics'):
            import inspect
            stats_method = self._analytics_db.get_statistics

            # 检查是否是协程函数
            if inspect.iscoroutinefunction(stats_method):
                try:
                    # 尝试获取当前事件循环
                    loop = asyncio.get_running_loop()
                    # 在异步环境中，使用线程池避免阻塞
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        # 使用 lambda 包装以正确处理协程
                        future = executor.submit(lambda: asyncio.run(stats_method()))
                        return future.result()
                except RuntimeError:
                    # 不在异步环境中，直接运行
                    return asyncio.run(stats_method())
            else:
                # 同步方法，直接调用
                return stats_method()
        return {}

    async def get_statistics_async(self) -> Dict[str, Any]:
        """异步获取统计信息（带超时）"""
        if not self._analytics_db or not hasattr(self._analytics_db, 'get_statistics'):
            return {}

        timeout = self._timeout_manager.get_timeout(TimeoutCategory.DB_QUERY)
        try:
            return await asyncio.wait_for(
                self._analytics_db.get_statistics(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            self._logger.warning(f"Get statistics timeout after {timeout} seconds")
            return {"error": "Timeout getting statistics"}
        except Exception as e:
            self._logger.error(f"Failed to get statistics: {e}")
            return {"error": str(e)}

    async def execute_query(self, query: str, params: Optional[Dict] = None) -> Any:
        """执行分析查询（带超时）"""
        if not self._analytics_db:
            raise RuntimeError("Analytics DB not initialized")

        # 根据查询类型选择超时
        is_complex = any(keyword in query.upper() for keyword in ['JOIN', 'GROUP BY', 'ORDER BY', 'UNION'])
        timeout = self._timeout_manager.get_timeout(
            TimeoutCategory.DB_TRANSACTION if is_complex else TimeoutCategory.DB_QUERY
        )

        try:
            async def _execute():
                if hasattr(self._analytics_db, 'execute'):
                    return await self._analytics_db.execute(query, params)
                else:
                    raise RuntimeError("Analytics DB does not support execute")

            return await asyncio.wait_for(_execute(), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Query execution timeout after {timeout} seconds")

    def get_instance(self) -> Optional[Any]:
        """获取DuckDB实例（供其他组件使用）"""
        return self._analytics_db

    async def sync_data(self) -> Dict[str, Any]:
        """手动触发数据同步（带超时）"""
        if not self._sync_service:
            return {"error": "Sync service not initialized"}

        timeout = self._timeout_manager.get_timeout(TimeoutCategory.DB_TRANSACTION)
        try:
            async def _sync():
                if hasattr(self._sync_service, 'sync_now'):
                    return await self._sync_service.sync_now()
                else:
                    return {"error": "Sync service does not support manual sync"}

            return await asyncio.wait_for(_sync(), timeout=timeout)
        except asyncio.TimeoutError:
            return {"error": f"Sync timeout after {timeout} seconds"}
        except Exception as e:
            self._logger.error(f"Data sync failed: {e}")
            return {"error": str(e)}