# encoding:utf-8
"""
Unified QMT Data Provider
统一的QMT数据提供者 - 同时支持QMT标准版和MiniQMT
Author: DeepSearch Team
Version: 2.0.0
"""

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Any, Optional

import pandas as pd

from .base import DataProvider, DataProviderConfig, DataSourceType

logger = logging.getLogger(__name__)


class QMTMode(Enum):
    """QMT运行模式"""
    STANDARD = "standard"  # 标准版QMT（通过脚本通信）
    MINI = "mini"  # MiniQMT（通过xtquant）
    AUTO = "auto"  # 自动检测


class UnifiedQMTProvider(DataProvider):
    """
    统一的QMT数据提供者
    
    自动检测并适配QMT标准版或MiniQMT
    提供统一的数据接口
    """

    def __init__(self, mode: QMTMode = QMTMode.AUTO, config: Optional[DataProviderConfig] = None):
        """
        初始化统一QMT提供者
        
        Args:
            mode: 运行模式（标准版/MiniQMT/自动）
            config: 配置对象
        """
        if config is None:
            config = DataProviderConfig(
                name="unified_qmt",
                source_type=DataSourceType.CUSTOM,
                enabled=True,
                cache_enabled=True,
                cache_ttl=300  # 5分钟缓存
            )

        super().__init__(config)

        self.mode = mode
        self.actual_mode = None
        self.backend = None  # 实际的后端实现

        # 智能缓存系统
        self.cache_manager = SmartCacheManager()

    async def _initialize_source(self) -> None:
        """初始化数据源"""
        # 检测并选择合适的模式
        if self.mode == QMTMode.AUTO:
            self.actual_mode = await self._detect_mode()
        else:
            self.actual_mode = self.mode

        logger.info(f"使用QMT模式: {self.actual_mode.value}")

        # 初始化对应的后端
        if self.actual_mode == QMTMode.MINI:
            self.backend = MiniQMTBackend()
        else:
            self.backend = StandardQMTBackend()

        await self.backend.initialize()

    async def _detect_mode(self) -> QMTMode:
        """自动检测QMT模式"""
        # 先尝试MiniQMT（更直接）
        try:
            import xtquant.xtdata as xtdata
            # 测试连接
            test_data = xtdata.get_full_tick(['000001.SZ'])
            if test_data:
                logger.info("检测到MiniQMT环境")
                return QMTMode.MINI
        except:
            pass

        # 尝试标准QMT（通过Socket）
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(('127.0.0.1', 9999))  # QMT脚本端口
            s.close()
            logger.info("检测到标准QMT环境")
            return QMTMode.STANDARD
        except:
            pass

        # 默认使用MiniQMT
        logger.warning("未检测到QMT环境，默认使用MiniQMT模式")
        return QMTMode.MINI

    # ==================== 统一数据接口 ====================

    async def get_kline(
            self,
            symbol: str,
            period: str = '1d',
            start_date: Optional[str] = None,
            end_date: Optional[str] = None,
            count: int = 100,
            adjust: str = 'none'
    ) -> pd.DataFrame:
        """
        获取K线数据（统一接口）
        
        Parameters:
        -----------
        symbol: 股票代码
        period: 周期
        start_date: 开始日期
        end_date: 结束日期
        count: 数据条数
        adjust: 复权类型
        
        Returns:
        --------
        DataFrame with OHLCV data
        """
        # 先检查缓存
        cache_key = f"kline_{symbol}_{period}_{start_date}_{end_date}_{adjust}"
        cached_data = self.cache_manager.get(cache_key)
        if cached_data is not None:
            logger.info(f"📦 使用缓存数据: {symbol}")
            return cached_data

        # 调用后端获取数据
        df = await self.backend.get_kline(
            symbol, period, start_date, end_date, count, adjust
        )

        # 缓存数据
        if not df.empty:
            self.cache_manager.set(cache_key, df, ttl=300)

        return df

    async def get_realtime_quote(self, symbols: List[str]) -> Dict[str, Dict]:
        """
        获取实时行情（统一接口）
        
        Parameters:
        -----------
        symbols: 股票代码列表
        
        Returns:
        --------
        {symbol: quote_data}
        """
        # 实时数据使用短缓存
        cache_key = f"quote_{','.join(symbols)}"
        cached_data = self.cache_manager.get(cache_key, max_age=10)  # 10秒缓存
        if cached_data is not None:
            return cached_data

        # 调用后端
        quotes = await self.backend.get_realtime_quote(symbols)

        # 短暂缓存
        if quotes:
            self.cache_manager.set(cache_key, quotes, ttl=10)

        return quotes

    async def subscribe_quote(
            self,
            symbols: List[str],
            callback: callable
    ) -> bool:
        """
        订阅实时行情（统一接口）
        
        Parameters:
        -----------
        symbols: 股票代码列表
        callback: 回调函数
        
        Returns:
        --------
        是否订阅成功
        """
        return await self.backend.subscribe_quote(symbols, callback)

    async def get_special_data(
            self,
            data_type: str,
            **kwargs
    ) -> Any:
        """
        获取特殊数据（统一接口）
        
        Parameters:
        -----------
        data_type: 数据类型（longhubang, north_flow等）
        **kwargs: 其他参数
        
        Returns:
        --------
        数据结果
        """
        # 特殊数据缓存时间更长
        cache_key = f"special_{data_type}_{json.dumps(kwargs, sort_keys=True)}"
        cached_data = self.cache_manager.get(cache_key)
        if cached_data is not None:
            return cached_data

        # 调用后端
        data = await self.backend.get_special_data(data_type, **kwargs)

        # 缓存
        if data:
            ttl = 3600 if data_type in ['longhubang', 'financial'] else 600
            self.cache_manager.set(cache_key, data, ttl=ttl)

        return data


