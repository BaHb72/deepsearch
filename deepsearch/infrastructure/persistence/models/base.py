"""数据库模型基类定义。"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有数据库 ORM 模型的 Declarative 基类。

    使用 SQLAlchemy 2.0 的 DeclarativeBase 配合 Mapped + mapped_column 语法，
    mypy 可以正确识别 ORM 模型的属性类型。

    注意：不使用 MappedAsDataclass 以避免强制执行 dataclass 的参数顺序规则，
    这可能会破坏现有代码中使用关键字参数创建 ORM 实例的地方。

    参考：https://docs.sqlalchemy.org/en/20/orm/mapping_api.html
    """

    pass
