# CloudFlare Worker 完整部署指南

## 1. 项目概述

DeepSearch 使用 CloudFlare Worker 作为纯 HTTP 代理服务，为 AKShare 数据访问提供可靠的代理层。

### 主要优势
- 🛡️ 隐藏真实服务器 IP，防止被数据源封禁
- 🌍 利用 CloudFlare 全球网络加速访问
- 💾 智能缓存机制，减少重复请求
- 🔧 无需修改 AKShare 库代码
- 📊 支持 50+ 金融数据源网站

## 2. 架构说明

### 纯代理模式
Worker 作为纯 HTTP 代理，不处理业务逻辑：
- DeepSearch 使用 akshare 库处理数据
- Worker 只负责代理 HTTP 请求
- 数据格式统一，由 akshare 处理
- 支持智能缓存和请求合并

### 文件说明

| 文件 | 大小 | 用途 | 推荐场景 |
|------|------|------|----------|
| `worker.js` | ~15KB | 完整版本，带注释 | 开发测试 |
| `worker.min.js` | ~7KB | 压缩版本 | 一般生产 |
| `worker.ultra.min.js` | ~4KB | 极致压缩版本 | 高流量生产 |

## 3. 功能特性

### 核心功能
- ✅ 代理访问 50+ 金融数据源网站
- ✅ 智能缓存机制（实时5秒，分钟60秒，日线300秒）
- ✅ 支持 CORS 跨域请求
- ✅ 请求合并和速率限制
- ✅ 健康检查端点
- ✅ User-Agent 轮换，避免被识别
- ✅ 请求头清理，保护隐私
- ✅ 自动重试机制

### 支持的数据源（27个白名单域名）

#### 主要数据源
- **新浪财经**: finance.sina.com.cn, hq.sinajs.cn, money.finance.sina.com.cn
- **网易财经**: quotes.money.163.com, api.money.126.net
- **腾讯财经**: qt.gtimg.cn, web.ifzq.gtimg.cn, stock.finance.qq.com
- **东方财富**: push2.eastmoney.com, push2his.eastmoney.com, push2ex.eastmoney.com
- **同花顺**: d.10jqka.com.cn, q.10jqka.com.cn
- **雪球**: xueqiu.com, stock.xueqiu.com

#### 官方数据源
- **上海证券交易所**: www.sse.com.cn, query.sse.com.cn
- **深圳证券交易所**: www.szse.cn
- **中国外汇交易中心**: www.chinamoney.com.cn
- **中证指数**: www.csindex.com.cn

#### 新增数据源（2025-08-21）
- **push2ex.eastmoney.com** - 涨停跌停池数据
- **np-anotice-stock.eastmoney.com** - 股票公告数据
- **np-listnotice.eastmoney.com** - 公告列表数据
- **money.finance.sina.com.cn** - 新浪财经报表数据

## 4. 快速部署指南

### 方法1: CloudFlare Dashboard（推荐新手）

1. **登录 CloudFlare**
   ```
   https://dash.cloudflare.com/
   ```

2. **创建 Worker**
   - 进入 **Workers & Pages**
   - 点击 **Create Application** → **Create Worker**
   - 命名（如 `akshare-proxy`）

3. **部署代码**
   - 点击 **Quick Edit**
   - 复制 `worker.ultra.min.js` 内容并粘贴
   - 点击 **Save and Deploy**

4. **获取 Worker URL**
   - 格式：`https://akshare-proxy.你的子域名.workers.dev`

### 方法2: Wrangler CLI（推荐开发者）

```bash
# 安装 Wrangler
npm install -g wrangler

# 登录 CloudFlare
wrangler login

# 创建配置文件 wrangler.toml
cat > wrangler.toml << EOF
name = "akshare-proxy"
main = "worker.js"
compatibility_date = "2024-01-01"

[env.production]
vars = { ENVIRONMENT = "production" }
EOF

# 部署到生产环境
wrangler deploy

# 查看实时日志
wrangler tail
```

### 方法3: API 部署（自动化部署）

```bash
# 使用 CloudFlare API
curl -X PUT "https://api.cloudflare.com/client/v4/accounts/{account_id}/workers/scripts/{script_name}" \
     -H "Authorization: Bearer {api_token}" \
     -H "Content-Type: application/javascript" \
     --data-binary "@worker.ultra.min.js"
```

## 5. 详细配置说明

### DeepSearch 配置

在 `deepsearch/config/settings.prod.yaml` 中配置：

```yaml
# CloudFlare Workers 配置
cloudflare:
  workers:
    - "https://akshare-proxy.934073514.workers.dev"  # 你的 Worker URL
  worker_url: "https://akshare-proxy.934073514.workers.dev"
  
cloudflare_workers:
  url: "https://akshare-proxy.934073514.workers.dev"
  api_key: ""  # 可选，如需认证则设置
  fallback_to_direct: true  # Worker 不可用时回退到直连
  timeout: 30
  retry_count: 3
  cache_enabled: true
  cache_ttl: 300
```

### 环境变量配置（可选）

在 `wrangler.toml` 中配置：

