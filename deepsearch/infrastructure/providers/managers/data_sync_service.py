"""
数据同步服务

负责从PostgreSQL同步数据到DuckDB进行分析
"""

import asyncio
import inspect
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from loguru import logger


class DataSyncService:
    """数据同步服务 - PostgreSQL到DuckDB的数据同步"""

    def __init__(self, database_component=None):
        """
        初始化数据同步服务

        Args:
            database_component: 数据库组件实例，用于获取PostgreSQL连接
        """
        self._database_component = database_component
        self._analytics_db = None
        self._running = False
        self._sync_task = None
        self.sync_interval = 3600  # 默认1小时同步一次
        self._last_sync_time = {}

    def set_analytics_db(self, analytics_db):
        """设置DuckDB分析数据库实例"""
        self._analytics_db = analytics_db

    def set_database_component(self, database_component) -> None:
        """设置 PostgreSQL 数据源组件"""
        self._database_component = database_component

    @staticmethod
    def _coerce_dataframe(payload: Any) -> pd.DataFrame:
        """将任意负载转换为 DataFrame，用于统一写入 DuckDB。"""
        if payload is None:
            return pd.DataFrame()
        if isinstance(payload, pd.DataFrame):
            return payload.copy()
        if isinstance(payload, list):
            return pd.DataFrame(payload)
        if isinstance(payload, dict):
            return pd.DataFrame([payload])
        try:
            return pd.DataFrame(payload)
        except Exception:  # pragma: no cover - 容错
            return pd.DataFrame()

    async def start(self):
        """启动定时同步服务"""
        if self._running:
            logger.warning("数据同步服务已经在运行")
            return

        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info(f"数据同步服务已启动，同步间隔: {self.sync_interval}秒")

    async def stop(self):
        """停止同步服务"""
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        logger.info("数据同步服务已停止")

    async def _sync_loop(self):
        """同步循环"""
        while self._running:
            try:
                await self.sync_all_tables()
                await asyncio.sleep(self.sync_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"数据同步失败: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟重试

    async def sync_all_tables(self):
        """同步所有表"""
        try:
            # 同步K线历史数据
            await self.sync_kline_history()

            # 同步股票信息
            await self.sync_stock_info()

            # 同步实时数据快照
            await self.sync_realtime_snapshot()

            logger.info("所有表同步完成")
        except Exception as e:
            logger.error(f"同步所有表失败: {e}")

    async def sync_kline_history(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        symbols: Optional[List[str]] = None,
    ):
        """
        同步K线历史数据

        Args:
            start_date: 开始日期
            end_date: 结束日期
            symbols: 股票代码列表
        """
        if not self._analytics_db:
            logger.warning("DuckDB未初始化，跳过同步")
            return

        if not self._database_component:
            logger.warning("未配置 PostgreSQL 数据源，无法同步 K 线数据")
            return

        fetcher = getattr(self._database_component, "fetch_kline_history", None)
        if fetcher is None:
            logger.warning("数据库组件未实现 fetch_kline_history，跳过 K 线同步")
            return

        try:
            last_sync = self._last_sync_time.get("kline_history")
            if not start_date and last_sync:
                start_date = last_sync.strftime("%Y-%m-%d")
            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            fetch_kwargs: Dict[str, Any] = {}
            if start_date:
                fetch_kwargs["start_date"] = start_date
            if end_date:
                fetch_kwargs["end_date"] = end_date
            if symbols:
                fetch_kwargs["symbols"] = symbols

            result = fetcher(**fetch_kwargs)
            if inspect.iscoroutine(result):
                result = await result

        except TypeError as exc:
            logger.error(f"fetch_kline_history 参数不兼容: {exc}")
            return
        except Exception as exc:
            logger.error(f"拉取 K 线数据失败: {exc}")
            return

        df = self._coerce_dataframe(result)

        if df.empty:
            logger.info("没有新的K线数据需要同步")
            return

        try:
            await self._analytics_db.import_from_dataframe(df, "kline_history", if_exists="replace")
            self._last_sync_time["kline_history"] = datetime.now()
            logger.info("同步了 {} 条K线数据", len(df))
        except Exception as import_error:
            if "Duplicate key" in str(import_error):
                logger.warning(f"跳过重复的K线数据: {import_error}")
                try:
                    for _, row in df.iterrows():
                        self._analytics_db.conn.execute(
                            "DELETE FROM kline_history WHERE symbol = ? AND time = ?",
                            (row.get("symbol"), row.get("time")),
                        )
                    await self._analytics_db.import_from_dataframe(
                        df, "kline_history", if_exists="append"
                    )
                    logger.info("使用 upsert 方式同步了 {} 条K线数据", len(df))
                except Exception as upsert_error:
                    logger.error(f"Upsert失败: {upsert_error}")
            else:
                logger.error(f"写入 K 线数据失败: {import_error}")
                raise

    async def sync_stock_info(self):
        """同步股票信息"""
        if not self._analytics_db:
            logger.warning("DuckDB未初始化，跳过股票信息同步")
            return

        if not self._database_component:
            logger.warning("未配置 PostgreSQL 数据源，无法同步股票信息")
            return

        fetcher = None
        for attr in ("fetch_stock_info", "fetch_all_stock_info", "get_stock_info"):
            candidate = getattr(self._database_component, attr, None)
            if callable(candidate):
                fetcher = candidate
                break

        if fetcher is None:
            logger.warning("数据库组件未实现股票信息拉取接口，跳过同步")
            return

        try:
            result = fetcher()
            if inspect.iscoroutine(result):
                result = await result
        except Exception as exc:
            logger.error(f"拉取股票信息失败: {exc}")
            return

        stock_info = self._coerce_dataframe(result)
        if stock_info.empty:
            logger.info("无股票信息更新，跳过写入")
            return

        required_columns = {"symbol", "name"}
        missing = required_columns - set(stock_info.columns)
        if missing:
            logger.error("股票信息缺少必要字段: {}", ", ".join(sorted(missing)))
            return

        try:
            self._analytics_db.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_info
                (
                    symbol
                    VARCHAR
                    PRIMARY
                    KEY,
                    name
                    VARCHAR,
                    market
                    VARCHAR,
                    sector
                    VARCHAR
                )
                """
            )
            await self._analytics_db.import_from_dataframe(
                stock_info, "stock_info", if_exists="replace"
            )
            logger.info("同步了 {} 条股票信息", len(stock_info))
        except Exception as exc:
            logger.error(f"同步股票信息失败: {exc}")

    async def sync_realtime_snapshot(self):
        """同步实时数据快照"""
        try:
            # 获取最新的实时数据快照
            # 这里应该从实时数据源获取

            # 暂时跳过实时数据同步
            logger.debug("实时数据快照同步已跳过（等待实时数据源）")

        except Exception as e:
            logger.error(f"同步实时数据快照失败: {e}")

    async def sync_incremental(self, table_name: str):
        """
        增量同步指定表

        Args:
            table_name: 表名
        """
        try:
            if table_name == "kline_history":
                await self.sync_kline_history()
            elif table_name == "stock_info":
                await self.sync_stock_info()
            else:
                logger.warning(f"不支持的表: {table_name}")

        except Exception as e:
            logger.error(f"增量同步 {table_name} 失败: {e}")

    async def sync_historical_data(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        symbols: Optional[List[str]] = None,
    ) -> None:
        """
        同步历史数据

        Args:
            start_date: 开始日期
            end_date: 结束日期
            symbols: 股票代码列表
        """
        await self.sync_kline_history(start_date, end_date, symbols)

    async def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        return {
            "running": self._running,
            "sync_interval": self.sync_interval,
            "last_sync_time": {
                table: time.isoformat() if time else None
                for table, time in self._last_sync_time.items()
            },
            "analytics_db_connected": self._analytics_db is not None,
            "database_connected": self._database_component is not None,
        }

    async def sync_now(self) -> Dict[str, Any]:
        """立即执行一次同步"""
        logger.info("手动触发数据同步")
        await self.sync_all_tables()
        return {
            "status": "completed",
            "sync_time": datetime.now().isoformat(),
            "tables_synced": list(self._last_sync_time.keys()),
        }


# 全局实例
_sync_service_instance: Optional[DataSyncService] = None


def get_sync_service(database_component=None) -> DataSyncService:
    """
    获取全局数据同步服务实例

    Args:
        database_component: 数据库组件实例

    Returns:
        DataSyncService实例
    """
    global _sync_service_instance
    if _sync_service_instance is None:
        _sync_service_instance = DataSyncService(database_component)
    elif database_component is not None:
        _sync_service_instance.set_database_component(database_component)

    return _sync_service_instance
