# ApiClient.syncTimeoutConfig() 从未被调用

## 基本信息

- **发现时间**: 2026-02-07
- **严重程度**: 低
- **影响范围**: 前端 API 客户端 (client.ts)
- **文件位置**: `apps/web/src/api/core/client.ts:125-156`

## 问题描述

`ApiClient` 类实现了 `syncTimeoutConfig()` 方法，能从后端 `/api/config/timeouts` 同步超时配置，
但全项目中没有任何地方调用该方法。

### 背景

项目存在两套并行的 HTTP 客户端：

| 客户端 | 文件 | 使用者 | 超时同步 |
|--------|------|--------|---------|
| 旧 `request` | `apps/web/src/api/request.ts` | 14+ 个 API 模块 | setupRequest() 中已添加同步逻辑 |
| 新 `ApiClient` | `apps/web/src/api/core/client.ts` | 未广泛使用 | syncTimeoutConfig() 存在但未被调用 |

### 影响

- `ApiClient` 的超时始终使用默认值 90000ms，不会从后端动态获取
- 如果后端超时配置变更，`ApiClient` 不会感知

## 修复

已在 `apps/web/src/main-react.tsx` 的 `initApp()` 中添加调用：

```typescript
await setupRequest()
await apiClient.syncTimeoutConfig()  // 新增：同步 ApiClient 超时配置
```

现在两套 HTTP 客户端（旧 `request` 和新 `ApiClient`）都会在启动时从后端同步超时配置。

### 状态: 已解决
