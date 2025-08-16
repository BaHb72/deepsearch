"""
股票信息服务（数据库版本）

提供股票基础信息的数据库存储和查询服务
支持自动更新和内存缓存
"""
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, Session

from deepsearch.config import get_config
from deepsearch.storage.models import StockInfo


class StockInfoService:
    """股票信息服务（数据库版）"""

    def __init__(self):
        """初始化服务"""
        self.config = get_config()
        self.engine = None
        self.Session = None

        # 内存缓存（一级缓存）
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl = 300  # 5分钟

        # 数据库更新阈值
        self._db_update_threshold = 86400  # 24小时

        # 初始化数据库连接
        self._init_database()

    def _init_database(self):
        """初始化数据库连接"""
        try:
            db_config = self.config.database.main
            if db_config.enabled:
                self.engine = create_engine(
                    db_config.get_connection_string(),
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True
                )
                self.Session = sessionmaker(bind=self.engine)
                logger.info("股票信息服务数据库连接初始化成功")
            else:
                logger.warning("数据库未启用，股票信息服务将使用纯内存模式")
        except Exception as e:
            logger.error(f"初始化数据库连接失败: {e}")
            self.engine = None
            self.Session = None

    def _get_session(self) -> Optional[Session]:
        """获取数据库会话"""
        if self.Session:
            return self.Session()
        return None

    def get(self, symbol: str, force_update: bool = False) -> Optional[Dict[str, Any]]:
        """
        获取股票信息
        
        Args:
            symbol: 股票代码
            force_update: 是否强制更新
            
        Returns:
            股票信息字典
        """
        # 1. 检查内存缓存
        if not force_update and symbol in self._memory_cache:
            cache_time = self._cache_timestamps.get(symbol, 0)
            if time.time() - cache_time < self._cache_ttl:
                return self._memory_cache[symbol]

        # 2. 查询数据库
        session = self._get_session()
        if session:
            try:
                stock_info = session.query(StockInfo).filter_by(symbol=symbol).first()

                if stock_info:
                    # 检查是否需要更新
                    if force_update or self._should_update(stock_info):
                        # 异步更新数据库（这里简化处理，实际应该调用API）
                        logger.debug(f"股票 {symbol} 信息需要更新")
                        # TODO: 调用API更新股票信息

                    # 转换为字典
                    info_dict = self._model_to_dict(stock_info)

                    # 更新内存缓存
                    self._memory_cache[symbol] = info_dict
                    self._cache_timestamps[symbol] = time.time()

                    return info_dict
                else:
                    # 数据库中没有，尝试从API获取
                    logger.debug(f"数据库中没有股票 {symbol} 的信息")
                    # TODO: 调用API获取并保存到数据库

            except SQLAlchemyError as e:
                logger.error(f"查询股票信息失败: {e}")
            finally:
                session.close()

        return None

    def set(self, symbol: str, info: Dict[str, Any]):
        """
        设置股票信息
        
        Args:
            symbol: 股票代码
            info: 股票信息字典
        """
        session = self._get_session()
        if session:
            try:
                # 查找或创建
                stock_info = session.query(StockInfo).filter_by(symbol=symbol).first()

                if stock_info:
                    # 更新现有记录
                    for key, value in info.items():
                        if hasattr(stock_info, key):
                            setattr(stock_info, key, value)
                else:
                    # 创建新记录
                    stock_info = StockInfo(symbol=symbol, **info)
                    session.add(stock_info)

                session.commit()

                # 更新内存缓存
                self._memory_cache[symbol] = info
                self._cache_timestamps[symbol] = time.time()

                logger.debug(f"成功保存股票 {symbol} 信息")

            except SQLAlchemyError as e:
                logger.error(f"保存股票信息失败: {e}")
                session.rollback()
            finally:
                session.close()
        else:
            # 仅更新内存缓存
            self._memory_cache[symbol] = info
            self._cache_timestamps[symbol] = time.time()

    def update_batch(self, stock_info_dict: Dict[str, Dict[str, Any]]):
        """
        批量更新股票信息
        
        Args:
            stock_info_dict: 股票信息字典 {symbol: info}
        """
        session = self._get_session()
        if session:
            try:
                for symbol, info in stock_info_dict.items():
                    stock_info = session.query(StockInfo).filter_by(symbol=symbol).first()

                    if stock_info:
                        # 更新现有记录
                        for key, value in info.items():
                            if hasattr(stock_info, key):
                                setattr(stock_info, key, value)
                    else:
                        # 创建新记录
                        stock_info = StockInfo(symbol=symbol, **info)
                        session.add(stock_info)

                    # 更新内存缓存
                    self._memory_cache[symbol] = info
                    self._cache_timestamps[symbol] = time.time()

                session.commit()
                logger.info(f"批量更新了 {len(stock_info_dict)} 条股票信息")

            except SQLAlchemyError as e:
                logger.error(f"批量更新股票信息失败: {e}")
                session.rollback()
            finally:
                session.close()
        else:
            # 仅更新内存缓存
            for symbol, info in stock_info_dict.items():
                self._memory_cache[symbol] = info
                self._cache_timestamps[symbol] = time.time()

    def search(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        搜索股票
        
        Args:
            keyword: 搜索关键词（代码、名称）
            limit: 返回结果数量限制
            
        Returns:
            匹配的股票列表
        """
        results = []
        keyword = keyword.lower()

        session = self._get_session()
        if session:
            try:
                # 搜索数据库
                query = session.query(StockInfo).filter(
                    (StockInfo.symbol.ilike(f"%{keyword}%")) |
                    (StockInfo.name.ilike(f"%{keyword}%"))
                ).limit(limit)

                for stock_info in query:
                    results.append(self._model_to_dict(stock_info))

            except SQLAlchemyError as e:
                logger.error(f"搜索股票失败: {e}")
            finally:
                session.close()
        else:
            # 从内存缓存搜索
            for symbol, info in self._memory_cache.items():
                if keyword in symbol.lower() or keyword in info.get('name', '').lower():
                    results.append({
                        'symbol': symbol,
                        **info
                    })
                    if len(results) >= limit:
                        break

        return results

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        """获取所有股票信息"""
        all_stocks = {}

        session = self._get_session()
        if session:
            try:
                for stock_info in session.query(StockInfo).all():
                    all_stocks[stock_info.symbol] = self._model_to_dict(stock_info)

            except SQLAlchemyError as e:
                logger.error(f"获取所有股票信息失败: {e}")
            finally:
                session.close()
        else:
            # 返回内存缓存的所有数据
            all_stocks = self._memory_cache.copy()

        return all_stocks

    def clear_cache(self):
        """清空内存缓存"""
        self._memory_cache.clear()
        self._cache_timestamps.clear()
        logger.info("内存缓存已清空")

    def _should_update(self, stock_info: StockInfo) -> bool:
        """
        判断是否需要更新股票信息
        
        Args:
            stock_info: 股票信息模型
            
        Returns:
            是否需要更新
        """
        if not stock_info.updated_at:
            return True

        # 超过24小时需要更新
        threshold = datetime.now() - timedelta(seconds=self._db_update_threshold)
        return stock_info.updated_at < threshold

    def _model_to_dict(self, stock_info: StockInfo) -> Dict[str, Any]:
        """
        将模型转换为字典
        
        Args:
            stock_info: 股票信息模型
            
        Returns:
            股票信息字典
        """
        return {
            'symbol': stock_info.symbol,
            'name': stock_info.name,
            'industry': stock_info.industry,
            'sector': stock_info.sector,
            'market': stock_info.market,
            'listed_date': stock_info.listed_date.strftime('%Y-%m-%d') if stock_info.listed_date else None,
            'total_shares': stock_info.total_shares,
            'float_shares': stock_info.float_shares,
            'updated_at': stock_info.updated_at.isoformat() if stock_info.updated_at else None
        }

    async def update_from_api(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        从API更新股票信息
        
        Args:
            symbol: 股票代码
            
        Returns:
            更新后的股票信息
        """
        # TODO: 实现从实时API获取股票信息
        # 这里需要调用akshare或其他数据源API
        logger.info(f"从API更新股票 {symbol} 信息")
        return None


# 全局服务实例
_global_service: Optional[StockInfoService] = None


def get_stock_info_service() -> StockInfoService:
    """获取全局股票信息服务实例"""
    global _global_service
    if _global_service is None:
        _global_service = StockInfoService()
    return _global_service
