"""
配置服务层接口。

目前提供数据库连接配置的读写能力。
"""

from .database_connections import load_database_connections, persist_database_connections

__all__ = [
    "load_database_connections",
    "persist_database_connections",
]
