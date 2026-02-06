# AkShare: Fallback 机制重构与日志修复

> 日期: 2026-01-25
> 模块: packages/core/infrastructure/providers/implementations/akshare/
> 类型: refactor

---

## 为什么要改

### 遇到的问题

用户报告 AkShare 获取股票列表时，两个 API 都失败：

- `stock_zh_a_spot_em`（东方财富实时行情）
- `stock_info_a_code_name`（股票代码名称映射）

但诊断发现 `stock_info_a_code_name` 实际是**成功的**，返回 5473 只股票。

### 现有方案的问题

1. **日志级别过低**: 错误信息用 `logger.debug()` 记录，生产环境看不到
2. **无效的 fallback 设计**: `AkShareAdapter` 中的 primary/fallback 是同一个类
   - `AkShareProxyProvider` 已废弃，只是 `AkShareProvider` 的别名
   - 切换 fallback 毫无意义，两者行为完全相同
3. **代码混淆**: 多层 fallback 逻辑让问题难以定位

---

## 尝试过的方案

### 方案 A: 只修复日志级别

**思路**: 最小改动，只把 `debug` 改成 `warning`

**问题**: 没有解决架构混淆问题，未来维护者仍会被 fallback_provider 误导

### 方案 B: 完整重构 + 创建真正的备用 Provider

**思路**: 重新实现 `AkShareProxyProvider`，使用 Cloudflare Worker 代理

**问题**: 工作量大，且当前网络环境下代理也不稳定（代理超时）

---

## 最终方案

### 选择: 简化架构 + 修复日志

**原因**:

1. 内部 fallback 机制已经工作（`stock_zh_a_spot_em` -> `stock_info_a_code_name`）
2. 移除无效代码减少混淆
3. 提升日志级别让问题可见

### 关键改动

#### 文件: `akshare_direct.py`

```python
# 改之前 (第 1130、1145 行)
logger.debug(f"东方财富接口失败: {e1}")
logger.debug(f"stock_info_a_code_name失败: {e2}")

# 改之后
logger.warning(f"东方财富接口失败: {e1}")
logger.warning(f"stock_info_a_code_name失败: {e2}")
```

**为什么这样改**: 让生产环境能看到具体错误，方便定位问题

#### 文件: `akshare_adapter.py`

```python
# 改之前
self.provider = AKShareDirectProvider()
self.fallback_provider = AkShareProxyProvider()  # 实际是同一个类！

# 改之后
self.provider = AKShareDirectProvider()
self.fallback_provider = None  # 内部 fallback 由 provider 自行处理
```

**为什么这样改**:

- `AkShareProxyProvider` 已废弃，是 `AkShareProvider` 的别名
- 移除无效的 fallback 切换，减少代码混淆
- 真正的 fallback 发生在 `_fetch_stock_list_sync` 内部

---

## 注意事项

### 这个方案的局限

1. 如果 `stock_info_a_code_name` 也失败，没有额外的备用数据源
2. `stock_info_a_code_name` 需要 ~30 秒完成（访问上交所、深交所、北交所）

### 如果要恢复 Cloudflare Worker 代理

需要：

1. 确认 Worker 服务正常运行
2. 重新实现 `AkShareProxyProvider`，使用 `proxy_client.py`
3. 确保 `/proxy?url=*` 格式与 `worker.js` 兼容

### 东方财富接口失败的根本原因

诊断发现是 **SSL/代理问题**：

- 系统配置了代理 `127.0.0.1:10808`
- 代理对 `82.push2.eastmoney.com` 连接不稳定
- 这是网络环境问题，不是代码问题

---

## 关键结论

> **真正的 fallback 在 `_fetch_stock_list_sync` 内部**，`AkShareAdapter` 的 primary/fallback 是历史遗留的无效设计。
> 简化架构、提升日志级别，让问题更容易定位。
