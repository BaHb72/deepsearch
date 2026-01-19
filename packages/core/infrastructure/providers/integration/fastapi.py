"""
FastAPI 集成

提供 lifespan 上下文管理器和依赖注入函数。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from loguru import logger

from ..container import ProviderContainer


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
        if hasattr(config, "data_sources"):
            for name, ds_config in config.data_sources.items():
                if ds_config.get("enabled", False):
                    try:
                        await container.create_and_register(name, ds_config)
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
