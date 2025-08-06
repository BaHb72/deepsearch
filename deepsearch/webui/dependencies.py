"""
FastAPI 依赖注入

提供 FastAPI 应用的依赖注入功能。
"""
from fastapi import Depends, HTTPException, status

from deepsearch.core import MainEngine
from deepsearch.core.component_manager import ComponentManager
from deepsearch.core.context import get_context, ApplicationContext
from deepsearch.core.interfaces import Component, ComponentStatus


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
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="系统引擎未初始化"
        )


def get_component_manager(
        engine: MainEngine = Depends(get_engine)
) -> ComponentManager:
    """
    获取组件管理器依赖
    
    Args:
        engine: 主引擎
        
    Returns:
        ComponentManager 实例
    """
    return engine._component_manager


def get_component(component_name: str):
    """
    创建获取特定组件的依赖函数
    
    Args:
        component_name: 组件名称
        
    Returns:
        依赖函数
    """

    def _get_component(
            manager: ComponentManager = Depends(get_component_manager)
    ) -> Component:
        if not manager.has_component(component_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"组件 {component_name} 不存在"
            )

        component = manager.get_component(component_name)
        if not component:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"组件 {component_name} 未初始化"
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
            component: Component = Depends(get_component(component_name))
    ) -> Component:
        if component.status != ComponentStatus.RUNNING:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"组件 {component_name} 未运行（状态: {component.status}）"
            )
        return component

    return _get_running_component


# 预定义的组件依赖
def get_database_component(
        component: Component = Depends(get_component("database"))
) -> Component:
    """获取数据库组件"""
    return component


def get_cache_component(
        component: Component = Depends(get_component("cache"))
) -> Component:
    """获取缓存组件"""
    return component


def get_event_engine(
        component: Component = Depends(get_component("event_engine"))
) -> Component:
    """获取事件引擎组件"""
    return component


def get_message_bus(
        component: Component = Depends(get_component("message_bus"))
) -> Component:
    """获取消息总线组件"""
    return component


def get_monitor_component(
        component: Component = Depends(get_component("monitor"))
) -> Component:
    """获取监控组件"""
    return component


# WebSocket 管理器依赖
def get_websocket_manager(
        context: ApplicationContext = Depends(get_app_context)
) -> 'WebSocketManager':
    """
    获取 WebSocket 管理器
    
    Returns:
        WebSocket 管理器实例
    """
    # 从全局 app_state 获取（向后兼容）
    from .server import app_state
    return app_state.websocket_manager


# 服务依赖
def get_service(service_name: str):
    """
    创建获取特定服务的依赖函数
    
    Args:
        service_name: 服务名称
        
    Returns:
        依赖函数
    """

    def _get_service(
            context: ApplicationContext = Depends(get_app_context)
    ):
        try:
            return context.get_service(service_name)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"服务 {service_name} 不存在"
            )

    return _get_service
