"""
极简数据同步管道 (DataSyncPipeline)

核心理念：配置驱动，约定优于配置
设计原则：利用数据库原生能力（COALESCE + ON CONFLICT）实现数据合并

使用方式:
    pipeline = DataSyncPipeline(db)
    pipeline.register("amazingdata", fetcher=fetch_func, field_map={...})
    pipeline.register("akshare", fetcher=fetch_func, field_map={...})
    await pipeline.sync("kline_history")
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Union

import pandas as pd

from deepsearch.observability import get_logger

logger = get_logger(__name__)


# ============ 配置类 ============


@dataclass
class SourceConfig:
    """数据源配置

    Attributes:
        name: 数据源名称（唯一标识）
        fetcher: 数据拉取函数，签名为 (table, **kwargs) -> pd.DataFrame
        field_map: 字段映射，{原始字段名: 标准字段名}
        priority: 优先级，数值越大优先级越高（高优先级的数据作为基础）
        key_columns: 主键列名列表，用于 UPSERT
    """

    name: str
    fetcher: Callable[..., Union[pd.DataFrame, Any]]
    field_map: Dict[str, str]
    priority: int = 0
    key_columns: List[str] = field(default_factory=lambda: ["symbol", "timestamp"])


@dataclass
class SyncState:
    """同步状态

    记录每个数据源对每张表的同步进度
    """

    source: str
    table: str
    last_timestamp: Optional[datetime] = None
    last_sync_at: Optional[datetime] = None
    rows_synced: int = 0


@dataclass
class SyncResult:
    """同步结果"""

    source: str
    table: str
    rows_synced: int
    duration_ms: float
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


# ============ 核心管道 ============


class DataSyncPipeline:
    """极简数据同步管道

    核心功能:
    1. 从多个数据源拉取数据
    2. 规范化字段名
    3. UPSERT 到目标数据库（自动合并、空值补充）

    特性:
    - 增量同步：记住上次同步位置
    - 多源合并：使用 COALESCE 实现空值补充
    - 优先级：高优先级数据源的值优先保留
    """

    def __init__(self, target_db: Any):
        """初始化

        Args:
            target_db: 目标数据库实例，需要支持 execute() 和 query() 方法
        """
        self._db = target_db
        self._sources: Dict[str, SourceConfig] = {}
        self._states: Dict[str, SyncState] = {}
        self._initialized = False

    def register(
        self,
        name: str,
        fetcher: Callable[..., Union[pd.DataFrame, Any]],
        field_map: Dict[str, str],
        priority: int = 0,
        key_columns: Optional[List[str]] = None,
    ) -> "DataSyncPipeline":
        """注册数据源

        Args:
            name: 数据源名称
            fetcher: 拉取函数，支持同步或异步
            field_map: 字段映射 {原始名: 标准名}
            priority: 优先级（越大越优先）
            key_columns: 主键列，默认 ["symbol", "timestamp"]

        Returns:
            self，支持链式调用
        """
        self._sources[name] = SourceConfig(
            name=name,
            fetcher=fetcher,
            field_map=field_map,
            priority=priority,
            key_columns=key_columns or ["symbol", "timestamp"],
        )
        logger.info(f"注册数据源: {name}, 优先级={priority}, 字段数={len(field_map)}")
        return self

    def unregister(self, name: str) -> "DataSyncPipeline":
        """注销数据源"""
        if name in self._sources:
            del self._sources[name]
            logger.info(f"注销数据源: {name}")
        return self

    @property
    def sources(self) -> List[str]:
        """获取已注册的数据源名称列表"""
        return list(self._sources.keys())

    async def sync(
        self,
        table: str,
        sources: Optional[List[str]] = None,
        force_full: bool = False,
        parallel: bool = False,
        **fetch_kwargs,
    ) -> Dict[str, SyncResult]:
        """同步数据

        Args:
            table: 目标表名
            sources: 要同步的数据源列表，None 表示全部
            force_full: 是否强制全量同步
            parallel: 是否并行拉取（注意：写入仍按优先级顺序）
            **fetch_kwargs: 传递给 fetcher 的额外参数

        Returns:
            各数据源的同步结果
        """
        sources = sources or list(self._sources.keys())
        results: Dict[str, SyncResult] = {}

        # 按优先级排序（高优先级先同步）
        sorted_sources = sorted(
            [self._sources[s] for s in sources if s in self._sources], key=lambda x: -x.priority
        )

        if not sorted_sources:
            logger.warning("没有可用的数据源进行同步")
            return results

        logger.info(f"开始同步表 {table}，数据源: {[s.name for s in sorted_sources]}")

        if parallel:
            # 并行拉取
            fetch_tasks = [
                self._fetch_and_normalize(source, table, force_full, **fetch_kwargs)
                for source in sorted_sources
            ]
            fetch_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

            # 按优先级顺序写入
            for source, result in zip(sorted_sources, fetch_results):
                if isinstance(result, Exception):
                    results[source.name] = SyncResult(
                        source=source.name,
                        table=table,
                        rows_synced=0,
                        duration_ms=0,
                        error=str(result),
                    )
                else:
                    df, fetch_duration = result  # type: ignore[misc]
                    write_result = await self._write_data(df, table, source)
                    results[source.name] = SyncResult(
                        source=source.name,
                        table=table,
                        rows_synced=write_result,
                        duration_ms=fetch_duration,
                    )
        else:
            # 顺序同步
            for source in sorted_sources:
                result = await self._sync_source(source, table, force_full, **fetch_kwargs)  # type: ignore[assignment]
                results[source.name] = result  # type: ignore[assignment]

        # 统计
        total = sum(r.rows_synced for r in results.values())
        errors = [r.source for r in results.values() if r.error]

        if errors:
            logger.warning(f"同步完成，总计 {total} 行，失败数据源: {errors}")
        else:
            logger.info(f"同步完成，总计 {total} 行")

        return results

    async def _sync_source(
        self,
        source: SourceConfig,
        table: str,
        force_full: bool,
        **fetch_kwargs,
    ) -> SyncResult:
        """同步单个数据源"""
        start_time = datetime.now()

        try:
            # 1. Fetch + Normalize
            df, _ = await self._fetch_and_normalize(source, table, force_full, **fetch_kwargs)

            if df.empty:
                return SyncResult(
                    source=source.name,
                    table=table,
                    rows_synced=0,
                    duration_ms=0,
                )

            # 2. Write
            rows = await self._write_data(df, table, source)

            # 3. 更新状态
            self._update_state(source.name, table, df, rows)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            return SyncResult(
                source=source.name,
                table=table,
                rows_synced=rows,
                duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error(f"同步 {source.name} 失败: {e}", exc_info=True)
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            return SyncResult(
                source=source.name,
                table=table,
                rows_synced=0,
                duration_ms=duration_ms,
                error=str(e),
            )

    async def _fetch_and_normalize(
        self,
        source: SourceConfig,
        table: str,
        force_full: bool,
        **fetch_kwargs,
    ) -> tuple[pd.DataFrame, float]:
        """拉取并规范化数据"""
        start_time = datetime.now()

        # 获取增量起点
        if not force_full:
            state = self._get_state(source.name, table)
            if state.last_timestamp:
                fetch_kwargs["since"] = state.last_timestamp

        # 调用 fetcher
        logger.debug(f"从 {source.name} 拉取 {table}, kwargs={fetch_kwargs}")

        result = source.fetcher(table, **fetch_kwargs)

        # 处理异步 fetcher
        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
            result = await result

        # 确保返回 DataFrame
        if not isinstance(result, pd.DataFrame):
            if result is None:
                result = pd.DataFrame()
            else:
                result = pd.DataFrame(result)

        if result.empty:
            logger.debug(f"{source.name} 返回空数据")
            return pd.DataFrame(), 0

        # 规范化字段名
        df = self._normalize(result, source)

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"从 {source.name} 获取 {len(df)} 行，耗时 {duration_ms:.1f}ms")

        return df, duration_ms

    def _normalize(self, df: pd.DataFrame, source: SourceConfig) -> pd.DataFrame:
        """规范化字段名"""
        # 只重命名存在的列
        rename_map = {old: new for old, new in source.field_map.items() if old in df.columns}

        if rename_map:
            df = df.rename(columns=rename_map)

        # 添加元数据
        df["_source"] = source.name
        df["_synced_at"] = datetime.utcnow()

        return df

    async def _write_data(
        self,
        df: pd.DataFrame,
        table: str,
        source: SourceConfig,
    ) -> int:
        """写入数据（UPSERT + 空值补充）"""
        if df.empty:
            return 0

        columns = list(df.columns)
        key_cols = source.key_columns
        value_cols = [c for c in columns if c not in key_cols]

        # 构建 UPSERT SQL
        # 使用 COALESCE 实现"空值补充"：新值非空则用新值，否则保留旧值
        update_parts = []
        for col in value_cols:
            if col.startswith("_"):
                # 元数据字段总是更新
                update_parts.append(f"{col} = excluded.{col}")
            else:
                # 业务字段使用 COALESCE
                update_parts.append(f"{col} = COALESCE(excluded.{col}, {table}.{col})")

        update_clause = ", ".join(update_parts)

        placeholders = ", ".join(["?" for _ in columns])
        key_clause = ", ".join(key_cols)
        columns_clause = ", ".join(columns)

        sql = f"""
            INSERT INTO {table} ({columns_clause})
            VALUES ({placeholders})
            ON CONFLICT ({key_clause}) DO UPDATE SET
            {update_clause}
        """

        # 批量写入
        rows = 0
        batch_size = 1000

        for i in range(0, len(df), batch_size):
            batch = df.iloc[i : i + batch_size]

            for _, row in batch.iterrows():
                try:
                    values = tuple(None if pd.isna(row[c]) else row[c] for c in columns)
                    await self._execute(sql, values)
                    rows += 1
                except Exception as e:
                    logger.warning(f"写入行失败: {e}")
                    continue

        return rows

    async def _execute(self, sql: str, params: tuple) -> None:
        """执行 SQL"""
        if hasattr(self._db, "execute"):
            result = self._db.execute(sql, params)
            if asyncio.iscoroutine(result):
                await result
        else:
            raise RuntimeError("目标数据库不支持 execute() 方法")

    def _get_state(self, source: str, table: str) -> SyncState:
        """获取同步状态"""
        key = f"{source}:{table}"
        if key not in self._states:
            self._states[key] = SyncState(source=source, table=table)
        return self._states[key]

    def _update_state(
        self,
        source: str,
        table: str,
        df: pd.DataFrame,
        rows: int,
    ) -> None:
        """更新同步状态"""
        key = f"{source}:{table}"
        state = self._states.get(key) or SyncState(source=source, table=table)

        # 更新时间戳
        if "timestamp" in df.columns and not df.empty:
            max_ts = df["timestamp"].max()
            if pd.notna(max_ts):
                if isinstance(max_ts, str):
                    max_ts = pd.to_datetime(max_ts)
                state.last_timestamp = max_ts

        state.last_sync_at = datetime.utcnow()
        state.rows_synced += rows

        self._states[key] = state

    def get_state(self, source: str, table: str) -> Optional[SyncState]:
        """获取同步状态（公开方法）"""
        return self._states.get(f"{source}:{table}")

    def get_all_states(self) -> Dict[str, SyncState]:
        """获取所有同步状态"""
        return dict(self._states)

    def reset_state(self, source: str, table: str) -> None:
        """重置同步状态（将触发全量同步）"""
        key = f"{source}:{table}"
        if key in self._states:
            del self._states[key]
            logger.info(f"重置同步状态: {key}")


# ============ 便捷函数 ============


def create_pipeline(target_db: Any) -> DataSyncPipeline:
    """创建同步管道的工厂函数"""
    return DataSyncPipeline(target_db)
