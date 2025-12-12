"""模块数据源配置 Repository 层。

提供数据库 CRUD 操作封装，支持热更新。
"""

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from deepsearch.infrastructure.persistence.models.module_source import ModuleSourceConfig
from deepsearch.observability.logger import logger

if TYPE_CHECKING:
    from deepsearch.infrastructure.persistence.database import DatabaseService


class ModuleSourceRepository:
    """模块数据源配置 Repository。
    
    封装对 module_source_configs 表的所有数据库操作。
    """

    def __init__(self, db_service: "DatabaseService") -> None:
        """初始化 Repository。
        
        Args:
            db_service: 数据库服务实例
        """
        self._db = db_service

    async def get_all(self) -> List[Dict]:
        """获取所有模块配置。
        
        Returns:
            模块配置字典列表
        """
        try:
            async with self._db.get_session() as session:
                result = await session.execute(
                    select(ModuleSourceConfig).order_by(ModuleSourceConfig.category, ModuleSourceConfig.module_name)
                )
                configs = result.scalars().all()
                return [config.to_dict() for config in configs]
        except Exception as e:
            logger.error(f"获取模块配置失败: {e}")
            return []

    async def get_by_module(self, module_name: str) -> Optional[Dict]:
        """获取指定模块的配置。
        
        Args:
            module_name: 模块名称
            
        Returns:
            模块配置字典，不存在则返回 None
        """
        try:
            async with self._db.get_session() as session:
                result = await session.execute(
                    select(ModuleSourceConfig).where(ModuleSourceConfig.module_name == module_name)
                )
                config = result.scalar_one_or_none()
                return config.to_dict() if config else None
        except Exception as e:
            logger.error(f"获取模块 {module_name} 配置失败: {e}")
            return None

    async def upsert(
            self,
            module_name: str,
            *,
            label: Optional[str] = None,
            description: Optional[str] = None,
            category: Optional[str] = None,
            primary_source: Optional[str] = None,
            fallback_sources: Optional[List[str]] = None,
            enabled: bool = True,
    ) -> bool:
        """创建或更新模块配置。
        
        Args:
            module_name: 模块名称
            label: 显示名称
            description: 描述
            category: 分类
            primary_source: 主数据源
            fallback_sources: 回退数据源列表
            enabled: 是否启用
            
        Returns:
            操作是否成功
        """
        try:
            async with self._db.get_session() as session:
                # 使用 PostgreSQL upsert
                stmt = pg_insert(ModuleSourceConfig).values(
                    module_name=module_name,
                    label=label,
                    description=description,
                    category=category or "general",
                    primary_source=primary_source,
                    fallback_sources=fallback_sources or [],
                    enabled=enabled,
                )

                # ON CONFLICT 更新
                stmt = stmt.on_conflict_do_update(
                    index_elements=["module_name"],
                    set_={
                        "label": stmt.excluded.label,
                        "description": stmt.excluded.description,
                        "category": stmt.excluded.category,
                        "primary_source": stmt.excluded.primary_source,
                        "fallback_sources": stmt.excluded.fallback_sources,
                        "enabled": stmt.excluded.enabled,
                        "updated_at": ModuleSourceConfig.updated_at.default.arg,
                    },
                )

                await session.execute(stmt)
                await session.commit()
                logger.info(f"模块 {module_name} 配置已更新")
                return True
        except Exception as e:
            logger.error(f"更新模块 {module_name} 配置失败: {e}")
            return False

    async def delete(self, module_name: str) -> bool:
        """删除模块配置。
        
        Args:
            module_name: 模块名称
            
        Returns:
            操作是否成功
        """
        try:
            async with self._db.get_session() as session:
                await session.execute(
                    delete(ModuleSourceConfig).where(ModuleSourceConfig.module_name == module_name)
                )
                await session.commit()
                logger.info(f"模块 {module_name} 配置已删除")
                return True
        except Exception as e:
            logger.error(f"删除模块 {module_name} 配置失败: {e}")
            return False

    async def bulk_upsert(self, configs: List[Dict]) -> int:
        """批量创建或更新模块配置。
        
        Args:
            configs: 配置字典列表，每个字典应包含 module_name 等字段
            
        Returns:
            成功更新的配置数量
        """
        success_count = 0
        for config in configs:
            module_name = config.get("module_name")
            if not module_name:
                continue

            success = await self.upsert(
                module_name=module_name,
                label=config.get("label"),
                description=config.get("description"),
                category=config.get("category"),
                primary_source=config.get("primary_source"),
                fallback_sources=config.get("fallback_sources"),
                enabled=config.get("enabled", True),
            )
            if success:
                success_count += 1

        return success_count

    async def get_by_category(self, category: str) -> List[Dict]:
        """获取指定分类的所有模块配置。
        
        Args:
            category: 分类名称
            
        Returns:
            模块配置字典列表
        """
        try:
            async with self._db.get_session() as session:
                result = await session.execute(
                    select(ModuleSourceConfig)
                    .where(ModuleSourceConfig.category == category)
                    .order_by(ModuleSourceConfig.module_name)
                )
                configs = result.scalars().all()
                return [config.to_dict() for config in configs]
        except Exception as e:
            logger.error(f"获取分类 {category} 配置失败: {e}")
            return []


__all__ = ["ModuleSourceRepository"]
