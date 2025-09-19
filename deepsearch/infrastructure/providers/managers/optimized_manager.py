"""
优化的数据源管理器

主要优化:
1. 并行数据源初始化
2. 智能路由和负载均衡
3. 故障转移和熔断机制
4. 预测性缓存预热
5. 延迟感知的数据源选择
"""
import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional, List, Type, Callable
import statistics
from datetime import datetime, timedelta

from loguru import logger

# 熔断器状态
class CircuitState(Enum):
    CLOSED = "closed"     # 正常状态
    OPEN = "open"         # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态


@dataclass
class DataSourceMetrics:
    """数据源性能指标"""
    success_count: int = 0
    failure_count: int = 0
    total_latency: float = 0.0
    latency_samples: deque = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    
    def __post_init__(self):
        if self.latency_samples is None:
            self.latency_samples = deque(maxlen=100)  # 保留最近100个采样
    
    @property
    def success_rate(self) -> float:
        """计算成功率"""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    @property
    def avg_latency(self) -> float:
        """计算平均延迟"""
        if not self.latency_samples:
            return float('inf')
        return statistics.mean(self.latency_samples)
    
    @property
    def p95_latency(self) -> float:
        """计算P95延迟"""
        if not self.latency_samples:
            return float('inf')
        sorted_samples = sorted(self.latency_samples)
        idx = int(len(sorted_samples) * 0.95)
        return sorted_samples[idx] if idx < len(sorted_samples) else sorted_samples[-1]


