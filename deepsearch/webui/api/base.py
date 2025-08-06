"""
WebUI API 基础模块

提供统一的 API 错误处理、响应格式和通用工具。
"""
import functools
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from deepsearch.core import MainEngine
from deepsearch.core.interfaces import Component, ComponentStatus
from deepsearch.webui.server import app_state

# 类型变量
F = TypeVar('F', bound=Callable[..., Any])

# 获取logger
logger = logging.getLogger(__name__)


class APIResponse(BaseModel):
    """统一的 API 响应格式"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    timestamp: str = None

    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        super().__init__(**data)


def success_response(data: Any = None, message: str = None) -> JSONResponse:
    """
    创建成功响应
    
    Args:
        data: 响应数据
        message: 成功消息
    
    Returns:
        JSON响应
    """
    response_data = {
        "success": True,
        "data": data
    }
    if message:
        response_data["message"] = message

    return JSONResponse(
        content=APIResponse(**response_data).dict(),
        status_code=status.HTTP_200_OK
    )


def error_response(
        error: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict] = None
) -> JSONResponse:
    """
    创建错误响应
    
    Args:
        error: 错误消息
        status_code: HTTP状态码
        details: 额外的错误详情
    
    Returns:
        JSON响应
    """
    response_data = {
        "success": False,
        "error": error
    }
    if details:
        response_data["details"] = details

    return JSONResponse(
        content=APIResponse(**response_data).dict(),
        status_code=status_code
    )


def get_engine() -> MainEngine:
    """
    获取引擎实例
    
    Returns:
        MainEngine实例
        
    Raises:
        HTTPException: 如果引擎未初始化
    """
    if not app_state.engine:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="系统引擎未初始化"
        )
    return app_state.engine


def get_component(component_name: str) -> Component:
    """
    获取组件实例
    
    Args:
        component_name: 组件名称
        
    Returns:
        组件实例
        
    Raises:
        HTTPException: 如果组件不存在或未初始化
    """
    engine = get_engine()
    component_manager = engine._component_manager

    if not component_manager.has_component(component_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"组件 {component_name} 不存在"
        )

    component = component_manager.get_component(component_name)
    if not component:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"组件 {component_name} 未初始化"
        )

    return component


def require_component(component_name: str) -> Callable[[F], F]:
    """
    装饰器：要求特定组件必须存在且正在运行
    
    Args:
        component_name: 组件名称
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            component = get_component(component_name)
            if component.status != ComponentStatus.RUNNING:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"组件 {component_name} 未运行"
                )
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            component = get_component(component_name)
            if component.status != ComponentStatus.RUNNING:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"组件 {component_name} 未运行"
                )
            return func(*args, **kwargs)

        # 根据函数类型返回相应的包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def handle_api_errors(func: F) -> F:
    """
    装饰器：统一处理 API 错误
    
    将异常转换为统一的错误响应格式
    """

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException:
            # HTTPException 直接抛出
            raise
        except ValueError as e:
            # 值错误通常是客户端错误
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except PermissionError as e:
            # 权限错误
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        except FileNotFoundError as e:
            # 资源不存在
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except TimeoutError as e:
            # 超时错误
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=str(e)
            )
        except Exception as e:
            # 其他未预期的错误
            logger.error(f"API错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="内部服务器错误"
            )

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except HTTPException:
            # HTTPException 直接抛出
            raise
        except ValueError as e:
            # 值错误通常是客户端错误
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        except PermissionError as e:
            # 权限错误
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        except FileNotFoundError as e:
            # 资源不存在
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e)
            )
        except TimeoutError as e:
            # 超时错误
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail=str(e)
            )
        except Exception as e:
            # 其他未预期的错误
            logger.error(f"API错误: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="内部服务器错误"
            )

    # 根据函数类型返回相应的包装器
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper


class BaseAPIRouter:
    """
    API 路由基类
    
    提供通用的组件获取方法
    """

    @staticmethod
    def get_database_component():
        """获取数据库组件"""
        return get_component("database")

    @staticmethod
    def get_cache_component():
        """获取缓存组件"""
        return get_component("cache")

    @staticmethod
    def get_message_bus_component():
        """获取消息总线组件"""
        return get_component("message_bus")

    @staticmethod
    def get_event_engine_component():
        """获取事件引擎组件"""
        return get_component("event_engine")

    @staticmethod
    def get_monitor_component():
        """获取监控组件"""
        return get_component("monitor")


# 导出常用的状态码
class StatusCode:
    """HTTP 状态码常量"""
    OK = status.HTTP_200_OK
    CREATED = status.HTTP_201_CREATED
    ACCEPTED = status.HTTP_202_ACCEPTED
    NO_CONTENT = status.HTTP_204_NO_CONTENT

    BAD_REQUEST = status.HTTP_400_BAD_REQUEST
    UNAUTHORIZED = status.HTTP_401_UNAUTHORIZED
    FORBIDDEN = status.HTTP_403_FORBIDDEN
    NOT_FOUND = status.HTTP_404_NOT_FOUND
    CONFLICT = status.HTTP_409_CONFLICT

    INTERNAL_SERVER_ERROR = status.HTTP_500_INTERNAL_SERVER_ERROR
    NOT_IMPLEMENTED = status.HTTP_501_NOT_IMPLEMENTED
    SERVICE_UNAVAILABLE = status.HTTP_503_SERVICE_UNAVAILABLE
    GATEWAY_TIMEOUT = status.HTTP_504_GATEWAY_TIMEOUT
