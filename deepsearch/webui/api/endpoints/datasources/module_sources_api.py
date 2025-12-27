"""
模块数据源配置 API 端点。

提供模块数据源配置的 CRUD 操作（数据库存储）。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from deepsearch.infrastructure.providers.managers.data_source_manager import DataSourceManager
from deepsearch.infrastructure.providers.managers.module_registry import get_module_registry

router = APIRouter(prefix="/api/module-sources", tags=["Module Sources"])


class ModuleConfigResponse(BaseModel):
    """模块配置响应。"""

    name: str
    label: Optional[str] = None
    description: Optional[str] = None
    category: str = "general"
    currentConfig: Dict[str, Any]
    defaultConfig: Optional[Dict[str, Any]] = None
    availableSources: List[str]


class ModuleListResponse(BaseModel):
    """模块列表响应。"""

    modules: List[ModuleConfigResponse]
    categories: List[Dict[str, str]]


class UpdateModuleConfigRequest(BaseModel):
    """更新模块配置请求。"""

    label: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    primary: Optional[str] = None
    fallback: Optional[List[str]] = None
    enabled: bool = True


class UpdateModuleConfigResponse(BaseModel):
    """更新模块配置响应。"""

    success: bool
    message: str
    module: Optional[ModuleConfigResponse] = None


def _get_available_sources() -> List[str]:
    """获取可用数据源列表。"""
    available_sources = ["amazingdata", "akshare"]
    try:
        manager = DataSourceManager.get_instance()
        if manager.initialized:
            available_sources = [s.value for s in manager.get_available_sources()]
    except Exception:
        pass
    return available_sources


@router.get("", response_model=ModuleListResponse)
async def get_all_module_sources() -> ModuleListResponse:
    """获取所有模块及其数据源配置。"""
    registry = get_module_registry()
    available_sources = _get_available_sources()

    modules = []

    # 从数据库获取所有配置
    all_configs = await registry.get_all_configs()

    for config in all_configs:
        module_name = config["module_name"]
        module_info = registry.get_module(module_name)

        modules.append(
            ModuleConfigResponse(
                name=module_name,
                label=config.get("label") or (module_info.label if module_info else module_name),
                description=config.get("description")
                or (module_info.description if module_info else ""),
                category=config.get("category", "general"),
                currentConfig={
                    "primary": config.get("primary_source"),
                    "fallback": config.get("fallback_sources", []),
                },
                defaultConfig=config.get("default_config")
                or (module_info.to_dict()["defaultConfig"] if module_info else None),
                availableSources=available_sources,
            )
        )

    # 按分类排序
    modules.sort(key=lambda m: (m.category, m.name))

    categories = [cat.to_dict() for cat in registry.get_all_categories()]

    return ModuleListResponse(modules=modules, categories=categories)


@router.get("/{module_name}", response_model=ModuleConfigResponse)
async def get_module_source(module_name: str) -> ModuleConfigResponse:
    """获取单个模块的数据源配置。"""
    registry = get_module_registry()
    available_sources = _get_available_sources()

    # 从数据库获取配置
    current_config = await registry.get_module_config(module_name)
    module_info = registry.get_module(module_name)

    return ModuleConfigResponse(
        name=module_name,
        label=module_info.label if module_info else module_name,
        description=module_info.description if module_info else "",
        category=module_info.category if module_info else "general",
        currentConfig={
            "primary": current_config.primary.value if current_config.primary else None,
            "fallback": [s.value for s in current_config.fallback],
        },
        defaultConfig=module_info.to_dict()["defaultConfig"] if module_info else None,
        availableSources=available_sources,
    )


@router.put("/{module_name}", response_model=UpdateModuleConfigResponse)
async def update_module_source(
    module_name: str,
    request: UpdateModuleConfigRequest,
) -> UpdateModuleConfigResponse:
    """更新模块的数据源配置（写入数据库，立即生效）。"""
    registry = get_module_registry()

    if not registry.has_repository:
        raise HTTPException(status_code=503, detail="数据库未初始化，无法更新配置")

    success = await registry.update_module_config(
        module_name=module_name,
        label=request.label,
        description=request.description,
        category=request.category,
        primary_source=request.primary,
        fallback_sources=request.fallback,
        enabled=request.enabled,
    )

    if not success:
        raise HTTPException(status_code=500, detail="配置更新失败")

    # 返回更新后的配置
    current_config = await registry.get_module_config(module_name)
    module_info = registry.get_module(module_name)
    available_sources = _get_available_sources()

    return UpdateModuleConfigResponse(
        success=True,
        message=f"模块 {module_name} 配置已更新（立即生效）",
        module=ModuleConfigResponse(
            name=module_name,
            label=request.label or (module_info.label if module_info else module_name),
            description=request.description or (module_info.description if module_info else ""),
            category=request.category or (module_info.category if module_info else "general"),
            currentConfig={
                "primary": current_config.primary.value if current_config.primary else None,
                "fallback": [s.value for s in current_config.fallback],
            },
            defaultConfig=module_info.to_dict()["defaultConfig"] if module_info else None,
            availableSources=available_sources,
        ),
    )


@router.delete("/{module_name}")
async def delete_module_source(module_name: str) -> Dict[str, Any]:
    """删除模块配置（恢复为默认值）。"""
    registry = get_module_registry()

    if not registry.has_repository:
        raise HTTPException(status_code=503, detail="数据库未初始化，无法删除配置")

    success = await registry.delete_module_config(module_name)

    return {
        "success": success,
        "message": f"模块 {module_name} 配置已删除，将使用默认配置" if success else "删除失败",
    }
