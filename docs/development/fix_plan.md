# DeepSearch 修复计划

## 计划概述

基于 2026-01-13 的后端启动测试和代码扫描,本文档提供分阶段的修复路线图。

**总体目标**: 在 3 周内完成所有高中优先级问题修复,消除技术债,提升系统稳定性和性能。

**当前状态**:

- 后端启动: ✅ 成功
- 阻塞性错误 (P0): 0
- 高优先级问题 (P1): 4
- 中优先级问题 (P2): 7
- 低优先级问题 (P3): 2

---

## 修复阶段划分

### Phase 1: P1 错误修复 (本周完成)

**目标**: 修复所有高优先级问题,确保核心功能完整可用

**预计时间**: 7-10 小时 (分 5 个工作日完成)

**成功标准**:

- MiniQMT 提供者成功注册并可用
- 实时数据源连接正常工作
- 全市场涨跌幅榜功能完整
- 数据源可用性缓存生效

### Phase 2: P2 错误修复 (下周完成)

**目标**: 完善中优先级功能,提升系统性能和用户体验

**预计时间**: 5-7 小时 (分 4 个工作日完成)

**成功标准**:

- 配置警告消失
- DataProxy 正确初始化
- 策略引擎数据准确
- 筛选服务性能优化

### Phase 3: P3 错误修复 (第三周,可选)

**目标**: 清理技术债,优化代码架构

**预计时间**: 3.5-4.5 小时 (分 2 个工作日完成)

**成功标准**:

- 所有 TODO/FIXME 标记清零
- 代码架构更清晰
- 性能进一步提升

---

## Phase 1: P1 错误修复 (7-10 小时)

### 任务 1.1: 修复 MiniQMT 模块加载失败

**优先级**: P1 (高) - 立即执行

**问题描述**:

```
[ERROR] 加载模块失败 core.infrastructure.providers.implementations.qmt.miniqmt:
No module named 'core.infrastructure.providers.implementations.qmt.dask_plugin'
```

**文件**: `packages/core/infrastructure/providers/implementations/qmt/miniqmt.py`

**修复步骤**:

1. **调查根本原因** (15 分钟)

   ```bash
   # 搜索 git 历史中的 dask_plugin.py
   git log --all --full-history --oneline -- "**/dask_plugin.py"

   # 查看最近删除记录
   git log --diff-filter=D --summary | grep dask_plugin

   # 查看 miniqmt.py 的导入依赖
   rg "dask_plugin" packages/core/infrastructure/providers/implementations/qmt/
   ```

2. **确定修复方案** (15 分钟)
   - 选项 A: 如果 `dask_plugin.py` 在历史中存在,检查是否被重命名
   - 选项 B: 如果模块已删除,分析 `miniqmt.py` 是否仍需要该依赖
   - 选项 C: 如果依赖已移除,更新 `miniqmt.py` 移除相关导入

3. **实施修复** (30-60 分钟)
   - 根据选项 A/B/C 实施相应修复
   - 可能需要重新实现 Worker Plugin 逻辑
   - 或者移除对 Dask Plugin 的依赖,使用其他方式

4. **验证修复** (15 分钟)

   ```bash
   # 编译验证
   python -m py_compile packages/core/infrastructure/providers/implementations/qmt/miniqmt.py

   # 启动测试
   uv run deepsearch run dev --mode engine --no-frontend --log-level DEBUG

   # 检查日志中 MiniQMT 提供者是否成功注册
   ```

5. **编写测试** (15 分钟)

   ```python
   # tests/unit/providers/test_miniqmt_provider.py
   def test_miniqmt_provider_registration():
       """测试 MiniQMT 提供者能够成功注册"""
       ...
   ```

**预计时间**: 1-2 小时

**验证标准**:

- [ ] 启动时无 MiniQMT 模块加载错误
- [ ] `miniqmt` 提供者出现在注册日志中
- [ ] 单元测试通过

---

### 任务 1.2: 实现实时数据源连接

**优先级**: P1 (高)

**问题描述**:

- 回测数据源缺少与实时数据的连接
- `custom_data_feed.py:131` 标记为 TODO

**文件**: `packages/core/backtest/data/custom_data_feed.py`

**修复步骤**:

