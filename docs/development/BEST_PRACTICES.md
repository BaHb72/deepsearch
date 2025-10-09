# DeepSearch 最佳实践指南

## 1. 异步编程最佳实践

### 1.1 并发数据获取

**✅ 推荐：使用 asyncio.gather 并发获取**
```python
async def fetch_multiple_stocks(symbols: List[str]) -> List[Dict]:
    """并发获取多个股票数据"""
    tasks = [fetch_stock_data(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 过滤掉错误结果
    return [r for r in results if not isinstance(r, Exception)]
```

**❌ 避免：串行获取数据**
```python
async def fetch_multiple_stocks_bad(symbols: List[str]) -> List[Dict]:
    """低效的串行获取"""
    results = []
    for symbol in symbols:
        try:
            data = await fetch_stock_data(symbol)
            results.append(data)
        except:
            pass
    return results
```

### 1.2 超时控制

**✅ 推荐：设置合理的超时**
```python
async def fetch_with_timeout(symbol: str, timeout: float = 5.0):
    """带超时控制的数据获取"""
    try:
        return await asyncio.wait_for(
            fetch_stock_data(symbol),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning(f"获取 {symbol} 超时")
        return None
```

### 1.3 任务取消处理

**✅ 推荐：优雅处理任务取消**
```python
async def long_running_task():
    """长时间运行的任务"""
    try:
        while True:
            # 检查是否被取消
            if asyncio.current_task().cancelled():
                break
            
            await do_work()
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        # 清理资源
        await cleanup()
        raise  # 重新抛出以通知调用者
```

## 2. 缓存使用最佳实践

### 2.1 缓存键设计

**✅ 推荐：使用结构化的缓存键**
```python
def make_cache_key(data_type: str, symbol: str, **params) -> str:
    """生成结构化的缓存键"""
    # 使用冒号分隔不同部分
    key_parts = [data_type, symbol]
    
    # 添加排序后的参数
    for k, v in sorted(params.items()):
        key_parts.append(f"{k}={v}")
    
    return ":".join(key_parts)

# 使用示例
key = make_cache_key("kline", "000001.SZ", period="1d", limit=100)
# 结果: "kline:000001.SZ:limit=100:period=1d"
```

### 2.2 缓存装饰器

**✅ 推荐：使用装饰器简化缓存逻辑**
```python
from functools import wraps

def cached(ttl: int = 300, key_prefix: str = ""):
    """缓存装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # 尝试从缓存获取
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # 调用原函数
            result = await func(*args, **kwargs)
            
            # 存入缓存
            await cache.put(cache_key, result, ttl=ttl)
            
            return result
        return wrapper
    return decorator

# 使用示例
@cached(ttl=600, key_prefix="stock_info")
async def get_stock_info(symbol: str):
    return await fetch_from_api(symbol)
```

### 2.3 缓存预热

**✅ 推荐：在系统启动时预热关键数据**
```python
async def warmup_cache():
    """缓存预热"""
    # 获取热门股票列表
    hot_stocks = await get_hot_stocks()
    
    # 批量预热
    batch_size = 10
    for i in range(0, len(hot_stocks), batch_size):
        batch = hot_stocks[i:i+batch_size]
        tasks = [
            cache_stock_data(symbol)
            for symbol in batch
        ]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info(f"缓存预热完成，共预热 {len(hot_stocks)} 只股票")
```

## 3. 错误处理最佳实践

### 3.1 使用上下文管理器

**✅ 推荐：统一的错误处理**
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def error_handler(component: str, operation: str, fallback=None):
    """统一的错误处理上下文管理器"""
    try:
        yield
    except asyncio.CancelledError:
        logger.info(f"{component}.{operation} 被取消")
        raise
    except TimeoutError:
        logger.warning(f"{component}.{operation} 超时")
        return fallback
    except Exception as e:
        logger.error(f"{component}.{operation} 失败: {e}")
        return fallback

# 使用示例
async with error_handler("DataFetcher", "fetch_kline", fallback=[]):
    data = await risky_operation()
    return data
