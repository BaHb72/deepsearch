# encoding:utf-8
"""
AmazingData 数据提供者 - 优化版本
解决了线程池阻塞、心跳开销、缓存效率、内存泄漏等关键问题
Author: DeepSearch Team
Version: 2.0.0
"""

import asyncio
import concurrent.futures
import functools
import gc
import hashlib
import json
import os
import statistics
import time
import weakref
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, cast

import pandas as pd

# Arrow Cache for high-performance file-based caching
from core.infrastructure.cache import ArrowCacheManager
from core.infrastructure.providers.interfaces.base import DataProvider, DataProviderError

# Protocol interfaces
from core.infrastructure.providers.protocols.lifecycle import (
    HealthCheckResult,
    HealthStatus,
)
from core.ports.data.requests import KlineRequest, RealtimeQuoteRequest
from core.ports.data.responses import KlineResponse, RealtimeQuoteResponse

# AmazingData SDK
from ._sdk_loader import HAS_AMAZINGDATA, ad
from .config import (
    AmazingDataConfig,
    ProviderConfigLike,
    ensure_amazingdata_provider_config,
    resolve_local_cache_path,
)
from .helpers import fetch_stock_dataset_blocking, normalize_stock_records
from .logging_utils import ProcessLoggerAdapter
from .query_manager import AmazingDataQueryManager
from .types import AmazingDataSDKProtocol

logger = ProcessLoggerAdapter(action="optimized")


class ErrorCode(Enum):
    """错误代码枚举"""

    LOGIN_FAILED = "E001"
    CONNECTION_LOST = "E002"
    TIMEOUT = "E003"
    RATE_LIMIT = "E004"
    INVALID_PARAMS = "E005"
    DATA_ERROR = "E006"
    SUBSCRIPTION_FAILED = "E007"
    UNKNOWN = "E999"


@dataclass
class ErrorContext:
    """错误上下文"""

    code: ErrorCode
    message: str
    details: Dict[str, Any]
    timestamp: float
    retry_count: int = 0
    recoverable: bool = True
    suggestion: Optional[str] = None


@dataclass
class PerformanceMetrics:
    """性能指标"""

    latencies: deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    timestamps: deque[float] = field(default_factory=lambda: deque(maxlen=1000))

    def add_latency(self, latency: float):
        """添加延迟数据"""
        self.latencies.append(latency)
        self.timestamps.append(time.time())
        # deque 自动维护 maxlen，无需手动裁剪

    def get_statistics(self) -> dict:
        """获取统计数据"""
        if not self.latencies:
            return {}

        sorted_latencies = sorted(self.latencies)

        return {
            "count": len(self.latencies),
            "mean": statistics.mean(self.latencies),
            "median": statistics.median(self.latencies),
            "p50": sorted_latencies[int(len(sorted_latencies) * 0.5)],
            "p95": sorted_latencies[int(len(sorted_latencies) * 0.95)],
            "p99": sorted_latencies[int(len(sorted_latencies) * 0.99)],
            "min": min(self.latencies),
            "max": max(self.latencies),
            "qps": self._calculate_qps(),
        }

    def _calculate_qps(self) -> float:
        """计算 QPS"""
        if len(self.timestamps) < 2:
            return 0

        time_range = self.timestamps[-1] - self.timestamps[0]
        if time_range > 0:
            return len(self.timestamps) / time_range

        return 0


