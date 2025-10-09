# AKShare + CloudFlare 优化方案

## 当前状态

### 测试结果
- **CloudFlare Worker健康检查**: 353.5ms（正常）
- **AKShare实时行情获取**: 98秒（太慢！）
- **批量请求优化**: 213.8%性能提升
- **缓存效果**: 显著

## 问题分析

1. **AKShare实时行情太慢（98秒）**
   - 原因：`ak.stock_zh_a_spot_em()` 获取全市场数据，数据量大
   - 每次都下载全部A股数据，然后筛选

2. **CloudFlare延迟可接受（353ms）**
   - Worker本身响应快
   - 主要延迟在网络传输

## 优化方案

### 1. AKShare优化策略

```python
# 不要这样用（获取全市场再筛选）
df = ak.stock_zh_a_spot_em()  # 下载5000+股票数据
row = df[df['代码'] == symbol]  # 然后筛选

# 应该这样用（直接获取指定股票）
import akshare as ak

class OptimizedAKShare:
    def __init__(self):
        # 缓存全市场数据
        self._market_data = None
        self._market_data_time = 0
        self._cache_ttl = 5  # 5秒缓存
        
    def get_realtime_price(self, symbol: str):
        """获取单只股票实时价格"""
        # 使用新浪接口（更快）
        df = ak.stock_zh_a_real_time(symbol)
        return df
        
    def get_batch_quotes(self, symbols: List[str]):
        """批量获取行情"""
        # 使用缓存的全市场数据
        current_time = time.time()
        if not self._market_data or current_time - self._market_data_time > self._cache_ttl:
            self._market_data = ak.stock_zh_a_spot_em()
            self._market_data_time = current_time
        
        # 批量筛选
        return self._market_data[self._market_data['代码'].isin(symbols)]
```

### 2. CloudFlare Worker配置优化

#### 2.1 Worker端优化 (worker.js)
```javascript
// 增加缓存时间
const CACHE_TTL = {
    'realtime': 5,      // 实时数据5秒
    'kline': 60,        // K线1分钟
    'info': 3600,       // 基础信息1小时
};

// 启用KV存储缓存
export default {
    async fetch(request, env, ctx) {
        const cache = caches.default;
        
        // 检查缓存
        const cachedResponse = await cache.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        
        // 处理请求
        const response = await handleRequest(request);
        
        // 存入缓存
        ctx.waitUntil(cache.put(request, response.clone()));
        
        return response;
    }
}
```

#### 2.2 客户端优化
```python
class CloudFlareClient:
    def __init__(self):
        # 连接池配置
        self.connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        # 会话复用
        self.session = aiohttp.ClientSession(
            connector=self.connector,
            timeout=aiohttp.ClientTimeout(total=10, connect=2)
        )
        
    async def batch_request(self, urls: List[str]):
        """批量请求"""
        tasks = [self.session.get(url) for url in urls]
        responses = await asyncio.gather(*tasks)
        return responses
```

### 3. 数据源切换策略

```python
class DataSourceManager:
    """智能数据源管理"""
    
    def __init__(self):
        self.sources = {
            'realtime': 'sina',      # 实时用新浪（最快）
            'kline': 'eastmoney',    # K线用东财
            'financial': 'akshare',  # 财务用AKShare
        }
    
    async def get_data(self, data_type: str, symbol: str):
        source = self.sources.get(data_type)
        
        if source == 'sina':
            return await self.get_sina_data(symbol)
        elif source == 'eastmoney':
            return await self.get_eastmoney_data(symbol)
        else:
            return await self.get_akshare_data(symbol)
```

### 4. 实施步骤

#### 第一步：优化AKShare调用
1. 避免获取全市场数据
2. 使用特定接口获取单只股票
3. 实施本地缓存

#### 第二步：配置连接池
1. 复用HTTP连接
2. 设置合理超时
3. 启用Keep-Alive

#### 第三步：批量处理
1. 合并相似请求
2. 并发处理
3. 结果缓存

#### 第四步：监控和调优
1. 记录每个API的延迟
2. 识别瓶颈
3. 动态调整策略

## 性能目标

- **实时行情**: <500ms（当前98秒）
- **K线数据**: <1秒（当前未测）
- **批量请求**: <2秒获取10只股票

## 配置文件示例

### settings.yaml
```yaml
data_sources:
  akshare:
    enabled: true
    priority: 10
    cache_ttl: 5
    batch_size: 20
    max_concurrent: 10
    
  cloudflare:
    enabled: true
    priority: 20
    worker_url: "https://akshare-proxy.934073514.workers.dev"
    timeout: 10
    retry: 3
    
  cache:
    memory:
      enabled: true
      max_size: 1000
      ttl: 60
    redis:
      enabled: true
      ttl: 300
```

## 测试验证

```python
# 测试优化效果
async def test_optimized():
    # 测试前
    start = time.time()
    data = ak.stock_zh_a_spot_em()
    print(f"获取全市场: {time.time()-start:.1f}秒")
    
    # 测试后
    start = time.time()
    data = ak.stock_zh_a_real_time("000001")
    print(f"获取单只: {time.time()-start:.1f}秒")
```

## 总结

1. **主要问题是AKShare使用方式不对**，不应该获取全市场数据
2. **CloudFlare代理本身性能可接受**，350ms延迟在合理范围
3. **通过正确的API选择和缓存策略**，可以将延迟降至500ms以内