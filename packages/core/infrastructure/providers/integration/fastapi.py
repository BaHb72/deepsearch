"""
FastAPI 集成

提供 lifespan 上下文管理器和依赖注入函数。
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from loguru import logger

from ..container import ProviderContainer


def _to_dict(value: object) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
            if isinstance(dumped, dict):
                return dict(dumped)
        except Exception:
            return {}
    if hasattr(value, "__dict__"):
        raw = getattr(value, "__dict__", {})
        if isinstance(raw, dict):
            return dict(raw)
    return {}


def _iter_enabled_provider_configs(settings: object) -> list[tuple[str, dict[str, Any]]]:
    data_sources_obj = getattr(settings, "data_sources", None)
    if data_sources_obj is None:
        return []

    data_sources = _to_dict(data_sources_obj)
    providers = _to_dict(data_sources.get("providers"))
    enabled: list[tuple[str, dict[str, Any]]] = []

    for name, raw_provider in providers.items():
        provider = _to_dict(raw_provider)
        if not provider or not bool(provider.get("enabled", False)):
            continue

        provider_payload = dict(provider)
        provider_payload["config"] = _to_dict(provider.get("config"))

        enabled.append((str(name), provider_payload))

    return enabled


@asynccontextmanager
async def provider_lifespan(app: FastAPI):
    """Provider 容器生命周期管理

    在 FastAPI 应用启动时创建容器，关闭时清理。

    Usage:
        app = FastAPI(lifespan=provider_lifespan)

    Args:
        app: FastAPI 应用实例

    Yields:
        None: 应用运行中
    """
    # 启动
    logger.info("初始化 ProviderContainer...")
    container = ProviderContainer()
    app.state.provider_container = container

    # 预加载配置中的 Provider
    try:
        from core.config import get_config

        config = get_config()
        for name, provider_config in _iter_enabled_provider_configs(config):
            try:
                await container.create_and_register(name, provider_config)
                logger.info(f"预加载 Provider 成功: {name}")
            except Exception as e:
                logger.warning(f"预加载 Provider 失败: {name} - {e}")
    except Exception as e:
        logger.warning(f"无法加载配置: {e}")

    logger.info("ProviderContainer 初始化完成")

    yield  # 应用运行中

    # 关闭
    logger.info("关闭 ProviderContainer...")
    await container.shutdown()
    logger.info("ProviderContainer 已关闭")


def get_provider_container(request: Request) -> ProviderContainer:
    """FastAPI 依赖注入函数

    Usage:
        @router.get("/data")
        async def get_data(
            container: ProviderContainer = Depends(get_provider_container)
        ):
            provider = await container.get("amazingdata")
            ...

    Args:
        request: FastAPI Request 对象

    Returns:
        ProviderContainer: 容器实例
    """
    return request.app.state.provider_container
