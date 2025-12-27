"""
同步数据库连接管理

提供同步的数据库连接和会话管理
"""

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool

from deepsearch.config import get_config
from deepsearch.observability import logger

# 创建同步引擎
config = get_config()
database_config = config.database if config else None
raw_database_url: str | None = database_config.get_main_url() if database_config else None
database_url = raw_database_url or ""
echo_flag = (
    database_config.main.echo
    if database_config and getattr(database_config, "main", None)
    else False
)
engine = create_engine(
    database_url,
    echo=echo_flag,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,  # 1Сʱ��������
    poolclass=QueuePool,
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    获取数据库会话（用于 FastAPI 依赖注入）

    Usage:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_session():
    """
    获取数据库会话的上下文管理器

    Usage:
        with get_db_session() as db:
            items = db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()  # 自动提交
    except Exception:
        db.rollback()  # 出错时回滚
        logger.error("数据库事务回滚", exc_info=True)
        raise
    finally:
        db.close()


def init_db():
    """初始化数据库表结构"""
    from deepsearch.infrastructure.providers.entities.legacy_models import Base

    try:
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        logger.info("同步数据库表结构创建完成")
    except Exception as e:
        logger.error(f"初始化数据库失败: {e}")
        raise


def check_connection():
    """检查数据库连接"""
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT 1")
            result.fetchone()
        logger.info("数据库连接正常")
        return True
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return False
