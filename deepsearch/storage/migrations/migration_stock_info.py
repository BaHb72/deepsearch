"""
股票信息表迁移脚本

创建和管理stock_info表
"""
import asyncio
from datetime import datetime
from pathlib import Path

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from deepsearch.config import get_config
from deepsearch.storage.models.legacy_models import Base, StockInfo


async def create_stock_info_table():
    """创建股票信息表"""
    config = get_config()

    # 获取数据库配置
    db_config = config.database.main
    if not db_config.enabled:
        logger.warning("数据库未启用，跳过创建股票信息表")
        return

    # 创建数据库引擎
    engine = create_engine(db_config.get_connection_string())

    try:
        # 创建表（如果不存在）
        Base.metadata.create_all(engine, tables=[StockInfo.__table__])
        logger.info("股票信息表创建成功")

        # 检查表是否为空，如果为空则导入初始数据
        Session = sessionmaker(bind=engine)
        session = Session()

        count = session.query(StockInfo).count()
        if count == 0:
            logger.info("股票信息表为空，导入初始数据...")
            await import_initial_data(session)
        else:
            logger.info(f"股票信息表已有 {count} 条记录")

        session.close()

    except Exception as e:
        logger.error(f"创建股票信息表失败: {e}")
        raise
    finally:
        engine.dispose()


async def import_initial_data(session):
    """导入初始股票数据"""
    import json

    # 尝试从现有JSON文件导入
    json_file = Path(__file__).parent.parent / "data" / "stock_info_cache.json"

    if json_file.exists():
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                stock_data = json.load(f)

            for symbol, info in stock_data.items():
                stock_info = StockInfo(
                    symbol=symbol,
                    name=info.get('name', ''),
                    industry=info.get('industry'),
                    sector=info.get('sector'),
                    market=info.get('market'),
                    listed_date=datetime.strptime(info['listed_date'], '%Y-%m-%d') if info.get('listed_date') else None,
                    total_shares=info.get('total_shares'),
                    float_shares=info.get('float_shares')
                )
                session.add(stock_info)

            session.commit()
            logger.info(f"成功导入 {len(stock_data)} 条股票信息")

        except Exception as e:
            logger.error(f"导入初始数据失败: {e}")
            session.rollback()
    else:
        # 如果没有JSON文件，添加一些基础数据
        default_stocks = [
            {'symbol': '000001', 'name': '平安银行', 'industry': '银行', 'sector': '大金融', 'market': '深圳主板'},
            {'symbol': '000002', 'name': '万科A', 'industry': '房地产', 'sector': '房地产开发', 'market': '深圳主板'},
            {'symbol': '000858', 'name': '五粮液', 'industry': '白酒', 'sector': '食品饮料', 'market': '深圳主板'},
            {'symbol': '002415', 'name': '海康威视', 'industry': '安防', 'sector': '电子设备', 'market': '深圳中小板'},
            {'symbol': '300750', 'name': '宁德时代', 'industry': '新能源', 'sector': '动力电池', 'market': '创业板'},
            {'symbol': '600000', 'name': '浦发银行', 'industry': '银行', 'sector': '大金融', 'market': '上海主板'},
            {'symbol': '600036', 'name': '招商银行', 'industry': '银行', 'sector': '大金融', 'market': '上海主板'},
            {'symbol': '600519', 'name': '贵州茅台', 'industry': '白酒', 'sector': '食品饮料', 'market': '上海主板'},
        ]

        for stock_dict in default_stocks:
            stock_info = StockInfo(**stock_dict)
            session.add(stock_info)

        session.commit()
        logger.info(f"成功添加 {len(default_stocks)} 条默认股票信息")


async def drop_stock_info_table():
    """删除股票信息表（谨慎使用）"""
    config = get_config()
    db_config = config.database.main

    if not db_config.enabled:
        logger.warning("数据库未启用")
        return

    engine = create_engine(db_config.get_connection_string())

    try:
        # 删除表
        StockInfo.__table__.drop(engine, checkfirst=True)
        logger.info("股票信息表已删除")
    except Exception as e:
        logger.error(f"删除股票信息表失败: {e}")
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    # 运行迁移
    asyncio.run(create_stock_info_table())