class OptimizedThreadPoolManager:
    """优化的线程池管理器"""

    def __init__(self):
        # 动态计算线程池大小
        cpu_count = os.cpu_count() or 4
        self.pool_size = min(max(cpu_count * 4, 32), 128)  # 32-128 线程

        # 创建专用线程池
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.pool_size, thread_name_prefix="amazingdata-"
        )

        # 并发控制信号量
        self.semaphore = asyncio.Semaphore(self.pool_size // 2)  # 限制并发数

        # 监控指标
        self.stats = {
            "active_threads": 0,
            "queued_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
        }

    async def execute_async(self, func, *args, **kwargs):
        """异步执行同步函数，带并发控制"""
        async with self.semaphore:
            self.stats["active_threads"] += 1
            try:
                loop = asyncio.get_event_loop()
                wrapped = functools.partial(func, *args, **kwargs)
                result = await loop.run_in_executor(self.executor, wrapped)
                self.stats["completed_tasks"] += 1
                return result
            except Exception:
                self.stats["failed_tasks"] += 1
                raise
            finally:
                self.stats["active_threads"] -= 1

    def shutdown(self):
        """优雅关闭线程池"""
        # Python 3.9及更早版本不支持timeout参数
        # 只使用wait参数
        self.executor.shutdown(wait=True)


class OptimizedHeartbeat:
    """优化的心跳机制"""

    def __init__(self, config, sdk_getter: Optional[Callable[[], AmazingDataSDKProtocol]] = None):
        self.config = config
        self.base_interval = 60  # 基础间隔
        self.current_interval = self.base_interval
        self.consecutive_failures = 0
        self.last_activity = time.time()

        # sdk_getter 可选，默认使用已加载的 AmazingData SDK 句柄（在测试中为 MagicMock）
        self._sdk_getter = sdk_getter or self._build_default_sdk_getter()

        # 自适应参数
        self.min_interval = 30
        self.max_interval = 300
        self.activity_threshold = 60  # 60秒无活动则降低频率

        # 线程池（用于心跳）
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    @staticmethod
    def _build_default_sdk_getter() -> Callable[[], AmazingDataSDKProtocol]:
        """构造一个默认的 SDK 获取函数，确保类型安全并在缺失时抛出明确异常。"""

        def _getter() -> AmazingDataSDKProtocol:
            if not HAS_AMAZINGDATA or ad is None:
                raise RuntimeError("AmazingData SDK 未加载或初始化失败")
            return cast(AmazingDataSDKProtocol, ad)

        return _getter

    async def send_heartbeat(self):
        """发送优化的心跳"""
        try:
            # 使用轻量级查询作为心跳
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(self.executor, self._minimal_query), timeout=3.0
            )

            self._on_success()
            return True
        except Exception as e:
            self._on_failure(e)
            return False

    def _minimal_query(self):
        """最小数据查询作为心跳"""
        # 查询今天的交易日历（最小数据）
        today = datetime.now().strftime("%Y%m%d")
        sdk = self._sdk_getter()
        return sdk.BaseData.get_trading_calendar(today, today)

    def _on_success(self):
        """心跳成功处理"""
        self.consecutive_failures = 0
        self._adjust_interval()

    def _on_failure(self, error):
        """心跳失败处理"""
        self.consecutive_failures += 1

        # 指数退避
        if self.consecutive_failures > 3:
            self.current_interval = min(self.current_interval * 1.5, self.max_interval)

    def _adjust_interval(self):
        """自适应调整心跳频率"""
        current_time = time.time()
        time_since_activity = current_time - self.last_activity

        if time_since_activity > self.activity_threshold:
            # 长时间无活动，降低频率
            self.current_interval = min(self.current_interval * 1.2, self.max_interval)
        else:
            # 有活动，恢复正常频率
            self.current_interval = max(self.current_interval * 0.9, self.min_interval)

    async def heartbeat_loop(self):
        """优化的心跳循环"""
        heartbeat_count = 0

        while True:
            await asyncio.sleep(self.current_interval)

            success = await self.send_heartbeat()
            heartbeat_count += 1

            # 日志优化：减少日志噪音
            if success:
                if heartbeat_count % 10 == 0:  # 每10次心跳记录一次
                    logger.debug(
                        f"Heartbeat OK (count={heartbeat_count}, interval={self.current_interval}s)"
                    )
            else:
                logger.warning(f"Heartbeat failed ({self.consecutive_failures})")

    def update_activity(self):
        """更新活动时间"""
        self.last_activity = time.time()


