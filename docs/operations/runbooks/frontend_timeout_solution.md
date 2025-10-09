# 前端API调用超时问题解决方案

## 问题分析

前端设置了10秒超时，但仍然经常触发超时错误。根据之前的优化：
- P95延迟已从12秒降至~5秒
- 并发请求限制为5个
- 实施了请求优化器和缓存

## 建议解决方案

### 1. 短期解决方案（立即可用）

#### A. 调整前端超时时间
```javascript
// 修改 src/api/request.js
const request = axios.create({
    timeout: 30000,  // 增加到30秒，给复杂查询更多时间
    headers: {
        'Content-Type': 'application/json'
    }
})
```

#### B. 为不同API设置不同超时
```javascript
// 在 src/api/market.js 中为耗时API设置更长超时
export function getMarketOverview() {
    return request({
        url: '/market/overview',
        method: 'get',
        timeout: 20000  // 市场概览需要更多时间
    })
}
```

### 2. 中期优化方案

#### A. 实现渐进式加载
```javascript
// 分步加载数据，避免一次性请求过多
async loadMarketData() {
    // 先加载关键数据（快速）
    this.indices = await getIndices()
    
    // 再加载次要数据（较慢）
    this.capital = await getCapitalFlow()
    
    // 最后加载补充数据（可选）
    this.sectors = await getSectors()
}
```

#### B. 添加加载状态提示
```vue
<template>
  <div v-if="loading" class="loading-container">
    <el-progress :percentage="loadingProgress" />
    <p>正在加载市场数据，请稍候...</p>
  </div>
</template>
```

### 3. 长期优化方案

#### A. 实现WebSocket推送
- 建立WebSocket连接获取实时数据
- 避免频繁的HTTP请求
- 降低延迟和服务器负载

#### B. 实现数据预加载
- 在用户进入页面前预加载常用数据
- 使用Service Worker缓存静态数据
- 实现智能预取策略

## 配置建议

### 前端配置 (request.js)
```javascript
// 创建不同超时的请求实例
export const quickRequest = axios.create({
    timeout: 5000,   // 快速API：5秒
    baseURL: '/api'
})

export const normalRequest = axios.create({
    timeout: 15000,  // 普通API：15秒
    baseURL: '/api'
})

export const slowRequest = axios.create({
    timeout: 30000,  // 慢速API：30秒
    baseURL: '/api'
})
```

### 后端优化建议
1. 继续优化请求优化器
2. 增加缓存命中率
3. 实施数据预聚合
4. 使用异步任务队列处理耗时操作

## 监控指标

建议监控以下指标：
- API响应时间分布（P50, P95, P99）
- 超时率（超时请求/总请求）
- 缓存命中率
- 并发请求数
- 错误率

## 立即可执行的修改

最简单的修改是调整超时时间：

```bash
# 修改前端超时配置
sed -i 's/timeout: 10000/timeout: 30000/g' deepsearch/webui/frontend/src/api/request.js
```

然后重新构建前端：
```bash
cd deepsearch/webui/frontend
npm run build
```