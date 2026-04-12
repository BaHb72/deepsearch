"""
数据库存储层

提供缓存数据的持久化存储
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from loguru import logger


class DBStore:
    """
    数据库存储层

    将缓存数据持久化到数据库，支持服务重启恢复
    """

    def __init__(self):
        self._engine = None
        self._initialized = False

    def _get_engine(self):
        """获取数据库引擎（延迟加载）"""
        if self._engine is not None:
            return self._engine

        try:
            from core.config import settings
            from sqlalchemy import create_engine

            # 使用 SQLite 作为本地持久化
            db_path = getattr(settings, "CACHE_DB_PATH", "data/cache.db")
            self._engine = create_engine(f"sqlite:///{db_path}")
            return self._engine
        except Exception as e:
            logger.error(f"[DBStore] 无法创建数据库引擎: {e}")
            return None

    def _ensure_tables(self):
        """确保表存在"""
        if self._initialized:
            return

        engine = self._get_engine()
        if engine is None:
            return

        try:
            from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text

            metadata = MetaData()

            # 股票信息表
            Table(
                "cache_stock_info",
                metadata,
                Column("symbol", String(20), primary_key=True),
                Column("name", String(50)),
                Column("pinyin", String(50)),
                Column("sector", String(50)),
                Column("updated_at", DateTime, default=datetime.now),
            )

            # 缓存元数据表
            Table(
                "cache_metadata",
                metadata,
                Column("cache_key", String(100), primary_key=True),
                Column("data_json", Text),
                Column("data_count", Integer),
                Column("last_refresh", DateTime),
            )

            metadata.create_all(engine)
            self._initialized = True
            logger.info("[DBStore] 数据库表已初始化")

        except Exception as e:
            logger.error(f"[DBStore] 初始化表失败: {e}")

    def close(self) -> None:
        """释放当前 Engine 持有的连接池资源。"""
        engine = self._engine
        if engine is None:
            return

        try:
            engine.dispose()
        except Exception as e:
            logger.warning(f"[DBStore] 释放数据库引擎失败: {e}")
        finally:
            self._engine = None
            self._initialized = False

    async def save_records(self, task_name: str, records: List[Dict[str, Any]]) -> bool:
        """
        保存记录到数据库

        Args:
            task_name: 任务名称（用于确定表）
            records: 记录列表
        """
        if not records:
            return True

        self._ensure_tables()
        engine = self._get_engine()
        if engine is None:
            return False

        try:
            import json

            from sqlalchemy import text

            # 对于股票列表，使用专用表
            if task_name == "stock_list":
                with engine.connect() as conn:
                    # 批量插入/更新
                    for record in records:
                        conn.execute(
                            text("""
                                INSERT OR REPLACE INTO cache_stock_info
                                (symbol, name, pinyin, sector, updated_at)
                                VALUES (:symbol, :name, :pinyin, :sector, :updated_at)
                            """),
                            {
                                "symbol": record.get("symbol", ""),
                                "name": record.get("name", ""),
                                "pinyin": record.get("pinyin", ""),
                                "sector": record.get("sector", "沪深A股"),
                                "updated_at": datetime.now(),
                            },
                        )
                    conn.commit()
            else:
                # 其他任务使用通用元数据表
                with engine.connect() as conn:
                    conn.execute(
                        text("""
                            INSERT OR REPLACE INTO cache_metadata
                            (cache_key, data_json, data_count, last_refresh)
                            VALUES (:key, :data, :count, :time)
                        """),
                        {
                            "key": task_name,
                            "data": json.dumps(records, ensure_ascii=False),
                            "count": len(records),
                            "time": datetime.now(),
                        },
                    )
                    conn.commit()

            logger.debug(f"[DBStore] 保存成功: {task_name}, {len(records)} 条")
            return True

        except Exception as e:
            logger.error(f"[DBStore] 保存失败: {task_name}, {e}")
            return False

    async def load_records(self, task_name: str) -> Optional[List[Dict[str, Any]]]:
        """
        从数据库加载记录

        Args:
            task_name: 任务名称

        Returns:
            记录列表
        """
        self._ensure_tables()
        engine = self._get_engine()
        if engine is None:
            return None

        try:
            import json

            from sqlalchemy import text

            if task_name == "stock_list":
                with engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT symbol, name, pinyin, sector FROM cache_stock_info")
                    )
                    records = [
                        {"symbol": row[0], "name": row[1], "pinyin": row[2], "sector": row[3]}
                        for row in result
                    ]
                    return records if records else None
            else:
                with engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT data_json FROM cache_metadata WHERE cache_key = :key"),
                        {"key": task_name},
                    )
                    row = result.fetchone()
                    if row and row[0]:
                        return cast(List[Dict[str, Any]], json.loads(row[0]))
                    return None

        except Exception as e:
            logger.error(f"[DBStore] 加载失败: {task_name}, {e}")
            return None

    async def get_last_update_time(self, task_name: str) -> Optional[datetime]:
        """
        获取任务的最后更新时间

        Args:
            task_name: 任务名称

        Returns:
            最后更新时间，如果没有记录返回 None
        """
        self._ensure_tables()
        engine = self._get_engine()
        if engine is None:
            return None

        try:
            from sqlalchemy import text

            if task_name == "stock_list":
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT MAX(updated_at) FROM cache_stock_info"))
                    row = result.fetchone()
                    if row and row[0]:
                        return (
                            row[0]
                            if isinstance(row[0], datetime)
                            else datetime.fromisoformat(str(row[0]))
                        )
                    return None
            else:
                with engine.connect() as conn:
                    result = conn.execute(
                        text("SELECT last_refresh FROM cache_metadata WHERE cache_key = :key"),
                        {"key": task_name},
                    )
                    row = result.fetchone()
                    if row and row[0]:
                        return (
                            row[0]
                            if isinstance(row[0], datetime)
                            else datetime.fromisoformat(str(row[0]))
                        )
                    return None

        except Exception as e:
            logger.error(f"[DBStore] 获取更新时间失败: {task_name}, {e}")
            return None


# 全局实例
_db_store: Optional[DBStore] = None


def get_db_store() -> DBStore:
    """获取全局数据库存储实例"""
    global _db_store
    if _db_store is None:
        _db_store = DBStore()
    return _db_store
