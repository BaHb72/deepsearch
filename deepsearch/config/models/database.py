"""
数据库配置模型。
"""
from typing import Union

from pydantic import BaseModel, PostgresDsn

DatabaseUrl = Union[str, PostgresDsn, None]


class DatabaseConfig(BaseModel):
    """数据库配置。"""
    url: DatabaseUrl = None
