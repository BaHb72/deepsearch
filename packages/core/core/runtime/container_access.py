"""
全局容器访问工具

提供对 ApplicationContainer 的全局访问，用于需要从 DI 容器获取组件的场景。
"""

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .di_container import ApplicationContainer

_container: Optional["ApplicationContainer"] = None


def get_container() -> "ApplicationContainer":
    """
    获取全局 ApplicationContainer 实例

    Returns:
        ApplicationContainer 实例

    Raises:
        RuntimeError: 如果容器尚未初始化
    """
    global _container
    if _container is None:
        from .di_container import create_application_container

        _container = create_application_container()
    return _container


def set_container(container: "ApplicationContainer") -> None:
    """
    设置全局容器实例

    用于在应用启动时显式设置容器，或在测试中注入 mock 容器。

    Args:
        container: 要设置的容器实例
    """
    global _container
    _container = container


def reset_container() -> None:
    """
    重置全局容器

    主要用于测试场景，确保测试间隔离。
    """
    global _container
    _container = None
