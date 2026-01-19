"""
Provider 依赖注入函数（新架构）

提供基于新 ProviderContainer 的 FastAPI 依赖注入函数。
替代旧的 providers.py 中的依赖注入函数。
"""

from core.infrastructure.providers.container import ProviderContainer
from core.infrastructure.providers.protocols.lifecycle import HealthStatus
from fastapi import Depends, HTTPException, Request
from loguru import logger


async def get_provider_container(request: Request) -> ProviderContainer:
    """
    获取 Provider 容器（FastAPI 依赖）

    Args:
        request: FastAPI Request 对象

    Returns:
        ProviderContainer 实例

    Raises:
        HTTPException: 如果容器未初始化

    Examples:
        >>> @router.get("/data")
        >>> async def get_data(container: ProviderContainer = Depends(get_provider_container)):
        >>>     provider = await container.get("amazingdata")
        >>>     ...
    """
    container = getattr(request.app.state, "provider_container", None)

    if container is None:
        logger.error("ProviderContainer 未在 app.state 中初始化")
        raise HTTPException(status_code=503, detail="Provider 容器未初始化，请检查应用启动配置")

    if not isinstance(container, ProviderContainer):
        logger.error(f"app.state.provider_container 类型错误: {type(container)}")
        raise HTTPException(status_code=500, detail="Provider 容器类型错误")

    return container


async def get_amazingdata_provider(
    container: ProviderContainer = Depends(get_provider_container),
):
    """
    获取 AmazingData Provider（新架构）

    Args:
        container: ProviderContainer 实例（自动注入）

    Returns:
        AmazingData Provider 实例

    Raises:
        HTTPException: 如果 Provider 不可用

    Examples:
        >>> @router.get("/stocks")
        >>> async def get_stocks(provider = Depends(get_amazingdata_provider)):
        >>>     data = await provider.get_stock_list()
        >>>     return data
    """
    try:
        provider = await container.get("amazingdata")

        # 检查连接状态
        is_connected = getattr(provider, "_connected", True)
        if not is_connected:
            logger.warning("AmazingData Provider 未连接")
            raise HTTPException(
                status_code=503, detail="AmazingData Provider 未连接，请检查配置或重启服务"
            )

        return provider

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 AmazingData Provider 失败: {e}")
        raise HTTPException(status_code=503, detail=f"AmazingData Provider 不可用: {str(e)}") from e


async def get_akshare_provider(
    container: ProviderContainer = Depends(get_provider_container),
):
    """
    获取 AkShare Provider（新架构）

    Args:
        container: ProviderContainer 实例（自动注入）

    Returns:
        AkShare Provider 实例

    Raises:
        HTTPException: 如果 Provider 不可用

    Examples:
        >>> @router.get("/market")
        >>> async def get_market(provider = Depends(get_akshare_provider)):
        >>>     data = await provider.query_realtime(...)
        >>>     return data
    """
    try:
        provider = await container.get("akshare")
        return provider

    except Exception as e:
        logger.error(f"获取 AkShare Provider 失败: {e}")
        raise HTTPException(status_code=503, detail=f"AkShare Provider 不可用: {str(e)}") from e


async def get_miniqmt_provider(
    container: ProviderContainer = Depends(get_provider_container),
):
    """
    获取 MiniQMT Provider（新架构）

    Args:
        container: ProviderContainer 实例（自动注入）

    Returns:
        MiniQMT Provider 实例

    Raises:
        HTTPException: 如果 Provider 不可用

    Examples:
        >>> @router.get("/qmt/data")
        >>> async def get_qmt_data(provider = Depends(get_miniqmt_provider)):
        >>>     data = await provider.query_kline(...)
        >>>     return data
    """
    try:
        provider = await container.get("miniqmt")

        # 检查连接状态
        is_connected = getattr(provider, "_connected", True)
        if not is_connected:
            logger.warning("MiniQMT Provider 未连接")
            raise HTTPException(status_code=503, detail="MiniQMT Provider 未连接，请检查配置")

        return provider

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 MiniQMT Provider 失败: {e}")
        raise HTTPException(status_code=503, detail=f"MiniQMT Provider 不可用: {str(e)}") from e


async def get_provider_by_name(
    name: str,
    container: ProviderContainer = Depends(get_provider_container),
):
    """
    根据名称获取 Provider（通用函数）

    Args:
        name: Provider 名称
        container: ProviderContainer 实例（自动注入）

    Returns:
        Provider 实例

    Raises:
        HTTPException: 如果 Provider 不可用

    Examples:
        >>> @router.get("/providers/{name}/data")
        >>> async def get_data(name: str, provider = Depends(get_provider_by_name)):
        >>>     ...
    """
    try:
        provider = await container.get(name)
        return provider

    except Exception as e:
        logger.error(f"获取 Provider '{name}' 失败: {e}")
        raise HTTPException(status_code=404, detail=f"Provider '{name}' 不可用: {str(e)}") from e


# 健康检查辅助函数（不是依赖注入，而是工具函数）
async def check_provider_health(
    provider_name: str, container: ProviderContainer
) -> tuple[HealthStatus, str]:
    """
    检查 Provider 健康状态（工具函数）

    Args:
        provider_name: Provider 名称
        container: ProviderContainer 实例

    Returns:
        (HealthStatus, message) 元组

    Examples:
        >>> container = await get_provider_container(request)
        >>> status, message = await check_provider_health("akshare", container)
        >>> if status == HealthStatus.HEALTHY:
        >>>     ...
    """
    try:
        health_status = await container.health_check(provider_name)
        logger.debug(
            f"健康检查结果: {provider_name} -> {health_status} (type: {type(health_status)})"
        )

        if health_status == HealthStatus.HEALTHY:
            return health_status, "运行正常"
        elif health_status == HealthStatus.DEGRADED:
            return health_status, "性能降级，部分功能可能受限"
        elif health_status == HealthStatus.UNHEALTHY:
            return health_status, "服务不可用"
        else:
            logger.warning(f"未知的健康状态: {provider_name} -> {health_status}")
            return HealthStatus.UNKNOWN, "状态未知"

    except Exception as e:
        logger.error(f"健康检查失败: {provider_name} - {e}", exc_info=True)
        return HealthStatus.UNHEALTHY, f"健康检查失败: {str(e)}"
