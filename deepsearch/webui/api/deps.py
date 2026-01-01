"""
FastAPI 依赖注入模块

提供数据库会话、组件和服务的依赖注入函数，
遵循最佳实践确保资源在正确的事件循环中初始化。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from fastapi import Depends, HTTPException

if TYPE_CHECKING:
    from deepsearch.application.services.data_sources import DataSourceIngestionService
    from deepsearch.core.components.data_components import DatabaseComponent
    from deepsearch.infrastructure.persistence.database import DatabaseService


async def get_database_component() -> "DatabaseComponent":
    """
    获取数据库组件。

    通过 RuntimeContext 获取已初始化的数据库组件。
    支持两种初始化路径：
    1. 完整引擎模式：通过 ComponentManager 获取组件
    2. Lifespan 模式：通过 override_component 注入的组件

    Yields:
        DatabaseComponent: 数据库组件实例

    Raises:
        HTTPException: 如果数据库组件不可用
    """
    from deepsearch.core.components.data_components import DatabaseComponent
    from deepsearch.core.runtime.context import get_context

    try:
        context = get_context()

        # 尝试获取数据库组件（支持 override 和 component_manager 两种路径）
        try:
            component = context.get_component("database")
        except (RuntimeError, ValueError):
            # get_component 会在 _component_manager 未设置且无 override 时抛出异常
            raise HTTPException(status_code=503, detail="服务尚未完全启动，请稍后重试")

        if not isinstance(component, DatabaseComponent):
            raise HTTPException(status_code=503, detail="数据库组件未初始化")

        if not component.is_connected():
            raise HTTPException(status_code=503, detail="数据库未连接")

        return component

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"无法获取数据库组件: {e}")


async def get_database_service(
    db_component: "DatabaseComponent" = Depends(get_database_component),
) -> "DatabaseService":
    """
    获取数据库服务。

    基于数据库组件创建 DatabaseService 实例。

    Args:
        db_component: 数据库组件（通过依赖注入获取）

    Returns:
        DatabaseService: 数据库服务实例
    """
    from deepsearch.infrastructure.persistence.database import DatabaseService

    return DatabaseService(db_component)


async def get_ingestion_service(
    db_service: "DatabaseService" = Depends(get_database_service),
) -> "DataSourceIngestionService":
    """
    获取数据源取数服务。

    使用依赖注入的数据库服务创建 DataSourceIngestionService。
    每个请求获取独立的服务实例，避免跨请求的状态污染。

    Args:
        db_service: 数据库服务（通过依赖注入获取）

    Returns:
        DataSourceIngestionService: 数据源取数服务实例
    """
    from deepsearch.application.services.data_sources import DataSourceIngestionService
    from deepsearch.infrastructure.persistence.ingestion_records import DataSourceRecordPersistence

    record_store = DataSourceRecordPersistence(db_service)
    return DataSourceIngestionService(record_store=record_store)


async def get_optional_ingestion_service() -> Optional["DataSourceIngestionService"]:
    """
    获取可选的数据源取数服务（用于不需要强制数据库连接的端点）。

    优先使用 lifespan 中初始化的数据库组件（绑定到正确的事件循环）。
    如果数据库不可用，返回 None 而不是抛出异常。

    Returns:
        DataSourceIngestionService | None: 服务实例或 None
    """

    from deepsearch.application.services.data_sources import DataSourceIngestionService
    from deepsearch.infrastructure.persistence.database import DatabaseService
    from deepsearch.infrastructure.persistence.ingestion_records import DataSourceRecordPersistence

    try:
        # 方法1：尝试通过 app.state 获取 lifespan 初始化的服务
        # 这需要在请求上下文中，暂时跳过直接使用 RuntimeContext

        # 方法2：通过 RuntimeContext 获取（兼容旧方式）
        from deepsearch.core.components.data_components import DatabaseComponent
        from deepsearch.core.runtime.context import get_context

        context = get_context()

        # 尝试获取数据库组件（支持 override 和 component_manager 两种路径）
        try:
            component = context.get_component("database")
        except (RuntimeError, ValueError):
            return None

        if not isinstance(component, DatabaseComponent) or not component.is_connected():
            return None

        db_service = DatabaseService(component)
        record_store = DataSourceRecordPersistence(db_service)
        return DataSourceIngestionService(record_store=record_store)

    except RuntimeError as e:
        # 捕获事件循环相关错误
        if "Event loop is closed" in str(e):
            return None
        raise
    except Exception:
        return None


__all__ = [
    "get_database_component",
    "get_database_service",
    "get_ingestion_service",
    "get_optional_ingestion_service",
]