class OptimizedCacheManager:
    """优化的缓存管理器"""

    def __init__(self, ttl=300, max_size=32):
        self.cache = {}
        self.ttl = ttl
        self.max_size = max_size  # 缓存最大条数
        self.stats = {"hits": 0, "misses": 0, "evictions": 0}

    def _normalize_params(self, **params) -> dict:
        """参数标准化"""
        normalized = {}

        for key, value in params.items():
            if key == "start_date" or key == "end_date":
                # 统一日期格式
                normalized[key] = self._normalize_date(value)
            elif key == "count":
                # 统一 count 参数
                normalized[key] = value if value and value > 0 else None
            elif value is None or value == "":
                # 忽略空值
                continue
            else:
                normalized[key] = value

        return normalized

    def _normalize_date(self, date_str: Any) -> Optional[str]:
        """���ڸ�ʽ��׼��"""
        if not date_str:
            return None

        normalized = str(date_str).replace("-", "").replace("/", "")

        if len(normalized) == 8:
            return normalized

        return None

    def generate_cache_key(self, **params) -> str:
        """生成标准化缓存键"""
        # 参数标准化
        normalized = self._normalize_params(**params)

        # 排序保证顺序一致
        sorted_params = sorted(normalized.items())

        # 生成哈希键
        key_str = json.dumps(sorted_params, ensure_ascii=False)
        hash_key = hashlib.md5(key_str.encode()).hexdigest()[:16]

        # 添加可读前缀
        prefix = f"{params.get('symbol', 'unknown')}:{params.get('period', 'unknown')}"

        return f"{prefix}:{hash_key}"

    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key in self.cache:
            entry = self.cache[key]

            # 检查过期
            if time.time() - entry["timestamp"] < self.ttl:
                self.stats["hits"] += 1
                entry["hits"] += 1  # 记录命中次数
                return entry["data"]
            else:
                # 过期清理
                del self.cache[key]
                self.stats["evictions"] += 1

        self.stats["misses"] += 1
        return None

    def set(self, key: str, data: Any) -> None:
        """设置缓存"""
        # 检查缓存大小限制
        if len(self.cache) >= self.max_size:
            # 删除最旧的缓存项
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]["timestamp"])
            del self.cache[oldest_key]
            self.stats["evictions"] += 1
        self.cache[key] = {"data": data, "timestamp": time.time(), "hits": 0}

    def get_stats(self) -> dict:
        """获取缓存统计"""
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.stats["hits"] / total_requests if total_requests > 0 else 0

        return {
            "hit_rate": f"{hit_rate:.2%}",
            "total_hits": self.stats["hits"],
            "total_misses": self.stats["misses"],
            "cache_size": len(self.cache),
            "evictions": self.stats["evictions"],
        }


class SubscriptionManager:
    """订阅管理器，防止内存泄漏"""

    def __init__(self):
        # 使用弱引用存储回调
        self._subscriptions = {}
        self._weak_callbacks = weakref.WeakValueDictionary()
        self._subscription_tasks = {}

    def subscribe(self, symbol: str, callback: Callable) -> str:
        """订阅股票，返回订阅ID"""
        subscription_id = f"{symbol}_{id(callback)}"

        if symbol not in self._subscriptions:
            self._subscriptions[symbol] = {
                "callbacks": [],
                "active": False,
                "data_queue": asyncio.Queue(maxsize=1000),
            }

        # 使用弱引用包装回调
        callback_ref = weakref.ref(callback, self._cleanup_callback)
        self._subscriptions[symbol]["callbacks"].append(callback_ref)
        self._weak_callbacks[subscription_id] = callback

        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """取消订阅"""
        symbol = subscription_id.split("_")[0]

        if symbol in self._subscriptions:
            # 清理回调
            callbacks = self._subscriptions[symbol]["callbacks"]
            self._subscriptions[symbol]["callbacks"] = [cb for cb in callbacks if cb() is not None]

            # 如果没有回调了，清理整个订阅
            if not self._subscriptions[symbol]["callbacks"]:
                return self._cleanup_subscription(symbol)

        # 从弱引用字典中移除
        if subscription_id in self._weak_callbacks:
            del self._weak_callbacks[subscription_id]

        return True

    def _cleanup_subscription(self, symbol: str) -> bool:
        """完全清理订阅"""
        if symbol in self._subscriptions:
            # 取消任务
            if symbol in self._subscription_tasks:
                task = self._subscription_tasks[symbol]
                if not task.done():
                    task.cancel()
                del self._subscription_tasks[symbol]

            # 清理队列
            queue = self._subscriptions[symbol].get("data_queue")
            if queue:
                # 清空队列
                while not queue.empty():
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

            # 删除订阅
            del self._subscriptions[symbol]

            # 强制垃圾回收
            gc.collect()

            return True

        return False

    def _cleanup_callback(self, ref):
        """回调被垃圾回收时的清理"""
        # 遍历所有订阅，移除无效回调
        for symbol, sub_info in self._subscriptions.items():
            sub_info["callbacks"] = [cb for cb in sub_info["callbacks"] if cb() is not None]

    async def cleanup_all(self):
        """清理所有订阅和资源"""
        # 取消所有任务
        tasks = list(self._subscription_tasks.values())
        for task in tasks:
            if not task.done():
                task.cancel()

        # 等待任务完成
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # 清理所有订阅
        symbols = list(self._subscriptions.keys())
        for symbol in symbols:
            self._cleanup_subscription(symbol)

        # 清空所有容器
        self._subscriptions.clear()
        self._weak_callbacks.clear()
        self._subscription_tasks.clear()

        # 强制垃圾回收
        gc.collect()