```

### 3.2 重试机制

**✅ 推荐：实现指数退避重试**
```python
async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0
):
    """指数退避重试"""
    delay = initial_delay
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            
            if attempt < max_retries - 1:
                # 计算下次延迟
                delay = min(delay * exponential_base, max_delay)
                
                # 添加抖动避免惊群效应
                jitter = random.uniform(0, delay * 0.1)
                
                logger.debug(f"第 {attempt + 1} 次失败，{delay:.1f}秒后重试")
                await asyncio.sleep(delay + jitter)
    
    raise last_exception
```

## 4. 事件驱动编程最佳实践

### 4.1 事件处理器设计

**✅ 推荐：保持处理器简单且快速**
```python
class OrderHandler:
    """订单事件处理器"""
    
    def __init__(self, order_service):
        self.order_service = order_service
        # 使用队列解耦处理
        self.processing_queue = asyncio.Queue()
        
    async def handle_order_event(self, event: Event):
        """快速接收事件，异步处理"""
        # 快速验证
        if not self._validate_event(event):
            return
        
        # 放入处理队列，立即返回
        await self.processing_queue.put(event)
    
    async def _process_worker(self):
        """后台处理工作线程"""
        while True:
            event = await self.processing_queue.get()
            try:
                await self._process_order(event)
            except Exception as e:
                logger.error(f"处理订单失败: {e}")
```

### 4.2 批处理优化

**✅ 推荐：对高频事件使用批处理**
```python
class BatchEventProcessor:
    """批处理事件处理器"""
    
    def __init__(self, batch_size: int = 100, batch_timeout: float = 0.1):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.batch = []
        self.last_flush = time.time()
        
    async def add_event(self, event: Event):
        """添加事件到批次"""
        self.batch.append(event)
        
        # 检查是否需要刷新
        if len(self.batch) >= self.batch_size:
            await self.flush()
        elif time.time() - self.last_flush > self.batch_timeout:
            await self.flush()
    
    async def flush(self):
        """刷新批次"""
        if not self.batch:
            return
        
        # 批量处理
        await self.process_batch(self.batch)
        
        # 清空批次
        self.batch = []
        self.last_flush = time.time()
    
    async def process_batch(self, events: List[Event]):
        """批量处理事件"""
        # 批量写入数据库
        await db.insert_many(events)
```

## 5. 数据库操作最佳实践

### 5.1 连接池管理

**✅ 推荐：使用连接池避免频繁创建连接**
```python
class DatabasePool:
    """数据库连接池"""
    
    def __init__(self, min_size: int = 10, max_size: int = 50):
        self.pool = None
        self.min_size = min_size
        self.max_size = max_size
        
    async def initialize(self):
        """初始化连接池"""
        self.pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=self.min_size,
            max_size=self.max_size,
            max_queries=50000,
            max_inactive_connection_lifetime=300,
            command_timeout=60
        )
    
    @asynccontextmanager
    async def acquire(self):
        """获取连接"""
        async with self.pool.acquire() as connection:
            yield connection

# 使用示例
async with db_pool.acquire() as conn:
    result = await conn.fetch("SELECT * FROM stocks WHERE symbol = $1", symbol)
```

### 5.2 批量操作

**✅ 推荐：使用批量操作减少往返次数**
```python
async def batch_insert_klines(klines: List[Dict]):
    """批量插入K线数据"""
    async with db_pool.acquire() as conn:
        # 使用 COPY 命令批量插入（PostgreSQL）
        await conn.copy_records_to_table(
            'kline_data',
            records=[(k['symbol'], k['date'], k['open'], k['close']) 
                    for k in klines],
            columns=['symbol', 'date', 'open', 'close']
        )
```

## 6. 监控和日志最佳实践

### 6.1 结构化日志

**✅ 推荐：使用结构化日志便于分析**
```python
from loguru import logger

# 配置结构化日志
logger.add(
    "logs/app_{time}.log",
    format="{time} | {level} | {name}:{function}:{line} | {extra} | {message}",
    serialize=True,  # JSON格式
    rotation="100 MB",
    retention="7 days"
)

# 使用上下文信息
logger.bind(
    component="DataFetcher",
    symbol=symbol,
    user_id=user_id
).info("开始获取数据")
```

### 6.2 性能监控

**✅ 推荐：监控关键性能指标**
```python
from functools import wraps
import time