1. **分析数据源接口** (30 分钟)

   ```python
   # 阅读 CustomDataFeed 类定义
   # 确定实时数据源的接口规范
   # 确定数据流格式 (OHLCV, Tick 等)
   ```

2. **设计实时连接方案** (30 分钟)
   - 选择数据源: AmazingData WebSocket / MiniQMT 实时接口
   - 设计数据流订阅机制
   - 设计缓冲队列 (处理数据流速率)
   - 设计错误处理和重连逻辑

3. **实现数据连接** (60-90 分钟)

   ```python
   class CustomDataFeed:
       async def connect_live_source(self, symbols: List[str]):
           """连接实时数据源"""
           # 1. 选择数据提供者 (AmazingData/MiniQMT)
           provider = self.provider_registry.get("amazingdata")

           # 2. 订阅实时数据流
           await provider.subscribe_realtime(symbols)

           # 3. 处理数据流
           async for tick in provider.stream():
               self.on_tick(tick)
   ```

4. **编写测试** (30 分钟)

   ```python
   async def test_live_data_connection():
       """测试实时数据连接"""
       feed = CustomDataFeed()
       await feed.connect_live_source(["000001.SZ"])
       # 验证数据流接收
   ```

**预计时间**: 2-3 小时

**验证标准**:

- [ ] 实时数据流成功订阅
- [ ] Tick 数据正确接收和处理
- [ ] 错误处理和重连机制工作正常
- [ ] 单元测试和集成测试通过

---

### 任务 1.3: 实现全市场行情获取和排序

**优先级**: P1 (高)

**问题描述**:

- 涨跌幅榜功能未实现真实的全市场数据
- `top_gainers.py:33` 标记为 TODO

**文件**: `packages/core/application/services/aggregation/impl/top_gainers.py`

**修复步骤**:

1. **确定市场范围** (15 分钟)
   - A股: 上证 + 深证 + 创业板 + 科创板
   - 港股 (可选)
   - 美股 (可选)
   - 确定股票总数 (约 5000 只 A股)

2. **设计批量获取方案** (15 分钟)
   - 方案 A: 全量获取 (5000 只股票,可能较慢)
   - 方案 B: 分批获取 (每批 500 只,并发请求)
   - 方案 C: 从缓存获取 (市场数据预缓存)

3. **实现行情获取和排序** (30-60 分钟)

   ```python
   class TopGainersService:
       async def get_top_gainers(self, limit: int = 20):
           """获取涨幅榜"""
           # 1. 获取全市场股票列表
           symbols = await self.get_all_symbols()

           # 2. 批量获取实时行情
           quotes = await self.batch_get_quotes(symbols)

           # 3. 计算涨跌幅并排序
           sorted_quotes = sorted(
               quotes,
               key=lambda q: q.change_percent,
               reverse=True
           )

           # 4. 返回 Top N
           return sorted_quotes[:limit]
   ```

4. **添加 Redis 缓存** (15 分钟)

   ```python
   # 缓存 1-5 分钟,减少数据源压力
   @cached(ttl=60)
   async def get_top_gainers(self, limit: int = 20):
       ...
   ```

5. **性能优化** (15 分钟)
   - 并发批量请求 (asyncio.gather)
   - 限制并发数 (避免打爆数据源)
   - 监控响应时间

6. **编写测试** (15 分钟)

   ```python
   async def test_top_gainers():
       """测试涨幅榜功能"""
       service = TopGainersService()
       gainers = await service.get_top_gainers(20)
       assert len(gainers) == 20
       assert gainers[0].change_percent >= gainers[1].change_percent
   ```

**预计时间**: 1-2 小时

**验证标准**:

- [ ] 全市场行情获取成功
- [ ] 涨跌幅排序正确
- [ ] 缓存生效,性能满足要求 (< 2 秒)
- [ ] 单元测试和性能测试通过

---

### 任务 1.4: 实现数据源可用性缓存

**优先级**: P1 (高)

**问题描述**:

- 数据源路由器缺少可用性缓存
- `router.py:201` 标记为 TODO

**文件**: `packages/core/domain/data_proxy/router.py`

**修复步骤**:

