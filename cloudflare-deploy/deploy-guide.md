# Cloudflare Worker 详细部署指南

## 架构说明

DeepSearch 使用 Cloudflare Worker 作为纯 HTTP 代理，主要目的：

- 隐藏真实服务器 IP，防止被数据源封禁
- 利用 Cloudflare 的全球网络加速访问
- 提供智能缓存，减少重复请求
- 无需修改 akshare 库代码

## 快速部署步骤

### 1. 安装 Wrangler CLI

```bash
npm install -g wrangler
```

### 2. 登录 Cloudflare 账户

```bash
wrangler login
```

这将打开浏览器进行认证。

### 3. 获取您的账户ID

登录后运行：

```bash
wrangler whoami
```

记录显示的账户ID。

### 4. 更新配置文件

编辑 `wrangler-proxy.toml`，将以下行取消注释并填入您的账户ID：

```toml
account_id = "your-account-id-here"
```

### 5. 部署Worker

```bash
cd D:\Stock\code\deepsearch\cloudflare-deploy
wrangler deploy -c wrangler-proxy.toml
```

### 6. 配置DeepSearch

部署成功后，您将获得Worker URL（格式：`xxx.workers.dev`）。

更新 `deepsearch/config/settings.dev.yaml`：

```yaml
cloudflare_workers:
  url: "your-worker-name.workers.dev"  # 替换为您的Worker URL
  api_key: ""  # 可选，如需认证则设置
  fallback_to_direct: true
```

### 7. 测试Worker

```bash
# 健康检查
curl https://your-worker-name.workers.dev/health

# 代理测试
curl "https://your-worker-name.workers.dev/proxy?url=https://hq.sinajs.cn/list=sz000001"
```

## 可选：设置API密钥

如需启用认证：

```bash
wrangler secret put API_KEY
# 输入您的密钥
```

然后在DeepSearch配置中设置相同的密钥。

## 故障排查

1. **部署失败**
    - 确认已登录：`wrangler whoami`
    - 检查账户ID是否正确

2. **代理请求失败**
    - 检查目标URL是否在白名单中
    - 查看Worker日志：`wrangler tail`

3. **CORS错误**
    - Worker已配置CORS头，检查前端请求配置

## Worker功能

- ✅ 纯代理模式，保护服务器IP
- ✅ 白名单机制，只允许金融数据源
- ✅ 智能缓存（实时数据5秒，日线数据5分钟）
- ✅ 自动重试机制
- ✅ 随机User-Agent
- ✅ CORS支持

## 支持的数据源

- 新浪财经 (sina.com.cn)
- 网易财经 (163.com)
- 腾讯财经 (gtimg.cn)
- 东方财富 (eastmoney.com)
- 同花顺 (10jqka.com.cn)
- 雪球 (xueqiu.com)
- 上交所/深交所
- 其他金融数据源