def monitor_performance(metric_name: str):
    """性能监控装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            
            try:
                result = await func(*args, **kwargs)
                
                # 记录成功指标
                duration = time.perf_counter() - start_time
                metrics.record(f"{metric_name}.duration", duration)
                metrics.increment(f"{metric_name}.success")
                
                return result
                
            except Exception as e:
                # 记录失败指标
                metrics.increment(f"{metric_name}.failure")
                raise
                
        return wrapper
    return decorator

# 使用示例
@monitor_performance("fetch_kline")
async def fetch_kline_data(symbol: str):
    return await api.get_kline(symbol)
```

## 7. 资源管理最佳实践

### 7.1 内存管理

**✅ 推荐：定期清理大对象**
```python
import gc
import weakref

class DataManager:
    """数据管理器（带内存管理）"""
    
    def __init__(self, max_cache_size: int = 1000):
        # 使用弱引用避免内存泄漏
        self.cache = weakref.WeakValueDictionary()
        self.max_cache_size = max_cache_size
        
    async def cleanup_periodically(self):
        """定期清理"""
        while True:
            await asyncio.sleep(300)  # 5分钟
            
            # 手动触发垃圾回收
            gc.collect()
            
            # 清理过期数据
            self._cleanup_expired()
            
            logger.info(f"内存清理完成，当前缓存大小: {len(self.cache)}")
```

### 7.2 资源限制

**✅ 推荐：使用信号量限制并发**
```python
class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_concurrent: int = 10, max_per_second: int = 100):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limiter = AsyncLimiter(max_per_second, 1.0)
        
    async def execute(self, func: Callable, *args, **kwargs):
        """限流执行"""
        async with self.semaphore:  # 限制并发
            async with self.rate_limiter:  # 限制速率
                return await func(*args, **kwargs)

# 使用示例
limiter = RateLimiter(max_concurrent=5, max_per_second=10)

async def fetch_all_stocks(symbols: List[str]):
    tasks = [
        limiter.execute(fetch_stock, symbol)
        for symbol in symbols
    ]
    return await asyncio.gather(*tasks)
```

## 8. 测试最佳实践

### 8.1 异步测试

**✅ 推荐：使用 pytest-asyncio**
```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_fetch_data():
    """测试异步数据获取"""
    # 准备测试数据
    mock_data = {"symbol": "000001.SZ", "price": 10.5}
    
    # Mock 外部调用
    with patch('api.fetch') as mock_fetch:
        mock_fetch.return_value = mock_data
        
        # 执行测试
        result = await fetch_stock_data("000001.SZ")
        
        # 验证结果
        assert result == mock_data
        mock_fetch.assert_called_once_with("000001.SZ")
```

### 8.2 性能测试

**✅ 推荐：基准测试关键路径**
```python
import timeit
import asyncio

async def benchmark_event_engine():
    """基准测试事件引擎"""
    engine = EventEngine()
    events_count = 10000
    
    # 测量吞吐量
    start = time.perf_counter()
    
    for i in range(events_count):
        engine.put(Event("TEST", {"id": i}))
    
    # 等待处理完成
    await engine.wait_for_empty()
    
    duration = time.perf_counter() - start
    throughput = events_count / duration
    
    print(f"吞吐量: {throughput:.0f} events/sec")
    print(f"平均延迟: {duration / events_count * 1000:.2f} ms")
```

## 总结

遵循这些最佳实践可以：

1. **提高性能** - 通过并发、缓存和批处理优化
2. **提高可靠性** - 通过错误处理和重试机制
3. **提高可维护性** - 通过清晰的代码结构和监控
4. **降低资源消耗** - 通过合理的资源管理

记住：
- 始终测量，不要猜测
- 先保证正确性，再优化性能
- 保持代码简单清晰
- 文档化你的设计决策
## 9. 文档更新清单

- **更新概览索引**：新增或迁移文档后，记得同步维护 `docs/overview/document_index.md` 与 `docs/modules/README.md`，确保团队能快速定位内容。
- **API 文档生成**：涉及后端接口的改动需执行 `python tools/generate_api_documentation.py`，同时检查 `docs/api/` 是否生成新版本。
- **数据源文档**：调整数据源行为时，补充 `docs/datasources/` 下的对应说明，并在 PR 描述写明测试与降级策略。