1. **设计可用性评分机制** (30 分钟)

   ```python
   class DataSourceAvailability:
       provider_name: str
       score: float  # 0.0-1.0
       response_time_ms: float
       success_rate: float  # 最近 100 次请求成功率
       last_check: datetime
       status: Literal["healthy", "degraded", "down"]
   ```

2. **实现评分计算** (30 分钟)

   ```python
   def calculate_availability_score(self, provider: str) -> float:
       """计算数据源可用性评分"""
       # 权重: 响应时间 40% + 成功率 60%
       rt_score = 1.0 - min(response_time / 1000, 1.0)  # 1秒内满分
       success_score = success_rate
       return rt_score * 0.4 + success_score * 0.6
   ```

3. **实现 Redis 缓存** (30 分钟)

   ```python
   async def get_availability(self, provider: str) -> DataSourceAvailability:
       """获取可用性 (带缓存)"""
       # 1. 尝试从 Redis 获取
       cache_key = f"availability:{provider}"
       cached = await self.redis.get(cache_key)
       if cached:
           return DataSourceAvailability.parse_raw(cached)

       # 2. 重新计算
       availability = await self.check_availability(provider)

       # 3. 缓存 60 秒
       await self.redis.setex(cache_key, 60, availability.json())
       return availability
   ```

4. **添加后台刷新任务** (30-60 分钟)

   ```python
   async def refresh_availability_loop(self):
       """定期刷新可用性评分"""
       while True:
           for provider in self.providers:
               availability = await self.check_availability(provider)
               await self.update_cache(provider, availability)
           await asyncio.sleep(60)  # 每分钟刷新
   ```

5. **实现 Circuit Breaker** (30 分钟)

   ```python
   class CircuitBreaker:
       """熔断器"""
       def __init__(self, threshold: float = 0.3):
           self.threshold = threshold

       async def call(self, provider: str, func):
           availability = await self.get_availability(provider)
           if availability.score < self.threshold:
               raise CircuitOpenError(f"{provider} is down")
           return await func()
   ```

6. **编写测试** (15 分钟)

   ```python
   async def test_availability_cache():
       """测试可用性缓存"""
       router = DataSourceRouter()

       # 第一次请求,应该计算
       avail1 = await router.get_availability("amazingdata")

       # 第二次请求,应该从缓存获取
       avail2 = await router.get_availability("amazingdata")

       assert avail1.score == avail2.score
   ```

**预计时间**: 2-3 小时

**验证标准**:

- [ ] 可用性评分正确计算
- [ ] Redis 缓存生效
- [ ] 后台刷新任务正常运行
- [ ] Circuit Breaker 正确熔断不可用数据源
- [ ] 单元测试和集成测试通过

---

## Phase 2: P2 错误修复 (5-7 小时)

### 任务 2.1: 优化 AmazingData 配置

**优先级**: P2 (中) - 最快修复

**问题描述**:

```
[WARNING] AmazingData implementation_mode=process 已废弃,自动切换到 optimized
```

**修复步骤**:

1. **查找配置文件** (2 分钟)

   ```bash
   rg "implementation_mode.*process" packages/core/config/
   ```

2. **修改配置** (2 分钟)

   ```yaml
   # settings.dev.yaml 或 data_sources.yaml
   amazingdata:
     # 删除或修改以下行
     # implementation_mode: process
     implementation_mode: optimized  # 或直接删除,使用默认值
   ```

3. **验证** (1 分钟)

   ```bash
   uv run deepsearch run dev --mode engine --log-level DEBUG | grep "implementation_mode"
   # 应该不再看到警告
   ```

**预计时间**: 5 分钟

**验证标准**:

- [ ] 启动时无 implementation_mode 警告

---

### 任务 2.2: 补充 DataProxy 初始化逻辑

**优先级**: P2 (中)

**问题描述**:

- `proxy.py:83` 初始化逻辑标记为 TODO

**文件**: `packages/core/domain/data_proxy/proxy.py`

**修复步骤**:

1. **分析 DataProxy 职责** (15 分钟)
   - 阅读 `DataProxy` 类定义
   - 确定需要初始化的组件 (Router, Cache, Providers 等)