```toml
[vars]
API_KEY = "your-secret-key"  # API 密钥
CACHE_TTL = "300"  # 缓存时间（秒）
DEBUG = "false"  # 调试模式
```

### 设置 API 密钥（可选）

```bash
# 设置密钥
wrangler secret put API_KEY
# 输入你的密钥

# 在 DeepSearch 配置中使用相同密钥
```

## 6. 性能优化

### 缓存策略

根据数据类型自动应用不同缓存时间：
- **实时数据**：5秒缓存
- **分钟数据**：60秒缓存  
- **日线数据**：300秒缓存
- **历史数据**：3600秒缓存

### CloudFlare 优化设置

1. **启用 Auto Minify**
   - Dashboard → Speed → Optimization
   - 开启 JavaScript 自动压缩

2. **配置缓存规则**
   - Page Rules → Create Page Rule
   - 设置缓存级别为 "Cache Everything"

3. **启用 Argo Smart Routing**（付费）
   - 可减少 30% 延迟

### 混淆技术（worker.ultra.min.js）

使用多种混淆技术减小体积：
- 变量名混淆：`ALLOWED_HOSTS` → `A`
- 字符串压缩：数组转字符串分割
- 函数简化：箭头函数
- 条件优化：三元运算符
- 运算符简化：`~~` 代替 `Math.floor`

## 7. 安全建议

### 访问控制
1. **设置 API 密钥**：生产环境建议启用认证
2. **配置速率限制**：防止滥用
3. **监控使用量**：定期查看分析报告

### 隐私保护
1. **隐藏 Worker URL**：使用环境变量存储
2. **定期更新 User-Agent**：保持浏览器版本最新
3. **备份部署**：多个 Worker 实例分散风险

### 监控告警
1. 设置异常请求量告警
2. 监控错误率变化
3. 跟踪响应时间趋势

## 8. 故障排查

### 常见问题

| 错误 | 原因 | 解决方案 |
|------|------|----------|
| 403 Forbidden | 域名不在白名单 | 检查 ALLOWED_HOSTS |
| 502 Bad Gateway | 目标网站宕机 | 检查目标网站状态 |
| 超时错误 | 请求时间过长 | 优化目标 API 或增加超时 |
| CORS 错误 | 跨域配置问题 | 检查响应头配置 |

### 调试方法

```bash
# 查看实时日志
wrangler tail --format pretty

# 本地调试
wrangler dev --local

# 健康检查
curl https://your-worker.workers.dev/health

# 代理测试
curl "https://your-worker.workers.dev/proxy?url=https://httpbin.org/headers"
```

### 回滚方案

如果新版本出现问题：
1. Dashboard → Workers → 选择 Worker
2. 点击 **Deployments** 标签
3. 找到之前的版本
4. 点击 **Rollback**

## 9. 更新日志

### v2.0.0 (2025-08-21)
- 新增 4 个东方财富和新浪财经域名
- 支持涨停池、公告等新 API
- 优化缓存策略
- 总白名单域名增至 27 个

### v1.5.0 (2024-08)
- 简化为纯代理模式
- 移除复杂的数据处理逻辑
- 提升性能和稳定性

### v1.0.0 (2024-06)
- 初始版本发布
- 支持基础代理功能
- 实现智能缓存

## 10. API 参考

### 健康检查
```http
GET /health
```

响应示例：
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "allowed_hosts_count": 27,
  "cache_enabled": true
}
```

### 代理请求
```http
GET /proxy?url={target_url}
```

参数：
- `url` (必需): 目标 URL，必须在白名单中

示例：
```bash
# 获取股票实时数据
curl "https://worker.workers.dev/proxy?url=https://hq.sinajs.cn/list=sz000001"

# 获取涨停池数据
curl "https://worker.workers.dev/proxy?url=https://push2ex.eastmoney.com/getTopicZTPool"
```

### 统计信息
```http
GET /stats
```

响应示例：
```json
{
  "requests_total": 10000,
  "cache_hits": 8000,
  "cache_misses": 2000,
  "cache_hit_rate": "80%"
}
```

## 成本控制

### CloudFlare 免费版限制
- 100,000 请求/天
- 10ms CPU 时间/请求
- 128MB 内存

### 优化建议
1. 使用 `worker.ultra.min.js` 减少 CPU 时间
2. 启用缓存减少重复请求
3. 在 DeepSearch 端做请求合并
4. 合理设置缓存 TTL

## 测试建议

### 部署后测试清单
- [ ] 健康检查端点正常
- [ ] 代理请求返回数据
- [ ] 缓存机制生效
- [ ] CORS 头正确设置
- [ ] 错误处理正常

### 性能测试
```bash
# 测试延迟
time curl "https://worker.workers.dev/health"

# 并发测试
for i in {1..10}; do
  curl "https://worker.workers.dev/proxy?url=..." &
done
```

## 技术支持

- **问题反馈**: 通过项目 Issue 跟踪器
- **文档更新**: 定期查看本文档获取最新信息
- **社区支持**: 加入 DeepSearch 用户群

## 许可证

MIT License

---

**推荐配置**：生产环境使用 `worker.ultra.min.js`，获得最佳性能和最低成本。