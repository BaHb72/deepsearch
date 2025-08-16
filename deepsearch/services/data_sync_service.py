"""
数据同步服务

负责 PostgreSQL 到 DuckDB 的数据同步
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import pandas as pd
from loguru import logger
from sqlalchemy import text

from deepsearch.storage.duckdb_analytics import get_analytics_db


class DataSyncService:
    """PostgreSQL 到 DuckDB 数据同步服务"""

    def __init__(self, database_component=None):
        """
        初始化同步服务
        
        Args:
            database_component: 数据库组件（PostgreSQL）
        """
        self.database = database_component
        self.analytics_db = get_analytics_db()
        self.sync_interval = 3600  # 默认同步间隔（秒）
        self._sync_task = None
        self._running = False

    async def start(self):
        """启动同步服务"""
        if self._running:
            logger.warning("数据同步服务已在运行")
            return

        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        logger.info("数据同步服务已启动")

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
                # 执行同步
                await self.sync_historical_data()

                # 等待下次同步
                await asyncio.sleep(self.sync_interval)

            except Exception as e:
                logger.error(f"同步循环出错: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟重试

    async def sync_historical_data(
            self,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            symbols: Optional[List[str]] = None
    ):
        """
        同步历史数据
        
        Args:
            start_date: 开始日期，默认为 T-30
            end_date: 结束日期，默认为 T-1
            symbols: 股票列表，None 表示全部
        """
        sync_id = str(uuid.uuid4())
        sync_time = datetime.now()

        # 默认同步 T-30 到 T-1 的数据
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        logger.info(f"开始同步历史数据: {start_date} 到 {end_date}")

        try:
            # 记录同步开始
            await self._log_sync(
                sync_id, "kline_history", sync_time,
                status="RUNNING", start_time=datetime.now()
            )

            # 同步K线数据
            count = await self._sync_klines(start_date, end_date, symbols)

            # 记录同步完成
            await self._log_sync(
                sync_id, "kline_history", sync_time,
                status="SUCCESS", end_time=datetime.now(),
                records_count=count
            )

            logger.info(f"同步完成: {count} 条K线记录")

        except Exception as e:
            logger.error(f"同步失败: {e}")
            await self._log_sync(
                sync_id, "kline_history", sync_time,
                status="FAILED", error_message=str(e)
            )
            raise

    async def _sync_klines(
            self,
            start_date: str,
            end_date: str,
            symbols: Optional[List[str]] = None
    ) -> int:
        """
        同步K线数据
        
        Returns:
            同步的记录数
        """
        if not self.database:
            logger.warning("数据库组件未初始化，跳过同步")
            return 0

        # 构建查询
        query = """
                SELECT symbol, time, open, high, low, close, volume, amount
                FROM market_kline
                WHERE time BETWEEN :start_date AND :end_date \
                """

        if symbols:
            query += f" AND symbol IN ({','.join([f':{i}' for i in range(len(symbols))])})"

        query += " ORDER BY symbol, time"

        # 执行查询
        async with self.database.get_session() as session:
            params = {"start_date": start_date, "end_date": end_date}
            if symbols:
                for i, symbol in enumerate(symbols):
                    params[str(i)] = symbol

            result = await session.execute(text(query), params)
            rows = result.fetchall()

        if not rows:
            logger.info("没有需要同步的数据")
            return 0

        # 转换为 DataFrame
        df = pd.DataFrame(rows, columns=[
            'symbol', 'time', 'open', 'high', 'low', 'close', 'volume', 'amount'
        ])

        # 导入到 DuckDB
        count = await self.analytics_db.import_from_dataframe(
            df, "kline_history", if_exists="append"
        )

        return count

    async def sync_incremental(self, table: str = "kline_history"):
        """
        增量同步
        
        Args:
            table: 表名
        """
        # 获取最后同步时间
        last_sync = await self._get_last_sync_time(table)

        if last_sync:
            start_date = last_sync.strftime("%Y-%m-%d %H:%M:%S")
        else:
            # 第一次同步，同步最近7天
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        end_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"增量同步 {table}: {start_date} 到 {end_date}")

        if table == "kline_history":
            await self._sync_klines(start_date, end_date)
        elif table == "tick_archive":
            await self._sync_ticks(start_date, end_date)

    async def _sync_ticks(
            self,
            start_date: str,
            end_date: str,
            symbols: Optional[List[str]] = None
    ) -> int:
        """
        同步Tick数据到DuckDB
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            symbols: 股票代码列表
            
        Returns:
            同步的记录数
        """
        import numpy as np

        sync_id = str(uuid.uuid4())
        sync_time = datetime.now()
        total_count = 0

        try:
            logger.info(f"开始同步Tick数据: {start_date} to {end_date}")

            # 如果没有指定股票，获取所有活跃股票
            if not symbols:
                # 从PostgreSQL获取活跃股票列表
                if self.database and hasattr(self.database, 'session'):
                    # 这里简化处理，实际应该从数据库查询
                    symbols = ['600036', '000001', '000002']  # 示例股票

            # 为每个股票同步数据
            for symbol in symbols:
                try:
                    # 从Redis获取最新的Tick数据
                    tick_data = await self._get_tick_from_redis(symbol)

                    if tick_data:
                        # 准备数据
                        df = pd.DataFrame([{
                            'symbol': symbol,
                            'time': tick_data.get('timestamp', datetime.now()),
                            'last_price': tick_data.get('last_price', 0),
                            'volume': tick_data.get('volume', 0),
                            'amount': tick_data.get('amount', 0),
                            'bid_price1': tick_data.get('bid_price', [0])[0] if tick_data.get('bid_price') else 0,
                            'ask_price1': tick_data.get('ask_price', [0])[0] if tick_data.get('ask_price') else 0,
                            'bid_volume1': tick_data.get('bid_volume', [0])[0] if tick_data.get('bid_volume') else 0,
                            'ask_volume1': tick_data.get('ask_volume', [0])[0] if tick_data.get('ask_volume') else 0,
                            'spread': 0,  # 将在后面计算
                            'mid_price': 0,  # 将在后面计算
                            'imbalance': 0  # 将在后面计算
                        }])

                        # 计算微观结构指标
                        if len(df) > 0:
                            df['spread'] = df['ask_price1'] - df['bid_price1']
                            df['mid_price'] = (df['ask_price1'] + df['bid_price1']) / 2
                            total_vol = df['bid_volume1'] + df['ask_volume1']
                            df['imbalance'] = np.where(
                                total_vol > 0,
                                (df['bid_volume1'] - df['ask_volume1']) / total_vol,
                                0
                            )

                        # 导入到DuckDB
                        await self.analytics_db.import_from_dataframe(
                            df, "tick_data", if_exists="append"
                        )

                        total_count += len(df)
                        logger.debug(f"同步 {symbol} 的 {len(df)} 条Tick数据")

                except Exception as e:
                    logger.error(f"同步 {symbol} Tick数据失败: {e}")
                    continue

            # 记录同步日志
            await self._log_sync(
                sync_id=sync_id,
                table_name="tick_data",
                sync_time=sync_time,
                status="SUCCESS",
                start_time=pd.to_datetime(start_date),
                end_time=pd.to_datetime(end_date),
                record_count=total_count
            )

            logger.info(f"Tick数据同步完成，共同步 {total_count} 条记录")
            return total_count

        except Exception as e:
            logger.error(f"Tick数据同步失败: {e}")

            # 记录失败日志
            await self._log_sync(
                sync_id=sync_id,
                table_name="tick_data",
                sync_time=sync_time,
                status="FAILED",
                error_message=str(e)
            )

            return 0

    async def _get_tick_from_redis(self, symbol: str) -> Optional[Dict]:
        """
        从Redis获取Tick数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            Tick数据字典
        """
        import numpy as np

        try:
            # 这里简化处理，实际应该从Redis读取
            # 在生产环境中，应该连接到Redis并获取实时数据
            return {
                'symbol': symbol,
                'timestamp': datetime.now(),
                'last_price': 10.0 + np.random.random(),
                'volume': int(np.random.random() * 10000),
                'amount': np.random.random() * 1000000,
                'bid_price': [10.0 - i * 0.01 for i in range(5)],
                'ask_price': [10.1 + i * 0.01 for i in range(5)],
                'bid_volume': [int(np.random.random() * 1000) for _ in range(5)],
                'ask_volume': [int(np.random.random() * 1000) for _ in range(5)]
            }
        except Exception as e:
            logger.error(f"从Redis获取Tick数据失败: {e}")
            return None

    async def _get_last_sync_time(self, table: str) -> Optional[datetime]:
        """获取最后同步时间"""
        sql = """
              SELECT MAX(sync_time) as last_sync
              FROM sync_log
              WHERE table_name = ?
                AND status = 'SUCCESS' \
              """

        df = await self.analytics_db.query(sql, (table,))
        if not df.empty and df['last_sync'][0]:
            return pd.to_datetime(df['last_sync'][0])
        return None

    async def _log_sync(
            self,
            sync_id: str,
            table_name: str,
            sync_time: datetime,
            status: str,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
            records_count: int = 0,
            error_message: Optional[str] = None
    ):
        """记录同步日志"""
        log_data = pd.DataFrame([{
            'sync_id': sync_id,
            'table_name': table_name,
            'sync_time': sync_time,
            'start_time': start_time,
            'end_time': end_time,
            'records_count': records_count,
            'status': status,
            'error_message': error_message
        }])

        await self.analytics_db.import_from_dataframe(
            log_data, "sync_log", if_exists="append"
        )

    async def clean_old_data(self, days_to_keep: int = 365):
        """
        清理旧数据
        
        Args:
            days_to_keep: 保留的天数
        """
        cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).strftime("%Y-%m-%d")

        tables = ["kline_history", "tick_archive", "indicators"]

        for table in tables:
            try:
                sql = f"DELETE FROM {table} WHERE time < ?"
                await self.analytics_db.query(sql, (cutoff_date,))
                logger.info(f"清理 {table} 中 {cutoff_date} 之前的数据")
            except Exception as e:
                logger.error(f"清理 {table} 失败: {e}")

    async def optimize_tables(self):
        """优化表（压缩、重建索引等）"""
        try:
            # DuckDB 会自动优化，但可以手动触发
            await self.analytics_db.query("CHECKPOINT")
            await self.analytics_db.query("ANALYZE")
            logger.info("DuckDB 表优化完成")
        except Exception as e:
            logger.error(f"表优化失败: {e}")

    async def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        status = {
            "running": self._running,
            "sync_interval": self.sync_interval,
            "tables": {}
        }

        # 获取各表的最后同步时间
        tables = ["kline_history", "tick_archive", "indicators"]
        for table in tables:
            last_sync = await self._get_last_sync_time(table)
            status["tables"][table] = {
                "last_sync": last_sync.isoformat() if last_sync else None,
                "is_outdated": (
                        datetime.now() - last_sync > timedelta(hours=24)
                ) if last_sync else True
            }

        # 获取统计信息
        stats = await self.analytics_db.get_statistics()
        status["statistics"] = stats

        return status


# 全局实例
_sync_service: Optional[DataSyncService] = None


def get_sync_service(database_component=None) -> DataSyncService:
    """获取全局同步服务实例"""
    global _sync_service
    if _sync_service is None:
        _sync_service = DataSyncService(database_component)
    return _sync_service
