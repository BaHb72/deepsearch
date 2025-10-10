"""数据库模型基类定义。"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有数据库 ORM 模型的 Declarative 基类。"""

    pass
