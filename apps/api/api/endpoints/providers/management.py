"""
Provider 管理 API

提供 Provider 的列表、健康检查、重载等管理功能。
"""

from core.infrastructure.providers.container import ProviderContainer
from core.infrastructure.providers.protocols.lifecycle import HealthStatus
from fastapi import APIRouter, Depends, HTTPException, Path
from loguru import logger
from pydantic import BaseModel

from apps.api.api.provider_deps import check_provider_health, get_provider_container

router = APIRouter(prefix="/api/providers", tags=["Provider Management"])


# Response Models
class ProviderListResponse(BaseModel):
    """Provider 列表响应"""

    providers: list[str]
    count: int


class ProviderHealthResponse(BaseModel):
    """Provider 健康状态响应"""

    provider: str
    status: str
    healthy: bool
    message: str


class ProviderReloadResponse(BaseModel):
    """Provider 重载响应"""

    status: str
    provider: str
    message: str


# Endpoints
@router.get("", response_model=ProviderListResponse)
async def list_providers(
    container: ProviderContainer = Depends(get_provider_container),
):
    """
    列出所有已加载的 Provider

    返回所有在容器中注册的 Provider 名称列表。

    示例响应:
    ```json
    {
        "providers": ["amazingdata", "akshare", "miniqmt"],
        "count": 3
    }
    ```
    """
    providers = container.list_providers()
    logger.info(f"列出 Provider: {providers}")

    return ProviderListResponse(providers=providers, count=len(providers))


@router.get("/{name}/health", response_model=ProviderHealthResponse)
async def check_health(
    name: str = Path(..., description="Provider 名称"),
    container: ProviderContainer = Depends(get_provider_container),
):
    """
    检查指定 Provider 的健康状态

    参数:
    - name: Provider 名称（amazingdata, akshare, miniqmt）

    示例响应:
    ```json
    {
        "provider": "akshare",
        "status": "healthy",
        "healthy": true,
        "message": "运行正常"
    }
    ```

    健康状态:
    - healthy: 运行正常
    - degraded: 性能降级，部分功能可能受限
    - unhealthy: 服务不可用
    - unknown: 状态未知
    """
    try:
        health_status, message = await check_provider_health(name, container)

        return ProviderHealthResponse(
            provider=name,
            status=health_status.value,
            healthy=health_status == HealthStatus.HEALTHY,
            message=message,
        )

    except Exception as e:
        logger.error(f"健康检查失败: {name} - {e}")
        raise HTTPException(status_code=404, detail=f"Provider '{name}' 不存在: {str(e)}") from e


@router.post("/{name}/reload", response_model=ProviderReloadResponse)
async def reload_provider(
    name: str = Path(..., description="Provider 名称"),
    container: ProviderContainer = Depends(get_provider_container),
):
    """
    重新加载指定 Provider

    停止当前 Provider 并使用配置重新创建。

    参数:
    - name: Provider 名称（amazingdata, akshare, miniqmt）

    注意: 重载可能需要一些时间，请耐心等待。

    示例响应:
    ```json
    {
        "status": "success",
        "provider": "akshare",
        "message": "Provider 已成功重载"
    }
    ```
    """
    try:
        logger.info(f"开始重载 Provider: {name}")

        # 1. 获取现有 Provider
        try:
            provider = await container.get(name)
        except Exception as e:
            raise HTTPException(
                status_code=404, detail=f"Provider '{name}' 不存在: {str(e)}"
            ) from e

        # 2. 停止现有 Provider
        try:
            await container._lifecycle.stop(provider)
            logger.info(f"Provider '{name}' 已停止")
        except Exception as e:
            logger.warning(f"停止 Provider 时出错（继续重载）: {e}")

        # 3. 获取配置
        from core.config import get_config

        config = get_config()

        data_sources = getattr(config, "data_sources", None)
        if data_sources is None:
            raise HTTPException(status_code=500, detail="配置中缺少 data_sources")

        ds_config = data_sources.get_provider(name)

        if not ds_config:
            raise HTTPException(status_code=400, detail=f"配置中未找到 Provider '{name}'")

        # 转换配置
        if hasattr(ds_config, "model_dump"):
            provider_config = ds_config.model_dump()
        elif hasattr(ds_config, "dict"):
            provider_config = ds_config.dict()
        else:
            provider_config = {"config": {}}

        # 4. 重新创建 Provider
        await container.create_and_register(name, provider_config)

        logger.info(f"Provider '{name}' 已成功重载")

        return ProviderReloadResponse(
            status="success", provider=name, message="Provider 已成功重载"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重载 Provider 失败: {name} - {e}")
        raise HTTPException(status_code=500, detail=f"重载 Provider '{name}' 失败: {str(e)}") from e


@router.get("/status")
async def get_all_status(
    container: ProviderContainer = Depends(get_provider_container),
):
    """
    获取所有 Provider 的状态概览

    返回所有注册 Provider 的健康状态。

    示例响应:
    ```json
    {
        "providers": {
            "akshare": {
                "status": "healthy",
                "healthy": true,
                "message": "运行正常"
            },
            "amazingdata": {
                "status": "unhealthy",
                "healthy": false,
                "message": "服务不可用"
            }
        },
        "total": 2,
        "healthy_count": 1,
        "unhealthy_count": 1
    }
    ```
    """
    providers = container.list_providers()
    status_map = {}
    healthy_count = 0
    unhealthy_count = 0

    for name in providers:
        try:
            health_status, message = await check_provider_health(name, container)

            status_map[name] = {
                "status": health_status.value,
                "healthy": health_status == HealthStatus.HEALTHY,
                "message": message,
            }

            if health_status == HealthStatus.HEALTHY:
                healthy_count += 1
            else:
                unhealthy_count += 1

        except Exception as e:
            logger.error(f"获取 Provider '{name}' 状态失败: {e}")
            status_map[name] = {
                "status": "unknown",
                "healthy": False,
                "message": f"状态检查失败: {str(e)}",
            }
            unhealthy_count += 1

    return {
        "providers": status_map,
        "total": len(providers),
        "healthy_count": healthy_count,
        "unhealthy_count": unhealthy_count,
    }
