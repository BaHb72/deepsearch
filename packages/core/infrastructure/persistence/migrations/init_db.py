"""数据库初始化脚本

用于初始化数据库表结构和 TimescaleDB 配置
"""

import asyncio
from typing import List, cast

from core.core.component_factory import DatabaseComponentFactory
from core.infrastructure.persistence.database import DatabaseService
from core.observability.logger import logger
from sqlalchemy.ext.asyncio import AsyncSession


async def init_database(drop_existing: bool = False) -> None:
    """初始化数据库

    Args:
        drop_existing: 是否删除现有表（危险操作）
    """
    logger.info("开始初始化数据库...")

    # 创建数据库组件
    db_component = DatabaseComponentFactory.create()

    try:
        # 初始化连接
        await db_component.initialize_async()
        logger.info("数据库连接成功")

        # 创建数据库服务
        db_service = DatabaseService(db_component)

        if drop_existing:
            logger.warning("删除现有表结构...")
            from ..models import Base

            engine = db_component.engine
            if engine is None:
                raise RuntimeError("数据库引擎未初始化，无法删除表结构")

            async with engine.begin() as conn:
                # 删除所有表
                await conn.run_sync(Base.metadata.drop_all)
                logger.info("现有表结构已删除")

        # 初始化数据库
        await db_service.init_database()

        # 执行健康检查
        health = await db_component.health_check_async()
        logger.info(f"数据库健康状态: {health}")

        logger.info("数据库初始化完成!")

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise
    finally:
        # 清理资源
        await db_component.stop_async()


async def create_sample_data() -> None:
    """创建示例数据（用于测试）"""
    import random
    from datetime import datetime, timedelta
    from decimal import Decimal

    from ..models import Market1Min, MarketTick

    logger.info("创建示例数据...")

    db_component = DatabaseComponentFactory.create()
    await db_component.initialize_async()

    db_service = DatabaseService(db_component)

    async with db_service.get_session() as session:
        db_session: AsyncSession = cast(AsyncSession, session)
        # 创建一些示例 tick 数据
        base_time = datetime.now()
        symbols = ["000001.SZ", "000002.SZ", "600000.SH"]

        ticks: List[MarketTick] = []
        for i in range(100):
            for symbol in symbols:
                tick = MarketTick(
                    time=base_time - timedelta(seconds=i),
                    symbol=symbol,
                    last_price=Decimal(f"{random.uniform(10, 20):.2f}"),
                    volume=random.randint(1000, 10000),
                    turnover=Decimal(f"{random.uniform(10000, 100000):.2f}"),
                    bid_prices=[Decimal(f"{random.uniform(9, 10):.2f}") for _ in range(5)],
                    ask_prices=[Decimal(f"{random.uniform(10, 11):.2f}") for _ in range(5)],
                    bid_volumes=[random.randint(100, 1000) for _ in range(5)],
                    ask_volumes=[random.randint(100, 1000) for _ in range(5)],
                )
                ticks.append(tick)

        db_session.add_all(ticks)
        await db_session.commit()
        logger.info(f"创建了 {len(ticks)} 条 tick 数据")

        # 创建一些 1 分钟 K 线数据
        klines: List[Market1Min] = []
        for i in range(60):
            for symbol in symbols:
                kline = Market1Min(
                    time=base_time - timedelta(minutes=i),
                    symbol=symbol,
                    open=Decimal(f"{random.uniform(10, 20):.2f}"),
                    high=Decimal(f"{random.uniform(15, 25):.2f}"),
                    low=Decimal(f"{random.uniform(5, 15):.2f}"),
                    close=Decimal(f"{random.uniform(10, 20):.2f}"),
                    volume=random.randint(10000, 100000),
                    turnover=Decimal(f"{random.uniform(100000, 1000000):.2f}"),
                )
                klines.append(kline)

        db_session.add_all(klines)
        await db_session.commit()
        logger.info(f"创建了 {len(klines)} 条 K 线数据")

    await db_component.stop_async()
    logger.info("示例数据创建完成!")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="数据库初始化工具")
    parser.add_argument("--drop", action="store_true", help="删除现有表")
    parser.add_argument("--sample", action="store_true", help="创建示例数据")

    args = parser.parse_args()

    # 运行初始化
    asyncio.run(init_database(drop_existing=args.drop))

    # 如果需要，创建示例数据
    if args.sample:
        asyncio.run(create_sample_data())


if __name__ == "__main__":
    main()