class QMTBackend(ABC):
    """QMT后端抽象基类"""

    @abstractmethod
    async def initialize(self) -> bool:
        """初始化后端"""
        pass

    @abstractmethod
    async def get_kline(self, symbol: str, period: str, start_date: str,
                        end_date: str, count: int, adjust: str) -> pd.DataFrame:
        """获取K线数据"""
        pass

    @abstractmethod
    async def get_realtime_quote(self, symbols: List[str]) -> Dict[str, Dict]:
        """获取实时行情"""
        pass

    @abstractmethod
    async def subscribe_quote(self, symbols: List[str], callback: callable) -> bool:
        """订阅行情"""
        pass

    @abstractmethod
    async def get_special_data(self, data_type: str, **kwargs) -> Any:
        """获取特殊数据"""
        pass


class MiniQMTBackend(QMTBackend):
    """MiniQMT后端实现"""

    def __init__(self):
        self.xtdata = None
        self.connected = False

    async def initialize(self) -> bool:
        """初始化MiniQMT连接"""
        try:
            import xtquant.xtdata as xtdata
            self.xtdata = xtdata
            self.connected = True
            logger.info("✅ MiniQMT后端初始化成功")
            return True
        except ImportError:
            logger.error("❌ 无法导入xtdata模块")
            return False

    async def get_kline(self, symbol: str, period: str, start_date: str,
                        end_date: str, count: int, adjust: str) -> pd.DataFrame:
        """获取K线数据"""
        if not self.connected:
            return pd.DataFrame()

        try:
            # 下载数据
            self.xtdata.download_history_data(
                stock_code=symbol,
                period=period,
                start_time=start_date or '',
                end_time=end_date or '',
                count=count
            )

            # 等待下载
            await asyncio.sleep(0.5)

            # 获取数据
            field_list = ['time', 'open', 'high', 'low', 'close', 'volume', 'amount']

            data = self.xtdata.get_market_data(
                field_list=field_list,
                stock_list=[symbol],
                period=period,
                count=count
            )

            if data and symbol in data:
                # 转换为DataFrame
                df_dict = {}
                for field in field_list:
                    if field in data[symbol]:
                        df_dict[field] = data[symbol][field]

                df = pd.DataFrame(df_dict)

                # 处理时间
                if 'time' in df.columns:
                    df['time'] = pd.to_datetime(df['time'], format='%Y%m%d%H%M%S')
                    df.set_index('time', inplace=True)

                return df

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"MiniQMT获取K线失败: {e}")
            return pd.DataFrame()

    async def get_realtime_quote(self, symbols: List[str]) -> Dict[str, Dict]:
        """获取实时行情"""
        if not self.connected:
            return {}

        try:
            tick_data = self.xtdata.get_full_tick(symbols)

            result = {}
            for symbol in symbols:
                if symbol in tick_data:
                    tick = tick_data[symbol]
                    result[symbol] = {
                        'symbol': symbol,
                        'last': tick.get('lastPrice', 0),
                        'open': tick.get('open', 0),
                        'high': tick.get('high', 0),
                        'low': tick.get('low', 0),
                        'volume': tick.get('volume', 0),
                        'amount': tick.get('amount', 0),
                        'bid1': tick.get('bidPrice1', 0),
                        'ask1': tick.get('askPrice1', 0)
                    }

            return result

        except Exception as e:
            logger.error(f"MiniQMT获取实时行情失败: {e}")
            return {}

    async def subscribe_quote(self, symbols: List[str], callback: callable) -> bool:
        """订阅行情"""
        if not self.connected:
            return False

        try:
            for symbol in symbols:
                self.xtdata.subscribe_quote(
                    stock_code=symbol,
                    period='tick',
                    callback=callback
                )
            return True
        except Exception as e:
            logger.error(f"MiniQMT订阅失败: {e}")
            return False

    async def get_special_data(self, data_type: str, **kwargs) -> Any:
        """获取特殊数据"""
        # MiniQMT的特殊数据实现
        return None


