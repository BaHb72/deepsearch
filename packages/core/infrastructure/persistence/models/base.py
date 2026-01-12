"""数据库模型基类定义。"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass


class Base(MappedAsDataclass, DeclarativeBase):
    """所有数据库 ORM 模型的 Declarative 基类。

    使用 SQLAlchemy 2.0 的 MappedAsDataclass + DeclarativeBase，
    配合 Mapped + mapped_column 语法实现完整的类型安全。

    MappedAsDataclass 特性：
    - 自动生成 __init__, __repr__, __eq__ 方法
    - 完整的 mypy 类型推断
    - 字段需按 dataclass 规则排序：必填在前，可选在后

    参考：https://docs.sqlalchemy.org/en/20/orm/dataclasses.html
    """

    pass