class OptimizedDataConverter:
    """优化的数据转换器"""

    # 预编译的列映射
    COLUMN_MAPPING = {
        "datetime": "datetime",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "amount": "amount",
        "turnover_rate": "turnover_rate",
        "change": "change",
        "change_percent": "change_percent",
    }

    # 数值列（提前定义）
    NUMERIC_COLUMNS = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "turnover_rate",
        "change",
        "change_percent",
    ]

    @classmethod
    def convert_kline_vectorized(cls, data: list) -> pd.DataFrame:
        """向量化K线数据转换"""
        if not data:
            return pd.DataFrame()

        try:
            # 直接创建 DataFrame，避免多次复制
            df = pd.DataFrame(data)

            # 批量重命名列
            df.columns = pd.Index([cls.COLUMN_MAPPING.get(col, col) for col in df.columns])  # type: ignore

            # 向量化时间转换
            if "datetime" in df.columns:
                df["datetime"] = pd.to_datetime(df["datetime"], format="%Y%m%d", errors="coerce")
                df.set_index("datetime", inplace=True)

            # 向量化数值转换（一次性处理所有数值列）
            numeric_cols = list(df.columns.intersection(cls.NUMERIC_COLUMNS))  # type: ignore[attr-defined]
            if len(numeric_cols) > 0:
                df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

            # 使用 numpy 排序（更快）
            if not df.index.is_monotonic_increasing:
                df.sort_index(inplace=True)

            return df

        except Exception as e:
            logger.error(f"数据转换失败: {e}")
            return pd.DataFrame()

    @classmethod
    def validate_and_clean(cls, df: pd.DataFrame) -> pd.DataFrame:
        """数据验证和清理（向量化）"""
        # 使用向量化操作进行数据验证
        if "high" in df.columns and "low" in df.columns:
            # 修正 high < low 的异常数据
            mask = df["high"] < df["low"]
            if mask.any():
                df.loc[mask, ["high", "low"]] = df.loc[mask, ["low", "high"]].values

        # 移除负值（向量化）
        if "volume" in df.columns:
            df.loc[df["volume"] < 0, "volume"] = 0

        # 限制涨跌幅（向量化）
        if "change_percent" in df.columns:
            df["change_percent"] = df["change_percent"].clip(-20, 20)

        return df


class RateLimiter:
    """令牌桶限流器"""

    def __init__(self, rate: float = 100, burst: int = 20):
        self.rate = rate  # 每秒令牌数
        self.burst = burst  # 突发容量
        self.tokens = float(burst)
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens=1):
        """获取令牌"""
        async with self._lock:
            # 补充令牌
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            # 等待令牌
            while self.tokens < tokens:
                sleep_time = (tokens - self.tokens) / self.rate
                await asyncio.sleep(sleep_time)

                # 重新计算
                now = time.time()
                elapsed = now - self.last_update
                self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
                self.last_update = now

            self.tokens -= tokens


class CircuitBreaker:
    """断路器实现"""

    def __init__(self, failure_threshold=5, recovery_timeout=30, half_open_requests=3):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
        self.half_open_count = 0
        self._lock = asyncio.Lock()

    async def call(self, coro):
        """通过断路器调用"""
        async with self._lock:
            # 检查状态
            if self.state == "open":
                # 检查是否可以进入半开状态
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = "half_open"
                    self.half_open_count = 0
                else:
                    raise RuntimeError("服务暂时不可用（断路器开启）")

            if self.state == "half_open":
                # 半开状态，限制请求数
                if self.half_open_count >= self.half_open_requests:
                    # 等待结果
                    await asyncio.sleep(1)

        try:
            result = await coro

            # 成功，重置计数
            async with self._lock:
                if self.state == "half_open":
                    self.half_open_count += 1
                    if self.half_open_count >= self.half_open_requests:
                        # 恢复正常
                        self.state = "closed"
                        self.failure_count = 0
                elif self.state == "closed":
                    self.failure_count = 0

            return result

        except Exception:
            # 失败，增加计数
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()

                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                    logger.warning(f"断路器开启：连续失败 {self.failure_count} 次")

            raise


