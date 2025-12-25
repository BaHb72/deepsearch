"""
数据同步管道初始化模块

负责创建和配置 DataSyncPipeline，注册所有数据源。
供 AnalyticsComponent 使用。
"""

from typing import Any, Optional, TYPE_CHECKING

from deepsearch.observability import get_logger

if TYPE_CHECKING:
    from deepsearch.infrastructure.persistence.duckdb_analytics import DuckDBAnalytics
    from deepsearch.core.components.data_components import DatabaseComponent
    from .data_sync_pipeline import DataSyncPipeline

logger = get_logger(__name__)


def create_sync_pipeline(
    target_db: "DuckDBAnalytics",
    database_component: Optional["DatabaseComponent"] = None,
    amazingdata_client: Optional[Any] = None,
) -> "DataSyncPipeline":
    """创建并配置数据同步管道
    
    Args:
        target_db: 目标数据库（DuckDB）
        database_component: PostgreSQL 数据库组件
        amazingdata_client: AmazingData 客户端
        
    Returns:
        配置好的 DataSyncPipeline 实例
    """
    from .data_sync_pipeline import DataSyncPipeline
    from .sync_fetchers import (
        PostgreSQLFetcher,
        AmazingDataFetcher,
        AkShareFetcher,
    )
    
    pipeline = DataSyncPipeline(target_db)
    
    # 注册 PostgreSQL 数据源（如果可用）
    if database_component and database_component.is_connected():
        pg_fetcher = PostgreSQLFetcher(database_component)
        pipeline.register(
            name="postgresql",
            fetcher=pg_fetcher.fetch,
            field_map=PostgreSQLFetcher.get_field_map("kline_history"),
            priority=5,  # 中等优先级
        )
        logger.info("已注册 PostgreSQL 数据源")
    
    # 注册 AmazingData 数据源（如果可用）
    if amazingdata_client:
        ad_fetcher = AmazingDataFetcher(amazingdata_client)
        pipeline.register(
            name="amazingdata",
            fetcher=ad_fetcher.fetch,
            field_map=AmazingDataFetcher.get_field_map("kline_history"),
            priority=10,  # 高优先级
        )
        logger.info("已注册 AmazingData 数据源")
    
    # 注册 AkShare 数据源（作为补充）
    try:
        ak_fetcher = AkShareFetcher()
        if ak_fetcher._ak:  # 检查 akshare 是否已安装
            pipeline.register(
                name="akshare",
                fetcher=ak_fetcher.fetch,
                field_map=AkShareFetcher.get_field_map("kline_history"),
                priority=1,  # 低优先级，用于补充
            )
            logger.info("已注册 AkShare 数据源")
    except Exception as e:
        logger.debug(f"AkShare 注册失败（可选）: {e}")
    
    return pipeline


async def run_initial_sync(
    pipeline: "DataSyncPipeline",
    tables: Optional[list] = None,
) -> dict:
    """运行初始同步
    
    Args:
        pipeline: 数据同步管道
        tables: 要同步的表列表，默认 ["kline_history", "stock_info"]
        
    Returns:
        同步结果
    """
    tables = tables or ["kline_history", "stock_info"]
    all_results = {}
    
    for table in tables:
        try:
            results = await pipeline.sync(table)
            all_results[table] = results
            
            total = sum(r.rows_synced for r in results.values())
            logger.info(f"表 {table} 同步完成: {total} 行")
            
        except Exception as e:
            logger.error(f"表 {table} 同步失败: {e}")
            all_results[table] = {"error": str(e)}
    
    return all_results
