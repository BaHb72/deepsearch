# Cloudflare Worker 部署指南

这个文件夹包含可直接部署到 Cloudflare Workers 的代理服务。

## 架构说明

### 纯代理模式
Worker 作为纯 HTTP 代理，保护你的服务器 IP
- DeepSearch 使用 akshare 库处理数据
- Worker 只负责代理 HTTP 请求，不处理数据
- 数据格式统一，由 akshare 处理
- 支持智能缓存和请求合并

## 功能特性

- ✅ 代理访问 50+ 金融数据源网站
- ✅ 智能缓存机制（5分钟缓存，减少重复请求）
- ✅ 支持 CORS 跨域请求
- ✅ 请求合并和速率限制
- ✅ 健康检查端点
- ✅ User-Agent 轮换，避免被识别
- ✅ 请求头清理，保护隐私

## 支持的数据源

- 新浪财经 (finance.sina.com.cn)
- 网易财经 (quotes.money.163.com)
- 腾讯财经 (qt.gtimg.cn)
- 东方财富 (eastmoney.com)
- 同花顺 (10jqka.com.cn)
- 上交所/深交所官网
- 雪球 (xueqiu.com)
- 中国外汇交易中心
- 以及更多...

## 部署步骤

### 1. 安装 Wrangler CLI

```bash
npm install -g wrangler
```

### 2. 登录 Cloudflare

```bash
wrangler login
```

### 3. 创建 wrangler.toml

在本目录创建 `wrangler.toml` 文件：

```toml
name = "deepsearch-proxy"  # 你的 Worker 名称
main = "worker.js"
compatibility_date = "2024-01-01"

[env.production]
vars = { ENVIRONMENT = "production" }
```

### 4. 部署 Worker

```bash
# 开发环境测试
wrangler dev

# 部署到生产环境
wrangler publish
```

### 5. 配置 DeepSearch

在 DeepSearch 配置文件中设置 Worker URL：

```yaml
# config/settings.yaml
data_providers:
  cloudflare_proxy:
    url: "https://your-worker-name.your-subdomain.workers.dev"
    enabled: true
```

## API 使用示例

### 代理请求

```bash
# 通过 Worker 代理访问新浪财经
curl "https://your-worker.workers.dev/proxy?url=https://finance.sina.com.cn/stock/api/data"
```

### 健康检查

```bash
curl "https://your-worker.workers.dev/health"
```

### 查看缓存统计

```bash
curl "https://your-worker.workers.dev/stats"
```

## 环境变量配置

可选的环境变量（在 wrangler.toml 中配置）：

```toml
[vars]
# API 密钥（可选）
API_KEY = "your-secret-key"

# 缓存时间（秒）
CACHE_TTL = "300"

# 启用调试模式
DEBUG = "false"
```

## 安全建议

1. **设置 API 密钥**：在生产环境建议设置 API_KEY 防止滥用
2. **配置速率限制**：在 Cloudflare Dashboard 中配置速率限制规则
3. **监控使用量**：定期查看 Worker 分析，监控异常流量
4. **定期更新**：保持 Worker 代码最新，及时修复安全问题

## 性能优化

- 自动缓存热门数据，减少源站请求
- 请求合并，避免重复请求相同资源
- 智能重试机制，提高成功率
- 压缩响应，减少带宽使用

## 故障排查

### 常见问题

1. **502 错误**：检查目标网站是否可访问
2. **403 错误**：可能需要更新 User-Agent 或添加新的请求头
3. **超时错误**：增加超时时间或检查网络连接
4. **缓存未生效**：检查 Cache-Control 头设置

### 调试方法

```bash
# 查看实时日志
wrangler tail

# 本地调试
wrangler dev --local
```

## 监控和分析

在 Cloudflare Dashboard 中可以查看：
- 请求数量和趋势
- 响应时间分布
- 错误率统计
- 带宽使用情况

## 更新日志

- 2024-08: 简化为纯代理模式，移除复杂的数据处理逻辑
- 2024-07: 添加智能缓存和请求合并
- 2024-06: 初始版本发布

## 许可证

MIT License