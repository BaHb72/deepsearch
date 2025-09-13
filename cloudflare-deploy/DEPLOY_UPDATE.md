# CloudFlare Worker 更新部署说明

## 更新内容 (2025-08-21)

### 新增白名单域名
为支持更多AKShare API，已添加以下域名到ALLOWED_HOSTS：

1. **push2ex.eastmoney.com** - 涨停跌停池数据
   - 支持涨停池、跌停池等异动数据API
   
2. **np-anotice-stock.eastmoney.com** - 股票公告数据
   - 支持公告查询API
   
3. **np-listnotice.eastmoney.com** - 公告列表数据
   - 支持公告列表API
   
4. **money.finance.sina.com.cn** - 新浪财经数据
   - 支持财务报表等API

### 当前白名单统计
- 总域名数：27个
- 新增域名：4个
- 覆盖数据源：新浪财经、东方财富、网易财经、腾讯财经、同花顺、交易所、雪球等

## 部署步骤

### 1. 登录CloudFlare Dashboard
```
https://dash.cloudflare.com/
```

### 2. 选择Workers & Pages
在左侧菜单中选择 "Workers & Pages"

### 3. 找到现有Worker
找到名为 `akshare-proxy` 的Worker

### 4. 更新代码
1. 点击 "Quick edit" 或 "Edit code"
2. 将 `worker.js` 的内容复制粘贴到编辑器
3. 点击 "Save and Deploy"

### 5. 验证部署
访问健康检查端点验证更新：
```
https://akshare-proxy.934073514.workers.dev/health
```

应该看到：
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "allowed_hosts_count": 27,
  ...
}
```

## 测试新增API

### 测试涨停池API
```bash
curl "https://akshare-proxy.934073514.workers.dev/proxy?url=https://push2ex.eastmoney.com/getTopicZTPool"
```

### 测试公告API
```bash
curl "https://akshare-proxy.934073514.workers.dev/proxy?url=https://np-anotice-stock.eastmoney.com/api/security/ann"
```

## 注意事项

1. **缓存策略**：新增的API会根据路径自动应用缓存策略
   - 实时数据：5秒缓存
   - 分钟数据：60秒缓存
   - 日线数据：300秒缓存

2. **请求限制**：CloudFlare Worker有请求限制
   - 免费版：100,000请求/天
   - 建议在客户端实现本地缓存

3. **监控建议**：
   - 定期运行 `test_cloudflare_worker.py` 检查API可用性
   - 监控Worker的错误日志和请求统计

## 回滚方案

如果更新后出现问题，可以回滚到之前的版本：
1. 在CloudFlare Dashboard中找到Worker
2. 点击 "Deployments" 标签
3. 选择之前的版本并点击 "Rollback"

## 后续优化建议

1. **添加请求日志**：记录被代理的请求，便于调试
2. **智能路由**：根据API特性优化请求头和参数
3. **响应处理**：处理JSONP等特殊格式的响应
4. **监控告警**：设置异常请求量告警