2. **补充初始化逻辑** (30 分钟)

   ```python
   class DataProxy:
       def __init__(self, config: Config):
           # TODO: 初始化逻辑
           self.config = config
           self.router = DataSourceRouter(config)
           self.cache = CacheManager(config)
           self.providers = ProviderRegistry()
           self._initialized = False

       async def initialize(self):
           """异步初始化"""
           if self._initialized:
               return

           await self.router.initialize()
           await self.cache.initialize()
           await self.providers.load_all()
           self._initialized = True
   ```

3. **添加初始化状态检查** (15 分钟)

   ```python
   def _ensure_initialized(self):
       """确保已初始化"""
       if not self._initialized:
           raise RuntimeError("DataProxy not initialized. Call initialize() first.")
   ```

4. **编写测试** (15 分钟)

   ```python
   async def test_dataproxy_initialization():
       """测试 DataProxy 初始化"""
       proxy = DataProxy(config)
       assert not proxy._initialized

       await proxy.initialize()
       assert proxy._initialized
   ```

**预计时间**: 30 分钟 - 1 小时

**验证标准**:

- [ ] DataProxy 正确初始化所有依赖
- [ ] 初始化状态检查正常工作
- [ ] 单元测试通过

---

### 任务 2.3: 实现策略引擎开盘价获取

**优先级**: P2 (中)

**问题描述**:

- `engine.py:328` 使用硬编码的 `open_price=0`

**文件**: `packages/core/strategies/ttrading/engine.py`

**修复步骤**:

1. **实现开盘价获取** (15 分钟)

   ```python
   async def get_open_price(self, symbol: str) -> float:
       """获取当日开盘价"""
       # 1. 从缓存获取
       cache_key = f"open_price:{symbol}:{datetime.now().date()}"
       cached = await self.redis.get(cache_key)
       if cached:
           return float(cached)

       # 2. 从数据源获取
       quote = await self.data_feed.get_quote(symbol)
       open_price = quote.open

       # 3. 缓存全天 (开盘价不变)
       await self.redis.setex(cache_key, 86400, str(open_price))
       return open_price
   ```

2. **修改引擎代码** (5 分钟)

   ```python
   # Line 328
   open_price = await self.get_open_price(symbol)  # 替代硬编码的 0
   ```

3. **处理开盘前时段** (10 分钟)

   ```python
   async def get_open_price(self, symbol: str) -> float:
       """获取开盘价"""
       now = datetime.now().time()
       market_open = time(9, 30)

       if now < market_open:
           # 开盘前使用昨日收盘价
           return await self.get_prev_close(symbol)
       else:
           # 开盘后使用当日开盘价
           return await self._get_today_open(symbol)
   ```

4. **编写测试** (10 分钟)

   ```python
   async def test_open_price_retrieval():
       """测试开盘价获取"""
       engine = TradingEngine()
       price = await engine.get_open_price("000001.SZ")
       assert price > 0
   ```

**预计时间**: 30 分钟

**验证标准**:

- [ ] 开盘价正确获取
- [ ] 缓存生效
- [ ] 开盘前时段正确处理
- [ ] 策略计算准确性提升
- [ ] 单元测试通过

---

### 任务 2.4: 实现策略准确率追踪

**优先级**: P2 (中)

**问题描述**:

- `engine.py:357` 准确率追踪标记为 TODO

**文件**: `packages/core/strategies/ttrading/engine.py`

**修复步骤**:

1. **设计准确率数据模型** (15 分钟)

   ```python
   class StrategyAccuracy:
       strategy_name: str
       total_signals: int
       successful_signals: int  # 达到止盈
       failed_signals: int  # 触发止损
       pending_signals: int  # 未平仓
       win_rate: float  # 成功率
       avg_profit: float  # 平均收益率
       avg_loss: float  # 平均亏损率
       profit_loss_ratio: float  # 盈亏比
       last_updated: datetime
   ```

