"""手动设置 TimescaleDB"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from deepsearch.core.components import DatabaseComponent
from deepsearch.observability.logger import logger
from sqlalchemy import text


async def setup_timescaledb():
    """手动安装和配置 TimescaleDB"""
    db_component = DatabaseComponent()

    try:
        await db_component.initialize_async()

        async with db_component.engine.begin() as conn:
            # 检查可用的扩展
            logger.info("检查可用的 PostgreSQL 扩展...")
            result = await conn.execute(text("""
                                             SELECT name, default_version, installed_version, comment
                                             FROM pg_available_extensions
                                             WHERE name LIKE '%time%'
                                                OR name LIKE '%scale%'
                                             ORDER BY name;
                                             """))

            extensions = list(result)
            if extensions:
                logger.info("找到以下相关扩展：")
                for name, default_ver, installed_ver, comment in extensions:
                    status = f"已安装 v{installed_ver}" if installed_ver else "未安装"
                    logger.info(f"  - {name} (v{default_ver}): {status}")
                    if comment:
                        logger.info(f"    描述: {comment}")
            else:
                logger.warning("未找到 TimescaleDB 相关扩展")

            # 尝试创建 TimescaleDB 扩展
            try:
                logger.info("\n尝试创建 TimescaleDB 扩展...")
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
                logger.info("✓ TimescaleDB 扩展创建成功!")

                # 获取版本信息
                result = await conn.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"))
                version = result.scalar()
                logger.info(f"TimescaleDB 版本: {version}")

            except Exception as e:
                logger.error(f"创建 TimescaleDB 失败: {e}")
                logger.info("\n可能的解决方案：")
                logger.info("1. 确保 TimescaleDB 已正确安装到 PostgreSQL")
                logger.info("2. 检查 postgresql.conf 中是否添加了 shared_preload_libraries = 'timescaledb'")
                logger.info("3. 重启 PostgreSQL 服务")
                return

            # 如果成功，创建超表
            logger.info("\n开始创建超表...")

            # 将时序表转换为超表
            hypertables = [
                ("market_tick", "time", "7 days"),
                ("market_1min", "time", "7 days"),
                ("market_5min", "time", "30 days"),
                ("market_snapshot", "time", "1 day")
            ]

            for table_name, time_column, chunk_interval in hypertables:
                try:
                    # 检查表是否已经是超表
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
                        create_sql = text(
                            f"SELECT create_hypertable('{table_name}', '{time_column}', if_not_exists => TRUE);")
                        await conn.execute(create_sql)

                        # 设置分区间隔
                        interval_sql = text(
                            f"SELECT set_chunk_time_interval('{table_name}', INTERVAL '{chunk_interval}');")
                        await conn.execute(interval_sql)

                        logger.info(f"✓ 创建超表: {table_name} (分区间隔: {chunk_interval})")
                    else:
                        logger.info(f"- 超表已存在: {table_name}")

                except Exception as e:
                    logger.error(f"创建超表 {table_name} 失败: {e}")

            # 创建连续聚合
            logger.info("\n创建连续聚合视图...")
            try:
                # 检查是否已存在
                check_sql = text("""
                                 SELECT EXISTS (SELECT 1
                                                FROM timescaledb_information.continuous_aggregates
                                                WHERE view_name = 'market_5min_agg');
                                 """)
                result = await conn.execute(check_sql)
                exists = result.scalar()

                if not exists:
                    # 创建连续聚合
                    create_agg_sql = text("""
                        CREATE MATERIALIZED VIEW market_5min_agg
                        WITH (timescaledb.continuous) AS
                        SELECT 
                            time_bucket('5 minutes', time) AS bucket_time,
                            symbol,
                            first(open, time) as open,
                            max(high) as high,
                            min(low) as low,
                            last(close, time) as close,
                            sum(volume) as volume,
                            sum(turnover) as turnover
                        FROM market_1min
                        GROUP BY bucket_time, symbol
                        WITH NO DATA;
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

                    logger.info("✓ 创建连续聚合: market_5min_agg")
                else:
                    logger.info("- 连续聚合已存在: market_5min_agg")

            except Exception as e:
                logger.warning(f"创建连续聚合失败: {e}")

            # 显示超表信息
            logger.info("\n超表信息：")
            result = await conn.execute(text("""
                                             SELECT hypertable_name,
                                                    hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)                 as size_bytes,
                                                    pg_size_pretty(hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)) as size_pretty,
                                                    number_of_chunks
                                             FROM timescaledb_information.hypertables
                                             WHERE hypertable_schema = 'public'
                                             ORDER BY hypertable_name;
                                             """))

            for row in result:
                logger.info(f"  - {row.hypertable_name}: {row.size_pretty} ({row.number_of_chunks} 分区)")

    finally:
        await db_component.stop_async()


if __name__ == "__main__":
    asyncio.run(setup_timescaledb())
