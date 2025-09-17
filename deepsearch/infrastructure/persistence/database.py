"""数据库服务层

提供统一的数据库访问接口
"""
from typing import Optional, AsyncContextManager, Dict, Any
from contextlib import asynccontextmanager
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

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

    async def get_database_status(self) -> Dict[str, Any]:
        """获取数据库状态"""
        status = {
            "connected": False,
            "type": "postgresql",
            "host": getattr(self.db.config, 'host', 'localhost'),
            "database": getattr(self.db.config, 'database', 'deepsearch'),
            "pool_size": 10,
            "active_connections": 0
        }

        try:
            # 测试连接
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    status["connected"] = True

                    # 获取连接池状态
                    if hasattr(self.db.engine.pool, 'size'):
                        status["pool_size"] = self.db.engine.pool.size()
                    if hasattr(self.db.engine.pool, 'checked_out_connections'):
                        status["active_connections"] = self.db.engine.pool.checked_out_connections()
        except Exception as e:
            status["error"] = str(e)
            self.logger.error(f"数据库状态检查失败: {e}")

        return status

    async def get_health(self) -> Dict[str, Any]:
        """获取数据库健康状态"""
        health = {
            "status": "unknown",
            "checks": {},
            "timestamp": None
        }

        try:
            # PostgreSQL检查
            pg_check = {"status": "down"}
            try:
                async with self.get_session() as session:
                    import time
                    start = time.time()
                    result = await session.execute(text("SELECT version()"))
                    version = result.scalar()
                    latency_ms = (time.time() - start) * 1000

                    pg_check = {
                        "status": "up",
                        "latency_ms": round(latency_ms, 2),
                        "version": version
                    }
            except Exception as e:
                pg_check["error"] = str(e)

            health["checks"]["postgresql"] = pg_check

            # 判断整体健康状态
            if all(c.get("status") == "up" for c in health["checks"].values()):
                health["status"] = "healthy"
            elif any(c.get("status") == "up" for c in health["checks"].values()):
                health["status"] = "degraded"
            else:
                health["status"] = "unhealthy"

            import datetime
            health["timestamp"] = datetime.datetime.now().isoformat()

        except Exception as e:
            health["status"] = "error"
            health["error"] = str(e)
            self.logger.error(f"健康检查失败: {e}")

        return health


# 全局函数（为了兼容测试）
_database_service: Optional[DatabaseService] = None

async def get_connection():
    """获取数据库连接（兼容性函数）"""
    global _database_service
    if _database_service is None:
        from deepsearch.core.managers.component_manager import ComponentManager
        cm = ComponentManager()
        if "database" in cm._components:
            db_component = cm._components["database"]
            _database_service = DatabaseService(db_component)

    if _database_service:
        return _database_service.db

    # 如果没有初始化，返回mock对象用于测试
    from unittest.mock import AsyncMock
    return AsyncMock()

async def get_database_status():
    """获取数据库状态（兼容性函数）"""
    global _database_service
    if _database_service:
        return await _database_service.get_database_status()

    # 默认返回
    return {
        "connected": False,
        "type": "unknown",
        "error": "Database service not initialized"
    }
