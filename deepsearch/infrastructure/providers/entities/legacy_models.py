"""面向遗留脚本的 SQLAlchemy 股票模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类，供遗留模型复用。"""

    pass


class StockInfo(Base):
    """股票信息表模型，兼容迁移与同步脚本。"""

    __tablename__ = "stock_info"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    industry = Column(String(128), nullable=True)
    sector = Column(String(128), nullable=True)
    market = Column(String(32), nullable=True)
    listed_date = Column(DateTime, nullable=True)
    total_shares = Column(Numeric(18, 2), nullable=True)
    float_shares = Column(Numeric(18, 2), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
