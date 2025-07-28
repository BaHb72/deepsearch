"""数据库服务层

提供统一的数据库访问接口
"""
from typing import Optional, AsyncContextManager
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from deepsearch.observability.logger import logger


class DatabaseService:
    """数据库服务
    
    提供统一的数据库访问接口，封装数据库操作
    """

    def __init__(self, database_component: 'DatabaseComponent'):
        self.db = database_component
        self.logger = logger.bind(module="database_service")

    @asynccontextmanager
    async def get_session(self) -> AsyncContextManager[AsyncSession]:
        """获取数据库会话
        
        使用上下文管理器自动管理会话生命周期
        """
        async with self.db.get_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def init_database(self) -> None:
        """初始化数据库表结构"""
        from sqlalchemy import text
        from .models.base import Base

        async with self.db.engine.begin() as conn:
            # 创建所有表
            await conn.run_sync(Base.metadata.create_all)
            self.logger.info("数据库表结构创建完成")

            # 如果启用了 TimescaleDB，设置超表
            if self.db.is_timescale_enabled:
                await self._init_timescaledb_tables(conn)

    async def _init_timescaledb_tables(self, conn) -> None:
        """初始化 TimescaleDB 超表"""
        from sqlalchemy import text

        try:
            # 将时序表转换为超表
            hypertables = [
                ("market_tick", "time"),
                ("market_1min", "time"),
                ("market_5min", "time"),
                ("market_snapshot", "time")
            ]

            for table_name, time_column in hypertables:
                try:
                    # 检查是否已经是超表
                    check_sql = text(f"""
                        SELECT EXISTS (
                            SELECT 1 FROM timescaledb_information.hypertables 
                            WHERE hypertable_name = :table_name
                        );
                    """)
                    result = await conn.execute(check_sql, {"table_name": table_name})
                    is_hypertable = result.scalar()

                    if not is_hypertable:
                        # 创建超表
                        create_sql = text(f"SELECT create_hypertable('{table_name}', '{time_column}');")
                        await conn.execute(create_sql)
                        self.logger.info(f"创建超表: {table_name}")

                        # 设置分区间隔（7天一个分区）
                        interval_sql = text(f"""
                            SELECT set_chunk_time_interval('{table_name}', INTERVAL '7 days');
                        """)
                        await conn.execute(interval_sql)
                    else:
                        self.logger.info(f"超表已存在: {table_name}")

                except Exception as e:
                    self.logger.warning(f"创建超表 {table_name} 失败: {e}")

            # 创建连续聚合视图
            await self._create_continuous_aggregates(conn)

        except Exception as e:
            self.logger.error(f"TimescaleDB 初始化失败: {e}")
            raise

    async def _create_continuous_aggregates(self, conn) -> None:
        """创建连续聚合视图"""
        from sqlalchemy import text

        # 创建 1分钟 -> 5分钟 的连续聚合
        try:
            # 检查视图是否存在
            check_sql = text("""
                             SELECT EXISTS (SELECT 1
                                            FROM timescaledb_information.continuous_aggregates
                                            WHERE view_name = 'market_5min_agg');
                             """)
            result = await conn.execute(check_sql)
            exists = result.scalar()

            if not exists:
                create_agg_sql = text("""
                    CREATE MATERIALIZED VIEW market_5min_agg
                    WITH (timescaledb.continuous) AS
                    SELECT 
                        time_bucket('5 minutes', time) AS time,
                        symbol,
                        first(open, time) as open,
                        max(high) as high,
                        min(low) as low,
                        last(close, time) as close,
                        sum(volume) as volume,
                        sum(turnover) as turnover
                    FROM market_1min
                    GROUP BY time_bucket('5 minutes', time), symbol;
                """)
                await conn.execute(create_agg_sql)

                # 添加刷新策略
                policy_sql = text("""
                    SELECT add_continuous_aggregate_policy('market_5min_agg',
                        start_offset => INTERVAL '1 hour',
                        end_offset => INTERVAL '1 minute',
                        schedule_interval => INTERVAL '5 minutes');
                """)
                await conn.execute(policy_sql)

                self.logger.info("创建连续聚合: market_5min_agg")
            else:
                self.logger.info("连续聚合已存在: market_5min_agg")

        except Exception as e:
            self.logger.warning(f"创建连续聚合失败: {e}")
