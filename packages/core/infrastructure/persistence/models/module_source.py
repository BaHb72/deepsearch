"""模块数据源配置数据库模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ModuleSourceConfig(Base):
    """模块数据源配置表。

    存储每个功能模块的数据源选择配置，支持运行时动态更新。
    """

    __tablename__ = "module_source_configs"

    # 必填字段
    module_name: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # 可选字段
    label: Mapped[Optional[str]] = mapped_column(String(128), default=None)
    description: Mapped[Optional[str]] = mapped_column(String(512), default=None)
    category: Mapped[Optional[str]] = mapped_column(String(32), default="general")
    primary_source: Mapped[Optional[str]] = mapped_column(String(32), default=None)
    fallback_sources: Mapped[Optional[list[Any]]] = mapped_column(JSON, default_factory=list)
    enabled: Mapped[bool] = mapped_column(default=True)

    # 自动生成字段
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), init=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        init=False,
    )

    def __repr__(self) -> str:
        return f"<ModuleSourceConfig(module_name='{self.module_name}', primary='{self.primary_source}')>"

    def to_dict(self) -> dict[str, Any]:
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
