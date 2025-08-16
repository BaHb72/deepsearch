"""
股票信息服务（数据库版本）

提供股票基础信息的数据库存储和查询服务
支持自动更新和内存缓存
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, Session

from deepsearch.config import get_config
from deepsearch.storage.models import StockInfo

# 数据源抽象（黑盒）
# 数据源适配器（如果可用）
try:
    from deepsearch.services.data_source_adapter import StockDataSourceAdapter

    HAS_DATA_ADAPTER = True
except ImportError:
    HAS_DATA_ADAPTER = False
    StockDataSourceAdapter = None


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

        # 数据源适配器（黑盒，支持热切换）
        self._data_adapter = None
        if HAS_DATA_ADAPTER:
            try:
                self._data_adapter = StockDataSourceAdapter()
                self._init_data_sources()
            except Exception as e:
                logger.warning(f"初始化数据源适配器失败: {e}")

        # 初始化数据库连接
        self._init_database()

    def _init_database(self):
        """初始化数据库连接"""
        try:
            db_main = self.config.database.main
            if db_main.enabled:
                # 使用新的配置API获取URL（向后兼容）
                db_url = self.config.database.get_main_url() or db_main.get_url()
                if not db_url:
                    raise ValueError("无法构建数据库连接URL，请检查配置")
                self.engine = create_engine(
                    db_url,
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

    def _init_data_sources(self) -> None:
        """初始化并注册可用数据源（黑盒，支持热切换）"""
        if not self._data_adapter:
            return
        try:
            # 尝试使用现有的数据提供者
            logger.info("使用简化的数据源配置")
        except Exception as e:
            logger.error(f"初始化数据源失败: {e}")

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
                        # 异步更新数据库（实际调用数据源API，后台调度）
                        logger.debug(f"股票 {symbol} 信息需要更新")
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(self.update_from_api(symbol))
                        except RuntimeError:
                            # 无运行中的事件循环，直接同步执行（会阻塞当前调用）
                            asyncio.run(self.update_from_api(symbol))

                    # 转换为字典
                    info_dict = self._model_to_dict(stock_info)

                    # 更新内存缓存
                    self._memory_cache[symbol] = info_dict
                    self._cache_timestamps[symbol] = time.time()

                    return info_dict
                else:
                    # 数据库中没有，尝试从API获取
                    logger.debug(f"数据库中没有股票 {symbol} 的信息")
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(self.update_from_api(symbol))
                        # 无可返回的本地数据，先返回None，待后台更新完成
                        return None
                    except RuntimeError:
                        # 无事件循环，直接同步获取
                        return asyncio.run(self.update_from_api(symbol))

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
        从API更新股票信息（使用黑盒数据源适配器）
        
        Args:
            symbol: 股票代码
            
        Returns:
            更新后的股票信息（字典），若失败返回None
        """
        logger.info(f"从API更新股票 {symbol} 信息")

        # 如果没有数据适配器，尝试直接使用AkShare
        if not self._data_adapter:
            try:
                import akshare as ak
                # 同步调用AkShare
                stock_info_df = await asyncio.get_event_loop().run_in_executor(
                    None,
                    ak.stock_individual_info_em,
                    symbol
                )
                if stock_info_df is not None and not stock_info_df.empty:
                    # 转换为字典格式
                    info_dict = {}
                    for _, row in stock_info_df.iterrows():
                        item = row.get('item', '')
                        value = row.get('value', '')
                        if item == '股票代码':
                            info_dict['symbol'] = value
                        elif item == '股票简称':
                            info_dict['name'] = value
                        elif item == '上市时间':
                            info_dict['listed_date'] = value
                        elif item == '所属行业':
                            info_dict['industry'] = value
                    raw = info_dict
                else:
                    logger.warning(f"AkShare未返回股票信息: {symbol}")
                    return None
            except Exception as e:
                logger.error(f"直接调用AkShare失败: {e}")
                return None
        else:
            try:
                raw = await self._data_adapter.fetch_stock_info(symbol)
            except Exception as e:
                logger.error(f"从数据适配器获取失败: {e}")
                return None

        if not raw:
            logger.warning(f"数据源未返回股票信息: {symbol}")
            return None

        # 规范化并映射到数据库字段
        try:
            def parse_listed_date(v):
                if v is None:
                    return None
                if isinstance(v, datetime):
                    return v
                try:
                    # 纯日期字符串 'YYYY-MM-DD' 或 ISO 格式
                    return datetime.fromisoformat(str(v))
                except Exception:
                    pass
                try:
                    s = str(v)
                    if len(s) == 8 and s.isdigit():
                        return datetime.strptime(s, "%Y%m%d")
                except Exception:
                    pass
                return None

            def to_int(v):
                if v is None:
                    return None
                try:
                    return int(float(v))
                except Exception:
                    return None

            mapped: Dict[str, Any] = {
                'name': raw.get('name'),
                'industry': raw.get('industry'),
                'sector': raw.get('sector'),
                'market': raw.get('market'),
                'listed_date': parse_listed_date(raw.get('listed_date')),
                'total_shares': to_int(raw.get('total_shares')),
                'float_shares': to_int(raw.get('float_shares')),
                'updated_at': datetime.now(),
            }

            # 使用数据库会话进行UPSERT
            session = self._get_session()
            if session:
                try:
                    obj = session.query(StockInfo).filter_by(symbol=symbol).first()
                    if obj:
                        for k, v in mapped.items():
                            if hasattr(obj, k):
                                setattr(obj, k, v)
                    else:
                        obj = StockInfo(symbol=symbol, **{k: v for k, v in mapped.items() if k != 'updated_at'})
                        # 设置更新时间
                        if hasattr(obj, 'updated_at') and mapped.get('updated_at'):
                            setattr(obj, 'updated_at', mapped['updated_at'])
                        session.add(obj)
                    session.commit()

                    # 刷新缓存
                    info_dict = self._model_to_dict(obj)
                    self._memory_cache[symbol] = info_dict
                    self._cache_timestamps[symbol] = time.time()
                    logger.info(f"已更新股票 {symbol} 信息（API）")
                    return info_dict

                except SQLAlchemyError as e:
                    logger.error(f"保存股票信息到数据库失败: {e}")
                    session.rollback()
                finally:
                    session.close()
            else:
                # 无数据库，更新内存缓存
                cache_info = {k: (v.isoformat() if k == 'listed_date' and isinstance(v, datetime) else v) for k, v in
                              mapped.items() if k != 'updated_at'}
                self._memory_cache[symbol] = cache_info
                self._cache_timestamps[symbol] = time.time()
                return {'symbol': symbol, **cache_info}

        except Exception as e:
            logger.error(f"处理股票信息时出错 {symbol}: {e}")
            return None


# 全局服务实例
_global_service: Optional[StockInfoService] = None


def get_stock_info_service() -> StockInfoService:
    """获取全局股票信息服务实例"""
    global _global_service
    if _global_service is None:
        _global_service = StockInfoService()
    return _global_service