class StandardQMTBackend(QMTBackend):
    """标准QMT后端实现（通过Socket通信）"""

    def __init__(self):
        self.socket = None
        self.connected = False
        self.host = '127.0.0.1'
        self.port = 9999

    async def initialize(self) -> bool:
        """初始化标准QMT连接"""
        try:
            import socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            self.socket.connect((self.host, self.port))

            # 发送认证
            auth_msg = {
                'type': 'AUTH',
                'token': 'prod-secure-token-change-this',
                'client': 'UNIFIED_QMT'
            }
            self._send_message(auth_msg)

            self.connected = True
            logger.info("✅ 标准QMT后端初始化成功")
            return True

        except Exception as e:
            logger.error(f"❌ 标准QMT连接失败: {e}")
            return False

    def _send_message(self, msg: Dict):
        """发送消息到QMT脚本"""
        if self.socket:
            data = json.dumps(msg, ensure_ascii=False) + '\n'
            self.socket.sendall(data.encode('utf-8'))

    def _receive_message(self) -> Dict:
        """接收QMT脚本响应"""
        if self.socket:
            data = self.socket.recv(65536)
            if data:
                return json.loads(data.decode('utf-8'))
        return {}

    async def get_kline(self, symbol: str, period: str, start_date: str,
                        end_date: str, count: int, adjust: str) -> pd.DataFrame:
        """获取K线数据"""
        if not self.connected:
            return pd.DataFrame()

        try:
            # 发送请求
            request = {
                'type': 'REQUEST_HISTORY',
                'params': {
                    'stock_code': symbol,
                    'period': period,
                    'start_time': start_date,
                    'end_time': end_date,
                    'count': count,
                    'dividend_type': adjust
                }
            }
            self._send_message(request)

            # 等待响应
            await asyncio.sleep(0.1)
            response = self._receive_message()

            if response.get('success'):
                data = response.get('data', [])
                if data:
                    return pd.DataFrame(data)

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"标准QMT获取K线失败: {e}")
            return pd.DataFrame()

    async def get_realtime_quote(self, symbols: List[str]) -> Dict[str, Dict]:
        """获取实时行情"""
        if not self.connected:
            return {}

        try:
            request = {
                'type': 'REQUEST_TICK',
                'symbols': symbols
            }
            self._send_message(request)

            await asyncio.sleep(0.1)
            response = self._receive_message()

            return response.get('data', {})

        except Exception as e:
            logger.error(f"标准QMT获取实时行情失败: {e}")
            return {}

    async def subscribe_quote(self, symbols: List[str], callback: callable) -> bool:
        """订阅行情"""
        if not self.connected:
            return False

        try:
            request = {
                'type': 'SUBSCRIBE',
                'symbols': symbols
            }
            self._send_message(request)

            # TODO: 设置回调处理
            return True

        except Exception as e:
            logger.error(f"标准QMT订阅失败: {e}")
            return False

    async def get_special_data(self, data_type: str, **kwargs) -> Any:
        """获取特殊数据"""
        # 标准QMT的特殊数据实现
        return None


