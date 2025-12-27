"""
FastAPI 依赖注入

提供 FastAPI 应用的依赖注入功能。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, HTTPException, status

from deepsearch.core.interfaces.component import Component, ComponentStatus
from deepsearch.core.managers.component_manager import ComponentManager
from deepsearch.core.runtime.context import ApplicationContext, get_context
from deepsearch.core.runtime.engine import MainEngine
from deepsearch.infrastructure.notifications import NotificationService

if TYPE_CHECKING:
    from deepsearch.webui.server import WebSocketManager


def get_app_context() -> ApplicationContext:
    """
    获取应用上下文依赖

    Returns:
        应用上下文实例
    """
    return get_context()


def get_engine(context: ApplicationContext = Depends(get_app_context)) -> MainEngine:
    """
    获取引擎依赖

    Args:
        context: 应用上下文

    Returns:
        MainEngine 实例

    Raises:
        HTTPException: 如果引擎未初始化
    """
    try:
        return context.get_engine()
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="系统引擎未初始化"
        )


def get_engine_optional(
    context: ApplicationContext = Depends(get_app_context),
) -> MainEngine | None:
    """
    获取可选引擎依赖：当引擎未初始化时返回 None，而不是抛出 503。

    用于允许系统信息等端点在引擎未就绪时也能返回降级信息。
    """
    try:
        return context.get_engine()
    except RuntimeError:
        return None


def get_component_manager(engine: MainEngine = Depends(get_engine)) -> ComponentManager:
    """
    获取组件管理器依赖

    Args:
        engine: 主引擎

    Returns:
        ComponentManager 实例
    """
    try:
        return engine.get_component_manager()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="���������δ��ʼ��",
        ) from exc


def get_component(component_name: str):
    """
    创建获取特定组件的依赖函数

    Args:
        component_name: 组件名称

    Returns:
        依赖函数
    """

    def _get_component(manager: ComponentManager = Depends(get_component_manager)) -> Component:
        if not manager.has_component(component_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"组件 {component_name} 不存在"
            )

        component = manager.get_component(component_name)
        if not component:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"组件 {component_name} 未初始化",
            )

        return component

    return _get_component


def get_running_component(component_name: str):
    """
    创建获取运行中组件的依赖函数

    Args:
        component_name: 组件名称

    Returns:
        依赖函数
    """

    def _get_running_component(
        component: Component = Depends(get_component(component_name)),
    ) -> Component:
        if component.status != ComponentStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"组件 {component_name} 未运行（状态: {component.status}）",
            )
        return component

    return _get_running_component


# 预定义的组件依赖
def get_database_component(component: Component = Depends(get_component("database"))) -> Component:
    """获取数据库组件"""
    return component


def get_cache_component(component: Component = Depends(get_component("cache"))) -> Component:
    """获取缓存组件"""
    return component


def get_event_engine(component: Component = Depends(get_component("event_engine"))) -> Component:
    """获取事件引擎组件"""
    return component


def get_message_bus(component: Component = Depends(get_component("message_bus"))) -> Component:
    """获取消息总线组件"""
    return component


def get_monitor_component(component: Component = Depends(get_component("monitor"))) -> Component:
    """获取监控组件"""
    return component


# WebSocket 管理器依赖
def get_websocket_manager(
    context: ApplicationContext = Depends(get_app_context),
) -> WebSocketManager:
    """
    获取 WebSocket 管理器

    Returns:
        WebSocket 管理器实例
    """
    # 从全局 app_state 获取（向后兼容）
    from .server import WebSocketManager as _WebSocketManager
    from .server import app_state

    manager = getattr(app_state, "websocket_manager", None)
    if manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WebSocket ��������δ��ʼ��",
        )

    if not isinstance(manager, _WebSocketManager):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WebSocket ���������Ͳ�ƥ��",
        )

    return manager


# 服务依赖


def get_notification_service(
    context: ApplicationContext = Depends(get_app_context),
) -> NotificationService:
    """获取通知推送服务依赖"""
    if not context.has_service("notifications"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="通知服务未启用"
        )

    service = context.get_service("notifications")
    if not isinstance(service, NotificationService):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="通知服务实现类型不匹配"
        )
    return service


def get_service(service_name: str):
    """
    创建获取特定服务的依赖函数

    Args:
        service_name: 服务名称

    Returns:
        依赖函数
    """

    def _get_service(context: ApplicationContext = Depends(get_app_context)):
        try:
            return context.get_service(service_name)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"服务 {service_name} 不存在"
            )

    return _get_service