2. **实现准确率计算** (30 分钟)

   ```python
   async def update_accuracy(self, signal: TradingSignal, result: TradingResult):
       """更新准确率统计"""
       key = f"accuracy:{signal.strategy_name}"

       # 1. 获取当前统计
       stats = await self.get_accuracy_stats(signal.strategy_name)

       # 2. 更新统计
       stats.total_signals += 1
       if result.profit > 0:
           stats.successful_signals += 1
           stats.avg_profit = (
               stats.avg_profit * (stats.successful_signals - 1) + result.profit_rate
           ) / stats.successful_signals
       else:
           stats.failed_signals += 1
           stats.avg_loss = (
               stats.avg_loss * (stats.failed_signals - 1) + abs(result.profit_rate)
           ) / stats.failed_signals

       # 3. 计算衍生指标
       stats.win_rate = stats.successful_signals / stats.total_signals
       stats.profit_loss_ratio = stats.avg_profit / stats.avg_loss if stats.avg_loss > 0 else 0

       # 4. 保存到数据库
       await self.save_accuracy_stats(stats)
   ```

3. **添加持久化存储** (15 分钟)

   ```python
   # 使用 PostgreSQL 存储历史统计
   # 使用 Redis 缓存最新统计
   ```

4. **添加查询接口** (15 分钟)

   ```python
   async def get_strategy_accuracy(
       self,
       strategy_name: str,
       date_range: Optional[Tuple[date, date]] = None
   ) -> StrategyAccuracy:
       """查询策略准确率"""
       ...
   ```

5. **编写测试** (15 分钟)

   ```python
   async def test_accuracy_tracking():
       """测试准确率追踪"""
       engine = TradingEngine()

       # 模拟交易结果
       signal = TradingSignal(strategy_name="test")
       result = TradingResult(profit=100, profit_rate=0.05)

       await engine.update_accuracy(signal, result)

       # 验证统计
       stats = await engine.get_strategy_accuracy("test")
       assert stats.win_rate == 1.0
   ```

**预计时间**: 1-2 小时

**验证标准**:

- [ ] 准确率正确计算
- [ ] 数据持久化存储
- [ ] 查询接口正常工作
- [ ] 单元测试通过

---

### 任务 2.5: 实现筛选缓存和配置

**优先级**: P2 (中)

**问题描述**:

- `screening_service.py:403` 缓存未实现
- `screener.py:115` 自定义权重未实现
- `screener.py:122` 配置来源硬编码

**文件**:

- `packages/core/strategies/services/screening_service.py`
- `apps/api/api/endpoints/strategy_center/screener.py`

**修复步骤**:

1. **实现筛选结果缓存** (30 分钟)

   ```python
   async def screen_stocks(self, criteria: ScreeningCriteria) -> List[Stock]:
       """筛选股票 (带缓存)"""
       # 1. 生成缓存键 (包含筛选条件)
       cache_key = f"screening:{criteria.hash()}"

       # 2. 尝试从 Redis 获取
       cached = await self.redis.get(cache_key)
       if cached:
           return [Stock.parse_raw(s) for s in json.loads(cached)]

       # 3. 重新筛选
       results = await self._do_screening(criteria)

       # 4. 缓存 5-15 分钟 (根据市场开闭盘调整)
       ttl = 300 if self.is_market_open() else 900
       await self.redis.setex(cache_key, ttl, json.dumps([s.json() for s in results]))

       return results
   ```

2. **实现自定义权重支持** (30 分钟)

   ```python
   class ScreeningCriteria:
       indicators: List[str]  # ["pe_ratio", "roe", "revenue_growth"]
       weights: Dict[str, float]  # {"pe_ratio": 0.3, "roe": 0.4, "revenue_growth": 0.3}

       def validate_weights(self):
           """验证权重总和为 1"""
           total = sum(self.weights.values())
           if not (0.99 <= total <= 1.01):  # 允许浮点误差
               raise ValueError(f"Weights sum must be 1.0, got {total}")

   def calculate_score(self, stock: Stock, criteria: ScreeningCriteria) -> float:
       """计算加权评分"""
       score = 0.0
       for indicator, weight in criteria.weights.items():
           value = getattr(stock, indicator)
           normalized = self.normalize(indicator, value)
           score += normalized * weight
       return score
   ```

