# AkShare Cloudflare Worker 代理返回大量 520 错误

> 发现日期: 2026-02-08
> 发现位置: packages/core/infrastructure/providers/implementations/akshare/akshare_direct.py
> 类型: performance
> 严重程度: high
> 状态: resolved

---

## 问题描述

在启动预热阶段，AkShare 通过 Cloudflare Worker 代理获取股票列表时，遭遇大量 520 错误（服务器错误），导致所有数据获取失败。

### 现象

1. **Cloudflare Worker 代理失败**

   ```
   ERROR: 请求失败 https://82.push2.eastmoney.com/api/qt/clist/get:
   HTTPSConnectionPool(host='akshare-proxy.934073514.workers.dev', port=443):
   Max retries exceeded ... ResponseError('too many 520 error responses')
   ```

2. **东方财富接口失败**

   ```
   WARNING: 东方财富接口失败: ... too many 520 error responses
   ```

3. **备用接口也失败**

   ```
   WARNING: stock_info_a_code_name失败: Expecting value: line 1 column 1 (char 0)
   ```

4. **最终结果**

   ```
   ERROR: AkShare 获取股票列表失败，返回空列表
   WARNING: Stock list fetcher returned empty payload
   INFO: 板块数据预热完成 (来源: 网络, 板块数: 0, 总耗时: 55.81s)
   ```

### 影响

- **股票列表**：无法获取任何股票数据
- **板块数据**：预热失败，返回 0 条数据
- **实时行情**：无法正常工作
- **系统状态**：在 AmazingData/MiniQMT 不可用的情况下，AkShare 是唯一的数据源，现在也失败了

---

## 发现上下文

> 在执行"启动前后端收集错误"任务时发现此问题

后端服务启动后，在板块数据预热阶段（`market_data_runtime.py:218`）尝试通过 AkShare 获取股票列表时失败。

---

## 相关日志

```
[2m2026-02-08 10:23:11.252[0m  [31mERROR[0m [35m22424[0m [2m---[0m [[2moolExecutor-3_0[0m] [36mc.u.n.proxy_client:199                 [0m [2m:[0m [31m请求失败 https://82.push2.eastmoney.com/api/qt/clist/get: HTTPSConnectionPool(host='akshare-proxy.934073514.workers.dev', port=443): Max retries exceeded with url: /proxy?url=https%3A%2F%2F82.push2.eastmoney.com%2Fapi%2Fqt%2Fclist%2Fget... (Caused by ResponseError('too many 520 error responses'))[0m

[2m2026-02-08 10:23:11.252[0m  [33mWARNING[0m [35m22424[0m [2m---[0m [[2moolExecutor-3_0[0m] [36mc.i.p.i.a.akshare_direct:1132          [0m [2m:[0m [33m东方财富接口失败: ... too many 520 error responses[0m

[2m2026-02-08 10:23:11.412[0m  [33mWARNING[0m [35m22424[0m [2m---[0m [[2moolExecutor-3_0[0m] [36mc.i.p.i.a.akshare_direct:1147          [0m [2m:[0m [33mstock_info_a_code_name失败: Expecting value: line 1 column 1 (char 0)[0m

[2m2026-02-08 10:23:11.414[0m  [31mERROR[0m [35m22424[0m [2m---[0m [[2m     MainThread[0m] [36mc.i.p.i.a.akshare_adapter:309          [0m [2m:[0m [31mAkShare 获取股票列表失败，返回空列表[0m
```

---

## 根本原因分析

### 520 错误的含义

HTTP 520 是 Cloudflare 的自定义状态码，表示"Web Server Returned an Unknown Error"，通常意味着：

1. **源服务器错误**：东方财富的服务器返回了 Cloudflare 无法识别的响应
2. **超时**：Cloudflare Worker 超时（默认 10 秒 CPU 时间限制）
3. **速率限制**：Worker 被 Cloudflare 限流
4. **Worker 脚本错误**：Worker 代码本身有 bug

### 可能原因

1. **Cloudflare Worker 配额耗尽**
   - 免费版 Worker 每天有 100,000 次请求限制
   - 可能在开发测试中已经耗尽配额

2. **东方财富 API 封禁**
   - 东方财富可能检测到大量来自 Cloudflare IP 的请求并封禁
   - 返回异常响应导致 Worker 报错

3. **Worker 代理配置问题**
   - Worker 代码可能没有正确处理请求头或响应
   - 缺少必要的 User-Agent 或 Referer

4. **网络环境问题**
   - Worker 部署的地区网络问题
   - DNS 解析问题

---

## 修复方案

> **重要纠正**：此前的"方案 A: 切换到直连模式"分析有误。Cloudflare 代理优先级高于 AkShare 直连是**正确的设计** -- 代理模式通过 Cloudflare 边缘网络避开东方财富等源站的 WAF 封锁，直连反而更容易被限流。

### 方案：修复 Worker.js 服务端重试（已实施）

根因是 `worker.js` 对源站只发起单次请求，无服务端重试。客户端虽有 5 次重试，但每次都经过 Worker 的单次请求失败链路。

修复内容：

1. **Worker.js 添加 3 次服务端重试**（递增延迟 0/500/1500ms）
2. 仅对 5xx 服务端错误重试，4xx 不重试
3. 客户端重试 + 服务端重试 形成两层防护

### 其他建议

1. **检查 Worker 配额** - 免费版每天 100,000 次请求限制
2. **监控源站封锁** - 东方财富等源站可能封锁 Cloudflare IP 段

---

## 预估工作量

- [x] 小（< 30 分钟）- 如果只是配置问题
- [ ] 中（30分钟 - 2小时）- 如果需要修复 Worker 代码

---

## 备注

### 相关配置文件

- `packages/core/config/infrastructure.dev.yaml` - AkShare 代理配置
- `packages/core/infrastructure/providers/implementations/akshare/akshare_direct.py` - 实现代码
- `packages/core/utils/network/proxy_client.py` - 代理客户端

### 废弃警告

日志中出现警告：

```
WARNING: use_proxy=True 已废弃: AkShareProxyProvider 现在与 AKShareDirectProvider 相同
```

这说明代理模式可能已经被废弃，建议使用直连模式。

### 关联问题

这个问题与 **Issue #1 (Dask Worker 模块导入失败)** 相关：

- Issue #1 导致 AmazingData 和 MiniQMT 不可用
- 系统降级到 AkShare
- 但 AkShare 也失败了（本 Issue）
- 结果：**所有数据源都不可用**

---

## 解决记录

> 解决日期: 2026-02-16
> 解决方式: 在 `cloudflare-deploy/worker.js` 增加服务端 3 次重试，仅对 5xx 重试，并与客户端重试形成双层保护
> 验证方式: 代码审阅 `worker.js` 重试逻辑 + 回归测试通过（本轮相关单测未出现代理链路回归）
