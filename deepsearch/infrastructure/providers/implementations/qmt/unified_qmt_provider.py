# encoding:utf-8
"""
Unified QMT Data Provider
统一的QMT数据提供者 - 同时支持QMT标准版和MiniQMT
Author: DeepSearch Team
Version: 2.0.0
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import queue
import socket
import threading
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, TypedDict, cast, Iterable

import pandas as pd

from deepsearch.infrastructure.providers.interfaces.base import (
    DataProvider,
    DataProviderConfig,
    DataRequest,
    DataResponse,
    DataSourceType,
)
from deepsearch.infrastructure.providers.interfaces.capabilities import DataCapability
from deepsearch.infrastructure.providers.interfaces.runtime import CacheStats
from deepsearch.observability import get_logger
from deepsearch.observability.decorators.decorators import monitor_data_source
from deepsearch.observability.monitoring.data_source_monitor import (
    DataAccessType,
)
from deepsearch.observability.monitoring.data_source_monitor import (
    DataSourceType as MonitorDataSourceType,
)

logger = get_logger(__name__)


class QMTQuotePayload(TypedDict, total=False):
    """统一的QMT行情结构。"""

    symbol: str
    name: str
    last: float
    open: float
    high: float
    low: float
    volume: float
    amount: float
    bid1: float
    ask1: float
    change: float
    change_percent: float
    time: float
    status: str


QuotePayloadMapping = Dict[str, QMTQuotePayload]
QuoteCallback = Callable[[QMTQuotePayload], None]


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
                source_type=DataSourceType.QMT,
                enabled=True,
                config={"cache_enabled": True, "cache_ttl": 300},  # 5分钟缓存
            )

        super().__init__(config)

        self.mode = mode
        self.actual_mode: Optional[QMTMode] = None
        self.backend: Optional[QMTBackend] = None  # 实际的后端实现

        # 智能缓存系统
        self.cache_manager = SmartCacheManager()


    def _require_backend(self) -> "QMTBackend":
        """确保后端已初始化。"""

        if self.backend is None:
            raise RuntimeError("QMT后端未初始化")
        return self.backend


    def get_capabilities(self) -> set[DataCapability]:
        """返回 Unified QMT 支持的数据能力集合。"""

        return {
            DataCapability.REALTIME_QUOTE,
            DataCapability.REALTIME_QUOTES,
            DataCapability.TICK_DATA,
            DataCapability.MINUTE_DATA,
            DataCapability.KLINE_DATA,
        }

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
            xtdata_spec = importlib.util.find_spec("xtquant.xtdata")
            if xtdata_spec is None:
                raise ImportError

            xtdata = importlib.import_module("xtquant.xtdata")
            get_full_tick = getattr(xtdata, "get_full_tick", None)
            if callable(get_full_tick):
                test_data = get_full_tick(["000001.SZ"])
                if test_data:
                    logger.info("检测到MiniQMT环境")
                    return QMTMode.MINI
        except Exception:
            pass

        # 尝试标准QMT（通过Socket）
        try:
            import socket

            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", 9999))  # QMT脚本端口
            s.close()
            logger.info("检测到标准QMT环境")
            return QMTMode.STANDARD
        except Exception:
            pass

        # 默认使用MiniQMT
        logger.warning("未检测到QMT环境，默认使用MiniQMT模式")
        return QMTMode.MINI

    async def _start_source(self) -> None:
        """启动数据源特定服务"""
        if self.backend:
            # 如果后端有start方法，调用它
            if hasattr(self.backend, "start"):
                await self.backend.start()
            logger.info(f"QMT数据源已启动 (模式: {self.actual_mode})")

    async def _stop_source(self) -> None:
        """停止数据源特定服务"""
        if self.backend:
            # 如果后端有stop方法，调用它
            if hasattr(self.backend, "stop"):
                await self.backend.stop()
            logger.info("QMT数据源已停止")

    async def _fetch_data(self, request: DataRequest) -> pd.DataFrame:
        """
        获取数据的内部实现

        Args:
            request: DataRequest对象

        Returns:
            pd.DataFrame: 数据结果
        """
        if not self.backend:
            logger.error("QMT后端未初始化")
            return pd.DataFrame()

        # 根据请求类型调用相应的方法
        if request.symbol:
            # 获取K线数据
            period = request.period or "1d"
            adjust = request.adjust or "none"
            df = await self.get_kline(
                symbol=request.symbol,
                period=period,
                start_date=str(request.start_date) if request.start_date else None,
                end_date=str(request.end_date) if request.end_date else None,
                adjust=adjust,
            )
            return df
        elif request.symbols:
            # 批量获取实时行情
            quotes = await self.get_realtime_quote(request.symbols)
            if quotes:
                df = pd.DataFrame.from_dict(quotes, orient="index")
                return df

        return pd.DataFrame()

    async def get_data(self, request: DataRequest) -> DataResponse:
        """按照 DataRequest 协议返回统一的 DataResponse。"""

        metadata = {
            "source": self.config.name or self.__class__.__name__,
            "request_type": request.request_type,
        }

        if self.backend is None:
            return DataResponse(success=False, error="QMT后端未初始化", metadata=metadata)

        try:
            dataframe = await self._fetch_data(request)
        except Exception as exc:  # pragma: no cover - 防御性日志
            logger.exception("QMT 获取数据异常: %s", exc)
            return DataResponse(success=False, error=str(exc), metadata=metadata)

        return DataResponse(success=True, data=dataframe, metadata=metadata)

    # ==================== 统一数据接口 ====================

    @monitor_data_source(
        source=MonitorDataSourceType.QMT,
        access_type=DataAccessType.HISTORICAL_KLINE,
        extract_symbol=lambda *args, **kwargs: args[1] if len(args) > 1 else kwargs.get("symbol"),
    )
    async def get_kline(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: int = 100,
        adjust: str = "none",
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
            return cast(pd.DataFrame, cached_data)

        # 调用后端获取数据
        try:
            backend = self._require_backend()
        except RuntimeError:
            logger.error("QMT后端未初始化")
            return pd.DataFrame()

        start = start_date or ""
        end = end_date or ""
        adjust_value = adjust or "none"
        df = await backend.get_kline(symbol, period, start, end, count, adjust_value)

        # 缓存数据
        if not df.empty:
            self.cache_manager.set(cache_key, df, ttl=300)

        return df

    @monitor_data_source(
        source=MonitorDataSourceType.QMT,
        access_type=DataAccessType.REALTIME_QUOTE,
        extract_symbol=lambda *args, **kwargs: (
            ",".join(args[1])
            if len(args) > 1 and isinstance(args[1], list)
            else ",".join(kwargs.get("symbols", []))
        ),
    )
    async def get_realtime_quote(self, symbols: List[str]) -> QuotePayloadMapping:
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
        if isinstance(cached_data, dict):
            return cast(QuotePayloadMapping, cached_data)

        # 调用后端
        backend = self.backend
        if backend is None:
            logger.error("QMT后端未初始化")
            return {}

        quotes = await backend.get_realtime_quote(symbols)

        # 短暂缓存
        if quotes:
            self.cache_manager.set(cache_key, quotes, ttl=10)

        return quotes

    async def subscribe_quote(self, symbols: List[str], callback: Optional[QuoteCallback]) -> bool:
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
        backend = self.backend
        if backend is None:
            logger.error("QMT后端未初始化，无法订阅")
            return False

        return await backend.subscribe_quote(symbols, callback)

    async def get_special_data(self, data_type: str, **kwargs) -> Any:
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
        backend = self.backend
        if backend is None:
            logger.error("QMT后端未初始化")
            return None

        data = await backend.get_special_data(data_type, **kwargs)

        # 缓存
        if data:
            ttl = 3600 if data_type in ["longhubang", "financial"] else 600
            self.cache_manager.set(cache_key, data, ttl=ttl)

        return data


class QMTBackend(ABC):
    """QMT后端抽象基类"""

    @abstractmethod
    async def initialize(self) -> bool:
        """初始化后端"""
        pass

    @abstractmethod
    async def get_kline(
        self, symbol: str, period: str, start_date: str, end_date: str, count: int, adjust: str
    ) -> pd.DataFrame:
        """获取K线数据"""
        pass

    @abstractmethod
    async def get_realtime_quote(self, symbols: List[str]) -> QuotePayloadMapping:
        """获取实时行情"""
        pass

    @abstractmethod
    async def subscribe_quote(self, symbols: List[str], callback: Optional[QuoteCallback]) -> bool:
        """订阅行情"""
        pass

    @abstractmethod
    async def get_special_data(self, data_type: str, **kwargs) -> Any:
        """获取特殊数据"""
        pass


class MiniQMTBackend(QMTBackend):
    """MiniQMT后端实现"""

    def __init__(self):
        self.xtdata: Any | None = None
        self.connected = False

    async def initialize(self) -> bool:
        """初始化MiniQMT连接"""
        try:
            self.xtdata = importlib.import_module("xtquant.xtdata")
            self.connected = True
            logger.info("✅ MiniQMT后端初始化成功")
            return True
        except ImportError:
            logger.error("❌ 无法导入xtdata模块")
            return False

    async def get_kline(
        self, symbol: str, period: str, start_date: str, end_date: str, count: int, adjust: str
    ) -> pd.DataFrame:
        """获取K线数据"""
        if not self.connected:
            return pd.DataFrame()

        try:
            # 下载数据
            self.xtdata.download_history_data(
                stock_code=symbol,
                period=period,
                start_time=start_date or "",
                end_time=end_date or "",
                count=count,
            )

            # 等待下载
            await asyncio.sleep(0.5)

            # 获取数据
            field_list = ["time", "open", "high", "low", "close", "volume", "amount"]

            data = self.xtdata.get_market_data(
                field_list=field_list, stock_list=[symbol], period=period, count=count
            )

            if data and symbol in data:
                # 转换为DataFrame
                df_dict = {}
                for field in field_list:
                    if field in data[symbol]:
                        df_dict[field] = data[symbol][field]

                df = pd.DataFrame(df_dict)

                # 处理时间
                if "time" in df.columns:
                    df["time"] = pd.to_datetime(df["time"], format="%Y%m%d%H%M%S")
                    df.set_index("time", inplace=True)

                return df

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"MiniQMT获取K线失败: {e}")
            return pd.DataFrame()

    async def get_realtime_quote(self, symbols: List[str]) -> QuotePayloadMapping:
        """获取实时行情"""
        if not self.connected:
            return {}

        try:
            tick_data = self.xtdata.get_full_tick(symbols)

            result: QuotePayloadMapping = {}
            for symbol in symbols:
                if symbol in tick_data:
                    tick = tick_data[symbol]
                    result[symbol] = {
                        "symbol": symbol,
                        "last": tick.get("lastPrice", 0),
                        "open": tick.get("open", 0),
                        "high": tick.get("high", 0),
                        "low": tick.get("low", 0),
                        "volume": tick.get("volume", 0),
                        "amount": tick.get("amount", 0),
                        "bid1": tick.get("bidPrice1", 0),
                        "ask1": tick.get("askPrice1", 0),
                    }

            return result

        except Exception as e:
            logger.error(f"MiniQMT获取实时行情失败: {e}")
            return {}

    async def subscribe_quote(self, symbols: List[str], callback: Optional[QuoteCallback]) -> bool:
        """订阅行情"""
        if not self.connected:
            return False

        try:
            for symbol in symbols:
                self.xtdata.subscribe_quote(stock_code=symbol, period="tick", callback=callback)
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
        self.host = "127.0.0.1"
        self.port = 9999
        self._callbacks: Dict[str, list[QuoteCallback]] = {}
        self._callback_thread: Optional[threading.Thread] = None
        self._data_queue: queue.Queue[Mapping[str, Any]] = queue.Queue()

    async def initialize(self) -> bool:
        """初始化标准QMT连接"""
        try:
            import socket

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            self.socket.connect((self.host, self.port))

            # 发送认证
            auth_msg = {
                "type": "AUTH",
                "token": "prod-secure-token-change-this",
                "client": "UNIFIED_QMT",
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
            data = json.dumps(msg, ensure_ascii=False) + "\n"
            self.socket.sendall(data.encode("utf-8"))

    def _receive_message(self) -> Dict[str, Any]:
        """接收QMT脚本响应"""
        if self.socket:
            # 设置socket超时为4秒（留1秒给其他处理）
            original_timeout = self.socket.gettimeout()
            self.socket.settimeout(4.0)
            try:
                data = self.socket.recv(65536)
                if data:
                    return cast(Dict[str, Any], json.loads(data.decode("utf-8")))
            except socket.timeout:
                logger.warning("QMT响应超时（4秒）")
                return {}
            except Exception as e:
                logger.error(f"接收QMT响应失败: {e}")
                return {}
            finally:
                # 恢复原始超时设置
                self.socket.settimeout(original_timeout)
        return {}

    async def get_kline(
        self, symbol: str, period: str, start_date: str, end_date: str, count: int, adjust: str
    ) -> pd.DataFrame:
        """获取K线数据"""
        if not self.connected:
            return pd.DataFrame()

        try:
            # 发送请求
            request = {
                "type": "REQUEST_HISTORY",
                "params": {
                    "stock_code": symbol,
                    "period": period,
                    "start_time": start_date,
                    "end_time": end_date,
                    "count": count,
                    "dividend_type": adjust,
                },
            }
            self._send_message(request)

            # 等待响应
            await asyncio.sleep(0.1)
            response = self._receive_message()

            if response.get("success"):
                data = response.get("data", [])
                if data is not None and len(data) > 0:
                    return pd.DataFrame(data)

            return pd.DataFrame()

        except Exception as e:
            logger.error(f"标准QMT获取K线失败: {e}")
            return pd.DataFrame()

    async def get_realtime_quote(self, symbols: List[str]) -> QuotePayloadMapping:
        """获取实时行情"""
        if not self.connected:
            return {}

        try:
            request = {"type": "REQUEST_TICK", "symbols": symbols}
            self._send_message(request)

            await asyncio.sleep(0.1)
            response = self._receive_message()

            payload = response.get("data", {})
            result: QuotePayloadMapping = {}
            if isinstance(payload, Mapping):
                for symbol, raw in payload.items():
                    if isinstance(raw, Mapping):
                        result[str(symbol)] = cast(QMTQuotePayload, dict(raw))
            return result

        except Exception as e:
            logger.error(f"标准QMT获取实时行情失败: {e}")
            return {}

    async def subscribe_quote(self, symbols: List[str], callback: Optional[QuoteCallback]) -> bool:
        """订阅行情"""
        if not self.connected:
            return False

        try:
            # 存储回调函数
            if callback is not None:
                for symbol in symbols:
                    callbacks = self._callbacks.setdefault(symbol, [])
                    if callback not in callbacks:
                        callbacks.append(callback)

            # 发送订阅请求
            request = {
                "type": "SUBSCRIBE",
                "symbols": symbols,
                "callback_id": id(callback) if callback else None,
            }
            self._send_message(request)

            # 启动回调处理（如果需要）
            if callback and not self._callback_thread:
                self._callback_thread = threading.Thread(
                    target=self._process_callbacks, daemon=True, name="QMT-Callback-Processor"
                )
                self._callback_thread.start()
                logger.debug(f"Started callback processor for {len(symbols)} symbols")

            logger.info(f"QMT subscribed {len(symbols)} symbols with callback")
            return True

        except Exception as e:
            logger.error(f"标准QMT订阅失败: {e}")
            return False

    def _process_callbacks(self):
        """处理回调的后台线程"""
        import time

        while self.connected:
            try:
                # 检查是否有新数据
                while not self._data_queue.empty():
                    data = self._data_queue.get_nowait()
                    if isinstance(data, Mapping):
                        symbol = str(data.get("symbol", ""))
                        if symbol and symbol in self._callbacks:
                            # 异步调用所有回调
                            for callback in self._callbacks[symbol]:
                                try:
                                    callback(cast(QMTQuotePayload, dict(data)))
                                except Exception as e:
                                    logger.error(f"Callback error for {symbol}: {e}")
                time.sleep(0.01)  # 短暂休眠避免CPU占用
            except Exception as e:
                if self.connected:
                    logger.debug(f"Callback processor: {e}")
                time.sleep(0.1)

    async def get_special_data(self, data_type: str, **kwargs) -> Any:
        """获取特殊数据"""
        # 标准QMT的特殊数据实现
        return None

CacheEntry = tuple[float, object, int]


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
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.cache_stats: Dict[str, int] = {"hits": 0, "misses": 0, "evictions": 0}
        self.max_memory_size = max_memory_size
        self.access_times: Dict[str, float] = {}
        self.access_counts: Dict[str, int] = {}

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
                    self.cache_stats["misses"] += 1
                    return None
            elif age > ttl:
                del self.memory_cache[key]
                self.cache_stats["misses"] += 1
                return None

            # 更新访问记录
            self.access_times[key] = time.time()
            self.access_counts[key] = self.access_counts.get(key, 0) + 1

            self.cache_stats["hits"] += 1
            logger.debug(f"缓存命中: {key}")
            return cached_data

        self.cache_stats["misses"] += 1
        return None

    def set(self, key: str, data: Any, ttl: int = 300) -> None:
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

    def _evict_lru(self) -> None:
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

            self.cache_stats["evictions"] += 1
            logger.debug(f"缓存淘汰: {lru_key}")

    def clear(self) -> None:
        """清空缓存"""
        self.memory_cache.clear()
        self.access_times.clear()
        self.access_counts.clear()
        logger.info("缓存已清空")

    def get_stats(self) -> CacheStats:
        """获取缓存统计"""
        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        hit_rate = (self.cache_stats["hits"] / total_requests * 100) if total_requests > 0 else 0

        hot_keys: List[tuple[str, int]] = sorted(
            self.access_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]

        return {
            "size": len(self.memory_cache),
            "hits": self.cache_stats["hits"],
            "misses": self.cache_stats["misses"],
            "evictions": self.cache_stats["evictions"],
            "hit_rate": f"{hit_rate:.2f}%",
            "hot_keys": hot_keys,
        }

    def preload(self, keys: Iterable[str], data_loader: Callable[[str], Any]) -> None:
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
    df = await provider.get_kline(symbol="000001.SZ", period="1d", count=100)
    print(f"获取到 {len(df)} 条K线数据")

    # 获取实时行情（短缓存）
    quotes = await provider.get_realtime_quote(["000001.SZ", "600000.SH"])
    for symbol, quote in quotes.items():
        print(f"{symbol}: {quote['last']}")

    # 查看缓存统计
    stats = provider.cache_manager.get_stats()
    print(f"缓存统计: {stats}")


if __name__ == "__main__":
    asyncio.run(example())