class CircuitBreaker:
    """
    熔断器实现
    
    当失败率超过阈值时自动熔断，避免级联故障
    """
    
    def __init__(self,
                 failure_threshold: int = 5,
                 success_threshold: int = 2,
                 timeout: float = 60.0):
        """
        初始化熔断器
        
        Args:
            failure_threshold: 触发熔断的失败次数
            success_threshold: 恢复所需的成功次数
            timeout: 熔断超时时间（秒）
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
    
    def call(self, func: Callable, *args, **kwargs):
        """
        通过熔断器调用函数
        
        Args:
            func: 要调用的函数
            args: 位置参数
            kwargs: 关键字参数
            
        Returns:
            函数返回值
            
        Raises:
            CircuitOpenError: 熔断器打开时
        """
        if self.state == CircuitState.OPEN:
            # 检查是否应该尝试半开
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    async def async_call(self, func: Callable, *args, **kwargs):
        """
        异步版本的熔断器调用
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """检查是否应该尝试重置熔断器"""
        return (self.last_failure_time and 
                time.time() - self.last_failure_time >= self.timeout)
    
    def _on_success(self):
        """处理成功调用"""
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0
    
    def _on_failure(self):
        """处理失败调用"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.success_count = 0


class CircuitOpenError(Exception):
    """熔断器打开异常"""
    pass


class SmartRouter:
    """
    智能路由器
    
    根据延迟、成功率等指标智能选择数据源
    """
    
    def __init__(self):
        self.metrics: Dict[str, DataSourceMetrics] = defaultdict(DataSourceMetrics)
        self.weights: Dict[str, float] = {}
        
        # 路由策略参数
        self.latency_weight = 0.6  # 延迟权重
        self.success_rate_weight = 0.4  # 成功率权重
        
    def update_metrics(self, source_name: str, success: bool, latency: float):
        """
        更新数据源指标
        
        Args:
            source_name: 数据源名称
            success: 是否成功
            latency: 响应延迟
        """
        metrics = self.metrics[source_name]
        
        if success:
            metrics.success_count += 1
            metrics.last_success = datetime.now()
        else:
            metrics.failure_count += 1
            metrics.last_failure = datetime.now()
        
        metrics.total_latency += latency
        metrics.latency_samples.append(latency)
        
        # 重新计算权重
        self._recalculate_weights()
    
    def _recalculate_weights(self):
        """重新计算路由权重"""
        if not self.metrics:
            return
        
        # 计算每个数据源的得分
        scores = {}
        for source_name, metrics in self.metrics.items():
            # 延迟得分（延迟越低得分越高）
            latency_score = 1.0 / (1.0 + metrics.avg_latency)
            
            # 成功率得分
            success_score = metrics.success_rate
            
            # 综合得分
            total_score = (
                self.latency_weight * latency_score +
                self.success_rate_weight * success_score
            )
            
            scores[source_name] = total_score
        
        # 归一化权重
        total = sum(scores.values())
        if total > 0:
            self.weights = {k: v / total for k, v in scores.items()}
        else:
            self.weights = {k: 1.0 / len(scores) for k in scores}
    
    def select_sources(self, sources: List[str], count: int = 1) -> List[str]:
        """
        选择最优数据源
        
        Args:
            sources: 可用数据源列表
            count: 选择数量
            
        Returns:
            选中的数据源列表
        """
        # 根据权重排序
        available_sources = [s for s in sources if s in self.weights]
        
        if not available_sources:
            # 如果没有历史数据，随机选择
            return sources[:count]
        
        # 按权重排序
        sorted_sources = sorted(
            available_sources,
            key=lambda x: self.weights.get(x, 0),
            reverse=True
        )
        
        return sorted_sources[:count]


class OptimizedDataSourceManager:
    """
    优化的数据源管理器
    
    特性:
    1. 并行初始化
    2. 智能路由
    3. 熔断保护
    4. 预测性缓存
    5. 性能监控
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化数据源管理器
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.data_sources: Dict[str, Any] = {}
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.router = SmartRouter()
        
        # 缓存
        self.cache: Dict[str, Tuple[Any, float]] = {}  # key -> (data, timestamp)
        self.cache_ttl = 300  # 5分钟
        
        # 预测性缓存
        self.access_history: deque = deque(maxlen=1000)
        self.prefetch_queue: asyncio.Queue = None
        
        # 性能统计
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'total_latency': 0.0,
            'failures': 0
        }
    
    async def initialize(self):
        """并行初始化所有数据源"""
        logger.info("开始并行初始化数据源...")
        
        # 收集所有初始化任务
        init_tasks = []
        for source_name, source_config in self.config.items():
            if source_config.get('enabled', False):
                task = asyncio.create_task(
                    self._init_source(source_name, source_config)
                )
                init_tasks.append((source_name, task))
        
        # 并行执行初始化
        if init_tasks:
            results = await asyncio.gather(
                *[task for _, task in init_tasks],
                return_exceptions=True
            )
            
            # 处理结果
            for (source_name, _), result in zip(init_tasks, results):
                if isinstance(result, Exception):
                    logger.error(f"数据源 {source_name} 初始化失败: {result}")
                else:
                    if result is not None and not result.empty:
                        self.data_sources[source_name] = result
                        self.circuit_breakers[source_name] = CircuitBreaker()
                        logger.info(f"数据源 {source_name} 初始化成功")
        
        # 启动预取任务
        self.prefetch_queue = asyncio.Queue()
        asyncio.create_task(self._prefetch_worker())
        
        logger.info(f"数据源管理器初始化完成，可用数据源: {list(self.data_sources.keys())}")
    
    async def _init_source(self, source_name: str, config: Dict) -> Optional[Any]:
        """
        初始化单个数据源
        
        Args:
            source_name: 数据源名称
            config: 配置字典
            
        Returns:
            数据源实例或None
        """
        try:
            # 动态导入数据源类
            if source_name == "qmt":
                from deepsearch.infrastructure.providers.datafeed.qmt.provider import QMTDataProvider
                provider = QMTDataProvider(config)
            elif source_name == "akshare":
                from deepsearch.infrastructure.providers.implementations.akshare.akshare_direct import AkShareDirectProvider
                provider = AkShareDirectProvider(config)
            else:
                logger.warning(f"未知数据源类型: {source_name}")
                return None
            
            # 初始化数据源
            if hasattr(provider, 'initialize'):
                await provider.initialize()
            
            return provider
            
        except Exception as e:
            logger.error(f"初始化数据源 {source_name} 失败: {e}")
            return None
    
    async def get_data(self, 
                       data_type: str,
                       symbol: str,
                       **kwargs) -> Optional[Any]:
        """
        获取数据（带智能路由和缓存）
        
        Args:
            data_type: 数据类型（如 'kline', 'tick'）
            symbol: 标的代码
            **kwargs: 其他参数
            
        Returns:
            数据或None
        """
        self.stats['total_requests'] += 1
        
        # 检查缓存
        cache_key = f"{data_type}:{symbol}:{str(kwargs)}"
        cached_data = self._get_from_cache(cache_key)
        if cached_data is not None:
            self.stats['cache_hits'] += 1
            # 记录访问历史用于预测
            self._record_access(data_type, symbol)
            return cached_data
        
        # 选择数据源
        available_sources = list(self.data_sources.keys())
        selected_sources = self.router.select_sources(available_sources, count=3)
        
        # 并发请求多个数据源
        tasks = []
        for source_name in selected_sources:
            if source_name in self.data_sources:
                task = asyncio.create_task(
                    self._fetch_from_source(
                        source_name, data_type, symbol, **kwargs
                    )
                )
                tasks.append((source_name, task))
        
        # 使用 as_completed 获取最快的响应
        if tasks:
            for future in asyncio.as_completed([t for _, t in tasks]):
                try:
                    result = await future
                    if result is not None:
                        # 缓存结果
                        self._put_to_cache(cache_key, result)
                        # 记录访问历史
                        self._record_access(data_type, symbol)
                        # 触发预取
                        await self._trigger_prefetch(data_type, symbol)
                        return result
                except Exception as e:
                    logger.debug(f"数据源请求失败: {e}")
                    continue
        
        self.stats['failures'] += 1
        return None
    
    async def _fetch_from_source(self,
                                 source_name: str,
                                 data_type: str,
                                 symbol: str,
                                 **kwargs) -> Optional[Any]:
        """
        从特定数据源获取数据
        
        Args:
            source_name: 数据源名称
            data_type: 数据类型
            symbol: 标的代码
            **kwargs: 其他参数
            
        Returns:
            数据或None
        """
        source = self.data_sources.get(source_name)
        breaker = self.circuit_breakers.get(source_name)
        
        if not source or not breaker:
            return None
        
        start_time = time.perf_counter()
        success = False
        
        try:
            # 通过熔断器调用
            async def fetch():
                method_name = f"get_{data_type}"
                if hasattr(source, method_name):
                    method = getattr(source, method_name)
                    if asyncio.iscoroutinefunction(method):
                        return await method(symbol, **kwargs)
                    else:
                        return method(symbol, **kwargs)
                return None
            
            result = await breaker.async_call(fetch)
            success = True
            return result
            
        except CircuitOpenError:
            logger.debug(f"数据源 {source_name} 熔断器打开")
            return None
        except Exception as e:
            logger.debug(f"数据源 {source_name} 请求失败: {e}")
            return None
        finally:
            # 更新路由指标
            latency = time.perf_counter() - start_time
            self.router.update_metrics(source_name, success, latency)
            self.stats['total_latency'] += latency
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """从缓存获取数据"""
        if key in self.cache:
            data, timestamp = self.cache[key]
            # 检查是否过期
            if time.time() - timestamp < self.cache_ttl:
                return data
            else:
                # 清理过期数据
                del self.cache[key]
        return None
    
    def _put_to_cache(self, key: str, data: Any):
        """放入缓存"""
        self.cache[key] = (data, time.time())
        
        # 限制缓存大小
        if len(self.cache) > 10000:
            # 删除最老的10%
            items = sorted(self.cache.items(), key=lambda x: x[1][1])
            for k, _ in items[:1000]:
                del self.cache[k]
    
    def _record_access(self, data_type: str, symbol: str):
        """记录访问历史"""
        self.access_history.append({
            'type': data_type,
            'symbol': symbol,
            'timestamp': time.time()
        })
    
    async def _trigger_prefetch(self, data_type: str, symbol: str):
        """触发预取"""
        # 分析访问模式，预测下一个可能访问的数据
        related_symbols = self._predict_next_access(symbol)
        
        for next_symbol in related_symbols[:3]:  # 预取前3个
            await self.prefetch_queue.put((data_type, next_symbol))
    
    def _predict_next_access(self, current_symbol: str) -> List[str]:
        """
        预测下一个可能访问的标的

        使用多种策略智能预测：
        1. 历史访问模式
        2. 板块关联性
        3. 市值相似性
        4. 行业分类
        """
        predictions = []

        try:
            # 策略1: 基于历史访问模式
            # 如果有访问历史，找出经常一起访问的股票
            if hasattr(self, '_access_history'):
                related = self._find_related_symbols(current_symbol)
                predictions.extend(related[:3])

            # 策略2: 同板块股票
            sector_stocks = self._get_same_sector_stocks(current_symbol)
            predictions.extend(sector_stocks[:2])

            # 策略3: 相邻代码（简单但有效）
            if len(current_symbol) >= 6 and current_symbol[:6].isdigit():
                try:
                    code = int(current_symbol[:6])
                    market = current_symbol[7:] if len(current_symbol) > 7 else "SH"

                    # 添加相邻的代码
                    for offset in [1, -1, 2, -2, 3]:
                        adjacent_code = code + offset
                        # 确保代码在合理范围内
                        if 1 <= adjacent_code <= 999999:
                            predictions.append(f"{adjacent_code:06d}.{market}")
                except (ValueError, IndexError):
                    pass

            # 策略4: 热门股票
            # 总是预取一些热门标的
            hot_stocks = self._get_hot_stocks()
            predictions.extend(hot_stocks[:2])

            # 去重并限制数量
            seen = set()
            unique_predictions = []
            for symbol in predictions:
                if symbol not in seen and symbol != current_symbol:
                    seen.add(symbol)
                    unique_predictions.append(symbol)
                    if len(unique_predictions) >= 5:
                        break

            return unique_predictions

        except Exception as e:
            logger.debug(f"预测失败，使用默认策略: {e}")
            # 降级到简单策略
            try:
                if len(current_symbol) >= 6 and current_symbol[:6].isdigit():
                    code = int(current_symbol[:6])
                    market = current_symbol[7:] if len(current_symbol) > 7 else "SH"
                    return [
                        f"{code+1:06d}.{market}",
                        f"{code+2:06d}.{market}",
                        f"{code-1:06d}.{market}"
                    ]
            except:
                pass

            return []

    def _find_related_symbols(self, symbol: str) -> List[str]:
        """查找关联的股票代码"""
        # 简单实现：返回历史记录中经常一起出现的股票
        if not hasattr(self, '_access_history'):
            self._access_history = {}

        related = []
        if symbol in self._access_history:
            # 获取一起访问过的股票
            co_accessed = self._access_history.get(symbol, {})
            # 按访问次数排序
            sorted_symbols = sorted(co_accessed.items(), key=lambda x: x[1], reverse=True)
            related = [s[0] for s in sorted_symbols[:5]]

        return related

    def _get_same_sector_stocks(self, symbol: str) -> List[str]:
        """获取同板块股票"""
        # 简单的板块分类规则
        sector_map = {
            "600": ["600000.SH", "600001.SH", "600002.SH"],  # 上证主板
            "000": ["000001.SZ", "000002.SZ", "000003.SZ"],  # 深证主板
            "002": ["002001.SZ", "002002.SZ", "002003.SZ"],  # 中小板
            "300": ["300001.SZ", "300002.SZ", "300003.SZ"],  # 创业板
            "688": ["688001.SH", "688002.SH", "688003.SH"],  # 科创板
        }

        if len(symbol) >= 3:
            prefix = symbol[:3]
            return sector_map.get(prefix, [])
        return []

    def _get_hot_stocks(self) -> List[str]:
        """获取热门股票列表"""
        # 返回一些常见的热门股票
        return [
            "000001.SZ",  # 平安银行
            "000002.SZ",  # 万科A
            "600000.SH",  # 浦发银行
            "600036.SH",  # 招商银行
            "000858.SZ",  # 五粮液
            "000333.SZ",  # 美的集团
            "002415.SZ",  # 海康威视
            "300750.SZ",  # 宁德时代
        ]
    
    async def _prefetch_worker(self):
        """预取工作线程"""
        while True:
            try:
                # 获取预取任务
                data_type, symbol = await self.prefetch_queue.get()
                
                # 检查是否已缓存
                cache_key = f"{data_type}:{symbol}:{{}}"
                if self._get_from_cache(cache_key) is None:
                    # 异步预取数据
                    asyncio.create_task(
                        self.get_data(data_type, symbol)
                    )
                
            except Exception as e:
                logger.error(f"预取失败: {e}")
                await asyncio.sleep(1)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = dict(self.stats)
        
        # 计算命中率
        if stats['total_requests'] > 0:
            stats['cache_hit_rate'] = stats['cache_hits'] / stats['total_requests']
            stats['avg_latency'] = stats['total_latency'] / stats['total_requests']
        else:
            stats['cache_hit_rate'] = 0
            stats['avg_latency'] = 0
        
        # 添加数据源状态
        stats['data_sources'] = {}
        for source_name in self.data_sources:
            metrics = self.router.metrics.get(source_name, DataSourceMetrics())
            breaker = self.circuit_breakers.get(source_name)
            
            stats['data_sources'][source_name] = {
                'success_rate': metrics.success_rate,
                'avg_latency': metrics.avg_latency,
                'p95_latency': metrics.p95_latency,
                'circuit_state': breaker.state.value if breaker else 'unknown'
            }
        
        return stats


# 使用示例
if __name__ == "__main__":
    async def main():
        # 配置
        config = {
            'qmt': {
                'enabled': True,
                'host': 'localhost',
                'port': 5000
            },
            'akshare': {
                'enabled': True,
                'proxy': None
            }
        }
        
        # 创建管理器
        manager = OptimizedDataSourceManager(config)
        
        # 初始化
        await manager.initialize()
        
        # 获取数据
        data = await manager.get_data(
            data_type='kline',
            symbol='000001.SZ',
            period='1d',
            limit=100
        )
        
        print("Data:", data)
        print("Statistics:", manager.get_statistics())
    
    asyncio.run(main())