class MonitoringSystem:
    """监控系统"""

    def __init__(self):
        self.metrics = {
            "kline": PerformanceMetrics(),
            "snapshot": PerformanceMetrics(),
            "subscribe": PerformanceMetrics(),
        }

        self.counters = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        self.gauges = {
            "active_connections": 0,
            "active_subscriptions": 0,
            "thread_pool_size": 0,
            "memory_usage_mb": 0,
        }

        self.events = deque(maxlen=1000)

    def record_request(self, operation: str, latency: float, success: bool):
        """记录请求"""
        if operation in self.metrics:
            self.metrics[operation].add_latency(latency)

        self.counters["total_requests"] += 1

        if success:
            self.counters["successful_requests"] += 1
        else:
            self.counters["failed_requests"] += 1

    def record_event(self, event_type: str, details: dict):
        """记录事件"""
        self.events.append({"timestamp": time.time(), "type": event_type, "details": details})

    def get_health_status(self) -> dict:
        """获取健康状态"""
        total = self.counters["total_requests"]
        success = self.counters["successful_requests"]

        success_rate = success / total if total > 0 else 0

        # 判断健康状态
        if success_rate > 0.95:
            status = "healthy"
        elif success_rate > 0.8:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "success_rate": f"{success_rate:.2%}",
            "metrics": {name: metrics.get_statistics() for name, metrics in self.metrics.items()},
            "counters": self.counters,
            "gauges": self.gauges,
        }


