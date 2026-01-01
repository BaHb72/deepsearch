"""
GC 历史记录持久化服务

使用 SQLite 存储 GC 历史记录，支持：
- 记录每次 GC 的详细信息
- 按时间范围查询
- 统计摘要（按小时/天/周/月）
- 自动清理过期记录

数据库文件位置: data/gc_history.db
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Generator, List, Literal, Optional

from deepsearch.observability import get_logger

logger = get_logger(__name__)

TriggerType = Literal["periodic", "manual", "threshold", "shutdown"]

# 数据库表创建 SQL
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS gc_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    gen0_collected INTEGER DEFAULT 0,
    gen1_collected INTEGER DEFAULT 0,
    gen2_collected INTEGER DEFAULT 0,
    uncollectable INTEGER DEFAULT 0,
    duration_ms REAL,
    memory_before_mb REAL,
    memory_after_mb REAL,
    memory_freed_mb REAL,
    trigger_type TEXT CHECK(trigger_type IN ('periodic', 'manual', 'threshold', 'shutdown'))
);
"""

CREATE_INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_gc_timestamp ON gc_history(timestamp);",
    "CREATE INDEX IF NOT EXISTS idx_gc_trigger_type ON gc_history(trigger_type);",
]


class GCHistoryPersistence:
    """
    GC 历史记录持久化服务

    线程安全，使用线程本地存储管理数据库连接。

    Example:
        >>> persistence = GCHistoryPersistence()
        >>> persistence.record({
        ...     "collected": [100, 50, 10],
        ...     "uncollectable": 0,
        ...     "duration_ms": 5.5,
        ...     "memory_before_mb": 512.0,
        ...     "memory_after_mb": 500.0,
        ...     "memory_freed_mb": 12.0,
        ...     "timestamp": "2026-01-01T02:30:00"
        ... }, trigger_type="periodic")
        >>> records = persistence.query(limit=10)
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        初始化持久化服务

        Args:
            db_path: 数据库路径，默认为 data/gc_history.db
        """
        if db_path is None:
            # 默认使用 data 目录
            from deepsearch.config import get_config

            try:
                settings = get_config()
                data_dir = Path(settings.app.data_dir)
            except Exception:
                data_dir = Path("data")
            self.db_path = data_dir / "gc_history.db"
        else:
            self.db_path = db_path

        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 线程本地存储
        self._local = threading.local()
        self._lock = threading.Lock()

        # 初始化数据库
        self._init_db()

        logger.debug(f"GC 历史持久化服务已初始化: {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """获取线程本地的数据库连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30.0,
            )
            self._local.conn.row_factory = sqlite3.Row
            # 启用 WAL 模式提高并发性能
            self._local.conn.execute("PRAGMA journal_mode=WAL;")
            self._local.conn.execute("PRAGMA synchronous=NORMAL;")
        return self._local.conn

    @contextmanager
    def _get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """获取数据库游标的上下文管理器"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_db(self) -> None:
        """初始化数据库表和索引"""
        with self._lock:
            with self._get_cursor() as cursor:
                cursor.execute(CREATE_TABLE_SQL)
                for index_sql in CREATE_INDEX_SQL:
                    cursor.execute(index_sql)
            logger.debug("GC 历史数据库表已初始化")

    def record(
        self,
        gc_result: Dict[str, Any],
        trigger_type: TriggerType = "periodic",
    ) -> int:
        """
        记录 GC 结果

        Args:
            gc_result: GC 执行结果字典，包含：
                - collected: List[int] - 三代回收的对象数
                - uncollectable: int - 不可回收对象数
                - duration_ms: float - 执行耗时(毫秒)
                - memory_before_mb: float - GC 前内存(MB)
                - memory_after_mb: float - GC 后内存(MB)
                - memory_freed_mb: float - 释放内存(MB)
                - timestamp: str - ISO 格式时间戳
            trigger_type: 触发类型

        Returns:
            插入的记录 ID
        """
        # 解析 collected 列表
        collected = gc_result.get("collected", [0, 0, 0])
        if isinstance(collected, list) and len(collected) >= 3:
            gen0, gen1, gen2 = collected[0], collected[1], collected[2]
        else:
            gen0, gen1, gen2 = 0, 0, 0

        # 解析时间戳
        timestamp_str = gc_result.get("timestamp")
        if timestamp_str:
            try:
                if isinstance(timestamp_str, str):
                    timestamp = datetime.fromisoformat(timestamp_str)
                elif isinstance(timestamp_str, datetime):
                    timestamp = timestamp_str
                else:
                    timestamp = datetime.now()
            except ValueError:
                timestamp = datetime.now()
        else:
            timestamp = datetime.now()

        insert_sql = """
        INSERT INTO gc_history (
            timestamp, gen0_collected, gen1_collected, gen2_collected,
            uncollectable, duration_ms, memory_before_mb, memory_after_mb,
            memory_freed_mb, trigger_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self._get_cursor() as cursor:
            cursor.execute(
                insert_sql,
                (
                    timestamp.isoformat(),
                    gen0,
                    gen1,
                    gen2,
                    gc_result.get("uncollectable", 0),
                    gc_result.get("duration_ms", 0.0),
                    gc_result.get("memory_before_mb", 0.0),
                    gc_result.get("memory_after_mb", 0.0),
                    gc_result.get("memory_freed_mb", 0.0),
                    trigger_type,
                ),
            )
            record_id = cursor.lastrowid

        logger.debug(f"GC 历史已记录: id={record_id}, trigger={trigger_type}")
        return record_id or 0

    def query(
        self,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        trigger_type: Optional[TriggerType] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        按条件查询 GC 历史

        Args:
            start: 开始时间
            end: 结束时间
            trigger_type: 触发类型过滤
            limit: 返回记录数限制
            offset: 分页偏移

        Returns:
            GC 历史记录列表
        """
        conditions: List[str] = []
        params: List[Any] = []

        if start:
            conditions.append("timestamp >= ?")
            params.append(start.isoformat())

        if end:
            conditions.append("timestamp <= ?")
            params.append(end.isoformat())

        if trigger_type:
            conditions.append("trigger_type = ?")
            params.append(trigger_type)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query_sql = f"""
        SELECT
            id, timestamp, gen0_collected, gen1_collected, gen2_collected,
            (gen0_collected + gen1_collected + gen2_collected) as total_collected,
            uncollectable, duration_ms, memory_before_mb, memory_after_mb,
            memory_freed_mb, trigger_type
        FROM gc_history
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        with self._get_cursor() as cursor:
            cursor.execute(query_sql, params)
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_stats(
        self,
        period: Literal["hour", "day", "week", "month"] = "day",
    ) -> Dict[str, Any]:
        """
        获取统计摘要

        Args:
            period: 统计周期

        Returns:
            统计信息字典，包含：
            - period: 统计周期
            - start_time: 统计开始时间
            - end_time: 统计结束时间
            - total_gc_count: GC 执行总次数
            - total_collected: 总回收对象数
            - total_memory_freed_mb: 总释放内存(MB)
            - avg_duration_ms: 平均耗时(毫秒)
            - by_trigger_type: 按触发类型分组统计
        """
        now = datetime.now()

        if period == "hour":
            start_time = now - timedelta(hours=1)
        elif period == "day":
            start_time = now - timedelta(days=1)
        elif period == "week":
            start_time = now - timedelta(weeks=1)
        elif period == "month":
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(days=1)

        # 总体统计
        summary_sql = """
        SELECT
            COUNT(*) as total_gc_count,
            COALESCE(SUM(gen0_collected + gen1_collected + gen2_collected), 0) as total_collected,
            COALESCE(SUM(memory_freed_mb), 0) as total_memory_freed_mb,
            COALESCE(AVG(duration_ms), 0) as avg_duration_ms,
            COALESCE(MAX(memory_freed_mb), 0) as max_memory_freed_mb,
            COALESCE(MIN(memory_freed_mb), 0) as min_memory_freed_mb
        FROM gc_history
        WHERE timestamp >= ?
        """

        # 按触发类型分组
        by_type_sql = """
        SELECT
            trigger_type,
            COUNT(*) as count,
            COALESCE(SUM(memory_freed_mb), 0) as memory_freed_mb
        FROM gc_history
        WHERE timestamp >= ?
        GROUP BY trigger_type
        """

        with self._get_cursor() as cursor:
            cursor.execute(summary_sql, (start_time.isoformat(),))
            summary_row = cursor.fetchone()

            cursor.execute(by_type_sql, (start_time.isoformat(),))
            by_type_rows = cursor.fetchall()

        by_trigger_type = {
            row["trigger_type"]: {
                "count": row["count"],
                "memory_freed_mb": round(row["memory_freed_mb"], 2),
            }
            for row in by_type_rows
            if row["trigger_type"]
        }

        return {
            "period": period,
            "start_time": start_time.isoformat(),
            "end_time": now.isoformat(),
            "total_gc_count": summary_row["total_gc_count"] if summary_row else 0,
            "total_collected": summary_row["total_collected"] if summary_row else 0,
            "total_memory_freed_mb": round(
                summary_row["total_memory_freed_mb"] if summary_row else 0, 2
            ),
            "avg_duration_ms": round(summary_row["avg_duration_ms"] if summary_row else 0, 2),
            "max_memory_freed_mb": round(
                summary_row["max_memory_freed_mb"] if summary_row else 0, 2
            ),
            "min_memory_freed_mb": round(
                summary_row["min_memory_freed_mb"] if summary_row else 0, 2
            ),
            "by_trigger_type": by_trigger_type,
        }

    def cleanup(self, days: int = 90) -> int:
        """
        清理旧记录

        Args:
            days: 保留天数，默认 90 天

        Returns:
            删除的记录数
        """
        cutoff = datetime.now() - timedelta(days=days)

        delete_sql = "DELETE FROM gc_history WHERE timestamp < ?"

        with self._get_cursor() as cursor:
            cursor.execute(delete_sql, (cutoff.isoformat(),))
            deleted_count = cursor.rowcount

        if deleted_count > 0:
            logger.info(f"已清理 {deleted_count} 条过期 GC 历史记录 (保留 {days} 天)")

            # 执行 VACUUM 释放空间
            try:
                conn = self._get_connection()
                conn.execute("VACUUM;")
            except Exception as e:
                logger.debug(f"VACUUM 执行失败: {e}")

        return deleted_count

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        获取最近的 GC 记录（用于替代内存中的 _gc_history）

        Args:
            limit: 返回记录数

        Returns:
            最近的 GC 记录列表
        """
        return self.query(limit=limit)

    def close(self) -> None:
        """关闭数据库连接"""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None
        logger.debug("GC 历史持久化服务已关闭")


# 单例实例（延迟初始化）
_gc_persistence_instance: Optional[GCHistoryPersistence] = None
_gc_persistence_lock = threading.Lock()


def get_gc_persistence() -> GCHistoryPersistence:
    """获取 GC 历史持久化服务单例"""
    global _gc_persistence_instance

    if _gc_persistence_instance is None:
        with _gc_persistence_lock:
            if _gc_persistence_instance is None:
                _gc_persistence_instance = GCHistoryPersistence()

    return _gc_persistence_instance


__all__ = [
    "GCHistoryPersistence",
    "get_gc_persistence",
    "TriggerType",
]