3. **从配置文件读取配置** (30 分钟)

   ```yaml
   # config/screening_presets.yaml
   presets:
     value_investing:
       indicators:
         - pe_ratio
         - pb_ratio
         - dividend_yield
       weights:
         pe_ratio: 0.4
         pb_ratio: 0.3
         dividend_yield: 0.3

     growth_investing:
       indicators:
         - revenue_growth
         - profit_growth
         - roe
       weights:
         revenue_growth: 0.4
         profit_growth: 0.3
         roe: 0.3
   ```

   ```python
   class ScreeningConfig:
       @classmethod
       def load_presets(cls) -> Dict[str, ScreeningCriteria]:
           """从配置文件加载预设"""
           with open("config/screening_presets.yaml") as f:
               data = yaml.safe_load(f)
           return {
               name: ScreeningCriteria(**preset)
               for name, preset in data["presets"].items()
           }
   ```

4. **添加缓存失效逻辑** (30 分钟)

   ```python
   async def invalidate_screening_cache(self):
       """市场数据更新时清除缓存"""
       pattern = "screening:*"
       keys = await self.redis.keys(pattern)
       if keys:
           await self.redis.delete(*keys)
   ```

5. **编写测试** (30 分钟)

   ```python
   async def test_screening_cache():
       """测试筛选缓存"""
       service = ScreeningService()
       criteria = ScreeningCriteria(...)

       # 第一次请求
       result1 = await service.screen_stocks(criteria)

       # 第二次请求,应该从缓存获取
       result2 = await service.screen_stocks(criteria)

       assert result1 == result2

   def test_custom_weights():
       """测试自定义权重"""
       criteria = ScreeningCriteria(
           indicators=["pe", "roe"],
           weights={"pe": 0.6, "roe": 0.4}
       )
       criteria.validate_weights()  # 不应抛出异常
   ```

**预计时间**: 2.5 小时

**验证标准**:

- [ ] 筛选结果缓存生效
- [ ] 自定义权重正确应用
- [ ] 配置从文件读取
- [ ] 缓存失效逻辑正常工作
- [ ] 单元测试和集成测试通过

---

## Phase 3: P3 错误修复 (3.5-4.5 小时,可选)

### 任务 3.1: 补全 MarketSnapshot 字段

**优先级**: P3 (低)

**问题描述**:

- `snapshot_cache_adapter.py:76` MarketSnapshot 字段可能不完整

**文件**: `packages/core/adapters/market_data/snapshot_cache_adapter.py`

**修复步骤**:

1. **查看 MarketSnapshot 模型定义** (15 分钟)

   ```python
   # 确定所有必需字段
   class MarketSnapshot:
       symbol: str
       timestamp: datetime
       open: float
       high: float
       low: float
       close: float
       volume: int
       amount: float
       # ... 可能缺少的字段
   ```

2. **补全字段构造** (15 分钟)

   ```python
   def build_snapshot(self, raw_data) -> MarketSnapshot:
       """构造 MarketSnapshot"""
       return MarketSnapshot(
           symbol=raw_data["symbol"],
           timestamp=datetime.fromisoformat(raw_data["time"]),
           open=raw_data["open"],
           high=raw_data["high"],
           low=raw_data["low"],
           close=raw_data["close"],
           volume=raw_data["volume"],
           amount=raw_data["amount"],
           # 补全缺失字段
           turnover_rate=raw_data.get("turnover_rate", 0.0),
           pe_ratio=raw_data.get("pe", 0.0),
           ...
       )
   ```

3. **编写测试** (10 分钟)

   ```python
   def test_snapshot_completeness():
       """测试 MarketSnapshot 字段完整性"""
       adapter = SnapshotCacheAdapter()
       snapshot = adapter.build_snapshot(mock_data)

       # 验证所有必需字段存在
       assert snapshot.symbol
       assert snapshot.timestamp
       assert snapshot.open > 0
       ...
   ```

**预计时间**: 30 分钟

**验证标准**:

- [ ] 所有必需字段存在
- [ ] 字段值正确
- [ ] 单元测试通过

---

### 任务 3.2: 优化 AmazingDataActor 调用

**优先级**: P3 (低) - 技术债

**问题描述**:

- `amazingdata_extended.py:253` 建议统一为 `AmazingDataActor.call()` 调用

**文件**: `packages/core/infrastructure/providers/implementations/amazingdata/amazingdata_extended.py`

**修复步骤**:

1. **分析当前调用方式** (30 分钟)
   - 查找所有直接调用 AmazingData SDK 的位置
   - 分析与 `AmazingDataActor.call()` 的差异
   - 评估性能影响