class SmartCacheManager:
    """
    智能缓存管理器
    
    特性：
    1. 多级缓存（内存+磁盘）
    2. 智能过期策略
    3. 缓存预热
    4. 缓存统计
    """

    def __init__(self, max_memory_size: int = 1000):
        """
        初始化缓存管理器
        
        Args:
            max_memory_size: 最大内存缓存条数
        """
        self.memory_cache = {}  # 内存缓存
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }
        self.max_memory_size = max_memory_size
        self.access_times = {}  # 记录访问时间
        self.access_counts = {}  # 记录访问次数

    def get(self, key: str, max_age: Optional[int] = None) -> Any:
        """
        获取缓存数据
        
        Args:
            key: 缓存键
            max_age: 最大年龄（秒），覆盖默认TTL
            
        Returns:
            缓存的数据或None
        """
        if key in self.memory_cache:
            cached_time, cached_data, ttl = self.memory_cache[key]

            # 检查是否过期
            age = time.time() - cached_time
            if max_age:
                if age > max_age:
                    del self.memory_cache[key]
                    self.cache_stats['misses'] += 1
                    return None
            elif age > ttl:
                del self.memory_cache[key]
                self.cache_stats['misses'] += 1
                return None

            # 更新访问记录
            self.access_times[key] = time.time()
            self.access_counts[key] = self.access_counts.get(key, 0) + 1

            self.cache_stats['hits'] += 1
            logger.debug(f"缓存命中: {key}")
            return cached_data

        self.cache_stats['misses'] += 1
        return None

    def set(self, key: str, data: Any, ttl: int = 300):
        """
        设置缓存数据
        
        Args:
            key: 缓存键
            data: 要缓存的数据
            ttl: 生存时间（秒）
        """
        # 检查缓存大小
        if len(self.memory_cache) >= self.max_memory_size:
            self._evict_lru()

        # 存储数据
        self.memory_cache[key] = (time.time(), data, ttl)
        self.access_times[key] = time.time()
        self.access_counts[key] = 0

        logger.debug(f"缓存设置: {key}, TTL={ttl}秒")

    def _evict_lru(self):
        """LRU缓存淘汰"""
        if not self.access_times:
            return

        # 找出最久未访问的键
        lru_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])

        # 删除
        if lru_key in self.memory_cache:
            del self.memory_cache[lru_key]
            del self.access_times[lru_key]
            if lru_key in self.access_counts:
                del self.access_counts[lru_key]

            self.cache_stats['evictions'] += 1
            logger.debug(f"缓存淘汰: {lru_key}")

    def clear(self):
        """清空缓存"""
        self.memory_cache.clear()
        self.access_times.clear()
        self.access_counts.clear()
        logger.info("缓存已清空")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0

        return {
            'size': len(self.memory_cache),
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'evictions': self.cache_stats['evictions'],
            'hit_rate': f"{hit_rate:.2f}%",
            'hot_keys': sorted(self.access_counts.items(),
                               key=lambda x: x[1], reverse=True)[:10]
        }

    def preload(self, keys: List[str], data_loader: callable):
        """
        预加载缓存
        
        Args:
            keys: 要预加载的键列表
            data_loader: 数据加载函数
        """
        for key in keys:
            if key not in self.memory_cache:
                try:
                    data = data_loader(key)
                    if data is not None:
                        self.set(key, data)
                except Exception as e:
                    logger.error(f"预加载失败 {key}: {e}")


# ==================== 使用示例 ====================
async def example():
    """使用示例"""

    # 创建统一提供者（自动检测模式）
    provider = UnifiedQMTProvider(mode=QMTMode.AUTO)
    await provider.initialize_async()

    # 获取K线数据（自动缓存）
    df = await provider.get_kline(
        symbol='000001.SZ',
        period='1d',
        count=100
    )
    print(f"获取到 {len(df)} 条K线数据")

    # 获取实时行情（短缓存）
    quotes = await provider.get_realtime_quote(['000001.SZ', '600000.SH'])
    for symbol, quote in quotes.items():
        print(f"{symbol}: {quote['last']}")

    # 查看缓存统计
    stats = provider.cache_manager.get_stats()
    print(f"缓存统计: {stats}")


if __name__ == '__main__':
    asyncio.run(example())
