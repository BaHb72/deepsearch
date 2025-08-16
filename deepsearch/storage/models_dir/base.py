"""基础数据模型

提供所有数据模型的基类和通用功能
"""
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, func, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.declarative import declared_attr

# 创建基础模型类
Base = declarative_base()


class TimestampMixin:
    """时间戳混入类
    
    为模型添加创建时间和更新时间字段
    """
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间"
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间"
    )


class BaseModel(Base):
    """抽象基础模型
    
    所有模型的基类，提供通用功能
    """
    __abstract__ = True

    # 所有表都有自增ID作为主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")

    @declared_attr
    def __tablename__(cls):
        """自动生成表名（类名转小写下划线）"""
        # CamelCase -> camel_case
        name = cls.__name__
        result = [name[0].lower()]
        for char in name[1:]:
            if char.isupper():
                result.append('_')
                result.append(char.lower())
            else:
                result.append(char)
        return ''.join(result)

    def to_dict(self) -> dict[str, Any]:
        """将模型转换为字典"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result

    def __repr__(self):
        """字符串表示"""
        attrs = []
        for column in self.__table__.columns:
            attrs.append(f"{column.name}={getattr(self, column.name)!r}")
        return f"<{self.__class__.__name__}({', '.join(attrs)})>"


class TimeSeriesBase(Base):
    """时序数据基类
    
    用于存储时间序列数据的基类，不使用自增ID
    """
    __abstract__ = True

    @declared_attr
    def __tablename__(cls):
        """自动生成表名"""
        name = cls.__name__
        result = [name[0].lower()]
        for char in name[1:]:
            if char.isupper():
                result.append('_')
                result.append(char.lower())
            else:
                result.append(char)
        return ''.join(result)

    def to_dict(self) -> dict[str, Any]:
        """将模型转换为字典"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            result[column.name] = value
        return result