2. **设计统一调用接口** (30 分钟)

   ```python
   class AmazingDataActor:
       async def call(self, method: str, **kwargs) -> Any:
           """统一远程调用接口"""
           # 1. 验证方法存在
           if not hasattr(self.sdk, method):
               raise ValueError(f"Method {method} not found")

           # 2. 执行调用
           result = await getattr(self.sdk, method)(**kwargs)

           # 3. 错误处理和重试
           ...

           return result
   ```

3. **迁移现有调用** (60-120 分钟)

   ```python
   # 旧方式
   result = self.sdk.get_kline(symbol="000001.SZ", period="1d")

   # 新方式
   result = await self.actor.call("get_kline", symbol="000001.SZ", period="1d")
   ```

4. **性能测试** (30 分钟)
   - 对比新旧方式的性能
   - 确保无性能退化

5. **删除旧调用方式** (30 分钟)
   - 删除直接调用 SDK 的代码
   - 更新文档

6. **编写测试** (30 分钟)

   ```python
   async def test_actor_unified_call():
       """测试 Actor 统一调用"""
       actor = AmazingDataActor()
       result = await actor.call("get_kline", symbol="000001.SZ")
       assert result
   ```

**预计时间**: 3-4 小时

**验证标准**:

- [ ] 所有调用统一为 `actor.call()`
- [ ] 性能无退化
- [ ] 代码更清晰
- [ ] 单元测试通过

---

## 总结

### 时间估算汇总

| 阶段 | 任务数 | 预计时间 | 完成时限 |
|------|--------|---------|---------|
| Phase 1 (P1) | 4 | 7-10 小时 | 本周 (5 个工作日) |
| Phase 2 (P2) | 7 | 5-7 小时 | 下周 (4 个工作日) |
| Phase 3 (P3) | 2 | 3.5-4.5 小时 | 第三周 (2 个工作日,可选) |
| **总计** | **13** | **15.5-21.5 小时** | **3 周** |

### 每日工作计划

#### 第一周 (P1)

- **Day 1** (2h): 任务 1.1 - 修复 MiniQMT 模块
- **Day 2-3** (2-3h): 任务 1.2 - 实现实时数据源连接
- **Day 3-4** (1-2h): 任务 1.3 - 实现全市场行情
- **Day 4-5** (2-3h): 任务 1.4 - 实现可用性缓存

#### 第二周 (P2)

- **Day 1** (1h): 任务 2.1 + 2.2 - 配置优化 + DataProxy 初始化
- **Day 2** (1.5-2h): 任务 2.3 + 2.4 - 开盘价获取 + 准确率追踪
- **Day 3-4** (2.5h): 任务 2.5 - 筛选缓存和配置

#### 第三周 (P3,可选)

- **Day 1** (30min): 任务 3.1 - MarketSnapshot 字段
- **Day 2-3** (3-4h): 任务 3.2 - Actor 调用优化

### 风险管理

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| MiniQMT 模块重构复杂 | 中 | 高 | 分配额外 1-2 小时缓冲时间 |
| 实时数据流不稳定 | 中 | 中 | 添加充分的错误处理和重连机制 |
| 全市场行情性能差 | 低 | 中 | 优化并发请求,添加缓存 |
| 可用性缓存一致性 | 低 | 中 | 设计合理的缓存失效策略 |

### 验证检查清单

- [ ] 所有单元测试通过 (覆盖率 > 80%)
- [ ] 所有集成测试通过
- [ ] Mypy 类型检查通过 (0 错误)
- [ ] 后端启动无错误无警告
- [ ] 性能测试通过 (无性能退化)
- [ ] 代码审查通过
- [ ] 文档更新完成

### 下一步行动

1. **立即执行**: 任务 1.1 - 修复 MiniQMT 模块加载失败
2. **本周完成**: Phase 1 所有 P1 任务
3. **下周规划**: Phase 2 P2 任务分配
4. **第三周**: 根据进度决定是否执行 Phase 3

---

**计划生成时间**: 2026-01-13 12:20
**计划版本**: v1.0
**负责人**: 开发团队
**审核人**: 架构师
**下次更新**: Phase 1 完成后
