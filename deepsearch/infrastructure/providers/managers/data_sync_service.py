"""
数据同步服务

负责从PostgreSQL同步数据到DuckDB进行分析
"""

import asyncio
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

        try:
            # 获取最后同步时间
            last_sync = self._last_sync_time.get("kline_history")

            # 如果没有指定时间范围，使用增量同步
            if not start_date and last_sync:
                start_date = last_sync.strftime("%Y-%m-%d")

            if not end_date:
                end_date = datetime.now().strftime("%Y-%m-%d")

            # 构建查询条件
            conditions = []
            params = []

            if start_date:
                conditions.append("time >= %s")
                params.append(start_date)

            if end_date:
                conditions.append("time <= %s")
                params.append(end_date)

            if symbols:
                placeholders = ",".join(["%s"] * len(symbols))
                conditions.append(f"symbol IN ({placeholders})")
                params.extend(symbols)

            " AND ".join(conditions) if conditions else "1=1"

            # 从PostgreSQL读取数据 (这里使用模拟数据，实际应该从database_component获取)
            # 在实际实现中，应该使用 self._database_component 获取数据

            # 创建模拟数据用于测试
            import numpy as np

            dates = pd.date_range(
                start=start_date or "2024-01-01", end=end_date or datetime.now(), freq="D"
            )

            sample_data = []
            for symbol in symbols or ["000001", "000002", "600000"]:
                for date in dates:
                    base_price = 10 + np.random.rand() * 50
                    sample_data.append(
                        {
                            "symbol": symbol,
                            "time": date,
                            "open": base_price + np.random.randn(),
                            "high": base_price + abs(np.random.randn()) * 2,
                            "low": base_price - abs(np.random.randn()) * 2,
                            "close": base_price + np.random.randn(),
                            "volume": int(1000000 * (1 + np.random.rand())),
                            "amount": int(10000000 * (1 + np.random.rand())),
                        }
                    )

            df = pd.DataFrame(sample_data)

            if not df.empty:
                try:
                    # 导入到DuckDB，使用replace避免重复键冲突
                    await self._analytics_db.import_from_dataframe(
                        df, "kline_history", if_exists="replace"
                    )

                    # 更新最后同步时间
                    self._last_sync_time["kline_history"] = datetime.now()

                    logger.info(f"同步了 {len(df)} 条K线数据")
                except Exception as import_error:
                    if "Duplicate key" in str(import_error):
                        logger.warning(f"跳过重复的K线数据: {import_error}")
                        # 尝试使用upsert逻辑（先删除再插入）
                        try:
                            for _, row in df.iterrows():
                                self._analytics_db.conn.execute(
                                    "DELETE FROM kline_history WHERE symbol = ? AND time = ?",
                                    (row["symbol"], row["time"]),
                                )
                            await self._analytics_db.import_from_dataframe(
                                df, "kline_history", if_exists="append"
                            )
                            logger.info(f"使用upsert方式同步了 {len(df)} 条K线数据")
                        except Exception as upsert_error:
                            logger.error(f"Upsert失败: {upsert_error}")
                    else:
                        raise import_error
            else:
                logger.info("没有新的K线数据需要同步")

        except Exception as e:
            logger.error(f"同步K线历史数据失败: {e}")

    async def sync_stock_info(self):
        """同步股票信息"""
        try:
            # 这里应该从database_component获取股票信息
            # 暂时使用模拟数据

            stock_info = pd.DataFrame(
                [
                    {"symbol": "000001", "name": "平安银行", "market": "SZ", "sector": "金融"},
                    {"symbol": "000002", "name": "万科A", "market": "SZ", "sector": "房地产"},
                    {"symbol": "600000", "name": "浦发银行", "market": "SH", "sector": "金融"},
                ]
            )

            # 创建股票信息表（如果不存在）
            if self._analytics_db and hasattr(self._analytics_db, "conn"):
                self._analytics_db.conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS stock_info (
                        symbol VARCHAR PRIMARY KEY,
                        name VARCHAR,
                        market VARCHAR,
                        sector VARCHAR
                    )
                """
                )

                # 导入数据
                await self._analytics_db.import_from_dataframe(
                    stock_info, "stock_info", if_exists="replace"
                )

                logger.info(f"同步了 {len(stock_info)} 条股票信息")

        except Exception as e:
            logger.error(f"同步股票信息失败: {e}")

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
    elif database_component and not _sync_service_instance._database_component:
        # 如果提供了database_component且当前实例没有设置，则设置它
        _sync_service_instance._database_component = database_component

    return _sync_service_instance
