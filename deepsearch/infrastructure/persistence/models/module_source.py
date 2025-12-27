"""模块数据源配置数据库模型。"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, func

from .base import Base


class ModuleSourceConfig(Base):
    """模块数据源配置表。

    存储每个功能模块的数据源选择配置，支持运行时动态更新。
    """

    __tablename__ = "module_source_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    module_name = Column(String(64), unique=True, nullable=False, index=True)
    label = Column(String(128), nullable=True)
    description = Column(String(512), nullable=True)
    category = Column(String(32), nullable=True, default="general")
    primary_source = Column(String(32), nullable=True)
    fallback_sources = Column(JSON, nullable=True, default=list)
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<ModuleSourceConfig(module_name='{self.module_name}', primary='{self.primary_source}')>"

    def to_dict(self) -> dict:
        """转换为字典格式。"""
        return {
            "id": self.id,
            "module_name": self.module_name,
            "label": self.label,
            "description": self.description,
            "category": self.category,
            "primary_source": self.primary_source,
            "fallback_sources": self.fallback_sources or [],
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


__all__ = ["ModuleSourceConfig"]