class OptimizedAmazingDataProvider(DataProvider):
    """优化后的 AmazingData 数据提供者"""

    def __init__(self, config: ProviderConfigLike):
        provider_config = ensure_amazingdata_provider_config(config)
        super().__init__(provider_config)

        if not HAS_AMAZINGDATA or ad is None:
            raise ImportError("AmazingData SDK 未安装")

        self.config: AmazingDataConfig = provider_config

        self._sdk: AmazingDataSDKProtocol = cast(AmazingDataSDKProtocol, ad)

        # 优化的组件
        self.thread_pool = OptimizedThreadPoolManager()
        # 使用 Arrow IPC 文件缓存，支持跨进程共享和持久化
        self.cache = ArrowCacheManager(namespace="amazingdata", ttl=300)
        self.subscription_manager = SubscriptionManager()
        self.heartbeat = OptimizedHeartbeat(provider_config, self._require_sdk)

        # 并发控制
        self.rate_limiter = RateLimiter(rate=100, burst=20)
        self.circuit_breaker = CircuitBreaker()

        # 监控
        self.monitoring = MonitoringSystem()

        # 连接状态
        self._connected = False
        self._login_time: datetime | None = None
        self._stats: Dict[str, Any] = {}

        # 任务管理
        self._heartbeat_task: asyncio.Task[None] | None = None

    def _require_sdk(self) -> AmazingDataSDKProtocol:
        """确保 SDK 在运行时可用，并向类型检查器收窄可选类型。"""

        return self._sdk

    # ============ ILifecycleProvider 实现 ============

    async def initialize(self) -> None:
        """初始化 Provider

        内部调用现有的初始化逻辑。
        """
        try:
            logger.info("OptimizedAmazingDataProvider 初始化...")

            # 如果已经连接，跳过
            if self._connected:
                logger.info("Provider 已初始化，跳过")
                return

            # 执行登录（内部会初始化 SDK）
            # 注意：不启动心跳，由 start() 方法启动
            result = await self._login()
            if not result:
                from core.infrastructure.providers.exceptions import ProviderInitializationError

                raise ProviderInitializationError(provider="amazingdata", message="登录失败")

            logger.info("OptimizedAmazingDataProvider 初始化成功")

        except Exception as e:
            logger.error(f"OptimizedAmazingDataProvider 初始化失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderInitializationError

            raise ProviderInitializationError(provider="amazingdata", message=str(e)) from e

    async def start(self) -> None:
        """启动 Provider

        启动心跳等后台任务。
        """
        try:
            logger.info("OptimizedAmazingDataProvider 启动...")

            # 如果心跳任务已启动，跳过
            if self._heartbeat_task and not self._heartbeat_task.done():
                logger.info("心跳任务已运行，跳过")
                return

            # 启动心跳
            self._heartbeat_task = cast(
                asyncio.Task[None], asyncio.create_task(self.heartbeat.heartbeat_loop())
            )

            logger.info("OptimizedAmazingDataProvider 启动成功")

        except Exception as e:
            logger.error(f"OptimizedAmazingDataProvider 启动失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderStateError

            raise ProviderStateError(provider="amazingdata", message=f"启动失败: {e}") from e

    async def stop(self) -> None:
        """停止 Provider

        停止心跳，登出，清理资源。
        内部调用现有的 disconnect() 方法。
        """
        try:
            logger.info("OptimizedAmazingDataProvider 停止...")

            # 调用现有的 disconnect 方法
            await self.disconnect()

            logger.info("OptimizedAmazingDataProvider 停止成功")

        except Exception as e:
            logger.error(f"OptimizedAmazingDataProvider 停止失败: {e}")
            # 不抛出异常，确保优雅关闭

    async def health_check(self) -> HealthCheckResult:
        """健康检查

        检查连接状态、心跳状态、SDK 状态。
        """
        try:
            # 检查连接状态
            if not self._connected:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="未连接到 AmazingData",
                    details={"connected": False},
                )

            # 检查心跳任务
            heartbeat_alive = self._heartbeat_task is not None and not self._heartbeat_task.done()

            # 检查登录时间
            login_duration = 0.0
            if self._login_time:
                login_duration = (datetime.now() - self._login_time).total_seconds()

            # 组装详情
            details = {
                "connected": self._connected,
                "heartbeat_alive": heartbeat_alive,
                "login_duration_seconds": login_duration,
                "consecutive_heartbeat_failures": self.heartbeat.consecutive_failures,
            }

            # 判断健康状态
            if not heartbeat_alive:
                status = HealthStatus.DEGRADED
                message = "心跳任务未运行"
            elif self.heartbeat.consecutive_failures > 5:
                status = HealthStatus.DEGRADED
                message = f"心跳连续失败 {self.heartbeat.consecutive_failures} 次"
            else:
                status = HealthStatus.HEALTHY
                message = "运行正常"

            return HealthCheckResult(status=status, message=message, details=details)

        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY, message=f"健康检查异常: {e}", details={}
            )

    # ============ IKlineProvider 实现 ============

    async def query_kline(self, request: KlineRequest) -> KlineResponse:
        """查询K线数据

        适配现有的 get_kline_data 方法。
        """
        try:
            # 调用现有方法
            result = await self.get_kline_data(
                symbol=request.asset,
                period=request.timeframe,
                start_date=request.start_date,
                end_date=request.end_date,
                adjust=request.adjust,
            )

            # 转换为标准响应
            return KlineResponse(
                success=True,
                data=result,
                metadata={
                    "source": "amazingdata",
                    "symbol": request.asset,
                    "timeframe": request.timeframe,
                },
            )

        except Exception as e:
            logger.error(f"查询K线失败: {e}")
            from core.infrastructure.providers.exceptions import ProviderDataError

            raise ProviderDataError(provider="amazingdata", message=f"查询K线失败: {e}") from e

    # ============ IRealtimeProvider 实现 ============

    async def query_realtime(self, request: RealtimeQuoteRequest) -> RealtimeQuoteResponse:
        """查询实时行情

        注意：OptimizedAmazingDataProvider 当前可能没有实时行情方法，
        这里提供一个占位实现或抛出 NotImplementedError。
        """
        # 如果有实时行情方法，调用它
        # 如果没有，抛出未实现异常
        raise NotImplementedError("AmazingData Provider 暂不支持实时行情查询")

    # ============ 原有方法保留 ============

    async def connect(self) -> bool:
        """连接到数据源"""
        try:
            # 登录
            result = await self._login()
            if result:
                # 启动心跳
                self._heartbeat_task = cast(
                    asyncio.Task[None], asyncio.create_task(self.heartbeat.heartbeat_loop())
                )
                logger.info("AmazingData 优化版本连接成功")
                return True
            return False
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False

    async def disconnect(self) -> None:
        """断开连接"""
        try:
            # 取消心跳
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass

            # 清理订阅
            await self.subscription_manager.cleanup_all()

            # 登出
            await self._logout()

            # 关闭线程池（异步执行避免阻塞）
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.thread_pool.shutdown)

            logger.info("AmazingData 优化版本已断开连接")
        except Exception as e:
            logger.error(f"断开连接失败: {e}")

    async def _login(self) -> bool:
        """登录 AmazingData"""
        try:
            logger.info("正在登录 AmazingData (优化版本)...")

            username = (self.config.username or "").strip()
            password = (self.config.password or "").strip()
            if not username or username.replace("*", "").strip() == "":
                raise DataProviderError("AmazingData 优化版缺少有效的用户名配置")
            if not password:
                raise DataProviderError("AmazingData 优化版缺少有效的密码配置")

            # 使用优化的线程池执行登录
            sdk = self._require_sdk()
            try:
                result = await asyncio.wait_for(
                    self.thread_pool.execute_async(
                        sdk.login,
                        self.config.username,
                        self.config.password,
                        self.config.host,
                        self.config.port,
                    ),
                    timeout=5.0,
                )
            except SystemExit as exc:
                exit_code = getattr(exc, "code", 0)
                error_msg = f"SDK尝试强制退出，请查看 exit code: {exit_code}"
                await self._trigger_alert("SDK_EXIT", error_msg)
                raise DataProviderError(error_msg) from exc

            if result == 0 or result is True:
                self._connected = True
                self._login_time = datetime.now()
                logger.info("AmazingData 登录成功")
                return True
            else:
                logger.error(f"AmazingData 登录失败，错误码: {result}")
                return False

        except asyncio.TimeoutError:
            logger.error("登录超时")
            return False
        except Exception as e:
            logger.error(f"登录异常: {e}")
            if isinstance(e, DataProviderError):
                raise
            return False

    async def _trigger_alert(self, alert_type: str, message: str) -> None:
        """触发告警并记录基础统计"""
        try:
            logger.critical(f"[ALERT][{alert_type}] {message}")
            self.monitoring.record_event("alert", {"type": alert_type, "message": message})
            alerts = cast(List[Dict[str, str]], self._stats.setdefault(alert_type, []))
            alerts.append({"timestamp": datetime.now().isoformat(), "message": message})
        except Exception as exc:
            logger.error(f"Failed to trigger alert: {exc}")

    async def _logout(self) -> None:
        """登出 AmazingData"""
        if not self._connected:
            return

        sdk = self._require_sdk()
        username = getattr(self.config, "username", None)

        try:
            try:
                logout_args = (username,) if username else ()
                await self.thread_pool.execute_async(sdk.logout, *logout_args)
            except TypeError:
                # 不同 SDK 版本可能不需要 username 参数
                await self.thread_pool.execute_async(sdk.logout)
            logger.info("AmazingData 已登出")
        except SystemExit as exc:
            exit_code = getattr(exc, "code", None)
            logger.warning("AmazingData SDK 在登出时触发 SystemExit，exit_code={!r}", exit_code)
        except Exception as e:
            logger.error(f"登出失败: {e}")
        finally:
            self._connected = False

    async def get_kline(
        self,
        symbol: str,
        period: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        count: Optional[int] = None,
        adjust: Optional[str] = None,
    ) -> pd.DataFrame:
        """获取K线数据（优化版）"""
        start_time = time.time()

        try:
            # 更新活动时间
            self.heartbeat.update_activity()

            # 限流
            await self.rate_limiter.acquire()

            # 生成缓存键
            cache_key = self.cache.generate_cache_key(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                count=count,
                adjust=adjust,
            )

            # 查询缓存
            cached_data = self.cache.get(cache_key)
            if isinstance(cached_data, pd.DataFrame):
                self.monitoring.counters["cache_hits"] += 1
                return cached_data.copy()

            self.monitoring.counters["cache_misses"] += 1

            sdk = self._require_sdk()

            async def fetch() -> pd.DataFrame:
                result = await self.thread_pool.execute_async(
                    sdk.KLine.get_kline, symbol, period, start_date, end_date, count, adjust
                )

                df = AmazingDataQueryManager.normalize_kline_payload(result, symbol)
                df = OptimizedDataConverter.validate_and_clean(df)
                self.cache.set(cache_key, df)

                return df

            result = cast(pd.DataFrame, await self.circuit_breaker.call(fetch()))

            latency = time.time() - start_time
            self.monitoring.record_request("kline", latency, True)

            return result

        except Exception as e:
            # 记录失败
            latency = time.time() - start_time
            self.monitoring.record_request("kline", latency, False)

            logger.error(f"获取K线数据失败: {e}")
            raise DataProviderError(f"获取K线数据失败: {e}")

    async def subscribe(self, symbols: List[str], callback: Callable) -> List[str]:
        """订阅实时数据（优化版）"""
        subscription_ids = []

        for symbol in symbols:
            try:
                # 通过订阅管理器订阅
                sub_id = self.subscription_manager.subscribe(symbol, callback)
                subscription_ids.append(sub_id)

                # 记录监控
                self.monitoring.gauges["active_subscriptions"] += 1

            except Exception as e:
                logger.error(f"订阅 {symbol} 失败: {e}")

        return subscription_ids

    async def unsubscribe(self, subscription_ids: List[str]):
        """取消订阅（优化版）"""
        for sub_id in subscription_ids:
            try:
                success = self.subscription_manager.unsubscribe(sub_id)
                if success:
                    self.monitoring.gauges["active_subscriptions"] -= 1

            except Exception as e:
                logger.error(f"取消订阅 {sub_id} 失败: {e}")

    async def get_health_status(self) -> dict:
        """获取健康状态"""
        return {
            "provider": "amazingdata_optimized",
            "status": self.monitoring.get_health_status(),
            "cache": self.cache.get_stats(),
            "circuit_breaker": self.circuit_breaker.state,
            "thread_pool": {
                "size": self.thread_pool.pool_size,
                "active": self.thread_pool.stats["active_threads"],
                "completed": self.thread_pool.stats["completed_tasks"],
                "failed": self.thread_pool.stats["failed_tasks"],
            },
            "heartbeat": {
                "interval": self.heartbeat.current_interval,
                "failures": self.heartbeat.consecutive_failures,
            },
        }

    def is_connected(self) -> bool:
        """检查连接状态"""
        return self._connected

    async def initialize(self) -> bool:
        """初始化数据源 - 实现抽象方法"""
        return await self.connect()

    async def get_calendar(self, data_type: str = "int", market: str = "SH") -> list[int]:
        """
        获取交易日历

        Args:
            data_type: 返回数据类型，'int' 返回 YYYYMMDD 格式
            market: 市场代码，'SH' 或 'SZ'

        Returns:
            交易日期列表
        """
        try:
            loop = asyncio.get_event_loop()
            base_data = self._sdk.BaseData()
            result = await loop.run_in_executor(None, base_data.get_calendar, data_type, market)
            if not result:
                return []
            # 规范化为 int 列表
            return [int(d) for d in result]
        except Exception as e:
            logger.error(f"获取交易日历失败: {e}")
            return []

    async def get_stock_list(
        self, limit: Optional[int] = None, **kwargs
    ) -> Optional[list[dict[str, Any]]]:
        """获取股票列表 - 实现抽象方法"""
        try:
            # 限流
            await self.rate_limiter.acquire()

            # 通过优化的线程池执行
            sdk = self._require_sdk()
            security_type = str(kwargs.get("security_type", "EXTRA_STOCK_A"))
            start_date = kwargs.get("start_date")
            end_date = kwargs.get("end_date")
            local_path = resolve_local_cache_path(self.config, kwargs.get("local_path"))
            raw_dataset = await self.thread_pool.execute_async(
                fetch_stock_dataset_blocking,
                sdk,
                security_type=security_type,
                start_date=start_date,
                end_date=end_date,
                local_path=local_path,
            )

            records = normalize_stock_records(raw_dataset)
            if not records:
                return None

            if limit and limit > 0:
                records = records[:limit]

            return records

        except Exception as e:
            logger.error(f"获取股票列表失败: {e}")
            return None

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
        **kwargs,
    ) -> Optional[list[dict[str, Any]]]:
        """获取K线数据 - 实现抽象方法"""
        try:
            # 调用已有的get_kline方法
            df = await self.get_kline(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                count=limit,
                adjust=kwargs.get("adjust"),
            )

            if df.empty:
                return None

            # 转换为字典列表格式
            df = df.reset_index()
            kline_data: list[dict[str, Any]] = []

            for _, row in df.iterrows():
                kline_item: dict[str, Any] = {
                    "symbol": symbol,
                    "period": period,
                    "datetime": (
                        row.get("datetime", "").strftime("%Y-%m-%d %H:%M:%S")
                        if pd.notnull(row.get("datetime"))
                        else ""
                    ),
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)),
                    "amount": float(row.get("amount", 0)),
                }
                kline_data.append(kline_item)

            return kline_data

        except Exception as e:
            logger.error(f"获取K线数据失败: {e}")
            return None
